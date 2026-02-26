'use client';

import Link from "next/link";
import { FormEvent, useState } from "react";

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
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [payload, setPayload] = useState<ApiPayload | null>(null);

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
      <header className="rounded-3xl bg-card border border-border shadow-xl px-8 py-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-primary mb-1">
            Mosam – Classification Tarifaire CEDEAO
          </h1>
          <p className="text-muted-foreground">
            Assistant IA pour la classification douanière TEC/SH 2022 – Côte
            d&apos;Ivoire.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 text-right text-sm text-muted-foreground">
          <div>
            <div className="font-semibold text-primary">
              Direction Générale des Douanes
            </div>
            <div>21 sections · 97 chapitres · 5000+ codes</div>
          </div>
          <div className="flex gap-2 text-xs">
            <Link
              href="/historique"
              className="inline-flex items-center rounded-full bg-primary text-primary-foreground px-4 py-1 font-semibold shadow-md hover:bg-primary/90 transition-colors"
            >
              📋 Historique
            </Link>
            <Link
              href="/admin"
              className="inline-flex items-center rounded-full border border-border bg-background text-primary px-4 py-1 font-semibold shadow-md hover:bg-primary/10 transition-colors"
            >
              🛡️ Admin
            </Link>
          </div>
        </div>
      </header>

      <section className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary flex items-center gap-2">
            <span className="text-2xl">✍️</span> Décrire la marchandise
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
              className="w-full min-h-[140px] rounded-2xl border border-border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/70 resize-vertical"
              placeholder={
                "Exemples :\n" +
                "- Ordinateur portable 15'' écran LED, processeur i7, 16 Go RAM\n" +
                "- Barre en acier laminé à chaud, section rectangulaire"
              }
            />
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-6 py-2 text-sm font-semibold shadow-md hover:bg-primary/90 disabled:opacity-70 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? (
                <>
                  <span className="inline-block h-4 w-4 border-2 border-primary-foreground/40 border-t-transparent rounded-full animate-spin" />
                  Mosam réfléchit…
                </>
              ) : (
                <>
                  <span className="text-lg">🚀</span> Lancer la classification
                </>
              )}
            </button>
          </form>
          {error && (
            <div className="mt-3 rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </div>
          )}
        </div>

        <div className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary flex items-center gap-2">
            <span className="text-2xl">📌</span> Résumé
          </h2>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>
              <span className="font-semibold text-primary">Statut :</span>{" "}
              {loading ? "Analyse en cours…" : "Prêt"}
            </li>
            <li>
              <span className="font-semibold text-primary">API :</span>{" "}
              {API_BASE_URL}
            </li>
            <li>
              <span className="font-semibold text-primary">
                Marchandises classées :
              </span>{" "}
              {classifications.length || "–"}
            </li>
          </ul>
          <p className="text-xs text-muted-foreground mt-4">
            Astuce : dans ta future UI Next.js, tu pourras ajouter d&apos;autres
            pages (historique, administration) qui consommeront la même API
            FastAPI.
          </p>
        </div>
      </section>

      {payload && (
        <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary flex items-center gap-2">
            <span className="text-2xl">📊</span> Résultat structuré
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

      {raw && (
        <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-3">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-primary">
              Voir le JSON brut renvoyé par le modèle
            </summary>
            <pre className="mt-3 max-h-80 overflow-auto rounded-2xl bg-background border border-border px-3 py-2 text-xs text-muted-foreground">
{raw}
            </pre>
          </details>
        </section>
      )}
    </div>
  );
}

