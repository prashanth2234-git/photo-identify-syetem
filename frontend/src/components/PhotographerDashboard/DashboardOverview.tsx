import React, { useState, useEffect } from 'react';
import { Plus, UploadCloud, Camera, Eye, Search, Image as ImageIcon, Sparkles, Layers, ArrowRight, CheckCircle2, FolderDown } from 'lucide-react';
import { Event, PhotographerStats } from '../../types';
import { api } from '../../services/api';

interface DashboardOverviewProps {
  events: Event[];
  stats: PhotographerStats | null;
  onCreateEventClick: () => void;
  onUploadPhotosClick: (event: Event) => void;
  onImportDriveClick: (event: Event) => void;
  onOpenCloudinarySettings: () => void;
  onViewEventGallery: (event: Event) => void;
  onGoToFindPhotos: (eventId?: string) => void;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  events,
  stats,
  onCreateEventClick,
  onUploadPhotosClick,
  onImportDriveClick,
  onOpenCloudinarySettings,
  onViewEventGallery,
  onGoToFindPhotos
}) => {
  // Real face index counts fetched dynamically per event
  const [faceIndexCounts, setFaceIndexCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    events.forEach(async (ev) => {
      try {
        const data = await api.getEventFaceIndex(ev.id);
        setFaceIndexCounts((prev) => ({ ...prev, [ev.id]: data.total_indexed_faces ?? 0 }));
      } catch (err) {
        console.error(`Failed to fetch face-index for ${ev.id}:`, err);
      }
    });
  }, [events]);

  const totalPhotos = events.reduce((sum, e) => sum + (e.total_photos || 0), 0);
  const totalFaces = Object.values(faceIndexCounts).reduce((sum, count) => sum + count, 0);

  return (
    <div className="py-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-left">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8 pb-6 border-b border-white/10">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-xs font-mono text-purple-300 mb-2">
            <Camera className="w-3.5 h-3.5 text-purple-400" />
            <span>Photographer Studio</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-white tracking-tight">
            Event Management Hub
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload event photos directly to Cloudinary, track AI face indexing, and verify attendee search.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => onGoToFindPhotos()}
            className="px-4 py-2.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 hover:text-white border border-sky-400/30 text-xs font-semibold flex items-center space-x-2 transition-all cursor-pointer"
          >
            <Search className="w-3.5 h-3.5 text-sky-400" />
            <span>Find My Photos →</span>
          </button>

          <button
            onClick={onOpenCloudinarySettings}
            className="px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/10 text-xs font-semibold flex items-center space-x-2 transition-all cursor-pointer"
          >
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span>Cloudinary Config</span>
          </button>

          <button
            onClick={onCreateEventClick}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-95 text-white text-xs font-bold shadow-lg shadow-purple-500/20 flex items-center space-x-2 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>+ Create Event</span>
          </button>
        </div>
      </div>

      {/* Real Statistics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        <div className="p-5 rounded-2xl glass-panel border border-white/10">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Total Events</span>
            <Camera className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-2xl sm:text-3xl font-black text-white">
            {events.length}
          </p>
          <span className="text-[11px] text-slate-500 font-mono mt-1 block">Active Galleries</span>
        </div>

        <div className="p-5 rounded-2xl glass-panel border border-white/10">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Photos Uploaded</span>
            <ImageIcon className="w-4 h-4 text-sky-400" />
          </div>
          <p className="text-2xl sm:text-3xl font-black text-white">
            {totalPhotos.toLocaleString()}
          </p>
          <span className="text-[11px] text-sky-400 font-mono mt-1 block">Cloudinary Media Synced</span>
        </div>

        <div className="p-5 rounded-2xl glass-panel border border-white/10">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Faces Indexed</span>
            <Sparkles className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl sm:text-3xl font-black text-emerald-400">
            {totalFaces.toLocaleString()}
          </p>
          <span className="text-[11px] text-slate-500 font-mono mt-1 block">Biometric Embeddings</span>
        </div>

        <div className="p-5 rounded-2xl glass-panel border border-white/10">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Cloudinary Status</span>
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-sm font-bold text-white truncate">
            {stats?.active_cloud || 'Connected'}
          </p>
          <span className="text-[11px] text-emerald-400 font-mono mt-1 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>Live Cloudinary API</span>
          </span>
        </div>
      </div>

      {/* Events Section Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Event Galleries ({events.length})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Select an event to upload photos, inspect the gallery, or test selfie search.
          </p>
        </div>
      </div>

      {/* Events Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {events.map((event) => {
          const indexedCount = faceIndexCounts[event.id];

          return (
            <div
              key={event.id}
              className="group relative rounded-2xl overflow-hidden glass-panel border border-white/10 hover:border-purple-400/40 transition-all duration-300 shadow-xl flex flex-col justify-between"
            >
              <div>
                {/* Event Cover Photo */}
                <div className="relative aspect-[16/9] overflow-hidden">
                  <img
                    src={event.cover_url}
                    alt={event.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#090b14] via-transparent to-transparent"></div>

                  <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-black/75 backdrop-blur-md border border-white/10 text-[10px] font-mono text-purple-300">
                    {event.type}
                  </div>

                  <div className="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-black/75 backdrop-blur-md border border-white/10 text-[10px] font-mono text-slate-300">
                    ID: {event.id}
                  </div>
                </div>

                {/* Event Info */}
                <div className="p-5 space-y-4">
                  <div>
                    <h3 className="text-base font-bold text-white group-hover:text-purple-300 transition-colors line-clamp-1">
                      {event.title}
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-1">{event.location}</p>
                    <p className="text-[11px] text-slate-500 font-mono mt-0.5">{event.date}</p>
                  </div>

                  {/* Basic Event Statistics: Photos Uploaded & Faces Indexed */}
                  <div className="grid grid-cols-2 gap-3 bg-black/40 p-3 rounded-xl border border-white/5 text-center">
                    <div>
                      <span className="text-sm font-bold text-white block">
                        {(event.total_photos ?? 0).toLocaleString()}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">
                        Photos Uploaded
                      </span>
                    </div>
                    <div>
                      <span className="text-sm font-bold text-emerald-400 block">
                        {indexedCount !== undefined ? indexedCount.toLocaleString() : '...'}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">
                        Faces Indexed
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="p-5 pt-0 border-t border-white/[0.05] space-y-2 mt-2">
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => onUploadPhotosClick(event)}
                    className="py-2.5 px-3 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 hover:text-white border border-purple-500/30 text-xs font-semibold flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>Upload Photos</span>
                  </button>

                  <button
                    onClick={() => onImportDriveClick(event)}
                    className="py-2.5 px-3 rounded-xl bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 hover:text-white border border-sky-500/30 text-xs font-semibold flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
                  >
                    <FolderDown className="w-3.5 h-3.5" />
                    <span>Google Drive</span>
                  </button>

                  <button
                    onClick={() => onViewEventGallery(event)}
                    className="py-2.5 px-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/10 text-xs font-semibold flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View Gallery</span>
                  </button>
                </div>

                <button
                  onClick={() => onGoToFindPhotos(event.id)}
                  className="w-full py-2 px-3 rounded-xl bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 hover:text-sky-200 border border-sky-400/20 text-xs font-medium flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
                >
                  <Search className="w-3 h-3 text-sky-400" />
                  <span>Find My Photos in this Event &rarr;</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
