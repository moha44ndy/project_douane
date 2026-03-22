/**
 * Formate le corps d’erreur HTTP pour l’UI : évite d’afficher une page HTML
 * complète (404 Next, proxy, etc.) quand l’API renvoie du HTML au lieu de JSON.
 */
function isGenericNetworkDetail(s: string): boolean {
  const m = s.trim().toLowerCase();
  return (
    m === "fetch failed" ||
    m === "failed to fetch" ||
    m.startsWith("econnrefused") ||
    m.startsWith("etimedout") ||
    m.includes("networkerror")
  );
}

/** Quand `fetch` échoue avant toute réponse HTTP (réseau, CORS navigateur, etc.). */
export function humanizeClientFetchError(message: string): string {
  const m = (message || "").trim().toLowerCase();
  if (
    m.includes("failed to fetch") ||
    m === "fetch failed" ||
    m.includes("load failed") ||
    m.includes("networkerror") ||
    m.includes("network request failed")
  ) {
    return (
      "Impossible de joindre le serveur. Sur Vercel : vérifiez MOSAM_API_UPSTREAM (backend joignable depuis Internet, pare-feu OCI port 8080) et que l’API ne tourne pas uniquement dans Cloud Shell."
    );
  }
  return (message || "").trim();
}

function tryJsonApiDetail(t: string): string | null {
  if (!t.startsWith("{") && !t.startsWith("[")) return null;
  try {
    const j = JSON.parse(t) as unknown;
    if (j && typeof j === "object") {
      const o = j as Record<string, unknown>;
      const errStr = typeof o.error === "string" ? o.error.trim() : "";
      const detStr = typeof o.detail === "string" ? o.detail.trim() : "";

      if (Array.isArray(o.detail) && o.detail.length > 0) {
        const first = o.detail[0] as Record<string, unknown>;
        if (first && typeof first.msg === "string") return first.msg;
      }

      if (errStr) return errStr;
      if (detStr) {
        if (isGenericNetworkDetail(detStr)) {
          return humanizeClientFetchError(detStr);
        }
        return detStr;
      }
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function httpApiErrorMessage(status: number, bodyText: string): string {
  const t = (bodyText ?? "").trim();
  const fromJson = tryJsonApiDetail(t);
  if (fromJson) return fromJson;
  if (
    t.startsWith("<!DOCTYPE") ||
    t.startsWith("<!doctype") ||
    /<\s*html[\s>]/i.test(t.slice(0, 800)) ||
    t.includes("This page could not be found") ||
    t.includes("__next_f") ||
    t.includes("/_next/static/")
  ) {
    return `Réponse HTML reçue (HTTP ${status}) : l’URL de l’API est probablement incorrecte ou pointe vers le site Vercel au lieu du backend FastAPI. Vérifiez NEXT_PUBLIC_API_BASE_URL et redéployez.`;
  }
  if (t.length > 400) {
    const head = t.slice(0, 400).replace(/\s+/g, " ");
    return `${head}… (HTTP ${status}, message tronqué)`;
  }
  return t || `Erreur HTTP ${status}`;
}
