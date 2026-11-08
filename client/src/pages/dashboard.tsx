import { Link, NavLink, Outlet } from "react-router";
import logo from "../assets/logo.png";
import { AccountMenu } from "../components/account-menu";
import { Badges } from "../components/badges";
import { Goal } from "../components/goal";
import { Mission } from "../components/mission";

const tabs = [
  { to: "/dashboard", label: "Home", end: true },
  { to: "/dashboard/transactions", label: "Transactions" },
  { to: "/dashboard/simulation", label: "Simulation" },
  { to: "/dashboard/recap", label: "Your week" },
];

export function Dashboard() {
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-blue-grey-800 bg-canvas p-4">
        <Link
          to="/dashboard"
          aria-label="Waypoint home"
          className="mb-8 self-center rounded-lg focus-visible:outline-2 focus-visible:outline-purple-400"
        >
          <img src={logo} alt="" className="w-24" />
        </Link>

        <nav className="flex flex-col gap-1">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                [
                  "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-surface-raised text-blue-grey-050 shadow-[inset_3px_0_0_var(--color-purple-400)]"
                    : "text-blue-grey-300 hover:bg-surface hover:text-blue-grey-050",
                ].join(" ")
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>

        <Badges />

        <div className="mt-auto border-t border-blue-grey-800 pt-4">
          <AccountMenu />
        </div>
      </aside>

      <main className="flex-1 p-8">
        <div className="mx-auto w-full max-w-5xl">
          <Goal className="mb-3" />
          <Mission className="mb-8" />
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default Dashboard;
