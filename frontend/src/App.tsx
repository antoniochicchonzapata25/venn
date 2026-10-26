import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import AppShell from "./components/AppShell";
import AuthPage from "./pages/AuthPage";
import Coach from "./pages/Coach";
import Body from "./pages/Body";
import Dashboard from "./pages/Dashboard";
import Nutrition from "./pages/Nutrition";
import Onboarding from "./pages/Onboarding";
import Settings from "./pages/Settings";
import Training from "./pages/Training";
import WorkoutPage from "./pages/WorkoutPage";
import type { User } from "./types";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const [askedSetup, setAskedSetup] = useState(false);

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setChecking(false));
  }, []);

  // First run: send people with an incomplete profile to the questionnaire once (they can skip it).
  useEffect(() => {
    if (!user || askedSetup) return;
    setAskedSetup(true);
    api.profile().then((p) => {
      if (!p.is_complete && location.pathname === "/") navigate("/welcome", { replace: true });
    }).catch(() => undefined);
  }, [user, askedSetup, location.pathname, navigate]);

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setUser(null);
  }, []);

  if (checking) return <div className="splash" aria-busy="true">Loading…</div>;
  if (!user) return <AuthPage onAuthenticated={setUser} />;

  return (
    <AppShell user={user} onLogout={logout}>
      <Routes>
        <Route path="/" element={<Dashboard user={user} />} />
        <Route path="/nutrition" element={<Nutrition />} />
        <Route path="/training" element={<Training />} />
        <Route path="/training/workouts/:id" element={<WorkoutPage />} />
        <Route path="/body" element={<Body />} />
        <Route path="/coach" element={<Coach />} />
        <Route path="/welcome" element={<Onboarding />} />
        <Route path="/settings" element={<Settings user={user} onLogout={logout} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
