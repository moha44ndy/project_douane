export type SelectOption = {
  value: string;
  label: string;
};

/** Pays d'origine courants (CEDEAO + partenaires commerciaux fréquents). */
export const ORIGIN_COUNTRY_OPTIONS: SelectOption[] = [
  { value: "Afrique du Sud", label: "Afrique du Sud" },
  { value: "Algérie", label: "Algérie" },
  { value: "Allemagne", label: "Allemagne" },
  { value: "Belgique", label: "Belgique" },
  { value: "Bénin", label: "Bénin" },
  { value: "Brésil", label: "Brésil" },
  { value: "Burkina Faso", label: "Burkina Faso" },
  { value: "Cameroun", label: "Cameroun" },
  { value: "Canada", label: "Canada" },
  { value: "Chine", label: "Chine" },
  { value: "Côte d'Ivoire", label: "Côte d'Ivoire" },
  { value: "Émirats arabes unis", label: "Émirats arabes unis" },
  { value: "Espagne", label: "Espagne" },
  { value: "États-Unis", label: "États-Unis" },
  { value: "France", label: "France" },
  { value: "Ghana", label: "Ghana" },
  { value: "Guinée", label: "Guinée" },
  { value: "Guinée-Bissau", label: "Guinée-Bissau" },
  { value: "Inde", label: "Inde" },
  { value: "Indonésie", label: "Indonésie" },
  { value: "Italie", label: "Italie" },
  { value: "Japon", label: "Japon" },
  { value: "Corée du Sud", label: "Corée du Sud" },
  { value: "Mali", label: "Mali" },
  { value: "Maroc", label: "Maroc" },
  { value: "Mauritanie", label: "Mauritanie" },
  { value: "Niger", label: "Niger" },
  { value: "Nigéria", label: "Nigéria" },
  { value: "Pays-Bas", label: "Pays-Bas" },
  { value: "Pologne", label: "Pologne" },
  { value: "Portugal", label: "Portugal" },
  { value: "Royaume-Uni", label: "Royaume-Uni" },
  { value: "Sénégal", label: "Sénégal" },
  { value: "Suisse", label: "Suisse" },
  { value: "Togo", label: "Togo" },
  { value: "Tunisie", label: "Tunisie" },
  { value: "Turquie", label: "Turquie" },
  { value: "Viêt Nam", label: "Viêt Nam" },
];

export const ORIGIN_COUNTRY_SUGGESTIONS = ORIGIN_COUNTRY_OPTIONS.map((o) => o.value);

/** Devises courantes en douane / CEDEAO. */
export const CURRENCY_OPTIONS: SelectOption[] = [
  { value: "XOF", label: "Franc CFA BCEAO (XOF)" },
  { value: "XAF", label: "Franc CFA BEAC (XAF)" },
  { value: "EUR", label: "Euro (EUR)" },
  { value: "USD", label: "Dollar US (USD)" },
  { value: "GBP", label: "Livre sterling (GBP)" },
  { value: "CHF", label: "Franc suisse (CHF)" },
  { value: "CNY", label: "Yuan (CNY)" },
  { value: "JPY", label: "Yen (JPY)" },
  { value: "CAD", label: "Dollar canadien (CAD)" },
  { value: "MAD", label: "Dirham marocain (MAD)" },
  { value: "NGN", label: "Naira (NGN)" },
  { value: "GHS", label: "Cedi (GHS)" },
];

export const CURRENCY_SUGGESTIONS = CURRENCY_OPTIONS.map((o) => o.value);

/** Unités de quantité courantes en douane / TEC (U.S.). */
export const UNIT_OPTIONS: SelectOption[] = [
  { value: "PCE", label: "Pièce (PCE)" },
  { value: "U", label: "Unité (U)" },
  { value: "KG", label: "Kilogramme (KG)" },
  { value: "G", label: "Gramme (G)" },
  { value: "T", label: "Tonne (T)" },
  { value: "L", label: "Litre (L)" },
  { value: "ML", label: "Millilitre (ML)" },
  { value: "M", label: "Mètre (M)" },
  { value: "M2", label: "Mètre carré (M2)" },
  { value: "M3", label: "Mètre cube (M3)" },
  { value: "PAIR", label: "Paire (PAIR)" },
  { value: "DOZ", label: "Douzaine (DOZ)" },
  { value: "SET", label: "Ensemble (SET)" },
  { value: "CARTON", label: "Carton" },
  { value: "COLIS", label: "Colis" },
];

export const UNIT_SUGGESTIONS = UNIT_OPTIONS.map((o) => o.value);
