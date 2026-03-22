'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "../../../lib/supabaseClient";
import { ConfirmModal } from "../../../components/ConfirmModal";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type HistoryItem = Record<string, any>;

type Filters = {
  search: string;
  section: string;
  status: string;
  agent: string;
  dossier: string;
  dateFrom: string;
  dateTo: string;
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

function normalizeHistoryItem(item: HistoryItem) {
  const id = item.id as number | undefined;

  const description =
    item.description_produit ??
    extractField(item, ["product", "description"], item.description ?? "N/A");

  const sectionFromFlat = item.section_produit;
  const sectionFromNested =
    extractField(item, ["classification", "section", "number"], undefined) ??
    extractField(item, ["classification", "section"], undefined);
  const section = String(sectionFromFlat ?? sectionFromNested ?? "N/A");

  const chapterFromFlat = item.chapitre_produit;
  const chapterFromNested = extractField(
    item,
    ["classification", "chapter"],
    undefined
  );
  const chapter = String(chapterFromFlat ?? chapterFromNested ?? "N/A");

  const code =
    item.code_tarifaire ??
    extractField(item, ["classification", "code"], "N/A");

  const confidenceRaw =
    item.classification_confidence ??
    extractField(item, ["classification", "confidence"], "0");
  const confidence =
    typeof confidenceRaw === "number" ? confidenceRaw : Number(confidenceRaw) || 0;

  const ddRate = (item.dd_rate ?? "N/R") as string;
  const rsRate = (item.rs_rate ?? "N/R") as string;
  const otherTaxes = (item.other_taxes ?? "N/R") as string;
  const usUnit = (item.us_unit ?? "N/R") as string;
  const origin = (item.origin ?? "N/A") as string;
  const value = (item.value ?? "N/A") as string;
  const quantityRaw = item.quantity ?? 1;
  const quantity =
    typeof quantityRaw === "number" ? quantityRaw : Number(quantityRaw) || 1;

  const status = (item.statut_validation ?? item.statut ?? "N/A") as string;

  const agentName = (item.agent_name ?? "N/A") as string;
  const dossierName = (item.dossier_name ?? "") as string;

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
    dateRaw,
    dateLabel,
    agentName,
    dossierName,
  };
}

