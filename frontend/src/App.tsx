import React, { useState, useEffect } from 'react';
import confetti from 'canvas-confetti';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { EventCategories } from './components/EventCategories';
import { HowItWorks } from './components/HowItWorks';
import { InteractiveDemo } from './components/InteractiveDemo';
import { PhotographerShowcase } from './components/PhotographerShowcase';
import { CloudinaryWorkflow } from './components/CloudinaryWorkflow';
import { PrivacySection } from './components/PrivacySection';
import { Footer } from './components/Footer';

import { EventSelector } from './components/FindMyPhotos/EventSelector';
import { PhotoSearchModal } from './components/FindMyPhotos/PhotoSearchModal';
import { ScanningAnimation } from './components/FindMyPhotos/ScanningAnimation';
import { ResultsGallery } from './components/FindMyPhotos/ResultsGallery';
import { LightboxViewer } from './components/LightboxViewer';

import { DashboardOverview } from './components/PhotographerDashboard/DashboardOverview';
import { CreateEventModal } from './components/PhotographerDashboard/CreateEventModal';
import { BulkUploadStudio } from './components/PhotographerDashboard/BulkUploadStudio';
import { DriveImportPanel } from './components/PhotographerDashboard/DriveImportPanel';
import { CloudinarySettingsModal } from './components/PhotographerDashboard/CloudinarySettingsModal';
import { PrivacyModal } from './components/PrivacyModal';

import { api } from './services/api';
import { Event, Photo, SearchResponse, DemoPersona, PhotographerStats, CreateEventPayload } from './types';

