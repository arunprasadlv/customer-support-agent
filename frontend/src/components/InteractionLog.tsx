import { useEffect, useState } from "react";
import { getInteractions } from "../lib/mockOpsData";
import type { InteractionLogEntry } from "../types/ops";
import InteractionLogTable from "./InteractionLogTable";

interface InteractionLogProps {
  /** Bumped by `Ops.tsx` whenever an escalation resolution is submitted
   * elsewhere on the page (frontend.md §11), so this list refetches and
   * reflects newly-resolved interactions without a manual page reload.
   * Optional so this component's own default/first-mount behavior is
   * unchanged if a caller doesn't pass it. */
  refreshToken?: number;
}

/**
 * Interaction log container (sad.md SS3, PRD NFR-003) — read-only,
 * supports explainability/traceability. Owns the fetch/loading state;
 * the only integration point with a future real backend is
 * `getInteractions` (lib/mockOpsData.ts) — `@integration.eng` swaps it
 * for a real `GET /interactions` call without touching this component
 * or InteractionLogTable.
 */
export default function InteractionLog({ refreshToken }: InteractionLogProps) {
  const [entries, setEntries] = useState<InteractionLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  // `@integration.eng`'s `*integrate-api`/`*verify-messageflow` addition:
  // `getInteractions` now hits a real backend and can reject (network
  // failure, non-2xx). Previously (mock) this `.then()` could never
  // reject, so there was no error path to handle; a bare `.then()` here
  // would leave the request in a permanent "Loading…" state and an
  // unhandled promise rejection in the console — surfaced instead with
  // the same plain-`<p>` status-message pattern already used for the
  // loading/empty states just below, not a new error component.
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInteractions()
      .then((data) => {
        if (!cancelled) {
          setEntries(data);
          setIsLoading(false);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          console.error("getInteractions failed", error);
          setLoadError(
            error instanceof Error ? error.message : "Could not load the interaction log.",
          );
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  if (isLoading) {
    return <p>Loading interaction log…</p>;
  }

  if (loadError) {
    return <p role="alert">Could not load the interaction log: {loadError}</p>;
  }

  if (entries.length === 0) {
    return <p>No interactions logged yet.</p>;
  }

  return <InteractionLogTable entries={entries} />;
}
