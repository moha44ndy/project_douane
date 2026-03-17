'use client';

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
  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        backgroundColor: "rgba(0,0,0,0.4)",
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
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
          <h2 className="text-lg font-semibold text-primary">{title}</h2>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <div className="flex justify-center gap-3 text-sm w-full">
          <button
            type="button"
            onClick={onCancel}
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
