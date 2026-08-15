import { useEffect, useState } from "react";
import { getInteractions } from "../lib/mockOpsData";
import type { InteractionLogEntry } from "../types/ops";
import InteractionLogTable from "./InteractionLogTable";

/**
 * Interaction log container (sad.md SS3, PRD NFR-003) — read-only,
 * supports explainability/traceability. Owns the fetch/loading state;
 * the only integration point with a future real backend is
 * `getInteractions` (lib/mockOpsData.ts) — `@integration.eng` swaps it
 * for a real `GET /interactions` call without touching this component
 * or InteractionLogTable.
 */
export default function InteractionLog() {
  const [entries, setEntries] = useState<InteractionLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getInteractions().then((data) => {
      if (!cancelled) {
        setEntries(data);
        setIsLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (isLoading) {
    return <p>Loading interaction log…</p>;
  }

  if (entries.length === 0) {
    return <p>No interactions logged yet.</p>;
  }

  return <InteractionLogTable entries={entries} />;
}
