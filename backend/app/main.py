from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import zomato, swiggy, blinkit
from app.database import close_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Scraping Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zomato.router)
app.include_router(swiggy.router)
app.include_router(blinkit.router)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Application started - Zomato, Swiggy & Blinkit ready")

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()
    logger.info("👋 Application shutdown")

@app.get("/")
async def root():
    return {
        "message": "Scraping Dashboard API",
        "version": "1.0.0",
        "platforms": ["zomato", "swiggy", "blinkit"],
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}