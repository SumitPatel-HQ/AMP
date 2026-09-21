import type { MissionSessionError } from "../state/types";

export function ErrorBanner({
  error,
  onDismiss,
}: {
  error: MissionSessionError | null;
  onDismiss: () => void;
}) {
  if (error === null) {
    return null;
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded border border-red-900 bg-red-950/60 px-4 py-2 text-sm text-red-200">
      <span>
        <span className="font-mono text-red-400">{error.code}</span>: {error.message}
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="text-red-400 hover:text-red-200"
        aria-label="Dismiss error"
      >
        ×
      </button>
    </div>
  );
}
