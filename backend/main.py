"""FastAPI application — AI Course Generator backend (Ollama-powered)."""

import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import CourseRequest, WeekDetailsRequest, DayDetailsRequest
from course_generator import generate_course_outline, generate_week_details, generate_day_details
from ai_providers import check_ollama_health, list_models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Course Generator",
    description="Generate personalized learning courses with Ollama AI",
    version="4.0.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler to ensure CORS headers are always present
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Course Generator API v4 (Ollama)"}


@app.get("/api/health")
async def health():
    ollama_status = await check_ollama_health()
    return {"status": "healthy", "ollama": ollama_status}


@app.get("/api/models")
async def get_models():
    """Return list of locally installed Ollama models."""
    models = await list_models()
    if not models:
        raise HTTPException(
            status_code=503,
            detail="No models found. Is Ollama running? Try: ollama pull deepseek-r1:1.5b"
        )
    return {"models": models}


@app.post("/api/generate/outline")
async def generate_outline(request: CourseRequest):
    """Generate the weekly course outline."""
    try:
        logger.info(f"Generating weekly outline for: {request.goal}")
        course = await generate_course_outline(request)
        return course
    except Exception as e:
        logger.error(f"Outline generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Outline generation failed: {str(e)}")


@app.post("/api/generate/week")
async def generate_week(request: WeekDetailsRequest):
    """Generate daily breakdown for a specific week."""
    try:
        logger.info(f"Generating Week {request.week_number} details")
        details = await generate_week_details(request)
        return details
    except Exception as e:
        logger.error(f"Week detail generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Week generation failed: {str(e)}")


@app.post("/api/generate/day")
async def generate_day(request: DayDetailsRequest):
    """Generate details for a specific day."""
    try:
        details = await generate_day_details(request)
        return details
    except Exception as e:
        logger.error(f"Day detail generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Day generation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
