import { BrowserRouter, NavLink, Routes, Route, Navigate } from "react-router-dom";
import { Camera, Video, HardDrive, Settings } from "lucide-react";
import Live from "./pages/Live";
import Recordings from "./pages/Recordings";
import Storage from "./pages/Storage";
import SettingsPage from "./pages/Settings";

const NAV = [
  { to: "/live",       label: "Live View",   Icon: Camera   },
  { to: "/recordings", label: "Recordings",  Icon: Video    },
  { to: "/storage",    label: "Storage",     Icon: HardDrive },
  { to: "/settings",   label: "Settings",    Icon: Settings  },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        {/* ── Sidebar ─────────────────────────────────────────── */}
        <aside className="sidebar">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">📷</div>
            <div>
              <div className="sidebar-logo-text">CCTV NVR</div>
              <div className="sidebar-logo-sub">Self-Hosted</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            {NAV.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
              >
                <Icon size={17} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="sidebar-footer">CCTV NVR v1.0</div>
        </aside>

        {/* ── Page content ────────────────────────────────────── */}
        <main className="main-content">
          <Routes>
            <Route path="/"            element={<Navigate to="/live" replace />} />
            <Route path="/live"        element={<Live />} />
            <Route path="/recordings"  element={<Recordings />} />
            <Route path="/storage"     element={<Storage />} />
            <Route path="/settings"    element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
