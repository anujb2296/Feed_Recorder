import { AlertTriangle, Trash2, X } from "lucide-react";

interface ConfirmDialogProps {
  title:      string;
  body:       string;
  onConfirm:  () => void;
  onCancel:   () => void;
  loading?:   boolean;
}

export default function ConfirmDialog({
  title, body, onConfirm, onCancel, loading,
}: ConfirmDialogProps) {
  return (
    <div className="dialog-backdrop" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-icon">
          <AlertTriangle size={20} />
        </div>
        <div className="dialog-title">{title}</div>
        <div className="dialog-body">{body}</div>
        <div className="dialog-actions">
          <button className="btn btn-ghost" onClick={onCancel} disabled={loading}>
            <X size={15} /> Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm} disabled={loading}>
            {loading ? (
              <><span className="spinner" style={{ width: 15, height: 15 }} /> Deleting...</>
            ) : (
              <><Trash2 size={15} /> Confirm Delete</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
