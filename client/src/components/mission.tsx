import { useState } from "react";
import { apiFetch } from "../lib/api";
import { useAsync } from "../lib/use-async";
import { Button } from "./button";

type Period = "week" | "day";

interface MissionProgress {
  kind: "spend_cap" | "save";
  period: Period;
  label: string;
  amount: number;
  usual: number;
  why: string;
  progress: number;
  days_left: number;
  status: "active" | "met" | "missed";
}

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const when = { week: "this week", day: "today" } as const;

/** The mission's wording; every number comes from the server, which checked the AI's pick. */
function goalText(m: MissionProgress) {
  return m.kind === "save"
    ? `Move ${dollars.format(m.amount)} to ${m.label} ${when[m.period]}`
    : `Keep ${m.label} under ${dollars.format(m.amount)} ${when[m.period]}`;
}

function MissionRow({ period, mission, onStart, starting }: {
  period: Period;
  mission: MissionProgress | null;
  onStart: () => void;
  starting: boolean;
}) {
  const title = period === "week" ? "This week" : "Today";
  if (!mission || mission.status !== "active") {
    const result = mission && (mission.status === "met" ? "Done! Nice work." : "Not this time. New chance below.");
    return (
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-blue-grey-300">
          <span className="font-semibold text-blue-grey-100">{title}:</span>{" "}
          {result ?? (period === "week" ? "get a mission picked from your spending." : "get a quick challenge for today.")}
        </p>
        <Button size="sm" onClick={onStart} disabled={starting}>
          {starting ? "Picking…" : period === "week" ? "Get weekly mission" : "Get daily challenge"}
        </Button>
      </div>
    );
  }
  const save = mission.kind === "save";
  const over = !save && mission.progress > mission.amount;
  const pct = Math.min(100, (mission.progress / Math.max(1, mission.amount)) * 100);
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-blue-grey-100">
        <span className="font-semibold">{title}:</span> {goalText(mission)}
        <span className="text-blue-grey-400"> (usually {dollars.format(mission.usual)})</span>
      </p>
      {mission.why && <p className="text-xs text-blue-grey-400">{mission.why}</p>}
      <div role="progressbar" aria-label={`${title} progress`} aria-valuemin={0} aria-valuemax={mission.amount}
        aria-valuenow={mission.progress} className="h-2 overflow-hidden rounded-full bg-blue-grey-800">
        <div className={`h-full rounded-full ${over ? "bg-yellow-vivid-400" : "bg-teal-400"}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-blue-grey-400">
        {dollars.format(mission.progress)} {save ? "saved" : "spent"} of {dollars.format(mission.amount)}
        {period === "week" && <> · {mission.days_left} {mission.days_left === 1 ? "day" : "days"} left</>}
        {over && <> · over by {dollars.format(mission.progress - mission.amount)}. Slips happen; keep going.</>}
      </p>
    </div>
  );
}

/** Weekly mission and daily challenge, picked by AI from the student's data (GET/POST /api/me/mission). */
export function Mission({ className = "" }: { className?: string }) {
  const [fresh, setFresh] = useState(0); // bumping it re-reads bank data instead of the cached profile
  const [starting, setStarting] = useState<Period | null>(null);
  const [failed, setFailed] = useState(false);
  const { data, error, loading, reload } = useAsync(
    () => apiFetch<Record<Period, MissionProgress | null>>(`/api/me/mission${fresh ? "?refresh=true" : ""}`),
    [fresh],
  );

  async function start(period: Period) {
    setStarting(period);
    setFailed(false);
    try {
      await apiFetch(`/api/me/mission?period=${period}`, { method: "POST" });
      reload();
    } catch {
      setFailed(true);
    } finally {
      setStarting(null);
    }
  }

  const box = `flex flex-col gap-3 rounded-lg border border-blue-grey-800 bg-surface px-5 py-3 text-sm ${className}`;
  if (loading && !data) return <div aria-hidden="true" className={`h-24 animate-pulse rounded-lg bg-surface ${className}`} />;
  if (error || !data) return <p className={`${box} text-blue-grey-400`}>Couldn't load your missions.</p>;

  return (
    <section aria-label="Missions" className={box}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-widest text-blue-grey-400">Missions</span>
        <button type="button" onClick={() => setFresh((n) => n + 1)} aria-label="Refresh mission progress"
          className="rounded px-1.5 text-blue-grey-400 hover:text-blue-grey-050 focus-visible:outline-2 focus-visible:outline-purple-400">
          ↻
        </button>
      </div>
      {(["week", "day"] as const).map((period) => (
        <MissionRow key={period} period={period} mission={data[period]} onStart={() => start(period)} starting={starting === period} />
      ))}
      {failed && <p role="alert" className="text-xs text-yellow-vivid-200">Couldn't pick a mission right now. Try again.</p>}
    </section>
  );
}

export default Mission;
