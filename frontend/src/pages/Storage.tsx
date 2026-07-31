import { useEffect, useState } from "react";
import { HardDrive, Trash2, Calendar, CalendarX, AlertTriangle } from "lucide-react";
import ConfirmDialog from "../components/ConfirmDialog";
import { formatBytes } from "../hooks/useRecordings";

interface CameraStat {
  id:               string;
  name:             string;
  bytes_used:       number;
  recording_count:  number;
  oldest_recording: string | null;
  newest_recording: string | null;
}

interface Stats {
  total_bytes: number;
  cameras:     CameraStat[];
}

interface PreviewResult {
  count:       number;
  total_bytes: number;
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
}

export default function Storage() {
  const [stats,   setStats]   = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  // Delete by date state
  const [dateValue,    setDateValue]    = useState("");
  const [dateCam,      setDateCam]      = useState("");
  const [datePreview,  setDatePreview]  = useState<PreviewResult | null>(null);
  const [datePreviewing, setDatePreviewing] = useState(false);
  const [dateConfirm,  setDateConfirm]  = useState(false);
  const [dateDeleting, setDateDeleting] = useState(false);

  // Delete before date state
  const [beforeValue,    setBeforeValue]    = useState("");
  const [beforeCam,      setBeforeCam]      = useState("");
  const [beforePreview,  setBeforePreview]  = useState<PreviewResult | null>(null);
  const [beforePreviewing, setBeforePreviewing] = useState(false);
  const [beforeConfirm,  setBeforeConfirm]  = useState(false);
  const [beforeDeleting, setBeforeDeleting] = useState(false);

  const loadStats = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/storage/stats");
      setStats(await r.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { loadStats(); }, []);

  // ── Preview delete by date ──────────────────────────────────────────────
  const handleDatePreview = async () => {
    if (!dateValue) return;
    setDatePreviewing(true);
    try {
      const r = await fetch("/api/storage/preview/date", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: dateValue, camera_id: dateCam || null }),
      });
      setDatePreview(await r.json());
    } catch (e) { console.error(e); }
    setDatePreviewing(false);
  };

  const handleDateDelete = async () => {
    setDateDeleting(true);
    try {
      await fetch("/api/storage/delete/date", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: dateValue, camera_id: dateCam || null }),
      });
      setDateConfirm(false);
      setDatePreview(null);
      setDateValue("");
      loadStats();
    } catch (e) { console.error(e); }
    setDateDeleting(false);
  };

  // ── Preview delete before date ──────────────────────────────────────────
  const handleBeforePreview = async () => {
    if (!beforeValue) return;
    setBeforePreviewing(true);
    try {
      const r = await fetch("/api/storage/preview/before", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ before_date: beforeValue, camera_id: beforeCam || null }),
      });
      setBeforePreview(await r.json());
    } catch (e) { console.error(e); }
    setBeforePreviewing(false);
  };

  const handleBeforeDelete = async () => {
    setBeforeDeleting(true);
    try {
      await fetch("/api/storage/delete/before", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ before_date: beforeValue, camera_id: beforeCam || null }),
      });
      setBeforeConfirm(false);
      setBeforePreview(null);
      setBeforeValue("");
      loadStats();
    } catch (e) { console.error(e); }
    setBeforeDeleting(false);
  };

  const camOptions = [
    { value: "",     label: "All Cameras" },
    ...(stats?.cameras.map(c => ({ value: c.id, label: c.name })) ?? []),
  ];

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Storage</h1>
        <p className="page-subtitle">
          Current usage and manual deletion controls. Nothing is ever auto-deleted.
        </p>
      </div>

      <div className="page-body">
        {/* ── Storage stats ── */}
        {loading ? (
          <div style={{ color: "var(--text-muted)", padding: 20 }}>Loading stats...</div>
        ) : stats ? (
          <>
            <div className="stats-grid">
              {/* Total */}
              <div className="stat-card" style={{ borderColor: "var(--accent-border)", boxShadow: "0 0 20px var(--accent-glow)" }}>
                <div className="stat-card-label"><HardDrive size={11} style={{ display:"inline", marginRight:4 }} />Total Used</div>
                <div className="stat-card-value">
                  {formatBytes(stats.total_bytes).replace(/\s(\w+)$/, "")}<span>{formatBytes(stats.total_bytes).match(/\s(\w+)$/)?.[1]}</span>
                </div>
                <div className="stat-card-sub">{stats.cameras.reduce((s, c) => s + c.recording_count, 0)} recording segments</div>
              </div>

              {/* Per-camera */}
              {stats.cameras.map(cam => (
                <div key={cam.id} className="stat-card">
                  <div className="stat-card-label">{cam.name}</div>
                  <div className="stat-card-value">
                    {formatBytes(cam.bytes_used).replace(/\s(\w+)$/, "")}<span>{formatBytes(cam.bytes_used).match(/\s(\w+)$/)?.[1] ?? ""}</span>
                  </div>
                  <div className="stat-card-sub">
                    {cam.recording_count} segments · {fmtDate(cam.oldest_recording)} → {fmtDate(cam.newest_recording)}
                  </div>
                </div>
              ))}
            </div>

            <div className="divider" />

            {/* ── Deletion forms ── */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>Manual Deletion</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                All deletions require an explicit confirmation step. Nothing happens until you confirm.
              </div>
            </div>

            <div className="delete-section">
              {/* Delete by date */}
              <div className="delete-form">
                <div className="delete-form-title">
                  <Calendar size={16} style={{ color: "var(--accent)" }} />
                  Delete a Specific Date
                </div>

                <div className="form-row">
                  <label className="form-label">Date</label>
                  <input type="date" className="form-input" value={dateValue}
                    onChange={e => { setDateValue(e.target.value); setDatePreview(null); }} />
                </div>

                <div className="form-row">
                  <label className="form-label">Camera</label>
                  <select className="form-select" value={dateCam} onChange={e => { setDateCam(e.target.value); setDatePreview(null); }}>
                    {camOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>

                <button className="btn btn-ghost" onClick={handleDatePreview}
                  disabled={!dateValue || datePreviewing}>
                  {datePreviewing ? <><span className="spinner" style={{width:14,height:14}} />Checking...</> : "Preview what will be deleted"}
                </button>

                {datePreview && (
                  <div className={`preview-box ${datePreview.count > 0 ? "danger" : ""}`}>
                    {datePreview.count === 0
                      ? "No recordings found for this date."
                      : <>
                          <AlertTriangle size={13} style={{ display:"inline", marginRight:5 }} />
                          This will permanently delete <strong>{datePreview.count} recording{datePreview.count !== 1 ? "s" : ""}</strong> totaling{" "}
                          <strong>{formatBytes(datePreview.total_bytes)}</strong>.
                        </>
                    }
                  </div>
                )}

                {datePreview && datePreview.count > 0 && (
                  <button className="btn btn-danger" onClick={() => setDateConfirm(true)}>
                    <Trash2 size={14} /> Delete {datePreview.count} Recording{datePreview.count !== 1 ? "s" : ""}
                  </button>
                )}
              </div>

              {/* Delete before date */}
              <div className="delete-form">
                <div className="delete-form-title">
                  <CalendarX size={16} style={{ color: "var(--danger)" }} />
                  Delete Everything Before a Date
                </div>

                <div className="form-row">
                  <label className="form-label">Delete all recordings before</label>
                  <input type="date" className="form-input" value={beforeValue}
                    onChange={e => { setBeforeValue(e.target.value); setBeforePreview(null); }} />
                </div>

                <div className="form-row">
                  <label className="form-label">Camera</label>
                  <select className="form-select" value={beforeCam} onChange={e => { setBeforeCam(e.target.value); setBeforePreview(null); }}>
                    {camOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>

                <button className="btn btn-ghost" onClick={handleBeforePreview}
                  disabled={!beforeValue || beforePreviewing}>
                  {beforePreviewing ? <><span className="spinner" style={{width:14,height:14}} />Checking...</> : "Preview what will be deleted"}
                </button>

                {beforePreview && (
                  <div className={`preview-box ${beforePreview.count > 0 ? "danger" : ""}`}>
                    {beforePreview.count === 0
                      ? "No recordings found before this date."
                      : <>
                          <AlertTriangle size={13} style={{ display:"inline", marginRight:5 }} />
                          This will permanently delete <strong>{beforePreview.count} recording{beforePreview.count !== 1 ? "s" : ""}</strong> totaling{" "}
                          <strong>{formatBytes(beforePreview.total_bytes)}</strong>.
                        </>
                    }
                  </div>
                )}

                {beforePreview && beforePreview.count > 0 && (
                  <button className="btn btn-danger" onClick={() => setBeforeConfirm(true)}>
                    <Trash2 size={14} /> Delete {beforePreview.count} Recording{beforePreview.count !== 1 ? "s" : ""}
                  </button>
                )}
              </div>
            </div>
          </>
        ) : null}
      </div>

      {/* Confirm dialogs */}
      {dateConfirm && (
        <ConfirmDialog
          title="Delete Recordings"
          body={`This will permanently delete ${datePreview?.count} recording(s) totaling ${formatBytes(datePreview?.total_bytes ?? null)} from ${dateValue}. Files will be removed from disk and the database. This cannot be undone.`}
          onConfirm={handleDateDelete}
          onCancel={() => setDateConfirm(false)}
          loading={dateDeleting}
        />
      )}
      {beforeConfirm && (
        <ConfirmDialog
          title="Delete Old Recordings"
          body={`This will permanently delete ${beforePreview?.count} recording(s) totaling ${formatBytes(beforePreview?.total_bytes ?? null)} (all recordings before ${beforeValue}). Files will be removed from disk and the database. This cannot be undone.`}
          onConfirm={handleBeforeDelete}
          onCancel={() => setBeforeConfirm(false)}
          loading={beforeDeleting}
        />
      )}
    </>
  );
}
