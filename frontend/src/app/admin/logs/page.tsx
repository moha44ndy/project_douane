'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "../../../lib/apiBase";
import { httpApiErrorMessage } from "../../../lib/httpApiErrorMessage";
import { supabase } from "../../../lib/supabaseClient";

type AuditLog = {
  id: string;
  created_at: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details?: Record<string, any> | null;
  actor_name?: string | null;
  entity_name?: string | null;
};

function formatActionLabel(action: string): string {
  switch (action) {
    case "user.create":
      return "Création utilisateur";
    case "user.update":
      return "Mise à jour utilisateur";
    case "user.delete":
      return "Suppression utilisateur";
    case "user.reset_password":
      return "Reset mot de passe";
    case "classification.validate":
      return "Validation classification";
    case "classification.update_status":
      return "Changement de statut classification";
    default:
      return action;
  }
}

type Filters = {
  search: string;
  actor: string;
  entityType: string;
  action: string;
  dateFrom: string;
  dateTo: string;
};

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

export default function AdminLogsPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({
    search: "",
    actor: "",
    entityType: "",
    action: "",
    dateFrom: "",
    dateTo: "",
  });
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
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
        const params = new URLSearchParams();
        params.append("limit", "200");
        const res = await fetch(
          `${API_BASE_URL}/audit-logs?${params.toString()}`,
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        );
        if (!res.ok) {
          const text = await res.text();
          throw new Error(httpApiErrorMessage(res.status, text));
        }
        const json = await res.json();
        setLogs(Array.isArray(json) ? json : []);
        setCheckingSession(false);
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Erreur inconnue côté client";
        setError(msg);
        setCheckingSession(false);
      } finally {
        setLoading(false);
      }
    };
    fetchLogs();
  }, [router]);

  const filtered = useMemo(() => {
    return logs.filter((log) => {
      if (filters.search) {
        const s = filters.search.toLowerCase();
        const blob = `${log.actor_id} ${log.action} ${log.entity_type} ${log.entity_id}`.toLowerCase();
        if (!blob.includes(s)) {
          return false;
        }
      }
      if (filters.actor && log.actor_id !== filters.actor) {
        return false;
      }
      if (filters.entityType && log.entity_type !== filters.entityType) {
        return false;
      }
      if (filters.action && log.action !== filters.action) {
        return false;
      }
      if (filters.dateFrom) {
        const from = new Date(filters.dateFrom);
        const current = new Date(log.created_at);
        if (!Number.isNaN(from.getTime()) && !Number.isNaN(current.getTime())) {
          if (current < from) return false;
        }
      }
      if (filters.dateTo) {
        const to = new Date(filters.dateTo);
        const current = new Date(log.created_at);
        if (!Number.isNaN(to.getTime()) && !Number.isNaN(current.getTime())) {
          if (current > to) return false;
        }
      }
      return true;
    });
  }, [logs, filters]);

  if (checkingSession) {
    return <div className="min-h-screen bg-background" />;
  }

  const uniqueActors = Array.from(new Set(logs.map((l) => l.actor_id))).sort();
  const uniqueEntityTypes = Array.from(
    new Set(logs.map((l) => l.entity_type))
  ).sort();
  const uniqueActions = Array.from(new Set(logs.map((l) => l.action))).sort();

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
              Total logs chargés : {logs.length}
            </div>
            <div>Filtrés : {filtered.length}</div>
          </div>
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-primary mb-1">
            Journal d&apos;audit
          </h1>
          <p className="text-muted-foreground text-sm">
            Suivi des actions d&apos;administration (utilisateurs, classifications).
          </p>
        </div>
      </header>

      <section className="grid lg:grid-cols-3 gap-6">
        <div className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary">Filtres</h2>
          <div className="space-y-3 text-sm">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Recherche texte
              </label>
              <input
                type="text"
                value={filters.search}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, search: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                placeholder="actor, action, id..."
                title="Recherche dans acteur, action, type, id"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Acteur
              </label>
              <select
                value={filters.actor}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, actor: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                title="Filtrer par acteur"
              >
                <option value="">Tous</option>
                {uniqueActors.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Type d&apos;entité
              </label>
              <select
                value={filters.entityType}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, entityType: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                title="Filtrer par type d'entité"
              >
                <option value="">Tous</option>
                {uniqueEntityTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Action
              </label>
              <select
                value={filters.action}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, action: e.target.value }))
                }
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                title="Filtrer par action"
              >
                <option value="">Toutes</option>
                {uniqueActions.map((a) => (
                  <option key={a} value={a}>
                    {a}
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
              Actions d&apos;utilisateurs (création / mise à jour / suppression)
            </div>
            <div className="text-3xl font-bold text-primary leading-none">
              {
                filtered.filter((l) =>
                  l.action.startsWith("user.")
                ).length
              }
            </div>
          </div>
          <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
            <div className="text-xs text-muted-foreground">
              Actions sur classifications
            </div>
            <div className="text-3xl font-bold text-primary leading-none">
              {
                filtered.filter((l) =>
                  l.action.startsWith("classification.")
                ).length
              }
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-primary">
            Résultats ({filtered.length})
          </h2>
          {!loading && !error && filtered.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              <button
                type="button"
                onClick={async () => {
                  const {
                    data: { session },
                  } = await supabase.auth.getSession();
                  const accessToken = session?.access_token;
                  if (!accessToken) {
                    alert("Session expirée, veuillez vous reconnecter.");
                    return;
                  }

                  // Export admin-only : pas de window.open possible (pas de header).
                  const url = `${API_BASE_URL}/audit-logs.csv?limit=1000`;
                  const res = await fetch(url, {
                    headers: { Authorization: `Bearer ${accessToken}` },
                  });
                  if (!res.ok) {
                    const text = await res.text();
                    throw new Error(httpApiErrorMessage(res.status, text));
                  }
                  const blob = await res.blob();
                  const downloadUrl = window.URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = downloadUrl;
                  a.download = `audit_logs_tout_${new Date()
                    .toISOString()
                    .slice(0, 10)}.csv`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  window.URL.revokeObjectURL(downloadUrl);
                }}
                className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5"
              >
                Exporter tous les logs (CSV)
              </button>

              <button
                type="button"
                onClick={async () => {
                  const {
                    data: { session },
                  } = await supabase.auth.getSession();
                  const accessToken = session?.access_token;
                  if (!accessToken) {
                    alert("Session expirée, veuillez vous reconnecter.");
                    return;
                  }
                  const params = new URLSearchParams();
                  if (filters.actor) params.append("actor_id", filters.actor);
                  if (filters.entityType)
                    params.append("entity_type", filters.entityType);
                  if (filters.action) params.append("action", filters.action);
                  if (filters.search) params.append("q", filters.search);
                  if (filters.dateFrom)
                    params.append("date_from", filters.dateFrom);
                  if (filters.dateTo) params.append("date_to", filters.dateTo);
                  params.append("limit", "1000");

                  const url = `${API_BASE_URL}/audit-logs.csv?${params.toString()}`;

                  const res = await fetch(url, {
                    headers: {
                      Authorization: `Bearer ${accessToken}`,
                    },
                  });
                  if (!res.ok) {
                    const text = await res.text();
                    throw new Error(httpApiErrorMessage(res.status, text));
                  }
                  const blob = await res.blob();
                  const downloadUrl = window.URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = downloadUrl;
                  a.download = `audit_logs_filtre_${new Date()
                    .toISOString()
                    .slice(0, 10)}.csv`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  window.URL.revokeObjectURL(downloadUrl);
                }}
                className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5"
              >
                Exporter les logs filtrés (CSV)
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
          <div className="overflow-x-auto rounded-2xl border border-border bg-background">
            <table className="min-w-full text-xs">
              <thead className="bg-primary text-primary-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Date / heure</th>
                  <th className="px-3 py-2 text-left font-semibold">Acteur</th>
                  <th className="px-3 py-2 text-left font-semibold">Action</th>
                  <th className="px-3 py-2 text-left font-semibold">Type entité</th>
                  <th className="px-3 py-2 text-left font-semibold">Entité</th>
                  <th className="px-3 py-2 text-left font-semibold">Détails</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((log) => (
                  <tr key={log.id} className="odd:bg-muted/40 even:bg-background">
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDateTime(log.created_at)}
                    </td>
                    <td className="px-3 py-2">
                      <div>{log.actor_name ?? log.actor_id}</div>
                      {log.actor_name && (
                        <div className="text-[11px] font-mono text-muted-foreground">
                          {log.actor_id}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div>{formatActionLabel(log.action)}</div>
                      {log.action !== formatActionLabel(log.action) && (
                        <div className="text-[11px] text-muted-foreground">
                          {log.action}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">{log.entity_type}</td>
                    <td className="px-3 py-2">
                      <div>{log.entity_name ?? "-"}</div>
                      <div className="text-[11px] font-mono text-muted-foreground">
                        {log.entity_id}
                      </div>
                    </td>
                    <td className="px-3 py-2 max-w-[260px]">
                      {log.action === "user.update" &&
                        log.details &&
                        Object.keys(log.details).length > 0 && (
                          <div className="mb-1 text-[11px] text-emerald-700">
                            Champs modifiés:&nbsp;
                            {Object.keys(log.details).join(", ")}
                          </div>
                        )}
                      <pre className="whitespace-pre-wrap break-words text-[11px] text-muted-foreground">
                        {log.details
                          ? JSON.stringify(log.details, null, 2)
                          : "{}"}
                      </pre>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-3 py-4 text-center text-sm text-muted-foreground"
                    >
                      Aucun log ne correspond aux filtres.
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

