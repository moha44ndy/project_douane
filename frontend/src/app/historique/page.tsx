'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "../../lib/apiBase";
import {
  httpApiErrorMessage,
  humanizeClientFetchError,
} from "../../lib/httpApiErrorMessage";
import { supabase } from "../../lib/supabaseClient";

type HistoryItem = Record<string, any>;

type Filters = {
  search: string;
  section: string;
  status: string;
  dossier: string;
  agent?: string;
  dateFrom?: string;
  dateTo?: string;
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

function formatDateTime(raw: string | null | undefined): string {
  if (!raw) return "N/A";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "N/A";

  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");

  return `${day}/${month}/${year} ${hours}h${minutes}`;
}

function riskEmoji(level?: string): string {
  switch (level) {
    case "low":
      return "🟢";
    case "medium":
      return "🟡";
    case "high":
      return "🔴";
    default:
      return "";
  }
}

function normalizeHistoryItem(item: HistoryItem) {
  const id = item.id as number | undefined;

  // Description
  const description =
    item.description_produit ??
    extractField(item, ["product", "description"], item.description ?? "N/A");

  // Section
  const sectionFromFlat = item.section_produit;
  const sectionFromNested =
    extractField(item, ["classification", "section", "number"], undefined) ??
    extractField(item, ["classification", "section"], undefined);
  const section = String(sectionFromFlat ?? sectionFromNested ?? "N/A");

  // Chapitre (numéro)
  const chapterFromFlat = item.chapitre_produit;
  const chapterFromNested = extractField(
    item,
    ["classification", "chapter"],
    undefined
  );
  const chapter = String(chapterFromFlat ?? chapterFromNested ?? "N/A");

  // Code tarifaire
  const code =
    item.code_tarifaire ??
    extractField(item, ["classification", "code"], "N/A");

  // Confiance
  const confidenceRaw =
    item.classification_confidence ??
    extractField(item, ["classification", "confidence"], "0");
  const confidence =
    typeof confidenceRaw === "number" ? confidenceRaw : Number(confidenceRaw) || 0;

  // Taux et métadonnées
  const ddRate = (item.dd_rate ?? "N/R") as string;
  const rsRate = (item.rs_rate ?? "N/R") as string;
  const otherTaxes = (item.other_taxes ?? "N/R") as string;
  const usUnit = (item.us_unit ?? "N/R") as string;
  const origin = (item.origin ?? "N/A") as string;
  const value = (item.value ?? "N/A") as string;
  const quantityRaw = item.quantity ?? 1;
  const quantity =
    typeof quantityRaw === "number" ? quantityRaw : Number(quantityRaw) || 1;

  // Statut
  const status = (item.statut_validation ?? item.statut ?? "N/A") as string;

  const riskLevel = (item.risk_level ?? "") as string;
  const riskLabel = (item.risk_label ?? "") as string;

  const dossierName = (item.dossier_name ?? "") as string;

  // Date
  const dateRaw = item.date_classification ?? item.date ?? "";
  const dateLabel = formatDateTime(dateRaw);

  return {
    id,
    description,
    section,
    chapter,
    code,
    confidence,
    ddRate,
    rsRate,
    otherTaxes,
    usUnit,
    origin,
    value,
    quantity: Math.max(1, Math.floor(quantity)),
    status,
    riskLevel,
    riskLabel,
    dossierName,
    dateRaw,
    dateLabel,
  };
}

export default function HistoriquePage() {
  const router = useRouter();
  const [data, setData] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({
    search: "",
    section: "Toutes",
    status: "Tous",
    dossier: "Tous",
    agent: "Tous",
    dateFrom: "",
    dateTo: "",
  });
  const [userId, setUserId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const [checkingSession, setCheckingSession] = useState(true);
  // Etat d'affichage des dossiers (fermé / ouvert) dans le tableau.
  // Par défaut: tous les dossiers sont fermés.
  const [collapsedDossiers, setCollapsedDossiers] = useState<Record<string, boolean>>(
    {}
  );
  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          // Utilisateur non connecté : on reste sur un écran vide
          // et on remplace l'URL par /login pour éviter tout flash.
          router.replace("/login");
          return;
        }
        const id = session.user.id ?? null;
        setUserId(id);

        const url =
          id != null
            ? `${API_BASE_URL}/history?user_id=${encodeURIComponent(id)}`
            : `${API_BASE_URL}/history`;
        const res = await fetch(url);
        if (!res.ok) {
          const text = await res.text();
          throw new Error(httpApiErrorMessage(res.status, text));
        }
        const json = await res.json();
        setData(Array.isArray(json) ? json : []);
        // On ne termine le "checking" que si la session est valide
        setCheckingSession(false);
      } catch (err) {
        const raw =
          err instanceof Error ? err.message : "Erreur inconnue côté client";
        setError(humanizeClientFetchError(raw));
        // En cas d'erreur réseau/API, on sort aussi de l'état de "checking"
        setCheckingSession(false);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [router]);
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

  const dossierOptions = useMemo(() => {
    const set = new Set<string>();
    normalized.forEach((n) => {
      const v = n.dossierName && String(n.dossierName).trim();
      if (v) set.add(String(v));
    });

    return [
      { value: "Tous", label: "Tous" },
      { value: "__has__", label: "tous les dossiers" },
      { value: "__none__", label: "aucun dossier" },
      ...Array.from(set).sort().map((d) => ({ value: d, label: d })),
    ];
  }, [normalized]);

  const filtered = useMemo(() => {
    return normalized.filter((item) => {
      if (filters.search) {
        const s = filters.search.toLowerCase();
        if (
          !item.description.toLowerCase().includes(s) &&
          !item.code.toLowerCase().includes(s) &&
          !(
            item.dossierName &&
            String(item.dossierName).toLowerCase().includes(s)
          )
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

      if (filters.dossier !== "Tous") {
        if (filters.dossier === "__none__") {
          if (item.dossierName && String(item.dossierName).trim()) return false;
        } else if (filters.dossier === "__has__") {
          if (!item.dossierName || !String(item.dossierName).trim()) return false;
        } else {
          if (String(item.dossierName || "").trim() !== filters.dossier) return false;
        }
      }
      return true;
    });
  }, [normalized, filters]);

  const filteredDossierKeys = useMemo(() => {
    const set = new Set<string>();
    filtered.forEach((n) => {
      const k = n.dossierName && String(n.dossierName).trim()
        ? String(n.dossierName).trim()
        : null;
      if (k) set.add(k);
    });
    return Array.from(set).sort();
  }, [filtered]);

  useEffect(() => {
    // Si l'utilisateur filtre par dossier, on déplie automatiquement les
    // dossiers correspondants pour qu'on voie les items filtrés.
    if (filters.dossier === "Tous" || filters.dossier === "__none__") return;

    if (filters.dossier === "__has__") {
      setCollapsedDossiers((prev) => {
        const next = { ...prev };
        filteredDossierKeys.forEach((k) => {
          next[k] = false;
        });
        return next;
      });
      return;
    }

    // Dossier spécifique
    setCollapsedDossiers((prev) => ({
      ...prev,
      [filters.dossier]: false,
    }));
  }, [filters.dossier, filteredDossierKeys]);

  const total = data.length;
  const totalFiltered = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginated = useMemo(
    () =>
      filtered.slice(
        (currentPage - 1) * pageSize,
        (currentPage - 1) * pageSize + pageSize
      ),
    [filtered, currentPage, pageSize]
  );

  if (checkingSession) {
    return (
      <div className="min-h-screen bg-background" />
    );
  }

  const avgConfidence =
    paginated.reduce((acc, it) => acc + it.confidence, 0) /
      (paginated.length || 1) || 0;

  // Par défaut, on ferme tous les dossiers (les dossiers non présents dans
  // l'objet collapsedDossiers sont considérés fermés).

  // Actions d'admin retirées de cette page : la vue globale et le forçage
  // de statut sont réservés au panneau d'administration.

  return (
    <div className="space-y-8">
      <header className="rounded-3xl bg-card border border-border shadow-xl px-4 sm:px-8 py-6 space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <Link
            href="/"
            className="mosam-btn-admin mosam-header-btn inline-flex w-full shrink-0 items-center justify-center touch-manipulation lg:w-auto"
          >
            Retour à la classification
          </Link>
          <div className="text-sm text-muted-foreground lg:text-right">
            <div className="font-semibold text-primary">
              Total en base : {total}
            </div>
            <div>Filtrés : {totalFiltered}</div>
          </div>
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-primary mb-1">
            Historique des classifications
          </h1>
          <p className="text-muted-foreground text-sm">
            Retrouvez les classifications passées avec leur section, code
            tarifaire et statut.
          </p>
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
                title="Filtrer par section"
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
                title="Filtrer par statut"
              >
                {statuses.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Dossier
              </label>
              <select
                value={filters.dossier}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, dossier: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                title="Filtrer par dossier"
              >
                {dossierOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            {/* Filtres avancés (agent, dates) réservés à la vue admin globale */}
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
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-primary">
            Résultats ({totalFiltered})
          </h2>
          {!loading && !error && userId && (
            <div className="flex items-center gap-3 flex-wrap">
              <button
                type="button"
                onClick={() => {
                  const url = `${API_BASE_URL}/history.csv?user_id=${encodeURIComponent(
                    userId
                  )}`;
                  window.open(url, "_blank", "noopener,noreferrer");
                }}
                className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5"
              >
                Exporter tout (CSV)
              </button>

              <button
                type="button"
                onClick={() => {
                  const params = new URLSearchParams();
                  params.set("user_id", userId);
                  if (filters.search.trim())
                    params.set("search", filters.search.trim());
                  if (filters.section !== "Toutes")
                    params.set("section", filters.section);
                  if (filters.status !== "Tous")
                    params.set("status", filters.status);
                  if (filters.dossier && filters.dossier !== "Tous")
                    params.set("dossier", filters.dossier);

                  const url = `${API_BASE_URL}/history.csv?${params.toString()}`;
                  window.open(url, "_blank", "noopener,noreferrer");
                }}
                className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5"
              >
                Exporter filtré (CSV)
              </button>
            </div>
          )}
        </div>

        {loading && (
          <div className="text-sm text-muted-foreground">Chargement...</div>
        )}
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-2xl px-3 py-2">
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Table partout (mobile + desktop) */}
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
                      Chapitre
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">
                      Code tarifaire
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">Qté</th>
                    <th className="px-3 py-2 text-left font-semibold">D.D.</th>
                    <th className="px-3 py-2 text-left font-semibold">R.S.</th>
                    <th className="px-3 py-2 text-left font-semibold">
                      Autres taxes
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">U.S.</th>
                    <th className="px-3 py-2 text-left font-semibold">Origine</th>
                    <th className="px-3 py-2 text-left font-semibold">Valeur</th>
                    <th className="px-3 py-2 text-left font-semibold">Date / heure</th>
                    <th className="px-3 py-2 text-left font-semibold">Confiance</th>
                    <th className="px-3 py-2 text-left font-semibold">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    type DossierInfo = { count: number; first: number; last: number };
                    const dossierInfo = new Map<string, DossierInfo>();

                    paginated.forEach((it, idx) => {
                      const dossierKey =
                        it.dossierName && String(it.dossierName).trim()
                          ? String(it.dossierName).trim()
                          : null;
                      if (!dossierKey) return;
                      const current = dossierInfo.get(dossierKey);
                      if (!current) {
                        dossierInfo.set(dossierKey, {
                          count: 1,
                          first: idx,
                          last: idx,
                        });
                      } else {
                        dossierInfo.set(dossierKey, {
                          ...current,
                          count: current.count + 1,
                          last: idx,
                        });
                      }
                    });

                    return paginated.flatMap((it, idx) => {
                      const dossierKey =
                        it.dossierName && String(it.dossierName).trim()
                          ? String(it.dossierName).trim()
                          : null;

                      // Aucun dossier => rendu direct à la position chronologique
                      if (!dossierKey) {
                        return [
                          <tr
                            key={`ungrouped-${currentPage}-row-${idx}`}
                            className={
                              idx % 2 === 0 ? "bg-muted/40" : "bg-background"
                            }
                          >
                            <td className="px-3 py-2">{it.description}</td>
                            <td className="px-3 py-2">{it.section}</td>
                            <td className="px-3 py-2">{it.chapter}</td>
                            <td className="px-3 py-2 font-mono">{it.code}</td>
                            <td className="px-3 py-2">{it.quantity}</td>
                            <td className="px-3 py-2">{it.ddRate}</td>
                            <td className="px-3 py-2">{it.rsRate}</td>
                            <td className="px-3 py-2">{it.otherTaxes}</td>
                            <td className="px-3 py-2">{it.usUnit}</td>
                            <td className="px-3 py-2">{it.origin}</td>
                            <td className="px-3 py-2">{it.value}</td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {it.dateLabel}
                            </td>
                            <td className="px-3 py-2">
                              <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                                {it.confidence.toFixed(1)}%
                              </span>
                              {it.riskLabel ? (
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {riskEmoji(it.riskLevel)} {it.riskLabel}
                                </div>
                              ) : null}
                            </td>
                            <td className="px-3 py-2">{it.status}</td>
                          </tr>,
                        ];
                      }

                      const info = dossierInfo.get(dossierKey);
                      if (!info) return [];

                      // Si le dossier n'a jamais été ouvert manuellement,
                      // on le considère fermé par défaut.
                      const isCollapsed = collapsedDossiers[dossierKey] ?? true;
                      const isFirst = idx === info.first;
                      const isLast = idx === info.last;

                      const out: JSX.Element[] = [];

                      // Header du dossier à la première occurrence (donc il reste dans le bon ordre)
                      if (isFirst) {
                        out.push(
                          <tr key={`group-header-${dossierKey}-${currentPage}`}>
                            <td
                              colSpan={14}
                              className="px-3 py-2 bg-primary/5 font-semibold text-primary"
                            >
                              <button
                                type="button"
                                onClick={() => {
                                  setCollapsedDossiers((prev) => ({
                                    ...prev,
                                    [dossierKey]: !(prev[dossierKey] ?? false),
                                  }));
                                }}
                                className="inline-flex items-center gap-2"
                                aria-label={`Dossier ${dossierKey}: ${
                                  isCollapsed ? "déplier" : "réduire"
                                }`}
                              >
                                <span aria-hidden="true">
                                  {isCollapsed ? ">" : "v"}
                                </span>
                                <span>{dossierKey}</span>
                                <span className="text-muted-foreground font-normal">
                                  ({info.count})
                                </span>
                              </button>
                            </td>
                          </tr>
                        );
                      }

                      // Eléments du dossier uniquement si déplié
                      if (!isCollapsed) {
                        out.push(
                          <tr
                            key={`group-item-${dossierKey}-${currentPage}-row-${idx}`}
                            className={
                              idx % 2 === 0 ? "bg-muted/40" : "bg-background"
                            }
                          >
                            <td className="px-3 py-2">{it.description}</td>
                            <td className="px-3 py-2">{it.section}</td>
                            <td className="px-3 py-2">{it.chapter}</td>
                            <td className="px-3 py-2 font-mono">{it.code}</td>
                            <td className="px-3 py-2">{it.quantity}</td>
                            <td className="px-3 py-2">{it.ddRate}</td>
                            <td className="px-3 py-2">{it.rsRate}</td>
                            <td className="px-3 py-2">{it.otherTaxes}</td>
                            <td className="px-3 py-2">{it.usUnit}</td>
                            <td className="px-3 py-2">{it.origin}</td>
                            <td className="px-3 py-2">{it.value}</td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {it.dateLabel}
                            </td>
                            <td className="px-3 py-2">
                              <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                                {it.confidence.toFixed(1)}%
                              </span>
                              {it.riskLabel ? (
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {riskEmoji(it.riskLevel)} {it.riskLabel}
                                </div>
                              ) : null}
                            </td>
                            <td className="px-3 py-2">{it.status}</td>
                          </tr>
                        );

                        // Séparateur de fin du dossier : après la dernière ligne rendue du dossier
                        if (isLast) {
                          out.push(
                            <tr key={`group-sep-${dossierKey}-${currentPage}-${idx}`}>
                              <td colSpan={14} className="px-3 py-0">
                                <div className="h-5 bg-primary/100 rounded-lg shadow-[0_10px_24px_rgba(16,185,129,0.35)]" />
                              </td>
                            </tr>
                          );
                        }
                      }

                      return out;
                    });
                  })()}
                  {filtered.length === 0 && (
                    <tr>
                      <td
                        colSpan={14}
                        className="px-3 py-4 text-center text-sm text-muted-foreground"
                      >
                        Aucune classification ne correspond aux filtres.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
        {!loading && !error && filtered.length > 0 && (
          <div className="flex items-center justify-between pt-4 text-sm text-muted-foreground">
            <div>
              Page {currentPage} / {totalPages} •{" "}
              {paginated.length} lignes affichées
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded-full border border-border bg-background disabled:opacity-50"
              >
                Précédent
              </button>
              <button
                type="button"
                disabled={currentPage === totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1 rounded-full border border-border bg-background disabled:opacity-50"
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </section>

    </div>
  );
}

