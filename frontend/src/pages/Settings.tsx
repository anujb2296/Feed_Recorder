import { useEffect, useState } from "react";
import { Save, Eye, EyeOff, RefreshCw } from "lucide-react";

interface CameraSettings {
  id:       string;
  name:     string;
  rtsp_url: string;
}

interface Settings {
  cameras:                CameraSettings[];
  segment_seconds:        number;
  default_retention_days: number;
  log_level:              string;
}

export default function SettingsPage() {
  const [, setSettings]  = useState<Settings | null>(null);
  const [form,      setForm]      = useState<Settings | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [saving,    setSaving]    = useState(false);
  const [saved,     setSaved]     = useState(false);
  const [showRtsp,  setShowRtsp]  = useState<Record<string, boolean>>({});
  const [error,     setError]     = useState<string | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/settings");
      const s = await r.json();
      setSettings(s);
      setForm(JSON.parse(JSON.stringify(s)));  // deep clone for editing
    } catch (e) { setError(String(e)); }
    setLoading(false);
  };

  useEffect(() => { loadSettings(); }, []);

  const handleSave = async () => {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const r = await fetch("/api/settings", {
        method:  "PUT",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          cameras:                form.cameras,
          segment_seconds:        form.segment_seconds,
          default_retention_days: form.default_retention_days,
          log_level:              form.log_level,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      await loadSettings();
    } catch (e) { setError(String(e)); }
    setSaving(false);
  };

  const updateCamera = (idx: number, field: keyof CameraSettings, value: string) => {
    if (!form) return;
    const cams = [...form.cameras];
    cams[idx] = { ...cams[idx], [field]: value };
    setForm({ ...form, cameras: cams });
  };

  if (loading) return <div className="page-body" style={{ color: "var(--text-muted)" }}>Loading...</div>;
  if (!form)   return <div className="page-body" style={{ color: "var(--danger)" }}>Failed to load settings.</div>;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Camera configuration and recording preferences.</p>
      </div>

      <div className="page-body">
        <div className="settings-form">

          {/* ── Camera settings ── */}
          <div className="settings-section">
            <div className="settings-section-title">Cameras</div>
            {form.cameras.map((cam, idx) => (
              <div key={cam.id} style={{ marginBottom: idx < form.cameras.length - 1 ? 20 : 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 10 }}>
                  {cam.id.toUpperCase()}
                </div>

                <div className="form-row" style={{ marginBottom: 10 }}>
                  <label className="form-label">Display Name</label>
                  <input
                    className="form-input"
                    value={cam.name}
                    onChange={e => updateCamera(idx, "name", e.target.value)}
                  />
                </div>

                <div className="form-row">
                  <label className="form-label">
                    RTSP URL
                    <span style={{ color: "var(--text-muted)", marginLeft: 6, fontWeight: 400 }}>
                      (special chars in password should be URL-encoded, e.g. @ → %40)
                    </span>
                  </label>
                  <div className="rtsp-input-wrapper">
                    <input
                      className="form-input"
                      type={showRtsp[cam.id] ? "text" : "password"}
                      value={cam.rtsp_url}
                      onChange={e => updateCamera(idx, "rtsp_url", e.target.value)}
                      placeholder="rtsp://user:pass@192.168.1.x:554/stream"
                    />
                    <button
                      className="rtsp-toggle-btn"
                      type="button"
                      onClick={() => setShowRtsp(v => ({ ...v, [cam.id]: !v[cam.id] }))}
                    >
                      {showRtsp[cam.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {idx < form.cameras.length - 1 && <div className="divider" style={{ margin: "16px 0" }} />}
              </div>
            ))}
          </div>

          {/* ── Recording settings ── */}
          <div className="settings-section">
            <div className="settings-section-title">Recording</div>

            <div className="form-row" style={{ marginBottom: 14 }}>
              <label className="form-label">Segment Length</label>
              <select
                className="form-select"
                value={form.segment_seconds}
                onChange={e => setForm({ ...form, segment_seconds: Number(e.target.value) })}
              >
                <option value={900}>15 minutes</option>
                <option value={1800}>30 minutes</option>
                <option value={3600}>1 hour (recommended)</option>
                <option value={7200}>2 hours</option>
              </select>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                Shorter segments = less data lost on a crash. Longer = fewer files to manage.
              </div>
            </div>
          </div>

          {/* ── UI preferences ── */}
          <div className="settings-section">
            <div className="settings-section-title">UI Preferences</div>

            <div className="form-row" style={{ marginBottom: 14 }}>
              <label className="form-label">Default Recordings Window</label>
              <select
                className="form-select"
                value={form.default_retention_days}
                onChange={e => setForm({ ...form, default_retention_days: Number(e.target.value) })}
              >
                {[1,2,3,5,7,10,15,20,30].map(d => (
                  <option key={d} value={d}>Last {d} {d === 1 ? "day" : "days"}</option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <label className="form-label">Log Level</label>
              <select
                className="form-select"
                value={form.log_level}
                onChange={e => setForm({ ...form, log_level: e.target.value })}
              >
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
            </div>
          </div>

          {/* ── Actions ── */}
          {error && (
            <div style={{ color: "var(--danger)", fontSize: 13, padding: "10px 14px", background: "var(--danger-glow)", borderRadius: "var(--radius-sm)", border: "1px solid var(--danger)" }}>
              Error: {error}
            </div>
          )}

          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving
                ? <><RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> Saving...</>
                : <><Save size={14} /> Save Settings</>
              }
            </button>

            {saved && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--success)" }}>
                ✓ Saved! Restart recording workers to apply RTSP URL changes.
              </div>
            )}
          </div>

          <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>
            ⓘ  After changing RTSP URLs, restart the backend container for changes to take effect:
            <br /><code style={{ background: "var(--bg-surface)", padding: "2px 6px", borderRadius: 4 }}>docker-compose restart backend</code>
          </div>
        </div>
      </div>
    </>
  );
}
