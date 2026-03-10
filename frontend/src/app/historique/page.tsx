'use client';

import { useEffect, useMemo, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type HistoryItem = Record<string, any>;

type Filters = {
  search: string;
  section: string;
  status: string;
};

function extractField(item: HistoryItem, path: string[], fallback = "N/A") {
  let current: any = item;
  for (const key of path) {
    if (current && typeof current === "object") {
      current = current[key];
    } else {
      current = undefined;
      break;
    }
  }
  return current ?? fallback;
}

function normalizeHistoryItem(item: HistoryItem) {
  // Description
  const description =
    item.description_produit ??
    extractField(item, ["product", "description"], item.description ?? "N/A");

  // Section
  const sectionFromFlat = item.section_produit;
  const sectionFromNested =
    extractField(item, ["classification", "section", "number"], null) ??
    extractField(item, ["classification", "section"], null);
  const section = String(sectionFromFlat ?? sectionFromNested ?? "N/A");

  // Code tarifaire
  const code =
    item.code_tarifaire ??
    extractField(item, ["classification", "code"], "N/A");

  // Confiance
  const confidenceRaw =
    item.classification_confidence ??
    extractField(item, ["classification", "confidence"], 0);
  const confidence =
    typeof confidenceRaw === "number" ? confidenceRaw : Number(confidenceRaw) || 0;

  // Statut
  const status = (item.statut_validation ?? item.statut ?? "N/A") as string;

  // Date
  const dateRaw = item.date_classification ?? item.date ?? "";

  return { description, section, code, confidence, status, dateRaw };
}

export default function HistoriquePage() {
  const [data, setData] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({
    search: "",
    section: "Toutes",
    status: "Tous",
  });

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE_URL}/history`);
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `Erreur HTTP ${res.status}`);
        }
        const json = await res.json();
        setData(Array.isArray(json) ? json : []);
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Erreur inconnue côté client";
        setError(msg);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  const normalized = useMemo(
    () => data.map((item) => normalizeHistoryItem(item)),
    [data]
  );

  const sections = useMemo(() => {
    const set = new Set<string>();
    normalized.forEach((n) => {
      if (n.section && n.section !== "N/A") set.add(String(n.section));
    });
    return ["Toutes", ...Array.from(set).sort()];
  }, [normalized]);

  const statuses = useMemo(() => {
    const set = new Set<string>();
    normalized.forEach((n) => {
      if (n.status && n.status !== "N/A") set.add(String(n.status));
    });
    return ["Tous", ...Array.from(set).sort()];
  }, [normalized]);

  const filtered = useMemo(() => {
    return normalized.filter((item) => {
      if (filters.search) {
        const s = filters.search.toLowerCase();
        if (
          !item.description.toLowerCase().includes(s) &&
          !item.code.toLowerCase().includes(s)
        ) {
          return false;
        }
      }
      if (filters.section !== "Toutes" && item.section !== filters.section) {
        return false;
      }
      if (filters.status !== "Tous" && item.status !== filters.status) {
        return false;
      }
      return true;
    });
  }, [normalized, filters]);

  const total = data.length;
  const totalFiltered = filtered.length;
  const avgConfidence =
    filtered.reduce((acc, it) => acc + it.confidence, 0) /
      (filtered.length || 1) || 0;

  return (
    <div className="space-y-8">
      <header className="rounded-3xl bg-card border border-border shadow-xl px-8 py-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-primary mb-1">
            Historique des classifications
          </h1>
          <p className="text-muted-foreground text-sm">
            Vue Next.js de l&apos;historique déjà enregistré dans{" "}
            <code>sam/table_data.json</code>.
          </p>
        </div>
        <div className="text-right text-sm text-muted-foreground">
          <div className="font-semibold text-primary">
            Total en base : {total}
          </div>
          <div>Filtrés : {totalFiltered}</div>
        </div>
      </header>

      <section className="grid lg:grid-cols-3 gap-6">
        <div className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary">Filtres</h2>
          <div className="space-y-3 text-sm">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Recherche (description, code)
              </label>
              <input
                type="text"
                value={filters.search}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, search: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/70"
                placeholder="Ex: textile, 8517..."
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Section
              </label>
              <select
                value={filters.section}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, section: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
              >
                {sections.map((sec) => (
                  <option key={sec} value={sec}>
                    {sec}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Statut
              </label>
              <select
                value={filters.status}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, status: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
              >
                {statuses.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
            <div className="text-xs text-muted-foreground">
              Total classifications
            </div>
            <div className="text-3xl font-bold text-primary leading-none">
              {total}
            </div>
          </div>
          <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
            <div className="text-xs text-muted-foreground">
              Confiance moyenne (filtrés)
            </div>
            <div className="text-3xl font-bold text-primary leading-none">
              {avgConfidence.toFixed(1)}%
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
        <h2 className="text-xl font-semibold text-primary">
          Résultats ({totalFiltered})
        </h2>

        {loading && (
          <div className="text-sm text-muted-foreground">Chargement...</div>
        )}
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-2xl px-3 py-2">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="overflow-x-auto rounded-2xl border border-border bg-background">
            <table className="min-w-full text-sm">
              <thead className="bg-primary text-primary-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">
                    Description
                  </th>
                  <th className="px-3 py-2 text-left font-semibold">
                    Section
                  </th>
                  <th className="px-3 py-2 text-left font-semibold">
                    Code tarifaire
                  </th>
                  <th className="px-3 py-2 text-left font-semibold">
                    Confiance
                  </th>
                  <th className="px-3 py-2 text-left font-semibold">Statut</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item, idx) => (
                  <tr
                    key={idx}
                    className={
                      idx % 2 === 0 ? "bg-muted/40" : "bg-background"
                    }
                  >
                    <td className="px-3 py-2">{item.description}</td>
                    <td className="px-3 py-2">{item.section}</td>
                    <td className="px-3 py-2 font-mono">{item.code}</td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                        {item.confidence.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-3 py-2">{item.status}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-4 text-center text-sm text-muted-foreground"
                    >
                      Aucune classification ne correspond aux filtres.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