export const App: React.FC = () => {
  // Navigation View State: 'home' | 'find-photos' | 'photographer'
  const [activeView, setActiveView] = useState<'home' | 'find-photos' | 'photographer'>('home');

  // Data State
  const [events, setEvents] = useState<Event[]>([]);
  const [demoPersonas, setDemoPersonas] = useState<DemoPersona[]>([]);
  const [stats, setStats] = useState<PhotographerStats | null>(null);
  const [favorites, setFavorites] = useState<string[]>([]);

  // Search Flow State
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanQueryType, setScanQueryType] = useState<'selfie' | 'bib'>('selfie');
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Lightbox State
  const [lightboxPhoto, setLightboxPhoto] = useState<Photo | null>(null);

  // Photographer Dashboard Modals
  const [isCreateEventOpen, setIsCreateEventOpen] = useState(false);
  const [bulkUploadEvent, setBulkUploadEvent] = useState<Event | null>(null);
  const [driveImportEvent, setDriveImportEvent] = useState<Event | null>(null);
  const [isCloudinaryModalOpen, setIsCloudinaryModalOpen] = useState(false);
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);

  // Toast Notification
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // Initial Data Load
  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    try {
      const [eventsData, personasData, statsData] = await Promise.all([
        api.getEvents(),
        api.getDemoPersonas(),
        api.getPhotographerStats()
      ]);
      setEvents(eventsData);
      setDemoPersonas(personasData);
      setStats(statsData);
    } catch (err) {
      console.error('Error fetching initial data:', err);
    }
  };

  // Trigger Confetti upon successful photo discovery
  const triggerCelebration = () => {
    confetti({
      particleCount: 60,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#38bdf8', '#818cf8', '#c084fc', '#34d399']
    });
  };

  // Search by Selfie
  const handleStartSelfieSearch = async (file?: File, personaId?: string) => {
    if (!selectedEvent) return;
    setSearchError(null);
    setSearchResponse(null);
    setIsSearchModalOpen(false);
    setScanQueryType('selfie');
    setIsScanning(true);

    try {
      const res = await api.searchBySelfie(selectedEvent.id, file, personaId);
      // Wait for scanning animation to complete
      setTimeout(() => {
        setSearchResponse(res);
        setIsScanning(false);
        if (res.total_matches > 0) {
          triggerCelebration();
          showToast(`Found ${res.total_matches} moments!`);
        } else {
          showToast(res.message || 'No matching photos found in this event.');
        }
      }, 1900);
    } catch (err) {
      console.error('Selfie search failed:', err);
      setIsScanning(false);
      setSearchResponse(null);
      const msg = err instanceof Error ? err.message : 'Search error. Please try again.';
      setSearchError(msg);
      setIsSearchModalOpen(true);
      showToast(msg);
    }
  };

  // Search by Bib Number
  const handleStartBibSearch = async (bibNumber: string) => {
    if (!selectedEvent) return;
    setIsSearchModalOpen(false);
    setScanQueryType('bib');
    setIsScanning(true);

    try {
      const res = await api.searchByBib(selectedEvent.id, bibNumber);
      setTimeout(() => {
        setSearchResponse(res);
        setIsScanning(false);
        if (res.total_matches > 0) {
          triggerCelebration();
          showToast(`Found ${res.total_matches} photos!`);
        } else {
          showToast(res.message || 'No photos found for this bib number.');
        }
      }, 1900);
    } catch (err) {
      console.error(err);
      setIsScanning(false);
      const msg = err instanceof Error ? err.message : 'Bib search error.';
      showToast(msg);
    }
  };

  // Toggle favorite
  const handleToggleFavorite = (photoId: string) => {
    setFavorites((prev) =>
      prev.includes(photoId) ? prev.filter((id) => id !== photoId) : [...prev, photoId]
    );
    showToast(favorites.includes(photoId) ? 'Removed from favorites' : 'Saved to favorites');
  };

  // Delete Search Data
  const handleDeleteSearchData = async () => {
    try {
      await api.deleteSearchData();
      showToast('Search session and temporary selfie vectors cleared.');
      if (lightboxPhoto) setLightboxPhoto(null);
    } catch (err) {
      showToast('Search data deleted.');
    }
  };

  // Create Event
  const handleCreateEvent = async (payload: CreateEventPayload) => {
    const newEvent = await api.createEvent(payload);
    setEvents((prev) => [newEvent, ...prev]);
    showToast(`Created event "${newEvent.title}"`);
    // Prompt for bulk upload immediately
    setBulkUploadEvent(newEvent);
  };

  return (
    <div className="min-h-screen bg-[#06070a] text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-black">
      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#0d101a] border border-sky-500/40 text-sky-300 text-xs px-4 py-2.5 rounded-xl shadow-2xl backdrop-blur-xl animate-fade-in flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping"></span>
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Global Navbar */}
      <Navbar
        onFindPhotosClick={() => {
          setActiveView('find-photos');
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onPhotographerClick={() => {
          setActiveView('photographer');
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onNavigateHome={() => {
          setActiveView('home');
          setSearchResponse(null);
          setSelectedEvent(null);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        activeView={activeView}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {/* VIEW 1: HOME LANDING PAGE */}
        {activeView === 'home' && (
          <>
            <Hero
              onFindPhotosClick={() => {
                setActiveView('find-photos');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              onPhotographerClick={() => {
                setActiveView('photographer');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />

            <EventCategories
              onCategorySelect={(cat) => {
                setActiveView('find-photos');
              }}
            />

            <HowItWorks />

            <InteractiveDemo
              onPhotoClick={(photo) => setLightboxPhoto(photo)}
              onFullSearchClick={(eventId, personaId) => {
                const ev = events.find((e) => e.id === eventId);
                if (ev) {
                  setSelectedEvent(ev);
                  setActiveView('find-photos');
                  handleStartSelfieSearch(undefined, personaId);
                }
              }}
            />

            <PhotographerShowcase
              onPhotographerClick={() => {
                setActiveView('photographer');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />

            <CloudinaryWorkflow />

            <PrivacySection />
          </>
        )}

        {/* VIEW 2: FIND MY PHOTOS EXPERIENCE */}
        {activeView === 'find-photos' && (
          <div className="pt-24 min-h-[85vh]">
            {!searchResponse ? (
              <EventSelector
                events={events}
                selectedEventId={selectedEvent?.id}
                onSelectEvent={(event) => {
                  setSelectedEvent(event);
                  setIsSearchModalOpen(true);
                }}
              />
            ) : (
              <ResultsGallery
                searchResponse={searchResponse}
                onPhotoClick={(photo) => setLightboxPhoto(photo)}
                onBackToSearch={() => setSearchResponse(null)}
                favorites={favorites}
                onToggleFavorite={handleToggleFavorite}
              />
            )}
          </div>
        )}

        {/* VIEW 3: PHOTOGRAPHER STUDIO DASHBOARD */}
        {activeView === 'photographer' && (
          <div className="pt-24 min-h-[85vh]">
            <DashboardOverview
              events={events}
              stats={stats}
              onCreateEventClick={() => setIsCreateEventOpen(true)}
              onUploadPhotosClick={(event) => setBulkUploadEvent(event)}
              onImportDriveClick={(event) => setDriveImportEvent(event)}
              onOpenCloudinarySettings={() => setIsCloudinaryModalOpen(true)}
              onGoToFindPhotos={(eventId) => {
                if (eventId) {
                  const ev = events.find((e) => e.id === eventId);
                  if (ev) {
                    setSelectedEvent(ev);
                    setIsSearchModalOpen(true);
                  }
                }
                setActiveView('find-photos');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              onViewEventGallery={async (event) => {
                setSelectedEvent(event);
                const detail = await api.getEventDetail(event.id);
                // Display event gallery as results
                setSearchResponse({
                  event_id: event.id,
                  event_title: event.title,
                  query_type: 'gallery' as any,
                  total_matches: detail.photos.length,
                  results: detail.photos.map((p) => ({
                    photo: p,
                    confidence_score: 1.0,
                    match_type: 'face'
                  })),
                  processing_time_ms: 100,
                  message: `Browsing ${detail.photos.length} photos in ${event.title}`
                });
                setActiveView('find-photos');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />
          </div>
        )}
      </main>

      {/* MODALS & OVERLAYS */}

      {/* 1. Photo Search Modal (Selfie upload / Bib Search) */}
      {isSearchModalOpen && selectedEvent && (
        <PhotoSearchModal
          event={selectedEvent}
          demoPersonas={demoPersonas}
          onStartSelfieSearch={handleStartSelfieSearch}
          onStartBibSearch={handleStartBibSearch}
          onClose={() => {
            setIsSearchModalOpen(false);
            setSearchError(null);
          }}
          searchError={searchError}
          onClearError={() => setSearchError(null)}
        />
      )}

      {/* 2. Radar Scanning Screen */}
      {isScanning && selectedEvent && (
        <ScanningAnimation
          eventTitle={selectedEvent.title}
          queryType={scanQueryType}
          onScanComplete={() => {}}
          targetCount={searchResponse?.total_matches}
        />
      )}

      {/* 3. Lightbox Photo Viewer with Dynamic Watermark Preview Toggle */}
      {lightboxPhoto && (
        <LightboxViewer
          photo={lightboxPhoto}
          eventTitle={
            events.find((e) => e.id === lightboxPhoto.event_id)?.title ||
            selectedEvent?.title ||
            'Event Gallery'
          }
          onClose={() => setLightboxPhoto(null)}
          isFavorite={favorites.includes(lightboxPhoto.id)}
          onToggleFavorite={handleToggleFavorite}
          onDeleteSearchData={handleDeleteSearchData}
        />
      )}

      {/* 4. Create Event Modal */}
      {isCreateEventOpen && (
        <CreateEventModal
          onClose={() => setIsCreateEventOpen(false)}
          onCreateEvent={handleCreateEvent}
        />
      )}

      {/* 5. Bulk Photo Upload Studio */}
      {bulkUploadEvent && (
        <BulkUploadStudio
          event={bulkUploadEvent}
          onClose={() => setBulkUploadEvent(null)}
          onUploadSuccess={() => {
            showToast('Photos uploaded to Cloudinary & indexed with AI!');
            loadAllData();
          }}
        />
      )}

      {/* 6. Google Drive Import Panel */}
      {driveImportEvent && (
        <DriveImportPanel
          event={driveImportEvent}
          onClose={() => setDriveImportEvent(null)}
          onImportSuccess={() => {
            showToast('Google Drive import finished — photos indexed!');
            loadAllData();
          }}
        />
      )}

      {/* 7. Cloudinary Settings Modal */}
      {isCloudinaryModalOpen && (
        <CloudinarySettingsModal onClose={() => setIsCloudinaryModalOpen(false)} />
      )}

      {/* 8. Privacy Policy Modal */}
      {isPrivacyModalOpen && (
        <PrivacyModal onClose={() => setIsPrivacyModalOpen(false)} />
      )}

      {/* Global Footer */}
      <Footer
        onFindPhotosClick={() => {
          setActiveView('find-photos');
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onPhotographerClick={() => {
          setActiveView('photographer');
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onOpenPrivacy={() => setIsPrivacyModalOpen(true)}
      />
    </div>
  );
};

export default App;
