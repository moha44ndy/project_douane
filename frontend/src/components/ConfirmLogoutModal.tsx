'use client';

type Props = {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmLogoutModal({ open, onConfirm, onCancel }: Props) {
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
          <h2 className="text-lg font-semibold text-primary">
            Confirmer la déconnexion
          </h2>
          <p className="text-sm text-muted-foreground">
            Vous allez être déconnecté de Mosam. Voulez-vous continuer ?
          </p>
        </div>
        <div className="flex justify-center gap-3 text-sm w-full">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-full border border-border bg-background px-4 py-1.5"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 rounded-full bg-primary text-primary-foreground px-4 py-1.5 font-semibold shadow-md"
          >
            Se déconnecter
          </button>
        </div>
      </div>
    </div>
  );
}

