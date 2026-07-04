import { API_BASE_URL } from "./apiBase";

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

async function consumeClassifyStream(
  response: Response,
  handlers: StreamHandlers
): Promise<ClassifyStreamResult> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Erreur HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Flux de progression indisponible.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ClassifyStreamResult | null = null;

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
        handlers.onStep?.({
          id: String(event.step ?? ""),
          label: String(event.label ?? event.step ?? ""),
          status: (event.status as ClassificationStepStatus) ?? "pending",
        });
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
        throw new Error(String(event.detail ?? "Classification échouée"));
      }
    }
  }

  if (!result?.raw) {
    throw new Error("Réponse de classification incomplète.");
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
  const response = await fetch(`${API_BASE_URL}/classify/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return consumeClassifyStream(response, handlers);
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
