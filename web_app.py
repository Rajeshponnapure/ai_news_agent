import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from database.db import get_db
from voice.voice_engine import generate_audio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of target companies for voice output
VOICE_TARGET_COMPANIES = {
    "openai", "anthropic", "google", "meta", "xai", "mistral", 
    "deepseek", "qwen", "kimi", "ollama", "cohere", "perplexity", 
    "hugging face", "midjourney", "elevenlabs", "gemini", "google deepmind"
}

db = get_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background task for generating audio
    task = asyncio.create_task(background_audio_generator())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="AI News Voice Dashboard", lifespan=lifespan)

# Mount static files and audio files
os.makedirs("static", exist_ok=True)
os.makedirs("data/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/audio", StaticFiles(directory="data/audio"), name="audio")

async def background_audio_generator():
    """Background loop to poll for ungenerated voice updates and generate MP3s."""
    logger.info("Starting background audio generator...")
    while True:
        try:
            updates = db.get_unprocessed_voice_updates()
            for update in updates:
                # Filter to only target companies and high/medium impact
                company = update.get("company", "").lower()
                impact = update.get("impact_level", "low")
                is_launch = update.get("is_launch", 0)
                is_top_company = update.get("is_top_company", 0)
                
                # We also consider top company launches even if not explicitly in the set, 
                # but let's stick to the set and impact criteria
                is_target = any(vc in company for vc in VOICE_TARGET_COMPANIES)
                
                if (is_target and impact in ["high", "medium"]) or (is_launch and is_top_company):
                    # Generate natural script
                    title = update.get("title", "")
                    summary = update.get("summary", "")
                    script = f"Breaking news from {update.get('company', 'AI tech')}. {title}. {summary}"
                    
                    logger.info(f"Generating audio for: {title[:50]}...")
                    filename = await generate_audio(script)
                    if filename:
                        db.mark_voice_generated(update["id"], filename)
                else:
                    # Mark as generated with no path to ignore it
                    db.mark_voice_generated(update["id"], "IGNORED")
                    
        except Exception as e:
            logger.error(f"Error in background audio generator: {e}")
            
        # Poll every 30 seconds
        await asyncio.sleep(30)


@app.get("/")
async def serve_dashboard():
    return FileResponse("static/index.html")

@app.get("/sw.js")
async def serve_sw():
    return FileResponse("static/sw.js", media_type="application/javascript")

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse("static/manifest.json", media_type="application/json")

@app.get("/api/queue")
async def get_queue():
    """Get the list of unplayed audio updates."""
    updates = db.get_unplayed_voice_updates()
    # Filter out ignored ones
    queue = [u for u in updates if u.get("voice_audio_path") and u.get("voice_audio_path") != "IGNORED"]
    return {"queue": queue}

class MarkPlayedRequest(BaseModel):
    update_id: str

@app.post("/api/mark-played")
async def mark_played(req: MarkPlayedRequest):
    """Mark an audio update as played."""
    db.mark_voice_played(req.update_id)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=5000, reload=True)
