import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { getSessionUser, logout } from "../lib/api";

/** Sidebar account button showing the signed-in user's name, with a sign-out menu that opens upward. */
export function AccountMenu() {
  const user = getSessionUser();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function signOut() {
    logout();
    navigate("/sign-in", { replace: true });
  }

  const name = user?.display_name ?? "Account";
  const initials = user ? `${user.first_name[0] ?? ""}${user.last_name[0] ?? ""}`.toUpperCase() : "?";

  return (
    <div ref={ref} className="relative">
      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute inset-x-0 bottom-full mb-2 rounded-lg border border-blue-grey-800 bg-surface-raised p-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            onClick={signOut}
            className="w-full cursor-pointer rounded-md px-3 py-2 text-left text-sm text-blue-grey-100 hover:bg-surface focus-visible:outline-2 focus-visible:outline-purple-400"
          >
            Sign out
          </button>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-blue-grey-300 transition-colors hover:bg-surface hover:text-blue-grey-050 focus-visible:outline-2 focus-visible:outline-purple-400"
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-purple-400/20 text-xs font-semibold text-purple-200">
          {initials}
        </span>
        <span className="truncate">{name}</span>
      </button>
    </div>
  );
}
