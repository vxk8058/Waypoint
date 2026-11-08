import { useState } from "react";
import { AiDocument } from "../components/ai-document";
import { apiFetch } from "../lib/api";
import { useAsync } from "../lib/use-async";

type Mode = "last7" | "calendar";
const modes: [Mode, string][] = [["last7", "Last 7 days"], ["calendar", "Calendar week"]];

/** Weekly recap built in code from the student's transactions (GET /api/me/recap). */
export function Recap() {
  const [mode, setMode] = useState<Mode>("last7");
  const { data, error, loading } = useAsync(() => apiFetch<unknown>(`/api/me/recap?mode=${mode}`), [mode]);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">Your week</h1>
        <div role="group" aria-label="Recap period" className="flex rounded-lg border border-blue-grey-800 p-0.5">
          {modes.map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
              className={`rounded-md px-3 py-1 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-purple-400 ${
                mode === value ? "bg-surface-raised text-blue-grey-050" : "text-blue-grey-400 hover:text-blue-grey-050"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-blue-grey-800 bg-surface p-5">
        {loading && !data ? (
          <div aria-hidden="true" className="h-64 animate-pulse rounded-lg bg-surface-raised" />
        ) : error || !data ? (
          <p role="alert" className="text-sm text-blue-grey-300">Couldn't load your recap.</p>
        ) : (
          <AiDocument document={data} />
        )}
      </div>
    </div>
  );
}

export default Recap;
