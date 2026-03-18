'use client';

import { useEffect, useId, useRef } from "react";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
};

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = "Annuler",
  onConfirm,
  onCancel,
  danger = false,
}: Props) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const cancelBtnRef = useRef<HTMLButtonElement | null>(null);

  const titleId = useId();
  const messageId = useId();
  const focusableSelector = FOCUSABLE_SELECTOR;

  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Focus sur "Annuler" par défaut (comportement sûr).
    const t = window.setTimeout(() => cancelBtnRef.current?.focus(), 0);

    const getFocusable = () => {
      const root = dialogRef.current;
      if (!root) return [];
      return Array.from(root.querySelectorAll<HTMLElement>(focusableSelector)).filter(
        (el) =>
          !el.hasAttribute("disabled") &&
          el.tabIndex !== -1 &&
          el.offsetParent !== null
      );
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
        return;
      }

      if (e.key !== "Tab") return;

      const focusable = getFocusable();
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (!active) return;

      if (e.shiftKey) {
        if (active === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [onCancel, focusableSelector]);

  return (
    <div
      hidden={!open}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        backgroundColor: "rgba(0,0,0,0.4)",
      }}
      role="dialog"
      aria-modal="true"
      aria-hidden={!open}
      aria-labelledby={titleId}
      aria-describedby={messageId}
      onMouseDown={(e) => {
        if (!open) return;
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="rounded-3xl bg-card border border-border shadow-xl text-center space-y-4"
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          minWidth: 320,
          maxWidth: 360,
          padding: 24,
        }}
      >
        <div className="space-y-1">
          <h2 id={titleId} className="text-lg font-semibold text-primary">
            {title}
          </h2>
          <p id={messageId} className="text-sm text-muted-foreground">
            {message}
          </p>
        </div>
        <div className="flex justify-center gap-3 text-sm w-full">
          <button
            type="button"
            onClick={onCancel}
            ref={cancelBtnRef}
            className="flex-1 rounded-full border border-border bg-background px-4 py-1.5"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={
              danger
                ? "flex-1 rounded-full bg-amber-600 text-white px-4 py-1.5 font-semibold shadow-md hover:bg-amber-700"
                : "flex-1 rounded-full bg-primary text-primary-foreground px-4 py-1.5 font-semibold shadow-md"
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
