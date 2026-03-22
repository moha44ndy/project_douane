const DEFAULT_DEV_API = "http://localhost:8000";

/**
 * Base URL du backend FastAPI.
 * Si la variable est vide (souvent par erreur sur Vercel), on ne doit pas utiliser ""
 * sinon fetch("/users") part sur le même domaine Next → 404 HTML.
 *
 * Sur Vercel (HTTPS) avec un backend seulement en HTTP : contenu mixte → "Failed to fetch".
 * Utilise alors NEXT_PUBLIC_API_BASE_URL=/api/mosam et MOSAM_API_UPSTREAM=http://IP:8080
 * (variable serveur, sans NEXT_PUBLIC_) pour proxifier via app/api/mosam/[[...path]].
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (raw == null) return DEFAULT_DEV_API;
  const t = raw.trim();
  if (!t) return DEFAULT_DEV_API;
  return t.replace(/\/+$/, "");
}

export const API_BASE_URL = getApiBaseUrl();
