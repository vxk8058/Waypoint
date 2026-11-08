// Savings goal from GET /api/me/goal, plus the derived numbers the goal bar shows.
import { apiFetch } from "./api";

/** Amounts are whole dollars; dates are "YYYY-MM-DD". */
export interface SavingsGoal {
  goal_id: string;
  name: string;
  goal_type: string; // "vehicle" | "emergency_fund" | "tuition" | "relocation" | …
  target_amount: number;
  current_saved: number;
  initial_saved: number;
  monthly_contribution: number;
  target_date: string;
  linked_account_id: string;
  created_date: string;
}

export interface GoalResponse {
  data: { as_of_date: string; stale: boolean; warnings: string[] };
  goal: SavingsGoal;
}

export const fetchGoal = () => apiFetch<GoalResponse>("/api/me/goal");

export type GoalStatus = "reached" | "ahead" | "on-track" | "behind" | "stalled";

export interface GoalProgress {
  /** Saved so far as a percentage of the target, 0–100. */
  pct: number;
  remaining: number;
  status: GoalStatus;
  /** First day of the month the goal is projected to be reached; undefined when reached or stalled. */
  projected?: Date;
}

/** Parses "YYYY-MM-DD" as a UTC date so it doesn't shift with the viewer's timezone. */
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

const monthIndex = (d: Date) => d.getUTCFullYear() * 12 + d.getUTCMonth();
const clamp = (n: number) => Math.min(100, Math.max(0, n));

/** `asOf` is the date the balances are from (the API's data.as_of_date). */
export function goalProgress(goal: SavingsGoal, asOf: Date): GoalProgress {
  const { target_amount, current_saved, monthly_contribution } = goal;
  const target = parseDate(goal.target_date);

  const pct = target_amount > 0 ? clamp((current_saved / target_amount) * 100) : 100;
  const remaining = Math.max(0, target_amount - current_saved);

  if (remaining === 0) return { pct, remaining, status: "reached" };
  if (monthly_contribution <= 0) return { pct, remaining, status: "stalled" };

  // Projected finish = asOf + remaining ÷ monthly contribution, rounded up to whole months.
  const finishMonth = monthIndex(asOf) + Math.ceil(remaining / monthly_contribution);
  const projected = new Date(Date.UTC(Math.floor(finishMonth / 12), finishMonth % 12, 1));
  const diff = finishMonth - monthIndex(target);
  const status: GoalStatus = diff < 0 ? "ahead" : diff === 0 ? "on-track" : "behind";
  return { pct, remaining, status, projected };
}
