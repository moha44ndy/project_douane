"use client";

import { ClassificationProgressStep } from "../lib/classificationStream";

type ClassificationProgressPanelProps = {
  steps: ClassificationProgressStep[];
};

function StepIcon({ status }: { status: ClassificationProgressStep["status"] }) {
  if (status === "done") {
    return (
      <span className="mosam-progress-icon mosam-progress-icon-done" aria-hidden="true">
        ✓
      </span>
    );
  }
  if (status === "active") {
    return (
      <span
        className="mosam-progress-icon mosam-progress-icon-active inline-block h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin"
        aria-hidden="true"
      />
    );
  }
  if (status === "skipped") {
    return (
      <span className="mosam-progress-icon mosam-progress-icon-skipped" aria-hidden="true">
        –
      </span>
    );
  }
  return <span className="mosam-progress-icon mosam-progress-icon-pending" aria-hidden="true" />;
}

export function ClassificationProgressPanel({ steps }: ClassificationProgressPanelProps) {
  const activeStep = steps.find((step) => step.status === "active");
  const doneCount = steps.filter((step) => step.status === "done").length;

  return (
    <div
      className="mosam-progress-panel rounded-2xl border border-border bg-muted/20 p-4 space-y-3"
      role="status"
      aria-live="polite"
      aria-label="Progression de la classification"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-primary">Analyse Mosam en cours</p>
        <p className="text-xs text-muted-foreground">
          {doneCount}/{steps.length}
        </p>
      </div>
      {activeStep && (
        <p className="text-xs text-muted-foreground">{activeStep.label}…</p>
      )}
      <ol className="space-y-2">
        {steps.map((step) => (
          <li
            key={step.id}
            className={`mosam-progress-step mosam-progress-step-${step.status} flex items-center gap-3 text-sm`}
          >
            <StepIcon status={step.status} />
            <span>{step.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
