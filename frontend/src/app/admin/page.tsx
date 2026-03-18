'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
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
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editNom, setEditNom] = useState("");
  const [editIdentifiant, setEditIdentifiant] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const [userSearch, setUserSearch] = useState("");
  const [userStatusFilter, setUserStatusFilter] = useState<string>("Tous");
  const [userRoleFilter, setUserRoleFilter] = useState<string>("Tous");

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

        const accessToken = session.access_token;

        const [usersRes, historyRes] = await Promise.all([
          fetch(`${API_BASE_URL}/users`, {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }),
          fetch(`${API_BASE_URL}/history`, {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }),
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

  const filteredUsers = users.filter((u) => {
    if (userSearch) {
      const s = userSearch.toLowerCase();
      const haystack =
        `${u.nom_user ?? ""} ${u.identifiant_user ?? ""} ${u.email ?? ""}`.toLowerCase();
      if (!haystack.includes(s)) {
        return false;
      }
    }
    if (userStatusFilter !== "Tous" && u.statut !== userStatusFilter) {
      return false;
    }
    if (userRoleFilter === "Admins" && !u.is_admin) {
      return false;
    }
    if (userRoleFilter === "Non admins" && u.is_admin) {
      return false;
    }
    return true;
  });

  const totalUserPages = Math.max(
    1,
    Math.ceil(filteredUsers.length / userPageSize)
  );
  const currentUserPage = Math.min(userPage, totalUserPages);
  const handleCreateUser = async (e: FormEvent) => {
    e.preventDefault();
    if (!nomUser || !identifiantUser || !email) return;

    setCreating(true);
    setError(null);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token;

      const res = await fetch(`${API_BASE_URL}/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
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
      if (created.initial_password) {
        setActionMessage(
          `Utilisateur créé. Mot de passe initial : ${created.initial_password}`
        );
      } else {
        setActionMessage("Utilisateur créé avec succès.");
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erreur inconnue côté client";
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

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

  const handleToggleStatus = async (user: User) => {
    if (!user.user_id) return;
    try {
      setError(null);
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token;
      const currentUserId = session?.user?.id;
      if (!accessToken) {
        throw new Error("Session expirée, veuillez vous reconnecter.");
      }
      // Empêche un admin de se désactiver lui-même.
      if (String(user.user_id) === String(currentUserId)) {
        setActionMessage(
          "Vous ne pouvez pas désactiver votre propre compte administrateur."
        );
        return;
      }
      const newStatus = user.statut === "actif" ? "inactif" : "actif";
      const res = await fetch(`${API_BASE_URL}/users/${user.user_id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ statut: newStatus }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const updated = await res.json();
      setUsers((prev) =>
        prev.map((u) => (u.user_id === updated.user_id ? updated : u))
      );
      setActionMessage(
        newStatus === "actif"
          ? "Utilisateur activé."
          : "Utilisateur désactivé."
      );
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erreur lors du changement de statut.";
      setError(msg);
    }
  };

  const handleToggleAdmin = async (user: User) => {
    if (!user.user_id) return;
    try {
      setError(null);
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token;
      const currentUserId = session?.user?.id;
      if (!accessToken) {
        throw new Error("Session expirée, veuillez vous reconnecter.");
      }
      // Empêche un admin de retirer ses propres droits depuis l'interface.
      if (String(user.user_id) === String(currentUserId) && user.is_admin) {
        setActionMessage(
          "Vous ne pouvez pas retirer vos propres droits administrateur."
        );
        return;
      }
      const res = await fetch(`${API_BASE_URL}/users/${user.user_id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ is_admin: !user.is_admin }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const updated = await res.json();
      setUsers((prev) =>
        prev.map((u) => (u.user_id === updated.user_id ? updated : u))
      );
      setActionMessage(
        updated.is_admin
          ? "L'utilisateur est maintenant administrateur."
          : "Les droits administrateur ont été retirés."
      );
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erreur lors du changement de rôle.";
      setError(msg);
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (!user.user_id) return;
    const confirm = window.confirm(
      `Supprimer l'utilisateur ${user.nom_user ?? ""} ?`
    );
    if (!confirm) return;
    try {
      setError(null);
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token;
      const currentUserId = session?.user?.id;
      if (!accessToken) {
        throw new Error("Session expirée, veuillez vous reconnecter.");
      }
      // Empêche un admin de se supprimer lui-même.
      if (String(user.user_id) === String(currentUserId)) {
        setActionMessage(
          "Vous ne pouvez pas supprimer votre propre compte administrateur."
        );
        return;
      }
      const res = await fetch(`${API_BASE_URL}/users/${user.user_id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const updated = await res.json();
      setUsers((prev) => prev.filter((u) => u.user_id !== updated.user_id));
      setActionMessage("Utilisateur supprimé définitivement.");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erreur lors de la suppression.";
      setError(msg);
    }
  };

  const handleResetPassword = async (user: User) => {
    if (!user.user_id) return;
    try {
      setError(null);
      const accessToken = await withAdminToken();
      const res = await fetch(
        `${API_BASE_URL}/users/${user.user_id}/reset-password`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const data = await res.json();
      setActionMessage(
        `Nouveau mot de passe pour ${data.email} : ${data.new_password}`
      );
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Erreur lors de la réinitialisation du mot de passe.";
      setError(msg);
    }
  };

  const startEditUser = (user: User) => {
    if (!user.user_id) return;
    setEditingUserId(user.user_id);
    setEditNom(user.nom_user ?? "");
    setEditIdentifiant(user.identifiant_user ?? "");
    setEditEmail(user.email ?? "");
    setActionMessage(null);
  };

  const handleUpdateUser = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingUserId) return;
    try {
      setError(null);
      const accessToken = await withAdminToken();
      const res = await fetch(`${API_BASE_URL}/users/${editingUserId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          nom_user: editNom,
          identifiant_user: editIdentifiant,
          email: editEmail,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      const updated = await res.json();
      setUsers((prev) =>
        prev.map((u) => (u.user_id === updated.user_id ? updated : u))
      );
      setEditingUserId(null);
      setActionMessage("Utilisateur mis à jour avec succès.");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erreur lors de la mise à jour.";
      setError(msg);
    }
  };

  if (checkingSession) {
    return <div className="min-h-screen bg-background" />;
  }

  const paginatedUsers = filteredUsers.slice(
    (currentUserPage - 1) * userPageSize,
    (currentUserPage - 1) * userPageSize + userPageSize
  );

  return (
    <div className="space-y-8">
      <header className="rounded-3xl bg-card border border-border shadow-xl px-4 sm:px-8 py-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/" className="mosam-btn-admin min-h-[44px] inline-flex items-center touch-manipulation">
              Retour à la classification
            </Link>
            <Link href="/admin/historique" className="mosam-btn-admin min-h-[44px] inline-flex items-center touch-manipulation">
              Historique global
            </Link>
            <Link href="/admin/logs" className="mosam-btn-admin min-h-[44px] inline-flex items-center touch-manipulation">
              Journal d&apos;audit
            </Link>
          </div>
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-primary mb-1">
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
          {actionMessage && (
            <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-2xl px-3 py-2 mt-2">
              {actionMessage}
            </div>
          )}
        </div>
      </section>

      {editingUserId && (
        <section className="flex justify-center">
          <div className="w-full max-w-xl rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
            <h2 className="text-xl font-semibold text-primary">
              Modifier un utilisateur
            </h2>
            <form onSubmit={handleUpdateUser} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1">
                  Nom complet
                </label>
                <input
                  type="text"
                  value={editNom}
                  onChange={(e) => setEditNom(e.target.value)}
                  className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1">
                  Identifiant
                </label>
                <input
                  type="text"
                  value={editIdentifiant}
                  onChange={(e) => setEditIdentifiant(e.target.value)}
                  className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-6 py-2 text-sm font-semibold shadow-md hover:bg-primary/90"
                >
                  Enregistrer
                </button>
                <button
                  type="button"
                  onClick={() => setEditingUserId(null)}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-background px-6 py-2 text-sm font-semibold"
                >
                  Annuler
                </button>
              </div>
            </form>
          </div>
        </section>
      )}

      <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-primary flex items-center gap-2">
            Utilisateurs
          </h2>
          {users.length > 0 && (
            <button
              type="button"
              onClick={() => {
                const params = new URLSearchParams();
                if (userSearch.trim()) {
                  params.append("search", userSearch.trim());
                }
                if (userStatusFilter !== "Tous") {
                  params.append("statut", userStatusFilter);
                }
                if (userRoleFilter !== "Tous") {
                  params.append(
                    "is_admin",
                    userRoleFilter === "Admins" ? "true" : "false"
                  );
                }
                const url =
                  params.toString().length > 0
                    ? `${API_BASE_URL}/users.csv?${params.toString()}`
                    : `${API_BASE_URL}/users.csv`;
                window.open(url, "_blank", "noopener,noreferrer");
              }}
              className="inline-flex items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/5"
            >
              Exporter les utilisateurs (CSV)
            </button>
          )}
        </div>
        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <div>
            <label className="block text-xs font-semibold text-muted-foreground mb-1">
              Recherche utilisateur
            </label>
            <input
              type="text"
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
              placeholder="Nom, identifiant ou email"
              title="Filtrer par texte (nom, identifiant, email)"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-muted-foreground mb-1">
              Statut
            </label>
            <select
              value={userStatusFilter}
              onChange={(e) => setUserStatusFilter(e.target.value)}
              className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
              title="Filtrer par statut utilisateur"
            >
              <option value="Tous">Tous</option>
              <option value="actif">actif</option>
              <option value="inactif">inactif</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-muted-foreground mb-1">
              Rôle
            </label>
            <select
              value={userRoleFilter}
              onChange={(e) => setUserRoleFilter(e.target.value)}
              className="w-full rounded-2xl border border-border bg-background px-3 py-2 text-sm"
              title="Filtrer par rôle utilisateur"
            >
              <option value="Tous">Tous</option>
              <option value="Admins">Admins</option>
              <option value="Non admins">Non admins</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto rounded-2xl border border-border bg-background text-sm">
          <table className="min-w-full">
            <thead className="bg-primary text-primary-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">
                  ID utilisateur
                </th>
                <th className="px-3 py-2 text-left font-semibold">Nom</th>
                <th className="px-3 py-2 text-left font-semibold">
                  Identifiant
                </th>
                <th className="px-3 py-2 text-left font-semibold">Email</th>
                <th className="px-3 py-2 text-left font-semibold">Statut</th>
                <th className="px-3 py-2 text-left font-semibold">Admin</th>
                <th className="px-3 py-2 text-left font-semibold">Actions</th>
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
                  <td className="px-3 py-2">{u.statut ?? "N/A"}</td>
                  <td className="px-3 py-2">
                    {u.is_admin ? "Oui" : "Non"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleToggleStatus(u)}
                        className="px-3 py-1 rounded-full border border-border bg-background text-xs"
                      >
                        {u.statut === "actif" ? "Désactiver" : "Activer"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleAdmin(u)}
                        className="px-3 py-1 rounded-full border border-border bg-background text-xs"
                      >
                        {u.is_admin ? "Retirer admin" : "Rendre admin"}
                      </button>
                      <button
                        type="button"
                        onClick={() => startEditUser(u)}
                        className="px-3 py-1 rounded-full border border-border bg-background text-xs"
                      >
                        Modifier
                      </button>
                      <button
                        type="button"
                        onClick={() => handleResetPassword(u)}
                        className="px-3 py-1 rounded-full border border-border bg-background text-xs"
                      >
                        Reset MDP
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteUser(u)}
                        className="px-3 py-1 rounded-full border border-red-300 text-xs text-red-700 bg-red-50"
                      >
                        Supprimer
                      </button>
                    </div>
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