export default function AdminHistoriquePage() {
  const router = useRouter();
  const [data, setData] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({
    search: "",
    section: "Toutes",
    status: "Tous",
    agent: "Tous",
    dossier: "Tous",
    dateFrom: "",
    dateTo: "",
  });
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const [checkingSession, setCheckingSession] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [cacheDisabled, setCacheDisabled] = useState<boolean | null>(null);
  const [hasCacheStatus, setHasCacheStatus] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [confirmCacheAction, setConfirmCacheAction] = useState<
    null | "disable" | "clear"
  >(null);
  const [cacheFeedback, setCacheFeedback] = useState<{
    success?: string;
    error?: string;
  } | null>(null);
  const [quantityDrafts, setQuantityDrafts] = useState<Record<string, number>>({});
  // Etat d'affichage des dossiers (fermé / ouvert). Par défaut: fermés.
  const [collapsedDossiers, setCollapsedDossiers] = useState<Record<string, boolean>>({});

  const fetchCacheStatus = async (token?: string) => {
    try {
      const accessToken = token ?? (await withAdminToken());
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);
      const res = await fetch(`${API_BASE_URL}/admin/cache/classify/status`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        const json = await res.json();
        setCacheDisabled(!!json.disabled);
        setHasCacheStatus(true);
      } else {
        setCacheDisabled(false);
      }
    } catch {
      setCacheDisabled(false);
    }
  };

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          router.replace("/login");
          return;
        }

        const accessToken = session.access_token;

        // Statut du cache avec le même token (pour persistance après refresh)
        fetchCacheStatus(accessToken);

        const res = await fetch(`${API_BASE_URL}/history`, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `Erreur HTTP ${res.status}`);
        }
        const json = await res.json();
        setData(Array.isArray(json) ? json : []);
        setCheckingSession(false);
        fetchCacheStatus();
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Erreur inconnue côté client";
        setError(msg);
        setCheckingSession(false);
        fetchCacheStatus();
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

  const agents = useMemo(() => {
    const set = new Set<string>();
    normalized.forEach((n) => {
      if (n.agentName && n.agentName !== "N/A") set.add(String(n.agentName));
    });
    return ["Tous", ...Array.from(set).sort()];
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
      if (filters.agent !== "Tous" && item.agentName !== filters.agent) {
        return false;
      }

      if (filters.dossier !== "Tous") {
        if (filters.dossier === "__none__") {
          if (item.dossierName && String(item.dossierName).trim()) return false;
        } else if (filters.dossier === "__has__") {
          if (!item.dossierName || !String(item.dossierName).trim()) return false;
        } else {
          if (String(item.dossierName || "").trim() !== filters.dossier)
            return false;
        }
      }

      if (filters.dateFrom) {
        const from = new Date(filters.dateFrom);
        const current = new Date(item.dateRaw);
        if (!Number.isNaN(from.getTime()) && !Number.isNaN(current.getTime())) {
          if (current < from) return false;
        }
      }
      if (filters.dateTo) {
        const to = new Date(filters.dateTo);
        const current = new Date(item.dateRaw);
        if (!Number.isNaN(to.getTime()) && !Number.isNaN(current.getTime())) {
          if (current > to) return false;
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
    // Quand l'utilisateur filtre par dossier, on déplie automatiquement
    // les dossiers concernés pour voir les items filtrés.
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
    return <div className="min-h-screen bg-background" />;
  }

  const avgConfidence =
    paginated.reduce((acc, it) => acc + it.confidence, 0) /
      (paginated.length || 1) || 0;

  const withAdminToken = async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const accessToken = session?.access_token;
    if (!accessToken) {
      throw new Error("Session expirée, veuillez vous reconnecter.");
    }
    return accessToken;
  };

  const handleExportFilteredCsv = async () => {
    setExporting(true);
    setError(null);
    setActionMessage(null);
    try {
      const accessToken = await withAdminToken();
      const params = new URLSearchParams();

      if (filters.search.trim()) params.set("search", filters.search.trim());
      if (filters.section !== "Toutes") params.set("section", filters.section);
      if (filters.status !== "Tous") params.set("status", filters.status);
      if (filters.agent !== "Tous") params.set("agent", filters.agent);
      if (filters.dossier && filters.dossier !== "Tous")
        params.set("dossier", filters.dossier);
      if (filters.dateFrom) params.set("date_from", filters.dateFrom);
      if (filters.dateTo) params.set("date_to", filters.dateTo);

      const url = `${API_BASE_URL}/admin/history.csv?${params.toString()}`;
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `historique_filtre_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setActionMessage(`Export filtré prêt (${totalFiltered} ligne(s)).`);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Erreur lors de l'export filtré.";
      setError(msg);
    } finally {
      setExporting(false);
    }
  };

  const updateStatus = async (itemId: number | undefined, statut: string) => {
    if (!itemId) return;
    try {
      setError(null);
      setActionMessage(null);
      const accessToken = await withAdminToken();
      const res = await fetch(
        `${API_BASE_URL}/classifications/${itemId}/status`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ statut_validation: statut }),
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const updated = await res.json();
      setData((prev) =>
        prev.map((row) => (row.id === updated.id ? { ...row, ...updated } : row))
      );
      setActionMessage(`Statut mis à jour en "${statut}".`);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Erreur lors de la mise à jour du statut.";
      setError(msg);
    }
  };

  const updateQuantity = async (itemId: number | undefined, quantity: number) => {
    if (!itemId) return;
    try {
      setError(null);
      setActionMessage(null);
      const accessToken = await withAdminToken();
      const res = await fetch(
        `${API_BASE_URL}/classifications/${itemId}/quantity`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ quantity }),
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const updated = await res.json();
      setData((prev) =>
        prev.map((row) => (row.id === updated.id ? { ...row, ...updated } : row))
      );
      setActionMessage(`Quantité mise à jour à ${quantity}.`);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Erreur lors de la mise à jour de la quantité.";
      setError(msg);
    }
  };

  return (
    <div className="space-y-8">
      <header className="rounded-3xl bg-card border border-border shadow-xl px-4 sm:px-8 py-6 space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <Link
            href="/admin"
            className="mosam-btn-admin mosam-header-btn inline-flex w-full shrink-0 items-center justify-center touch-manipulation lg:w-auto"
          >
            Retour au panneau admin
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
            Historique global des classifications
          </h1>
          <p className="text-muted-foreground text-sm">
            Vue réservée aux administrateurs : toutes les classifications, avec
            filtres avancés et forçage de statut.
          </p>
        </div>
      </header>

      <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
        <h2 className="text-xl font-semibold text-primary">Cache des classifications</h2>
        <p className="text-sm text-muted-foreground">
          Vider le cache pour forcer de nouvelles réponses du modèle.
        </p>
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-muted-foreground">
              Cache
            </span>
            <button
              type="button"
              aria-label={cacheDisabled ? "Cache désactivé, cliquer pour activer" : "Cache activé, cliquer pour désactiver"}
              title={cacheDisabled ? "Activer le cache" : "Désactiver le cache"}
              disabled={cacheDisabled === null}
              onClick={() => {
                setConfirmCacheAction("disable");
                setCacheFeedback(null);
              }}
              className={`
                relative inline-flex h-7 w-12 shrink-0 cursor-pointer rounded-full border-2 border-transparent
                transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2
                disabled:cursor-not-allowed disabled:opacity-50
                ${cacheDisabled === null ? "bg-muted" : cacheDisabled ? "bg-muted" : "bg-primary"}
              `}
            >
              <span
                className={`
                  pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow ring-0 transition
                  ${
                    cacheDisabled === null
                      ? "translate-x-3"
                      : cacheDisabled
                        ? "translate-x-0.5"
                        : "translate-x-6"
                  }
                `}
              />
            </button>
            <span className="text-sm font-medium min-w-[8rem]">
              {!hasCacheStatus
                ? "Chargement…"
                : cacheDisabled
                  ? "Désactivé"
                  : "Activé"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              setConfirmCacheAction("clear");
              setCacheFeedback(null);
            }}
            className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100"
          >
            Vider le cache
          </button>
        </div>
        {cacheFeedback && (
          <div className="pt-2">
            {cacheFeedback.error && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-2xl px-3 py-2">
                {cacheFeedback.error}
              </div>
            )}
            {cacheFeedback.success && !cacheFeedback.error && (
              <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-2xl px-3 py-2">
                {cacheFeedback.success}
              </div>
            )}
          </div>
        )}
      </section>

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
                Agent
              </label>
              <select
                value={filters.agent}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, agent: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                title="Filtrer par agent"
              >
                {agents.map((ag) => (
                  <option key={ag} value={ag}>
                    {ag}
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
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1">
                  Date min
                </label>
                <input
                  type="date"
                  value={filters.dateFrom}
                  onChange={(e) =>
                    setFilters((f) => ({ ...f, dateFrom: e.target.value }))
                  }
                  className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                  title="Date minimale"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1">
                  Date max
                </label>
                <input
                  type="date"
                  value={filters.dateTo}
                  onChange={(e) =>
                    setFilters((f) => ({ ...f, dateTo: e.target.value }))
                  }
                  className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                  title="Date maximale"
                />
              </div>
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
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-xl font-semibold text-primary">
            Résultats ({totalFiltered})
          </h2>
          {!loading && !error && (
            <div className="flex items-center gap-3 flex-wrap">
              <button
                type="button"
                onClick={() => {
                  const url = `${API_BASE_URL}/history.csv`;
                  window.open(url, "_blank", "noopener,noreferrer");
                }}
                className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5"
              >
                Exporter en CSV (tout)
              </button>
              <button
                type="button"
                onClick={() => void handleExportFilteredCsv()}
                disabled={exporting}
                className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {exporting ? "Export..." : "Exporter filtré (CSV)"}
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
        {actionMessage && !loading && !error && (
          <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-2xl px-3 py-2">
            {actionMessage}
          </div>
        )}

        {!loading && !error && (
          <div className="overflow-x-auto rounded-2xl border border-border bg-background text-sm">
            <table className="min-w-full">
              <thead className="bg-primary text-primary-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">
                    ID
                  </th>
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
                  <th className="px-3 py-2 text-left font-semibold">Dossier</th>
                  <th className="px-3 py-2 text-left font-semibold">Agent</th>
                  <th className="px-3 py-2 text-left font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                    type DossierInfo = { count: number; first: number; last: number };
                    const dossierInfo = new Map<string, DossierInfo>();

                    paginated.forEach((it, idx) => {
                      const k =
                        it.dossierName && String(it.dossierName).trim()
                          ? String(it.dossierName).trim()
                          : null;
                      if (!k) return;
                      const cur = dossierInfo.get(k);
                      if (!cur) {
                        dossierInfo.set(k, { count: 1, first: idx, last: idx });
                      } else {
                        dossierInfo.set(k, {
                          ...cur,
                          count: cur.count + 1,
                          last: idx,
                        });
                      }
                    });

                    return paginated.flatMap((item, idx) => {
                      const dossierKey =
                        item.dossierName && String(item.dossierName).trim()
                          ? String(item.dossierName).trim()
                          : null;

                      // Sans dossier => rendu normal
                      if (!dossierKey) {
                        return [
                          <tr
                            key={`admin-ungrouped-${currentPage}-${idx}`}
                            className={
                              idx % 2 === 0 ? "bg-muted/40" : "bg-background"
                            }
                          >
                            <td className="px-3 py-2">{item.id ?? "N/A"}</td>
                            <td className="px-3 py-2">{item.description}</td>
                            <td className="px-3 py-2">{item.section}</td>
                            <td className="px-3 py-2">{item.chapter}</td>
                            <td className="px-3 py-2 font-mono">{item.code}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <input
                                  type="number"
                                  min={1}
                                  step={1}
                                  value={
                                    quantityDrafts[String(item.id)] ?? item.quantity
                                  }
                                  onChange={(e) => {
                                    const next = Number(e.target.value);
                                    if (!Number.isFinite(next)) return;
                                    const safe = Math.max(1, Math.floor(next));
                                    setQuantityDrafts((prev) => ({
                                      ...prev,
                                      [String(item.id)]: safe,
                                    }));
                                  }}
                                  className="w-20 rounded-lg border border-border bg-background px-2 py-1 text-sm"
                                  aria-label={`Quantité pour ${item.description}`}
                                />
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateQuantity(
                                      item.id,
                                      quantityDrafts[String(item.id)] ?? item.quantity
                                    )
                                  }
                                  className="px-2 py-1 rounded-full border border-primary bg-primary/5 text-xs text-primary"
                                >
                                  OK
                                </button>
                              </div>
                            </td>
                            <td className="px-3 py-2">{item.ddRate}</td>
                            <td className="px-3 py-2">{item.rsRate}</td>
                            <td className="px-3 py-2">{item.otherTaxes}</td>
                            <td className="px-3 py-2">{item.usUnit}</td>
                            <td className="px-3 py-2">{item.origin}</td>
                            <td className="px-3 py-2">{item.value}</td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {item.dateLabel}
                            </td>
                            <td className="px-3 py-2">
                              <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                                {item.confidence.toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-3 py-2">{item.status}</td>
                            <td className="px-3 py-2">{item.dossierName || "N/A"}</td>
                            <td className="px-3 py-2">{item.agentName}</td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateStatus(
                                      item.id,
                                      item.status === "validé"
                                        ? "invalidé"
                                        : "validé"
                                    )
                                  }
                                  className="px-3 py-1 rounded-full border border-emerald-300 bg-emerald-50 text-xs text-emerald-700"
                                >
                                  {item.status === "validé"
                                    ? "Invalider"
                                    : "Valider"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateStatus(
                                      item.id,
                                      item.status === "archivé"
                                        ? "validé"
                                        : "archivé"
                                    )
                                  }
                                  className="px-3 py-1 rounded-full border border-slate-300 bg-slate-50 text-xs text-slate-700"
                                >
                                  {item.status === "archivé"
                                    ? "Désarchiver"
                                    : "Archiver"}
                                </button>
                              </div>
                            </td>
                          </tr>,
                        ];
                      }

                      const info = dossierInfo.get(dossierKey);
                      if (!info) return [];
                      const isCollapsed = collapsedDossiers[dossierKey] ?? true;

                      const out: JSX.Element[] = [];

                      // Header uniquement à la première occurrence
                      if (idx === info.first) {
                        out.push(
                          <tr key={`admin-dossier-header-${dossierKey}-${currentPage}`}>
                            <td colSpan={18} className="px-3 py-2 bg-primary/5 font-semibold text-primary">
                              <button
                                type="button"
                                onClick={() => {
                                  setCollapsedDossiers((prev) => ({
                                    ...prev,
                                    [dossierKey]: !(prev[dossierKey] ?? true),
                                  }));
                                }}
                                className="inline-flex items-center gap-2"
                                aria-label={`Dossier ${dossierKey}: ${
                                  isCollapsed ? "déplier" : "réduire"
                                }`}
                              >
                                <span aria-hidden="true">{isCollapsed ? ">" : "v"}</span>
                                <span>{dossierKey}</span>
                                <span className="text-muted-foreground font-normal">
                                  ({info.count})
                                </span>
                              </button>
                            </td>
                          </tr>
                        );
                      }

                      // Items si déplié
                      if (!isCollapsed) {
                        out.push(
                          <tr
                            key={`admin-dossier-row-${dossierKey}-${currentPage}-${idx}`}
                            className={`${idx % 2 === 0 ? "bg-muted/40" : "bg-background"}${
                              idx === info.last ? " border-b-6 border-emerald-500/95" : ""
                            }`}
                          >
                            <td className="px-3 py-2">{item.id ?? "N/A"}</td>
                            <td className="px-3 py-2">{item.description}</td>
                            <td className="px-3 py-2">{item.section}</td>
                            <td className="px-3 py-2">{item.chapter}</td>
                            <td className="px-3 py-2 font-mono">{item.code}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <input
                                  type="number"
                                  min={1}
                                  step={1}
                                  value={
                                    quantityDrafts[String(item.id)] ?? item.quantity
                                  }
                                  onChange={(e) => {
                                    const next = Number(e.target.value);
                                    if (!Number.isFinite(next)) return;
                                    const safe = Math.max(1, Math.floor(next));
                                    setQuantityDrafts((prev) => ({
                                      ...prev,
                                      [String(item.id)]: safe,
                                    }));
                                  }}
                                  className="w-20 rounded-lg border border-border bg-background px-2 py-1 text-sm"
                                  aria-label={`Quantité pour ${item.description}`}
                                />
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateQuantity(
                                      item.id,
                                      quantityDrafts[String(item.id)] ?? item.quantity
                                    )
                                  }
                                  className="px-2 py-1 rounded-full border border-primary bg-primary/5 text-xs text-primary"
                                >
                                  OK
                                </button>
                              </div>
                            </td>
                            <td className="px-3 py-2">{item.ddRate}</td>
                            <td className="px-3 py-2">{item.rsRate}</td>
                            <td className="px-3 py-2">{item.otherTaxes}</td>
                            <td className="px-3 py-2">{item.usUnit}</td>
                            <td className="px-3 py-2">{item.origin}</td>
                            <td className="px-3 py-2">{item.value}</td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {item.dateLabel}
                            </td>
                            <td className="px-3 py-2">
                              <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                                {item.confidence.toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-3 py-2">{item.status}</td>
                            <td className="px-3 py-2">{item.dossierName || "N/A"}</td>
                            <td className="px-3 py-2">{item.agentName}</td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateStatus(
                                      item.id,
                                      item.status === "validé"
                                        ? "invalidé"
                                        : "validé"
                                    )
                                  }
                                  className="px-3 py-1 rounded-full border border-emerald-300 bg-emerald-50 text-xs text-emerald-700"
                                >
                                  {item.status === "validé"
                                    ? "Invalider"
                                    : "Valider"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateStatus(
                                      item.id,
                                      item.status === "archivé"
                                        ? "validé"
                                        : "archivé"
                                    )
                                  }
                                  className="px-3 py-1 rounded-full border border-slate-300 bg-slate-50 text-xs text-slate-700"
                                >
                                  {item.status === "archivé"
                                    ? "Désarchiver"
                                    : "Archiver"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      }

                      return out;
                    });
                  })()}
                {filtered.length === 0 && (
                  <tr>
                    <td
                      colSpan={18}
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

      <ConfirmModal
        open={confirmCacheAction === "disable"}
        title={cacheDisabled ? "Activer le cache" : "Désactiver le cache"}
        message={
          cacheDisabled
            ? "Les réponses validées seront à nouveau mises en cache pour les requêtes identiques."
            : "Les prochaines classifications ne seront plus mises en cache (ni lues depuis le cache). Vous pourrez réactiver le cache à tout moment."
        }
        confirmLabel={cacheDisabled ? "Activer le cache" : "Désactiver le cache"}
        onCancel={() => setConfirmCacheAction(null)}
        onConfirm={async () => {
          setConfirmCacheAction(null);
          setCacheFeedback(null);
          try {
            const accessToken = await withAdminToken();
            const res = await fetch(
              `${API_BASE_URL}/admin/cache/classify/status`,
              {
                method: "PATCH",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${accessToken}`,
                },
                body: JSON.stringify({ disabled: !cacheDisabled }),
              }
            );
            if (!res.ok) throw new Error("Erreur HTTP");
            const json = await res.json();
            setCacheDisabled(!!json.disabled);
            setCacheFeedback({
              success: json.disabled ? "Cache désactivé." : "Cache activé.",
            });
          } catch (err) {
            setCacheFeedback({
              error:
                err instanceof Error
                  ? err.message
                  : "Erreur lors du changement d'état du cache.",
            });
          }
        }}
      />

      <ConfirmModal
        open={confirmCacheAction === "clear"}
        title="Vider le cache"
        message="Toutes les réponses de classification en cache seront supprimées. Les prochaines requêtes identiques appelleront à nouveau le modèle."
        confirmLabel="Vider le cache"
        danger
        onCancel={() => setConfirmCacheAction(null)}
        onConfirm={async () => {
          setConfirmCacheAction(null);
          setCacheFeedback(null);
          try {
            const accessToken = await withAdminToken();
            const res = await fetch(
              `${API_BASE_URL}/admin/cache/classify`,
              {
                method: "DELETE",
                headers: {
                  Authorization: `Bearer ${accessToken}`,
                },
              }
            );
            if (!res.ok) {
              const text = await res.text();
              throw new Error(text || `Erreur HTTP ${res.status}`);
            }
            const json = await res.json();
            const n = json?.keys_deleted ?? 0;
            setCacheFeedback({
              success:
                n > 0
                  ? `Cache vidé (${n} entrée(s) supprimée(s)).`
                  : "Cache vidé (aucune entrée en cache).",
            });
            fetchCacheStatus();
          } catch (err) {
            setCacheFeedback({
              error:
                err instanceof Error
                  ? err.message
                  : "Erreur lors du vidage du cache.",
            });
          }
        }}
      />
    </div>
  );
}

