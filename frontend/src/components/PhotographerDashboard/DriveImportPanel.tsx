import React, { useState, useEffect, useRef } from 'react';
import { X, FolderDown, Loader2, CheckCircle2, AlertCircle, Ban } from 'lucide-react';
import { Event, ImportJob } from '../../types';
import { api } from '../../services/api';

interface DriveImportPanelProps {
  event: Event;
  onClose: () => void;
  onImportSuccess: () => void;
}

const TERMINAL_STATUSES = ['completed', 'completed_with_errors', 'failed', 'cancelled'];

export const DriveImportPanel: React.FC<DriveImportPanelProps> = ({
  event,
  onClose,
  onImportSuccess
}) => {
  const [folderUrl, setFolderUrl] = useState('');
  const [job, setJob] = useState<ImportJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifiedRef = useRef(false);

  const isActive = job !== null && !TERMINAL_STATUSES.includes(job.status);

  // Poll the job status while it is queued/running
  useEffect(() => {
    if (!job || !isActive) return;
    const timer = setInterval(async () => {
      try {
        const latest = await api.getImportJob(job.id);
        setJob(latest);
      } catch (err) {
        console.error('Failed to poll import status:', err);
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [job?.id, isActive]);

  // Notify parent once, when the job reaches a terminal state
  useEffect(() => {
    if (job && TERMINAL_STATUSES.includes(job.status) && !notifiedRef.current) {
      notifiedRef.current = true;
      if (job.successful > 0) onImportSuccess();
    }
  }, [job?.status]);

  const startImport = async () => {
    if (!folderUrl.trim() || starting) return;
    setStarting(true);
    setError(null);
    try {
      const created = await api.startDriveImport(event.id, folderUrl.trim());
      notifiedRef.current = false;
      setJob(created);
    } catch (err: any) {
      setError(err.message || 'Failed to start import');
    } finally {
      setStarting(false);
    }
  };

  const cancelImport = async () => {
    if (!job) return;
    try {
      setJob(await api.cancelImportJob(job.id));
    } catch (err: any) {
      setError(err.message || 'Failed to cancel import');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-xl animate-fade-in overflow-y-auto">
      <div className="relative w-full max-w-3xl rounded-3xl glass-panel border border-white/20 shadow-2xl p-6 sm:p-8 my-8 text-left">
        <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-6">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-mono text-sky-400 mb-1">
              <span>{event.title}</span>
              <span>•</span>
              <span className="text-slate-400">Event ID: {event.id}</span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Import from Google Drive
            </h2>
            <p className="text-slate-400 text-xs mt-0.5">
              Share your Drive folder with the EventSnap service account as Viewer, then paste the folder link below.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full text-slate-400 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Folder URL Input */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <input
            type="text"
            value={folderUrl}
            onChange={(e) => setFolderUrl(e.target.value)}
            placeholder="https://drive.google.com/drive/folders/..."
            disabled={isActive}
            className="flex-1 px-4 py-2.5 rounded-xl bg-black/50 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-400/50 disabled:opacity-50"
          />
          <button
            onClick={startImport}
            disabled={!folderUrl.trim() || starting || isActive}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 hover:opacity-95 text-white text-xs font-bold shadow-xl shadow-sky-500/20 flex items-center justify-center space-x-2 disabled:opacity-50 transition-all cursor-pointer"
          >
            {starting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Starting...</span>
              </>
            ) : (
              <>
                <FolderDown className="w-4 h-4" />
                <span>Start Import</span>
              </>
            )}
          </button>
        </div>

        {error && (
          <p className="text-rose-400 text-xs font-mono mb-4 flex items-center space-x-1">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{error}</span>
          </p>
        )}

        {/* Progress */}
        {job && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs">
              <span className={`font-mono font-bold ${
                job.status === 'completed' ? 'text-emerald-400' :
                job.status === 'completed_with_errors' ? 'text-amber-400' :
                job.status === 'failed' || job.status === 'cancelled' ? 'text-rose-400' :
                'text-sky-400'
              }`}>
                {job.status.toUpperCase()}
              </span>
              <span className="text-slate-400 font-mono">{job.percentage}%</span>
            </div>

            <div className="w-full h-2.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-500 to-indigo-500 transition-all duration-500"
                style={{ width: `${job.percentage}%` }}
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
              {[
                ['Total', job.total, 'text-white'],
                ['Processed', job.processed, 'text-sky-300'],
                ['Imported', job.successful, 'text-emerald-400'],
                ['Skipped', job.skipped, 'text-amber-400'],
                ['Failed', job.failed, 'text-rose-400'],
              ].map(([label, value, color]) => (
                <div key={label as string} className="p-2 rounded-xl bg-black/40 border border-white/5">
                  <p className={`text-lg font-black ${color}`}>{value as number}</p>
                  <p className="text-[10px] text-slate-400 font-mono uppercase">{label as string}</p>
                </div>
              ))}
            </div>

            <div className="text-xs text-slate-400 font-mono space-y-1">
              <p>Remaining: {job.remaining}</p>
              <p>
                Face indexing: {job.with_faces} photo{job.with_faces === 1 ? '' : 's'} with detected faces •{' '}
                {job.no_faces} photo{job.no_faces === 1 ? '' : 's'} with no faces detected
              </p>
              {job.current_filename && isActive && (
                <p className="flex items-center space-x-1.5">
                  <Loader2 className="w-3 h-3 animate-spin text-sky-400" />
                  <span className="truncate">Currently: {job.current_filename}</span>
                </p>
              )}
              <p>{job.message}</p>
            </div>

            {job.errors.length > 0 && (
              <div className="max-h-32 overflow-y-auto rounded-xl bg-black/50 border border-white/10 p-3 space-y-1">
                {job.errors.map((e, idx) => (
                  <p key={idx} className="text-[11px] text-rose-300/90 font-mono truncate">
                    {e.file ? `${e.file}: ` : ''}{e.error}
                  </p>
                ))}
              </div>
            )}

            <div className="flex items-center justify-end space-x-3 pt-2">
              {isActive && (
                <button
                  onClick={cancelImport}
                  className="px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-rose-300 text-xs font-semibold cursor-pointer flex items-center space-x-1.5"
                >
                  <Ban className="w-3.5 h-3.5" />
                  <span>Cancel</span>
                </button>
              )}
              {!isActive && (
                <span className="text-[11px] font-mono text-emerald-400 flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Done</span>
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
