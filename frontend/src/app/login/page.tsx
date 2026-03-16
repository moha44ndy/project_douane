'use client';

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        setError(signInError.message);
        return;
      }

      if (data.session) {
        router.push("/");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur de connexion";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient flex items-center justify-center px-4">
      <div className="w-full max-w-lg rounded-3xl bg-card border border-border shadow-xl overflow-hidden">
        <div className="bg-primary text-primary-foreground px-8 py-6">
          <p className="text-xs uppercase tracking-[0.15em] opacity-80">
            Mosam · Direction Générale des Douanes
          </p>
          <h1 className="mt-2 text-2xl font-semibold">
            Connexion à l&apos;espace douanier
          </h1>
          <p className="mt-1 text-sm text-primary-foreground/80 max-w-md">
            Authentifiez-vous pour accéder à l&apos;assistant de classification
            tarifaire CEDEAO.
          </p>
        </div>

        <div className="px-8 py-6 space-y-6">
          <form onSubmit={handleSubmit} className="space-y-4 text-sm">
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-muted-foreground">
                Email professionnel
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/70"
                placeholder="prenom.nom@douane.ci"
                required
              />
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-muted-foreground">
                Mot de passe
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/70"
                required
              />
            </div>

            {error && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-2xl px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold shadow-md hover:bg-primary/90 disabled:opacity-70 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Connexion..." : "Se connecter"}
            </button>
          </form>

          <p className="text-[11px] text-muted-foreground text-center">
            Accès réservé aux agents habilités de la douane ivoirienne.
          </p>
        </div>
      </div>
    </div>
  );
}

