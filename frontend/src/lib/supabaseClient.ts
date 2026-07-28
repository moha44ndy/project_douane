import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

function readSupabaseEnv(): { url: string; key: string } {
  return {
    url: process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ?? "",
    key: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ?? "",
  };
}

export function isSupabaseConfigured(): boolean {
  const { url, key } = readSupabaseEnv();
  return Boolean(url && key);
}

/** Client Supabase (lazy) — évite un crash au build Vercel si les env ne sont pas encore injectées. */
export function getSupabase(): SupabaseClient {
  if (_client) return _client;
  const { url, key } = readSupabaseEnv();
  if (!url || !key) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY on Vercel."
    );
  }
  _client = createClient(url, key);
  return _client;
}

/**
 * Compatibilité avec l'import existant `import { supabase } from ...`.
 * Le client n'est instancié qu'au premier accès (pas au chargement du module).
 */
export const supabase: SupabaseClient = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    const client = getSupabase();
    const value = Reflect.get(client, prop, client) as unknown;
    if (typeof value === "function") {
      return (value as (...args: unknown[]) => unknown).bind(client);
    }
    return value;
  },
});
