'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { log } from "../lib/logger";
import { ConfirmLogoutModal } from "../components/ConfirmLogoutModal";

type ClassificationItem = {
  description?: string;
  quantity?: number;
  quantity_source?: string;
  quantity_raw?: string;
  quantity_confidence?: number;
  hs_code?: string;
  section?: string;
  section_name?: string;
  chapter?: string;
  chapter_name?: string;
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
  /** Réponse court-circuitée (ex. question sur Mosam) : pas de lignes à valider. */
  assistant_info?: boolean;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function tryParseStructuredPayload(rawText: string): ApiPayload | null {
  const stripCodeFences = (s: string) => {
    const t = s.trim();
    // ```json ... ``` or ``` ... ```
    const m = t.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
    return (m?.[1] ?? t).trim();
  };

  // On tente plusieurs passes car on a déjà vu des cas où `raw`
  // est un JSON *string* qui contient lui-même du JSON (parfois avec ```json).
  let current: unknown = rawText.trim();

  for (let i = 0; i < 3; i++) {
    if (typeof current === "string") {
      const candidate = stripCodeFences(current);

      // Si c'est une chaîne JSON encodée (commence par "{" mais entourée de quotes),
      // JSON.parse la gère déjà, donc on tente un parse direct.
      try {
        current = JSON.parse(candidate);
        continue;
      } catch {
        // Si ce n'est pas du JSON valide, on abandonne.
        return null;
      }
    }

    if (current && typeof current === "object") {
      const obj = current as ApiPayload;
      // Vérifie la forme minimale attendue
      if (Array.isArray(obj.classifications) || typeof obj.narrative === "string") {
        return obj;
      }
      return null;
    }

    return null;
  }

  return null;
}

/** Retire les phrases légales en fin de narrative déjà couvertes par la 1re ligne du copier-coller. */
function trimRedundantDouaneDisclaimerFromNarrative(n: string): string {
  let t = n.trim();
  const patterns: RegExp[] = [
    /\s+[.;]?\s*[àa]\s+valider\s+par\s+l[''\u2019]?autorit[ée]e?\s+douani[èe]re\.?\s*$/iu,
    /\s+proposition\s+indicative\s*,?\s*[àa]\s+faire\s+valider\s+par\s+l[''\u2019]?autorit[ée]e?\s+douani[èe]re\.?\s*$/iu,
    /\s+doit\s+être\s+validée?\s+par\s+l[''\u2019]?autorit[ée]e?\s+douani[èe]re\.?\s*$/iu,
    /\s+doit\s+etre\s+validee?\s+par\s+l[''\u2019]?autorit[ée]e?\s+douani[èe]re\.?\s*$/iu,
  ];
  let prev = "";
  while (prev !== t) {
    prev = t;
    for (const re of patterns) {
      t = t.replace(re, "").trim();
    }
  }
  return t;
}

/**
 * Corrige les formes sans accent fréquentes dans les réponses API (copier-coller uniquement).
 * Ne touche pas aux codes numériques ni aux sigles d'unité courants (PIECE, KG…).
 */
function polishFrenchForClipboard(s: string): string {
  if (!s) return s;
  let t = s;
  const fixes: Array<[RegExp, string]> = [
    [/\bNon renseigne\b/gi, "Non renseigné"],
    [/\bmateriels\b/gi, "matériels"],
    [/\bmateriel\b/gi, "matériel"],
    [/\bmecaniques\b/gi, "mécaniques"],
    [/\bmecanique\b/gi, "mécanique"],
    [/\bautorite\b/gi, "autorité"],
    [/\bdouaniere\b/gi, "douanière"],
    [/\bdouanier\b/gi, "douanier"],
    [/\bbasee\b/gi, "basée"],
    [/\bbasees\b/gi, "basées"],
    [/\bvalidee\b/gi, "validée"],
    [/\bvalidees\b/gi, "validées"],
    [/\betre\b/gi, "être"],
    [/\belectrique\b/gi, "électrique"],
    [/\belectronique\b/gi, "électronique"],
    [/\bregne\b/gi, "règne"],
    [/\brefrigeres\b/gi, "réfrigérés"],
    [/\brefrigere\b/gi, "réfrigéré"],
    [/\bcaracteristiques\b/gi, "caractéristiques"],
    [/\blegumes\b/gi, "légumes"],
    [/\blegume\b/gi, "légume"],
    [/\bimportees\b/gi, "importées"],
    [/\bimportee\b/gi, "importée"],
    [/\bimportes\b/gi, "importés"],
    [/\bimporte\b/gi, "importé"],
  ];
  for (const [re, rep] of fixes) {
    t = t.replace(re, rep);
  }
  return t;
}

/**
 * Texte prêt à coller : avertissement légal, synthèse éventuelle, puis tableau TSV
 * (en-tête + une ligne par classification) pour Excel / traitement de texte, sans bruit UI.
 */
function formatPayloadForClipboard(
  payload: ApiPayload,
  getItemQuantity: (item: ClassificationItem, index: number) => number
): string {
  const lines: string[] = [];
  lines.push(
    "Proposition indicative, à faire valider par l'autorité douanière."
  );
  lines.push("");

  const isAssistant = Boolean(payload.assistant_info);
  const narrativeClean = payload.narrative?.trim()
    ? trimRedundantDouaneDisclaimerFromNarrative(payload.narrative.trim())
    : "";

  if (isAssistant && narrativeClean) {
    lines.push(polishFrenchForClipboard(narrativeClean));
    return lines.join("\n");
  }

  if (narrativeClean) {
    lines.push(polishFrenchForClipboard(narrativeClean));
    lines.push("");
  }

  const rows = payload.classifications ?? [];
  if (rows.length === 0) {
    lines.push("(Aucune ligne de classification.)");
    return lines.join("\n");
  }

  const header = [
    "Marchandise",
    "Qté",
    "Code TEC/SH",
    "Section",
    "Intitulé section",
    "Chapitre",
    "Intitulé chapitre",
    "D.D.",
    "R.S.",
    "Autres taxes",
    "U.S.",
    "Confiance %",
    "Origine",
    "Valeur",
  ].join("\t");
  lines.push(header);

  const sanitizeCell = (s: string) =>
    polishFrenchForClipboard(
      s.replace(/\r?\n/g, " ").replace(/\t/g, " ").trim()
    );

  for (let i = 0; i < rows.length; i++) {
    const item = rows[i];
    const qty = getItemQuantity(item, i);
    const cells = [
      sanitizeCell(item.description ?? ""),
      String(qty),
      sanitizeCell(item.hs_code ?? ""),
      sanitizeCell(item.section ?? ""),
      sanitizeCell(item.section_name ?? ""),
      sanitizeCell(item.chapter ?? ""),
      sanitizeCell(item.chapter_name ?? ""),
      sanitizeCell(item.dd_rate ?? ""),
      sanitizeCell(item.rs_rate ?? ""),
      sanitizeCell(item.other_taxes ?? ""),
      sanitizeCell(item.us_unit ?? ""),
      typeof item.confidence === "number" ? String(item.confidence) : "",
      sanitizeCell(item.origin ?? ""),
      sanitizeCell(item.value ?? ""),
    ];
    lines.push(cells.join("\t"));
  }

  return lines.join("\n");
}

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [payload, setPayload] = useState<ApiPayload | null>(null);
  const [parseFailureDetail, setParseFailureDetail] = useState<string | null>(null);
  // Texte réellement envoyé au moteur de classification.
  // Utilisé ensuite pour `POST /classifications/validate` (cache).
  const [classifyQueryForCache, setClassifyQueryForCache] = useState<string | null>(null);
  const [fileItemsCount, setFileItemsCount] = useState<number | null>(null);
  // Pour éviter de valider deux fois la même ligne.
  const [validatedKeys, setValidatedKeys] = useState<Record<string, true>>({});
  // Fallback manuel: quantité corrigée par ligne (clé de ligne -> qty).
  const [quantityOverrides, setQuantityOverrides] = useState<Record<string, number>>({});
  const [userId, setUserId] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [validatingAll, setValidatingAll] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<"idle" | "ok" | "error">("idle");
  const copyFeedbackTimeoutRef = useRef<number | null>(null);

  // Optionnel : regroupe les validations dans un "dossier entreprise"
  // (ex: AMKsecurity) pour les retrouver dans l'historique.
  const [dossierName, setDossierName] = useState<string>("");
  const [dossiersOptions, setDossiersOptions] = useState<string[]>([]);

  useEffect(() => {
    const checkSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        // Si pas de session, on remplace l'URL par /login et
        // on garde checkingSession à true pour ne jamais afficher la page.
        router.replace("/login");
        return;
      }
      setUserId(session.user.id ?? null);
      setAccessToken(session.access_token ?? null);
      setCheckingSession(false);
    };
    void checkSession();
  }, [router]);

  useEffect(() => {
    const loadDossiers = async () => {
      if (!accessToken) return;
      try {
        const res = await fetch(`${API_BASE_URL}/dossiers`, {
          headers: {
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data)) {
          setDossiersOptions(
            data.map((d: any) => d?.name).filter((x: any) => typeof x === "string" && x.trim())
          );
        }
      } catch {
        /* ignore */
      }
    };
    void loadDossiers();
  }, [accessToken]);

  useEffect(() => {
    // Debug: confirmer que React rend bien les classifications après setPayload
    if (!payload) {
      log.debug("[frontend render] payload=null");
      return;
    }
    log.debug(
      "[frontend render] payload hasNarrative=",
      !!payload.narrative,
      "classifications_len=",
      payload.classifications?.length ?? 0
    );
  }, [payload]);

  const classifyNow = async () => {
    if (!query.trim()) return;

    log.debug("[frontend submit] start query_preview=", query.slice(0, 60));
    setClassifyQueryForCache(query.trim());
    setFileItemsCount(null);
    setValidatedKeys({});
    setQuantityOverrides({});
    setLoading(true);
    setError(null);
    setValidationMessage(null);
    setRaw(null);
    setPayload(null);
    setParseFailureDetail(null);

    try {
      const response = await fetch(`${API_BASE_URL}/classify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query, user_id: userId }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Erreur HTTP ${response.status}`);
      }

      const data = await response.json();
      const rawText: string =
        typeof data.raw === "string"
          ? data.raw
          : JSON.stringify(data.raw ?? "");
      setRaw(rawText);

      let parsed = tryParseStructuredPayload(rawText);
      if (!parsed && rawText.trim().startsWith('"')) {
        try {
          const once = JSON.parse(rawText.trim()) as unknown;
          if (typeof once === "string")
            parsed = tryParseStructuredPayload(once);
        } catch {
          /* ignore */
        }
      }
      if (!parsed) {
        try {
          const maybeJson = JSON.parse(rawText);
          const obj =
            typeof maybeJson === "string" ? JSON.parse(maybeJson) : maybeJson;
          if (obj && typeof obj === "object" && !Array.isArray(obj)) {
            const hasNarrative = typeof (obj as any).narrative === "string";
            const hasClassifications = Array.isArray(
              (obj as any).classifications
            );
            const missing = [
              !hasNarrative ? "narrative" : null,
              !hasClassifications ? "classifications" : null,
            ]
              .filter(Boolean)
              .join(" + ");
            setParseFailureDetail(
              missing
                ? `Schéma inattendu : champ(s) manquant(s) = ${missing}.`
                : "Schéma inattendu : réponse non interprétable par l'UI."
            );
          } else {
            setParseFailureDetail(
              "Réponse JSON reçue mais structure non compatible avec l'UI."
            );
          }
        } catch {
          setParseFailureDetail("Réponse JSON invalide côté client.");
        }
      }
      setPayload(parsed);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur inconnue côté client";
      setError(message);
      setParseFailureDetail(null);
    } finally {
      setLoading(false);
    }
  };

  const classifyFromFile = async (file: File) => {
    if (!file) return;

    log.debug("[frontend submit] start file name=", file.name);
    setFileItemsCount(null);
    setValidatedKeys({});
    setQuantityOverrides({});
    setLoading(true);
    setError(null);
    setValidationMessage(null);
    setRaw(null);
    setPayload(null);
    setParseFailureDetail(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/classify/file`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Erreur HTTP ${response.status}`);
      }

      const data = (await response.json()) as {
        raw?: string;
        effective_query?: string;
        items_count?: number;
      };

      const rawText: string =
        typeof data.raw === "string" ? data.raw : JSON.stringify(data.raw ?? "");
      const effectiveQuery =
        typeof data.effective_query === "string" ? data.effective_query : query.trim();
      setClassifyQueryForCache(effectiveQuery);
      if (typeof data.items_count === "number") setFileItemsCount(data.items_count);
      setRaw(rawText);

      let parsed = tryParseStructuredPayload(rawText);
      if (!parsed && rawText.trim().startsWith('"')) {
        try {
          const once = JSON.parse(rawText.trim()) as unknown;
          if (typeof once === "string")
            parsed = tryParseStructuredPayload(once);
        } catch {
          /* ignore */
        }
      }
      if (!parsed) {
        try {
          const maybeJson = JSON.parse(rawText);
          const obj =
            typeof maybeJson === "string" ? JSON.parse(maybeJson) : maybeJson;
          if (obj && typeof obj === "object" && !Array.isArray(obj)) {
            const hasNarrative = typeof (obj as any).narrative === "string";
            const hasClassifications = Array.isArray(
              (obj as any).classifications
            );
            const missing = [
              !hasNarrative ? "narrative" : null,
              !hasClassifications ? "classifications" : null,
            ]
              .filter(Boolean)
              .join(" + ");
            setParseFailureDetail(
              missing
                ? `Schéma inattendu : champ(s) manquant(s) = ${missing}.`
                : "Schéma inattendu : réponse non interprétable par l'UI."
            );
          } else {
            setParseFailureDetail(
              "Réponse JSON reçue mais structure non compatible avec l'UI."
            );
          }
        } catch {
          setParseFailureDetail("Réponse JSON invalide côté client.");
        }
      }
      setPayload(parsed);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur inconnue côté client";
      setError(message);
      setParseFailureDetail(null);
    } finally {
      setLoading(false);
    }
  };

  const retryClassification = async () => {
    if (selectedFile) {
      await classifyFromFile(selectedFile);
      return;
    }
    await classifyNow();
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim() && !selectedFile) return;
    if (selectedFile) {
      await classifyFromFile(selectedFile);
    } else {
      await classifyNow();
    }
  };

  const classifications = payload?.classifications ?? [];
  const isAssistantInfo = Boolean(payload?.assistant_info);
  const getRowKey = (item: ClassificationItem, index: number) =>
    `${index}||${item.hs_code ?? ""}||${item.description ?? ""}`;

  const getItemQuantity = (item: ClassificationItem, index: number) => {
    const rowKey = getRowKey(item, index);
    const overridden = quantityOverrides[rowKey];
    if (typeof overridden === "number" && overridden > 0) return Math.floor(overridden);
    return typeof item.quantity === "number" && item.quantity > 0 ? Math.floor(item.quantity) : 1;
  };

  const getQuantitySourceLabel = (source?: string) => {
    switch (source) {
      case "mixte":
        return "Mixte";
      case "repeat":
        return "Répétitions";
      case "range_upper":
        return "Plage (borne haute)";
      case "word_number":
        return "Nombre en lettres";
      case "lot":
        return "Format de lot";
      case "explicit":
      default:
        return "Valeur explicite";
    }
  };

  const totalClassifiedQuantity = classifications.reduce((sum, item, index) => {
    const qty = getItemQuantity(item, index);
    return sum + qty;
  }, 0);

  if (checkingSession) {
    return (
      <div className="min-h-screen bg-background" />
    );
  }

  const handleValidate = async (item: ClassificationItem, index: number) => {
    if (!userId) {
      setError("Utilisateur non authentifié, impossible de valider.");
      return;
    }

    const rowKey = getRowKey(item, index);
    const quantityToSend = getItemQuantity(item, index);
    try {
      setValidationMessage(null);
      const res = await fetch(`${API_BASE_URL}/classifications/validate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
          description: item.description ?? "",
          section: item.section_name
            ? `${item.section ?? "N/A"} - ${item.section_name}`
            : item.section ?? "N/A",
          chapter: item.chapter_name
            ? `${item.chapter ?? "N/A"} - ${item.chapter_name}`
            : item.chapter ?? "N/A",
          hs_code: item.hs_code ?? "",
          confidence: item.confidence ?? null,
          quantity: quantityToSend,
          dd_rate: item.dd_rate ?? null,
          rs_rate: item.rs_rate ?? null,
          other_taxes: item.other_taxes ?? null,
          us_unit: item.us_unit ?? null,
          origin: item.origin ?? null,
          value: item.value ?? null,
          user_id: userId,
          dossier_name: dossierName.trim() || undefined,
          query: classifyQueryForCache || undefined,
          raw_response: raw || undefined,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Erreur HTTP ${res.status}`);
      }
      setValidationMessage("Classification validée et enregistrée.");
      setValidatedKeys((prev) => ({ ...prev, [rowKey]: true }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur lors de la validation";
      setError(message);
    }
  };

  const handleValidateAll = async () => {
    if (validatingAll) return;
    if (!payload?.classifications?.length) return;
    if (!userId) {
      setError("Utilisateur non authentifié, impossible de valider.");
      return;
    }

    setError(null);
    setValidationMessage(null);
    setValidatingAll(true);

    try {
      // Travail en local pour eviter un double clic / double boucle
      // avant que React n'ait synchronisé `validatedKeys`.
      const validatedSet = new Set(Object.keys(validatedKeys));

      const keysToMark: string[] = [];
      const itemsToValidate: any[] = [];

      for (let i = 0; i < payload.classifications.length; i++) {
        const item = payload.classifications[i];
        const rowKey = getRowKey(item, i);
        if (validatedSet.has(rowKey)) continue;

        const quantityToSend = getItemQuantity(item, i);

        const section = item.section_name
          ? `${item.section ?? "N/A"} - ${item.section_name}`
          : item.section ?? "N/A";
        const chapter = item.chapter_name
          ? `${item.chapter ?? "N/A"} - ${item.chapter_name}`
          : item.chapter ?? "N/A";

        itemsToValidate.push({
          description: item.description ?? "",
          section,
          chapter,
          hs_code: item.hs_code ?? "",
          confidence: item.confidence ?? null,
          quantity: quantityToSend,
          dd_rate: item.dd_rate ?? null,
          rs_rate: item.rs_rate ?? null,
          other_taxes: item.other_taxes ?? null,
          us_unit: item.us_unit ?? null,
          origin: item.origin ?? null,
          value: item.value ?? null,
          user_id: userId,
        });

        keysToMark.push(rowKey);
      }

      if (!itemsToValidate.length) {
        setValidationMessage("Aucune classification à valider.");
        return;
      }

      const chunkSize = 50;
      const nextValidated: Record<string, true> = { ...validatedKeys };
      let validatedTotal = 0;
      let errorsTotal = 0;
      let total = keysToMark.length;

      for (let start = 0; start < itemsToValidate.length; start += chunkSize) {
        const chunkItems = itemsToValidate.slice(start, start + chunkSize);
        const chunkKeys = keysToMark.slice(start, start + chunkSize);
        const isFirstChunk = start === 0;

        const res = await fetch(`${API_BASE_URL}/classifications/validate/bulk`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({
            items: chunkItems,
            query: isFirstChunk ? classifyQueryForCache || undefined : undefined,
            raw_response: isFirstChunk ? raw || undefined : undefined,
            dossier_name: dossierName.trim() || undefined,
          }),
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `Erreur HTTP ${res.status}`);
        }

        const data = await res.json();
        validatedTotal += data?.validated ?? chunkItems.length;
        errorsTotal += data?.errors_len ?? 0;

        // Si certains items échouent, on ne les marque pas comme validés côté UI.
        const errs: any[] = Array.isArray(data?.errors) ? data.errors : [];
        const errorIdxs = new Set<number>(
          errs
            .map((e: any) => e?.index)
            .filter((x: any) => typeof x === "number" && x >= 0) as number[]
        );
        for (let j = 0; j < chunkKeys.length; j++) {
          if (!errorIdxs.has(j)) nextValidated[chunkKeys[j]] = true;
        }
      }

      setValidatedKeys(nextValidated);

      if (errorsTotal > 0) {
        setValidationMessage(
          `Validation terminée : ${validatedTotal}/${total} enregistrées, ${errorsTotal} erreurs.`
        );
      } else {
        setValidationMessage(`Tout validé : ${validatedTotal}/${total} enregistrées.`);
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur lors de la validation";
      setError(message);
    } finally {
      setValidatingAll(false);
    }
  };

  const handleCloseResults = () => {
    setPayload(null);
    setRaw(null);
    setParseFailureDetail(null);
    setFileItemsCount(null);
    setValidationMessage(null);
    setValidatedKeys({});
    setQuantityOverrides({});
    setCopyFeedback("idle");
    if (copyFeedbackTimeoutRef.current) {
      window.clearTimeout(copyFeedbackTimeoutRef.current);
      copyFeedbackTimeoutRef.current = null;
    }
  };

  const handleCopyResults = async () => {
    if (!payload) return;
    if (copyFeedbackTimeoutRef.current) {
      window.clearTimeout(copyFeedbackTimeoutRef.current);
      copyFeedbackTimeoutRef.current = null;
    }
    const text = formatPayloadForClipboard(payload, getItemQuantity);
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback("ok");
      copyFeedbackTimeoutRef.current = window.setTimeout(() => {
        setCopyFeedback("idle");
        copyFeedbackTimeoutRef.current = null;
      }, 2200);
    } catch {
      setCopyFeedback("error");
      copyFeedbackTimeoutRef.current = window.setTimeout(() => {
        setCopyFeedback("idle");
        copyFeedbackTimeoutRef.current = null;
      }, 3200);
    }
  };

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
          <button
            type="button"
            onClick={() => setShowLogoutModal(true)}
            aria-label="Se déconnecter"
            className="mosam-btn-logout"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
          <div className="mosam-header-actions-primary">
            <div className="mosam-hero-meta">
              Direction Générale des Douanes
            </div>
            <div className="mosam-hero-stats">
              21 sections · 97 chapitres · 5000+ codes
            </div>
          </div>
          <div className="mosam-header-actions-buttons">
            <Link href="/historique" className="mosam-btn-secondary">
              Historique
            </Link>
            <Link href="/admin" className="mosam-btn-admin">
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
            <div className="space-y-1">
              <label
                htmlFor="uploadFile"
                className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer touch-manipulation"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                Ou envoyer un fichier (txt, pdf)
              </label>
              <input
                id="uploadFile"
                type="file"
                accept=".txt,.pdf,text/plain,application/pdf"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setSelectedFile(f);
                }}
                className="mosam-file-input-hidden"
              />
              {selectedFile && (
                <div className="text-xs text-muted-foreground">
                  {selectedFile.name}{" "}
                  ({Math.max(1, Math.round(selectedFile.size / 1024))} Ko)
                  <button
                    type="button"
                    className="ml-2 text-xs text-primary underline"
                    onClick={() => setSelectedFile(null)}
                  >
                    retirer
                  </button>
                </div>
              )}
            </div>
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
          {validationMessage && (
            <div className="mt-3 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {validationMessage}
            </div>
          )}

        </div>
      </section>

      {!loading && raw && !payload && (
        <section className="rounded-3xl bg-card border border-amber-200 bg-amber-50/50 border-border shadow-xl p-6 space-y-2">
          <h2 className="text-lg font-semibold text-amber-800">
            Réponse reçue mais format inattendu
          </h2>
          <p className="text-sm text-amber-700">
            La réponse du serveur est valide en JSON, mais le schéma ne correspond pas à ce que l&apos;interface attend.
            {parseFailureDetail && (
              <span className="block mt-1">{parseFailureDetail}</span>
            )}
            <span className="block mt-1">
              Réessayez ; si le problème persiste, contactez un administrateur.
            </span>
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="button"
              onClick={() => void retryClassification()}
              className="mosam-btn-primary min-h-[44px] touch-manipulation"
            >
              Réessayer
            </button>
          </div>
          <pre className="text-xs overflow-auto max-h-48 p-3 rounded-xl bg-white border border-amber-200 text-left">
            {raw.slice(0, 2000)}
            {raw.length > 2000 ? "…" : ""}
          </pre>
        </section>
      )}

      {payload && (
        <section className="rounded-3xl bg-card border border-border shadow-xl p-6 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h2 className="text-xl font-semibold text-primary">
              {isAssistantInfo ? "Mosam" : "Résultat structuré"}
            </h2>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => void handleCopyResults()}
                aria-label="Copier les résultats (texte et tableau pour tableur)"
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-full border border-primary px-3 py-2 text-primary hover:bg-primary/10 touch-manipulation"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              </button>
              {copyFeedback === "ok" && (
                <span className="text-xs font-medium text-emerald-700 whitespace-nowrap" aria-hidden="true">
                  Copié
                </span>
              )}
              {copyFeedback === "error" && (
                <span className="text-xs font-medium text-red-700 max-w-[10rem] leading-tight" aria-hidden="true">
                  Copie impossible
                </span>
              )}
              <button
                type="button"
                onClick={handleCloseResults}
                aria-label="Fermer"
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-full border border-primary px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10 touch-manipulation"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>
          {!isAssistantInfo && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
              Proposition indicative, à faire valider par l&apos;autorité douanière.
            </p>
          )}
          {fileItemsCount !== null && (
            <p className="text-xs text-foreground bg-amber-50/40 border border-amber-200 rounded-xl px-3 py-2">
              {fileItemsCount} produit(s) détecté(s) dans le fichier.
            </p>
          )}
          {!isAssistantInfo && (
            <>
              <p className="text-xs text-foreground bg-amber-50/40 border border-amber-200 rounded-xl px-3 py-2">
                {classifications.length} classification(s) reçue(s) (dans l&apos;UI).
              </p>
              <p className="text-xs text-foreground bg-amber-50/40 border border-amber-200 rounded-xl px-3 py-2">
                {totalClassifiedQuantity} unité(s) classifiée(s) (quantité cumulée).
              </p>
            </>
          )}
          {payload.narrative &&
            (isAssistantInfo ? (
              <div className="rounded-2xl border border-sky-200 bg-sky-50/90 px-4 py-4 text-sm text-sky-950 leading-relaxed space-y-3">
                {payload.narrative
                  .split(/\n\s*\n+/)
                  .map((p) => p.trim())
                  .filter(Boolean)
                  .map((para, i) => (
                    <p key={i} className="m-0">
                      {para}
                    </p>
                  ))}
              </div>
            ) : (
              <p className="text-sm text-foreground leading-relaxed">{payload.narrative}</p>
            ))}

          {classifications.length === 0 && !isAssistantInfo && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Réponse reçue, mais aucune classification détectée.
              <div className="mt-3 flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  onClick={() => void retryClassification()}
                  className="mosam-btn-primary min-h-[44px] touch-manipulation"
                >
                  Réessayer
                </button>
              </div>
            </div>
          )}

          {classifications.length > 0 && (
            <>
              {/* Table partout (mobile + desktop) */}
              <div className="overflow-x-auto rounded-2xl border border-border bg-background">
                <table className="min-w-full text-sm">
                  <thead className="bg-primary text-primary-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold">
                        Marchandise
                      </th>
                      <th className="px-3 py-2 text-left font-semibold">
                        Qté
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
                      <th className="px-3 py-2 text-left font-semibold">
                        Action
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {classifications.map((item, index) => (
                      <tr
                        key={getRowKey(item, index)}
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
                          <input
                            type="number"
                            min={1}
                            step={1}
                            inputMode="numeric"
                            value={getItemQuantity(item, index)}
                            onChange={(e) => {
                              const next = Number(e.target.value);
                              if (!Number.isFinite(next)) return;
                              const safe = Math.max(1, Math.floor(next));
                              const rowKey = getRowKey(item, index);
                              setQuantityOverrides((prev) => ({ ...prev, [rowKey]: safe }));
                            }}
                            className="w-20 rounded-lg border border-border bg-background px-2 py-1 text-sm"
                            aria-label={`Quantité pour ${item.description || "Marchandise"}`}
                          />
                          <div className="mt-2 text-xs text-muted-foreground leading-snug">
                            <div className="font-semibold text-foreground/80">Detail calcul quantite</div>
                            <div>
                              Qte retenue:{" "}
                              <span className="font-semibold">{getItemQuantity(item, index)}</span>
                            </div>
                            <div>
                              Source: {getQuantitySourceLabel(item.quantity_source)}
                              {item.quantity_raw ? ` (brut: ${item.quantity_raw})` : ""}
                            </div>
                            <div>
                              Confiance extraction:{" "}
                              {typeof item.quantity_confidence === "number"
                                ? `${item.quantity_confidence}%`
                                : "N/R"}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2 align-top">
                          <div className="font-mono">
                            {item.hs_code || "Non renseigné"}
                          </div>
                        </td>
                        <td className="px-3 py-2 align-top text-sm">
                          <div>{item.section || "N/A"}</div>
                          {item.section_name && (
                            <div className="text-xs text-muted-foreground">
                              {item.section_name}
                            </div>
                          )}
                          <div className="mt-1 text-xs">
                            <span className="font-semibold">
                              Chapitre {item.chapter || "N/A"}
                            </span>
                            {item.chapter_name && (
                              <span className="text-muted-foreground">
                                {" "}
                                – {item.chapter_name}
                              </span>
                            )}
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
                        <td className="px-3 py-2 align-top">
                          <button
                            type="button"
                            onClick={() => handleValidate(item, index)}
                            className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-full border border-primary px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10 touch-manipulation"
                            disabled={!!validatedKeys[getRowKey(item, index)]}
                          >
                            {validatedKeys[getRowKey(item, index)] ? "Validé" : "Valider"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="text-sm font-semibold text-muted-foreground whitespace-nowrap">
                      Dossier entreprise (optionnel)
                    </div>
                    <input
                      type="text"
                      value={dossierName}
                      onChange={(e) => setDossierName(e.target.value)}
                      placeholder="Ex: AMKsecurity"
                      list="dossiers-list"
                      className="min-w-[260px] rounded-lg border border-border bg-background px-3 py-2 text-sm"
                      aria-label="Nom du dossier entreprise"
                    />
                    <datalist id="dossiers-list">
                      {dossiersOptions.map((n) => (
                        <option key={n} value={n} />
                      ))}
                    </datalist>
                  </div>

                  <button
                    type="button"
                    onClick={handleValidateAll}
                    disabled={validatingAll || !payload?.classifications?.length}
                    className="inline-flex items-center justify-center min-h-[44px] rounded-full border border-primary px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/10 touch-manipulation disabled:opacity-50"
                  >
                    {validatingAll ? "Validation en cours..." : "Tout valider"}
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      )}

      <ConfirmLogoutModal
        open={showLogoutModal}
        onCancel={() => setShowLogoutModal(false)}
        onConfirm={async () => {
          setShowLogoutModal(false);
          await fetch("/api/auth/session", { method: "DELETE" });
          await supabase.auth.signOut();
          router.push("/login");
        }}
      />
    </div>
  );
}

