import { API_BASE_URL } from "./apiBase";
import { httpApiErrorMessage, humanizeClientFetchError } from "./httpApiErrorMessage";

export type ClassificationStepStatus = "pending" | "active" | "done" | "skipped";

export type ClassificationProgressStep = {
  id: string;
  label: string;
  status: ClassificationStepStatus;
};

export type ClassifyStreamResult = {
  raw: string;
  effective_query?: string;
  items_count?: number;
};

type StreamHandlers = {
  onInit?: (steps: ClassificationProgressStep[]) => void;
  onStep?: (step: ClassificationProgressStep) => void;
  onDetail?: (message: string) => void;
  onResult?: (payload: ClassifyStreamResult) => void;
  onError?: (message: string) => void;
};

function parseSseEvents(
  buffer: string
): { events: Array<Record<string, unknown>>; rest: string } {
  const events: Array<Record<string, unknown>> = [];
  const chunks = buffer.split("\n\n");
  const rest = chunks.pop() ?? "";
  for (const chunk of chunks) {
    for (const line of chunk.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      try {
        events.push(JSON.parse(line.slice(6)) as Record<string, unknown>);
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
  return { events, rest };
}

class IncompleteStreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "IncompleteStreamError";
  }
}

function shouldFallbackToClassifyEndpoint(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  if (error instanceof IncompleteStreamError) return true;
  const msg = error.message.toLowerCase();
  return (
    msg.includes("incomplète") ||
    msg.includes("flux de progression indisponible") ||
    msg.includes("body stream") ||
    msg.includes("network")
  );
}

async function consumeClassifyStream(
  response: Response,
  handlers: StreamHandlers
): Promise<ClassifyStreamResult> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(httpApiErrorMessage(response.status, text));
  }
  if (!response.body) {
    throw new IncompleteStreamError("Flux de progression indisponible.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ClassifyStreamResult | null = null;
  let streamError: string | null = null;
  let sawProgress = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseEvents(buffer);
    buffer = parsed.rest;

    for (const event of parsed.events) {
      const type = String(event.type ?? "");
      if (type === "init" && Array.isArray(event.steps)) {
        handlers.onInit?.(
          event.steps.map((step) => {
            const row = step as Record<string, unknown>;
            return {
              id: String(row.id ?? ""),
              label: String(row.label ?? ""),
              status: "pending",
            };
          })
        );
      } else if (type === "step") {
        sawProgress = true;
        handlers.onStep?.({
          id: String(event.step ?? ""),
          label: String(event.label ?? event.step ?? ""),
          status: (event.status as ClassificationStepStatus) ?? "pending",
        });
      } else if (type === "detail") {
        handlers.onDetail?.(String(event.message ?? ""));
      } else if (type === "result" && event.payload && typeof event.payload === "object") {
        const payload = event.payload as Record<string, unknown>;
        result = {
          raw: String(payload.raw ?? ""),
          effective_query:
            typeof payload.effective_query === "string"
              ? payload.effective_query
              : undefined,
          items_count:
            typeof payload.items_count === "number"
              ? payload.items_count
              : undefined,
        };
        handlers.onResult?.(result);
      } else if (type === "error") {
        streamError = String(event.detail ?? "Classification échouée");
        handlers.onError?.(streamError);
        throw new Error(streamError);
      }
    }
  }

  if (!result?.raw) {
    const hint = streamError
      ? streamError
      : sawProgress
        ? "La classification a été interrompue avant la fin (délai serveur ou connexion coupée). Réessayez dans un instant."
        : "Réponse de classification incomplète.";
    throw new IncompleteStreamError(hint);
  }
  return result;
}

export type MerchandiseItemPayload = {
  designation: string;
  material: string;
  usage: string;
  characteristics: string;
  quantity: string;
  unit: string;
  origin: string;
  value: string;
  currency: string;
};

async function classifyWithoutStream(
  body: Record<string, unknown>,
  handlers: StreamHandlers
): Promise<ClassifyStreamResult> {
  const steps = DEFAULT_CLASSIFICATION_STEPS.map((step) => ({ ...step }));
  handlers.onInit?.(steps);

  for (const step of steps) {
    handlers.onStep?.({ ...step, status: "active" });
    handlers.onStep?.({ ...step, status: "done" });
  }

  const response = await fetch(`${API_BASE_URL}/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(httpApiErrorMessage(response.status, text));
  }
  const data = (await response.json()) as Record<string, unknown>;
  const result: ClassifyStreamResult = {
    raw: String(data.raw ?? ""),
    effective_query:
      typeof data.effective_query === "string" ? data.effective_query : undefined,
    items_count:
      typeof data.items_count === "number" ? data.items_count : undefined,
  };
  if (!result.raw) {
    throw new Error(
      "Le serveur n'a renvoyé aucun résultat de classification. Vérifiez que l'API est démarrée et que le quota OpenAI est disponible."
    );
  }
  handlers.onResult?.(result);
  return result;
}

export async function streamClassifyQuery(
  query: string,
  userId: string | null,
  handlers: StreamHandlers,
  items?: MerchandiseItemPayload[]
): Promise<ClassifyStreamResult> {
  const body: Record<string, unknown> = { query, user_id: userId };
  if (items && items.length > 0) {
    body.items = items;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/classify/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (response.status === 404 || response.status === 405) {
      return classifyWithoutStream(body, handlers);
    }

    return await consumeClassifyStream(response, handlers);
  } catch (err) {
    if (shouldFallbackToClassifyEndpoint(err)) {
      try {
        return await classifyWithoutStream(body, handlers);
      } catch (fallbackErr) {
        throw fallbackErr;
      }
    }
    if (err instanceof Error) {
      throw new Error(humanizeClientFetchError(err.message));
    }
    throw err;
  }
}

export const DEFAULT_CLASSIFICATION_STEPS: ClassificationProgressStep[] = [
  { id: "merchandise", label: "Analyse de la marchandise", status: "pending" },
  { id: "identification", label: "Identification du produit", status: "pending" },
  { id: "tec_context", label: "Recherche du contexte TEC", status: "pending" },
  { id: "position_hypothesis", label: "Hypothèse de position (analyse)", status: "pending" },
  { id: "subposition", label: "Discrimination TEC (sous-positions)", status: "pending" },
  { id: "rgi", label: "Application des RGI", status: "pending" },
  { id: "duties", label: "Calcul des droits", status: "pending" },
  { id: "report", label: "Génération du rapport", status: "pending" },
];

export function applyProgressStep(
  steps: ClassificationProgressStep[],
  update: ClassificationProgressStep
): ClassificationProgressStep[] {
  return steps.map((step) => {
    if (step.id !== update.id) return step;
    if (step.status === "done" && update.status === "active") return step;
    return { ...step, label: update.label || step.label, status: update.status };
  });
}

export function markAllStepsDone(
  steps: ClassificationProgressStep[]
): ClassificationProgressStep[] {
  return steps.map((step) =>
    step.status === "skipped"
      ? step
      : { ...step, status: "done" as ClassificationStepStatus }
  );
}
