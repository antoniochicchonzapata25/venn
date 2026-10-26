import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { APP_NAME } from "../brand";
import type { User } from "../types";
import Logo from "./Logo";
import NavIcon from "./NavIcon";

const NAV = [
  { to: "/", label: "Home", icon: "home" },
  { to: "/nutrition", label: "Nutrition", icon: "nutrition" },
  { to: "/training", label: "Training", icon: "training" },
  { to: "/body", label: "Body", icon: "body" },
  { to: "/coach", label: "Coach", icon: "coach" },
  { to: "/settings", label: "Settings", icon: "settings" },
] as const;

export default function AppShell({ user, onLogout, children }: { user: User; onLogout: () => void; children: ReactNode }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Logo size={30} />
          <span className="brand-name">{APP_NAME}</span>
        </div>
        <nav aria-label="Main">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} className="nav-link">
              {({ isActive }) => (
                <>
                  <span className="nav-icon"><NavIcon name={item.icon} active={isActive} /></span>
                  <span className="nav-label">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="muted small">Signed in as <strong>{user.display_name}</strong></span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onLogout}>Log out</button>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
