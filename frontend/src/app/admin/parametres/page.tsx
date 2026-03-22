'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "../../../lib/apiBase";
import { httpApiErrorMessage } from "../../../lib/httpApiErrorMessage";
import { supabase } from "../../../lib/supabaseClient";

type NormalizationAliasRow = {
  id: string;
  alias: string;
  canonical: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

async function getAccessToken(): Promise<string | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export default function AdminParametresPage() {
  const router = useRouter();
  const [rows, setRows] = useState<NormalizationAliasRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  const [aliasInput, setAliasInput] = useState("");
  const [canonicalInput, setCanonicalInput] = useState("");
  const [newIsActive, setNewIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadAliases = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      const res = await fetch(`${API_BASE_URL}/admin/normalization-aliases`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setError(
          "Cette page est réservée aux administrateurs. Demandez le rôle admin ou utilisez le tableau Supabase (normalization_aliases)."
        );
        setRows([]);
        return;
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(httpApiErrorMessage(res.status, text));
      }
      const json = await res.json();
      setRows(Array.isArray(json) ? json : []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur lors du chargement des alias."
      );
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const init = async () => {
      const token = await getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      setCheckingSession(false);
      await loadAliases();
    };
    void init();
  }, [router, loadAliases]);

  useEffect(() => {
    if (checkingSession) return;
    const id = window.location.hash.replace(/^#/, "");
    if (!id) return;
    const t = window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 80);
    return () => window.clearTimeout(t);
  }, [checkingSession]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    const alias = aliasInput.trim();
    const canonical = canonicalInput.trim();
    if (!alias || !canonical) return;

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      const res = await fetch(`${API_BASE_URL}/admin/normalization-aliases`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          alias,
          canonical,
          is_active: newIsActive,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(httpApiErrorMessage(res.status, text));
      }
      setAliasInput("");
      setCanonicalInput("");
      setNewIsActive(true);
      setMessage("Alias enregistré.");
      await loadAliases();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Impossible d'enregistrer l'alias."
      );
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (row: NormalizationAliasRow) => {
    setError(null);
    setMessage(null);
    try {
      const token = await getAccessToken();
      if (!token) return;
      const res = await fetch(
        `${API_BASE_URL}/admin/normalization-aliases/${encodeURIComponent(row.id)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ is_active: !row.is_active }),
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(httpApiErrorMessage(res.status, text));
      }
      setMessage(row.is_active ? "Alias désactivé." : "Alias réactivé.");
      await loadAliases();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Impossible de mettre à jour l'alias."
      );
    }
  };

  const removeAlias = async (row: NormalizationAliasRow) => {
    if (
      !window.confirm(
        `Supprimer définitivement l'alias « ${row.alias} » → « ${row.canonical} » ?`
      )
    ) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const token = await getAccessToken();
      if (!token) return;
      const res = await fetch(
        `${API_BASE_URL}/admin/normalization-aliases/${encodeURIComponent(row.id)}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(httpApiErrorMessage(res.status, text));
      }
      setMessage("Alias supprimé.");
      await loadAliases();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Impossible de supprimer l'alias."
      );
    }
  };

  if (checkingSession) {
    return <div className="min-h-screen bg-background" />;
  }

  return (
    <div className="space-y-8">
      <header className="rounded-3xl bg-card border border-border shadow-xl px-4 sm:px-8 py-6 space-y-4">
        <nav className="mosam-admin-nav" aria-label="Navigation administration">
          <Link
            href="/admin"
            className="mosam-btn-admin mosam-admin-nav-link touch-manipulation"
          >
            Retour au panneau admin
          </Link>
          <Link
            href="/"
            className="mosam-btn-admin mosam-admin-nav-link touch-manipulation"
          >
            Classification
          </Link>
        </nav>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-primary mb-1">
            Réglages
          </h1>
          <p className="text-muted-foreground text-sm max-w-3xl">
            Paramètres avancés de la classification et de l&apos;application.
            Réservé aux comptes administrateur. Vous pouvez ajouter d&apos;autres
            blocs ici au fil du temps.
          </p>
        </div>
      </header>

      {message && (
        <div className="rounded-2xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-primary">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive whitespace-pre-wrap">
          {error}
        </div>
      )}

      <section
        id="normalisation-alias"
        className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-2"
        aria-labelledby="normalisation-alias-heading"
      >
        <h2
          id="normalisation-alias-heading"
          className="text-xl font-semibold text-primary"
        >
          Alias de normalisation
        </h2>
        <p className="text-sm text-muted-foreground max-w-3xl pb-4">
          Chaque ligne relie une <strong>variante</strong> (mot saisi) à une{" "}
          <strong>forme canonique</strong> pour regrouper les libellés lors de la
          classification.
        </p>

        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-primary">Ajouter un alias</h3>
          <form
            onSubmit={handleCreate}
            className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end"
          >
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Variante (alias)
              </label>
              <input
                type="text"
                value={aliasInput}
                onChange={(e) => setAliasInput(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                placeholder="ex. smartphone"
                autoComplete="off"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Canonique
              </label>
              <input
                type="text"
                value={canonicalInput}
                onChange={(e) => setCanonicalInput(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                placeholder="ex. telephone"
                autoComplete="off"
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input
                id="new_is_active"
                type="checkbox"
                checked={newIsActive}
                onChange={(e) => setNewIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-border"
              />
              <label htmlFor="new_is_active" className="text-sm">
                Actif
              </label>
            </div>
            <div>
              <button
                type="submit"
                disabled={
                  saving || !aliasInput.trim() || !canonicalInput.trim()
                }
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-6 py-2 text-sm font-semibold shadow-md hover:bg-primary/90 disabled:opacity-70 disabled:cursor-not-allowed transition-colors touch-manipulation sm:w-auto"
                aria-label={
                  saving
                    ? "Enregistrement en cours"
                    : "Ajouter l'alias"
                }
              >
                {saving ? "Enregistrement…" : "Ajouter"}
              </button>
            </div>
          </form>
        </div>

        <div className="space-y-4 border-t border-border pt-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="text-lg font-medium text-primary">Liste des alias</h3>
            <button
              type="button"
              onClick={() => void loadAliases()}
              disabled={loading}
              title="Rafraîchir la liste"
              aria-label="Rafraîchir la liste des alias"
              className="inline-flex w-fit shrink-0 items-center justify-center self-start rounded-full border border-border bg-background px-2.5 py-1 text-[11px] font-semibold leading-none hover:bg-muted/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors touch-manipulation sm:self-auto"
            >
              {loading ? "…" : "MAJ"}
            </button>
          </div>

          {rows.length === 0 && !loading && !error && (
            <p className="text-sm text-muted-foreground">
              Aucun alias en base. Les abréviations par défaut du serveur (gsm,
              pc, etc.) s&apos;appliquent toujours ; cette table ajoute vos
              règles personnalisées.
            </p>
          )}

          {rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-semibold">Alias</th>
                    <th className="py-2 pr-4 font-semibold">Canonique</th>
                    <th className="py-2 pr-4 font-semibold">Actif</th>
                    <th className="py-2 font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b border-border/60">
                      <td className="py-2 pr-4 font-medium">{row.alias}</td>
                      <td className="py-2 pr-4">{row.canonical}</td>
                      <td className="py-2 pr-4">
                        {row.is_active ? "Oui" : "Non"}
                      </td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            onClick={() => void toggleActive(row)}
                            title={
                              row.is_active
                                ? "Désactiver cet alias"
                                : "Réactiver cet alias"
                            }
                            aria-label={
                              row.is_active
                                ? "Désactiver l'alias"
                                : "Réactiver l'alias"
                            }
                            className="px-2 py-0.5 rounded-full border border-border bg-background text-[11px] leading-tight font-medium touch-manipulation hover:bg-muted/50"
                          >
                            {row.is_active ? "Dés." : "Ré."}
                          </button>
                          <button
                            type="button"
                            onClick={() => void removeAlias(row)}
                            title="Supprimer cet alias"
                            aria-label="Supprimer l'alias"
                            className="px-2 py-0.5 rounded-full border border-red-300 text-[11px] leading-tight font-medium text-red-700 bg-red-50 touch-manipulation hover:bg-red-100"
                          >
                            ×
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section
        className="rounded-3xl border border-dashed border-border bg-muted/15 px-6 py-5"
        aria-label="Emplacement pour de futurs réglages"
      >
        <h2 className="text-lg font-semibold text-muted-foreground">
          Autres réglages
        </h2>
        <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
          Cette zone pourra accueillir d&apos;autres options (cache, seuils,
          libellés, intégrations, etc.) sans multiplier les pages dans le menu.
        </p>
      </section>
    </div>
  );
}
