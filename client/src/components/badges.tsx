import { apiFetch } from "../lib/api";
import { useAsync } from "../lib/use-async";

interface Badge {
  id: string;
  label: string;
  hint: string;
  earned: boolean;
  earned_on: string | null;
}

/** Badges for verified wins (GET /api/me/badges); once earned they stay, even after a withdrawal. */
export function Badges() {
  const { data } = useAsync(() => apiFetch<Badge[]>("/api/me/badges"), []);
  if (!data) return null;
  return (
    <section aria-label="Badges" className="mt-6">
      <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-widest text-blue-grey-400">
        Badges · {data.filter((b) => b.earned).length}/{data.length}
      </p>
      <ul className="grid grid-cols-2 gap-1.5">
        {data.map((b) => (
          <li
            key={b.id}
            title={b.earned ? `Earned ${b.earned_on}` : b.hint}
            aria-label={`${b.label}: ${b.earned ? "earned" : `not yet. ${b.hint}`}`}
            className={`rounded-md px-2 py-1.5 text-[11px] leading-tight ${
              b.earned ? "bg-purple-400/15 font-semibold text-purple-100" : "bg-surface text-blue-grey-500"
            }`}
          >
            {b.earned ? "★" : "☆"} {b.label}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default Badges;
