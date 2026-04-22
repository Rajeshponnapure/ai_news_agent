import asyncio
import os
import uuid
import logging
from pathlib import Path
import edge_tts

logger = logging.getLogger(__name__)

# Ensure audio directory exists
AUDIO_DIR = Path("data/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Default to a professional US English female news anchor voice
DEFAULT_VOICE = "en-US-AriaNeural"

async def generate_audio(text: str, voice: str = DEFAULT_VOICE) -> str:
    """
    Generate an MP3 audio file from text using edge-tts.
    Returns the filename of the generated audio.
    """
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = AUDIO_DIR / filename
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(filepath))
        logger.info(f"Generated audio file: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to generate audio: {e}")
        return ""
