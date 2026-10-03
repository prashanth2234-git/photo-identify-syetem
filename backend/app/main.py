from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.seed_data import load_seed_data
from app.routes.events import router as events_router
from app.routes.photos import router as photos_router
from app.routes.search import router as search_router
from app.routes.privacy import router as privacy_router
from app.routes.stats import router as stats_router
from app.routes.imports import router as imports_router

# Ensure seed data is always loaded
load_seed_data()

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_seed_data()
    print("[EventSnap] Backend started. Seed data loaded successfully.")
    yield
    print("[EventSnap] Backend shutting down.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="EventSnap API: AI-Powered Event Photo Discovery Platform with Cloudinary Integration",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(events_router)
app.include_router(photos_router)
app.include_router(search_router)
app.include_router(privacy_router)
app.include_router(stats_router)
app.include_router(imports_router)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "hackathon": "HackIndia 2026 — Pixels to Products (Track PS-03)"
    }
