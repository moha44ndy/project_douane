/**
 * Formate le corps d’erreur HTTP pour l’UI : évite d’afficher une page HTML
 * complète (404 Next, proxy, etc.) quand l’API renvoie du HTML au lieu de JSON.
 */
export function httpApiErrorMessage(status: number, bodyText: string): string {
  const t = (bodyText ?? "").trim();
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
