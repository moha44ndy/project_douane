'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { supabase } from "../lib/supabaseClient";

type ClassificationItem = {
  description?: string;
  hs_code?: string;
  section?: string;
  chapter?: string;
  dd_rate?: string;
  rs_rate?: string;
  us_unit?: string;
  other_taxes?: string;
  justification?: string;
  excerpt?: string;
  origin?: string;
  value?: string;
  confidence?: number;
};

type ApiPayload = {
  narrative?: string;
  classifications?: ClassificationItem[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [payload, setPayload] = useState<ApiPayload | null>(null);

  useEffect(() => {
    const checkSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login");
      }
    };
    void checkSession();
  }, [router]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setRaw(null);
    setPayload(null);

    try {
      const response = await fetch(`${API_BASE_URL}/classify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Erreur HTTP ${response.status}`);
      }

      const data = await response.json();
      const rawText: string = data.raw ?? "";
      setRaw(rawText);

      try {
        const parsed: ApiPayload = JSON.parse(rawText);
        setPayload(parsed);
      } catch {
        setPayload(null);
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur inconnue côté client";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const classifications = payload?.classifications ?? [];

  return (
    <div className="space-y-8">
      <header className="mosam-hero">
        <div>
          <h1 className="mosam-hero-title">
            Mosam – Classification Tarifaire CEDEAO
          </h1>
          <p className="mosam-hero-subtitle">
            Assistant IA pour la classification douanière TEC/SH 2022 – Côte
            d&apos;Ivoire.
          </p>
        </div>
        <div className="mosam-header-actions">
          <div className="mosam-header-actions-primary">
            <div className="mosam-hero-meta">
              Direction Générale des Douanes
            </div>
            <div className="mosam-hero-stats">
              21 sections · 97 chapitres · 5000+ codes
            </div>
          </div>
          <div className="mosam-header-actions-buttons">
            <Link
              href="/historique"
              className="mosam-btn-secondary"
            >
              Historique
            </Link>
            <Link
              href="/admin"
              className="mosam-btn-admin"
            >
              Administration
            </Link>
          </div>
        </div>
      </header>

      <section className="mosam-main-grid">
        <div className="lg:col-span-2 rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary">
            Décrire la marchandise
          </h2>
          <p className="text-sm text-muted-foreground">
            Décrivez la marchandise à classer (matière, usage, caractéristiques
            techniques…). Vous pouvez saisir plusieurs lignes ou puces, une par
            marchandise.
          </p>
          <form onSubmit={handleSubmit} className="space-y-3">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mosam-textarea min-h-[140px]"
              placeholder={
                "Exemples :\n" +
                "- Ordinateur portable 15'' écran LED, processeur i7, 16 Go RAM\n" +
                "- Barre en acier laminé à chaud, section rectangulaire"
              }
            />
            <button
              type="submit"
              disabled={loading}
              className="mosam-btn-primary"
            >
              {loading ? (
                <>
                  <span className="inline-block h-4 w-4 border-2 border-primary-foreground/40 border-t-transparent rounded-full animate-spin" />
                  Mosam réfléchit…
                </>
              ) : (
                <>Lancer la classification</>
              )}
            </button>
          </form>
          {error && (
            <div className="mt-3 rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </div>
          )}
        </div>
      </section>

      {payload && (
        <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary">
            Résultat structuré
          </h2>
          {payload.narrative && (
            <p className="text-sm text-foreground leading-relaxed">
              {payload.narrative}
            </p>
          )}

          {classifications.length > 0 && (
            <div className="overflow-x-auto rounded-2xl border border-border bg-background">
              <table className="min-w-full text-sm">
                <thead className="bg-primary text-primary-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold">
                      Marchandise
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">
                      Code TEC/SH
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">
                      Section / Chapitre
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">
                      Taux
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">
                      Confiance
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {classifications.map((item, index) => (
                    <tr
                      key={index}
                      className={index % 2 === 0 ? "bg-muted/40" : "bg-background"}
                    >
                      <td className="px-3 py-2 align-top">
                        <div className="font-semibold">
                          {item.description || "Marchandise"}
                        </div>
                        {item.origin && (
                          <div className="text-xs text-muted-foreground">
                            Origine : {item.origin}
                          </div>
                        )}
                        {item.value && (
                          <div className="text-xs text-muted-foreground">
                            Valeur : {item.value}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <div className="font-mono">
                          {item.hs_code || "Non renseigné"}
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-sm">
                        <div>{item.section || "N/A"}</div>
                        <div className="text-xs text-muted-foreground">
                          Chapitre {item.chapter || "N/A"}
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-xs">
                        <div>D.D. {item.dd_rate || "N/R"}</div>
                        <div>R.S. {item.rs_rate || "N/R"}</div>
                        <div>Autres {item.other_taxes || "N/R"}</div>
                        <div>U.S. {item.us_unit || "N/R"}</div>
                      </td>
                      <td className="px-3 py-2 align-top">
                        <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                          {typeof item.confidence === "number"
                            ? `${item.confidence}%`
                            : "N/R"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

