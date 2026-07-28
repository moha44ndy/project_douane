"use client";

import {
  CURRENCY_SUGGESTIONS,
  ORIGIN_COUNTRY_SUGGESTIONS,
  UNIT_SUGGESTIONS,
} from "../lib/merchandiseOptions";
import {
  MerchandiseRow,
  createEmptyMerchandiseRow,
} from "../lib/merchandiseQuery";

type MerchandiseTableFormProps = {
  rows: MerchandiseRow[];
  onChange: (rows: MerchandiseRow[]) => void;
  disabled?: boolean;
};

type TextColumn = {
  kind: "text";
  key: keyof MerchandiseRow;
  label: string;
  placeholder: string;
  className?: string;
  inputMode?: "text" | "numeric" | "decimal";
};

type ComboboxColumn = {
  kind: "combobox";
  key: "origin" | "currency" | "unit";
  label: string;
  placeholder: string;
  className?: string;
  listId: string;
  suggestions: string[];
  uppercase?: boolean;
};

type ColumnDef = TextColumn | ComboboxColumn;

const COLUMNS: ColumnDef[] = [
  {
    kind: "text",
    key: "designation",
    className: "min-w-[220px]",
    label: "Désignation",
    placeholder: "ex. Sac de voyage en cuir",
  },
  {
    kind: "text",
    key: "material",
    className: "min-w-[180px]",
    label: "Matière / composition",
    placeholder: "ex. 100 % cuir",
  },
  {
    kind: "text",
    key: "usage",
    className: "min-w-[190px]",
    label: "Usage",
    placeholder: "ex. transport effets personnels",
  },
  {
    kind: "text",
    key: "characteristics",
    className: "min-w-[280px]",
    label: "Caractéristiques",
    placeholder: "ex. livré monté, neuf",
  },
  {
    kind: "text",
    key: "quantity",
    label: "Qté",
    placeholder: "1",
    className: "w-16",
    inputMode: "numeric",
  },
  {
    kind: "combobox",
    key: "unit",
    label: "Unité",
    placeholder: "Choisir ou saisir (PCE, KG…)",
    className: "w-36",
    listId: "mosam-unit-suggestions",
    suggestions: UNIT_SUGGESTIONS,
    uppercase: true,
  },
  {
    kind: "combobox",
    key: "origin",
    label: "Pays d'origine",
    placeholder: "Choisir ou saisir un pays",
    className: "w-36",
    listId: "mosam-origin-suggestions",
    suggestions: ORIGIN_COUNTRY_SUGGESTIONS,
  },
  {
    kind: "text",
    key: "value",
    label: "Valeur",
    placeholder: "ex. 1500",
    className: "w-24",
    inputMode: "decimal",
  },
  {
    kind: "combobox",
    key: "currency",
    label: "Devise",
    placeholder: "Choisir ou saisir (EUR, XOF…)",
    className: "w-36",
    listId: "mosam-currency-suggestions",
    suggestions: CURRENCY_SUGGESTIONS,
    uppercase: true,
  },
];

function sanitizeQuantityInput(value: string): string {
  return value.replace(/[^\d]/g, "");
}

function sanitizeValueInput(value: string): string {
  const normalized = value.replace(/,/g, ".");
  const digitsAndDots = normalized.replace(/[^\d.]/g, "");
  const firstDot = digitsAndDots.indexOf(".");
  if (firstDot === -1) return digitsAndDots;
  return (
    digitsAndDots.slice(0, firstDot + 1) +
    digitsAndDots.slice(firstDot + 1).replace(/\./g, "")
  );
}

function sanitizeTextInput(
  key: keyof MerchandiseRow,
  value: string
): string {
  if (key === "quantity") return sanitizeQuantityInput(value);
  if (key === "value") return sanitizeValueInput(value);
  return value;
}

export function MerchandiseTableForm({
  rows,
  onChange,
  disabled = false,
}: MerchandiseTableFormProps) {
  const updateRow = (id: string, patch: Partial<MerchandiseRow>) => {
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  const addRow = () => {
    onChange([...rows, createEmptyMerchandiseRow()]);
  };

  const removeRow = (id: string) => {
    if (rows.length <= 1) {
      onChange([createEmptyMerchandiseRow()]);
      return;
    }
    onChange(rows.filter((row) => row.id !== id));
  };

  const comboboxLists = COLUMNS.filter(
    (col): col is ComboboxColumn => col.kind === "combobox"
  );

  return (
    <div className="space-y-3">
      {comboboxLists.map((col) => (
        <datalist key={col.listId} id={col.listId}>
          {col.suggestions.map((value) => (
            <option key={value} value={value} />
          ))}
        </datalist>
      ))}
      <div className="mosam-merchandise-table-wrap overflow-x-auto rounded-xl border border-border">
        <table className="mosam-merchandise-table w-full min-w-[1100px] text-sm">
          <thead>
            <tr className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              {COLUMNS.map((col) => (
                <th
                  key={col.label}
                  className={`px-3 py-2.5 font-semibold whitespace-nowrap ${col.className ?? ""}`}
                >
                  {col.label}
                </th>
              ))}
              <th className="px-3 py-2.5 font-semibold w-12" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id} className="border-t border-border/80 align-top">
                {COLUMNS.map((col) => (
                  <td key={col.label} className={`px-2 py-2 ${col.className ?? ""}`}>
                    {col.kind === "combobox" ? (
                      <input
                        type="text"
                        list={col.listId}
                        value={row[col.key]}
                        disabled={disabled}
                        onChange={(e) => {
                          const value = col.uppercase
                            ? e.target.value.toUpperCase()
                            : e.target.value;
                          updateRow(row.id, { [col.key]: value });
                        }}
                        placeholder={col.placeholder}
                        className={`mosam-table-input ${col.uppercase ? "uppercase" : ""}`}
                        aria-label={`${col.label} ligne ${index + 1}`}
                      />
                    ) : (
                      <input
                        type="text"
                        inputMode={col.inputMode}
                        value={row[col.key]}
                        disabled={disabled}
                        onChange={(e) =>
                          updateRow(row.id, {
                            [col.key]: sanitizeTextInput(col.key, e.target.value),
                          })
                        }
                        placeholder={
                          col.key === "designation" && index > 0
                            ? "Nom ou type de produit"
                            : col.placeholder
                        }
                        className={`mosam-table-input ${col.inputMode === "numeric" ? "text-center" : ""}`}
                        aria-label={`${col.label} ligne ${index + 1}`}
                      />
                    )}
                  </td>
                ))}
                <td className="px-2 py-2 text-center">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => removeRow(row.id)}
                    className="mosam-table-remove-btn"
                    aria-label={`Supprimer la ligne ${index + 1}`}
                    title="Supprimer la ligne"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={addRow}
        className="text-sm font-medium text-primary hover:underline touch-manipulation"
      >
        + Ajouter une marchandise
      </button>
    </div>
  );
}
