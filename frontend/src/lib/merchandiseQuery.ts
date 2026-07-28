export type MerchandiseRow = {
  id: string;
  designation: string;
  material: string;
  usage: string;
  characteristics: string;
  quantity: string;
  unit: string;
  origin: string;
  value: string;
  currency: string;
};

export function createEmptyMerchandiseRow(): MerchandiseRow {
  return {
    id: crypto.randomUUID(),
    designation: "",
    material: "",
    usage: "",
    characteristics: "",
    quantity: "",
    unit: "",
    origin: "",
    value: "",
    currency: "",
  };
}

function looksLikeManufacturerReference(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  const hasAlpha = /[A-Za-z]/.test(text);
  const hasDigit = /\d/.test(text);
  if (!hasAlpha || !hasDigit) return false;
  const specialCount = (text.match(/[-_./]/g) ?? []).length;
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 1) return true;
  if (specialCount >= 1 && words.length <= 4) return true;
  return /\b[A-Z]{1,5}[-_]?\d{2,}/i.test(text);
}

function formatQuantity(row: MerchandiseRow): string {
  const qty = row.quantity.trim();
  const unit = row.unit.trim();
  if (qty && unit) return `${qty} ${unit}`;
  return qty || unit;
}

function rowToStructuredDossier(row: MerchandiseRow): string {
  const lines: string[] = [`Produit : ${row.designation.trim()}`];
  if (looksLikeManufacturerReference(row.designation)) {
    lines.push(`Reference fabricant : ${row.designation.trim()}`);
  }
  if (row.material.trim()) {
    lines.push(`Composition :\n- ${row.material.trim()}`);
  }
  if (row.usage.trim()) {
    lines.push(`Usage :\n${row.usage.trim()}`);
  }
  if (row.characteristics.trim()) {
    lines.push(`Caractéristiques :\n- ${row.characteristics.trim()}`);
  }
  const quantity = formatQuantity(row);
  if (quantity) {
    lines.push(`Quantité :\n${quantity}`);
  }
  if (row.origin.trim()) {
    lines.push(`Origine :\n${row.origin.trim()}`);
  }
  if (row.value.trim()) {
    const valueLine = row.currency.trim()
      ? `${row.value.trim()} ${row.currency.trim()}`
      : row.value.trim();
    lines.push(`Valeur :\n${valueLine}`);
  } else if (row.currency.trim()) {
    lines.push(`Devise :\n${row.currency.trim()}`);
  }
  return lines.join("\n");
}

function rowToListLine(row: MerchandiseRow): string {
  const parts = [row.designation.trim()];
  if (looksLikeManufacturerReference(row.designation)) {
    parts.push(`reference fabricant ${row.designation.trim()}`);
  }
  if (row.material.trim()) parts.push(`matière ${row.material.trim()}`);
  if (row.usage.trim()) parts.push(`usage ${row.usage.trim()}`);
  if (row.characteristics.trim()) parts.push(row.characteristics.trim());
  const quantity = formatQuantity(row);
  if (quantity) parts.push(`qté ${quantity}`);
  if (row.origin.trim()) parts.push(`origine ${row.origin.trim()}`);
  if (row.value.trim()) {
    parts.push(
      row.currency.trim()
        ? `valeur ${row.value.trim()} ${row.currency.trim()}`
        : `valeur ${row.value.trim()}`
    );
  }
  return parts.join(", ");
}

/** Construit le texte envoyé à l'API à partir du tableau de saisie. */
export function buildMerchandiseQuery(rows: MerchandiseRow[]): string {
  const active = rows.filter((row) => row.designation.trim());
  if (active.length === 0) return "";

  if (active.length === 1) {
    const row = active[0];
    const hasDetail =
      row.material.trim() ||
      row.usage.trim() ||
      row.characteristics.trim() ||
      row.quantity.trim() ||
      row.unit.trim() ||
      row.origin.trim() ||
      row.value.trim() ||
      row.currency.trim();
    if (hasDetail) {
      return rowToStructuredDossier(row);
    }
    return row.designation.trim();
  }

  return active.map((row) => `- ${rowToListLine(row)}`).join("\n");
}
