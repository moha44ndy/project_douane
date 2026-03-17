'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { supabase } from "../../lib/supabaseClient";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type User = {
  user_id?: number;
  nom_user?: string;
  identifiant_user?: string;
  email?: string;
  statut?: string;
  is_admin?: boolean;
};

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [historyCount, setHistoryCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [nomUser, setNomUser] = useState("");
  const [identifiantUser, setIdentifiantUser] = useState("");
  const [email, setEmail] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [creating, setCreating] = useState(false);

  const [userPage, setUserPage] = useState(1);
  const userPageSize = 25;
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          // On ne montre jamais la page admin si l'utilisateur n'est pas connecté.
          // On remplace l'URL par /login pour éviter tout flash.
          router.replace("/login");
          return;
        }

        const [usersRes, historyRes] = await Promise.all([
          fetch(`${API_BASE_URL}/users`),
          fetch(`${API_BASE_URL}/history`),
        ]);

        if (!usersRes.ok) {
          throw new Error(
            (await usersRes.text()) || `Erreur HTTP users ${usersRes.status}`
          );
        }
        if (!historyRes.ok) {
          throw new Error(
            (await historyRes.text()) ||
              `Erreur HTTP history ${historyRes.status}`
          );
        }

        const usersJson = await usersRes.json();
        const historyJson = await historyRes.json();
        setUsers(Array.isArray(usersJson) ? usersJson : []);
        setHistoryCount(Array.isArray(historyJson) ? historyJson.length : 0);
        // Session valide + données chargées : on peut rendre la page
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

    fetchAll();
  }, [router]);

  const totalUsers = users.length;
  const activeUsers = users.filter((u) => u.statut === "actif").length;
  const adminUsers = users.filter((u) => u.is_admin).length;

  const totalUserPages = Math.max(
    1,
    Math.ceil(totalUsers / userPageSize)
  );
  const currentUserPage = Math.min(userPage, totalUserPages);
  const handleCreateUser = async (e: FormEvent) => {
    e.preventDefault();
    if (!nomUser || !identifiantUser || !email) return;

    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nom_user: nomUser,
          identifiant_user: identifiantUser,
          email,
          is_admin: isAdmin,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const created = await res.json();
      setUsers((prev) => [...prev, created]);
      setNomUser("");
      setIdentifiantUser("");
      setEmail("");
      setIsAdmin(false);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erreur inconnue côté client";
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  if (checkingSession) {
    return (
      <div className="min-h-screen bg-background" />
    );
  }

  const paginatedUsers = useMemo(
    () =>
      users.slice(
        (currentUserPage - 1) * userPageSize,
        (currentUserPage - 1) * userPageSize + userPageSize
      ),
    [users, currentUserPage, userPageSize]
  );

  return (
    <div className="space-y-8">
      <header className="rounded-3xl bg-card border border-border shadow-xl px-8 py-6 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Link href="/" className="mosam-btn-admin">
              Retour à la classification
            </Link>
            <button
              type="button"
              onClick={async () => {
                await supabase.auth.signOut();
                router.push("/login");
              }}
              className="mosam-btn-secondary"
            >
              Se déconnecter
            </button>
          </div>
        </div>
        <div>
          <h1 className="text-3xl font-bold text-primary mb-1">
            Panneau administrateur
          </h1>
          <p className="text-muted-foreground text-sm">
            Gestion des utilisateurs et suivi des statistiques globales.
          </p>
        </div>
      </header>

      <section className="grid lg:grid-cols-4 gap-4">
        <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
          <div className="text-xs text-muted-foreground">
            Utilisateurs totaux
          </div>
          <div className="text-3xl font-bold text-primary leading-none">
            {totalUsers}
          </div>
        </div>
        <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
          <div className="text-xs text-muted-foreground">
            Utilisateurs actifs
          </div>
          <div className="text-3xl font-bold text-primary leading-none">
            {activeUsers}
          </div>
        </div>
        <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
          <div className="text-xs text-muted-foreground">
            Administrateurs
          </div>
          <div className="text-3xl font-bold text-primary leading-none">
            {adminUsers}
          </div>
        </div>
        <div className="rounded-3xl bg-card border border-border shadow-xl p-5 flex items-end justify-between">
          <div className="text-xs text-muted-foreground">
            Classifications enregistrées
          </div>
          <div className="text-3xl font-bold text-primary leading-none">
            {historyCount}
          </div>
        </div>
      </section>

      <section className="flex justify-center">
        <div className="w-full max-w-xl rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <h2 className="text-xl font-semibold text-primary">
            Inscription d&apos;un nouvel utilisateur
          </h2>
          <form onSubmit={handleCreateUser} className="space-y-3 text-sm">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Nom complet *
              </label>
              <input
                type="text"
                value={nomUser}
                onChange={(e) => setNomUser(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                placeholder="Ex: Jean Dupont"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Identifiant *
              </label>
              <input
                type="text"
                value={identifiantUser}
                onChange={(e) => setIdentifiantUser(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                placeholder="Ex: jean.dupont"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Email *
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                placeholder="jean.dupont@douane.ci"
              />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <input
                id="is_admin"
                type="checkbox"
                checked={isAdmin}
                onChange={(e) => setIsAdmin(e.target.checked)}
              />
              <label htmlFor="is_admin">Accorder les privilèges d&apos;admin</label>
            </div>
            <button
              type="submit"
              disabled={creating}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-6 py-2 text-sm font-semibold shadow-md hover:bg-primary/90 disabled:opacity-70 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? "Création..." : "Créer l'utilisateur"}
            </button>
          </form>
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-2xl px-3 py-2 mt-2">
              {error}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
        <h2 className="text-xl font-semibold text-primary flex items-center gap-2">
          Utilisateurs
        </h2>
        <div className="overflow-x-auto rounded-2xl border border-border bg-background text-sm">
          <table className="min-w-full">
            <thead className="bg-primary text-primary-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">ID</th>
                <th className="px-3 py-2 text-left font-semibold">Nom</th>
                <th className="px-3 py-2 text-left font-semibold">
                  Identifiant
                </th>
                <th className="px-3 py-2 text-left font-semibold">Email</th>
                <th className="px-3 py-2 text-left font-semibold">Admin</th>
              </tr>
            </thead>
            <tbody>
              {paginatedUsers.map((u) => (
                <tr key={u.user_id ?? u.identifiant_user}>
                  <td className="px-3 py-2">{u.user_id ?? "N/A"}</td>
                  <td className="px-3 py-2">{u.nom_user ?? "N/A"}</td>
                  <td className="px-3 py-2">
                    {u.identifiant_user ?? "N/A"}
                  </td>
                  <td className="px-3 py-2">{u.email ?? "N/A"}</td>
                  <td className="px-3 py-2">
                    {u.is_admin ? "Oui" : "Non"}
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-3 py-4 text-center text-sm text-muted-foreground"
                  >
                    Aucun utilisateur enregistré pour le moment.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {users.length > 0 && (
          <div className="flex items-center justify-between pt-4 text-xs text-muted-foreground">
            <div>
              Page {currentUserPage} / {totalUserPages} •{" "}
              {paginatedUsers.length} utilisateurs affichés
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={currentUserPage === 1}
                onClick={() => setUserPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded-full border border-border bg-background disabled:opacity-50"
              >
                Précédent
              </button>
              <button
                type="button"
                disabled={currentUserPage === totalUserPages}
                onClick={() =>
                  setUserPage((p) => Math.min(totalUserPages, p + 1))
                }
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

