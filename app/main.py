from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import financial
from app.database import engine, Base
from app.config import settings

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Finance Assistant API",
    description="AI-powered personal finance management",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(financial.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/")
async def root():
    return {
        "message": "AI Finance Assistant API",
        "docs": "/docs",
        "health": "/health"
    }