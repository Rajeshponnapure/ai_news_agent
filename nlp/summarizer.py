import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

SYSTEM_PROMPT = """You are an expert, highly engaging AI News Anchor. 
Your job is to rewrite raw news updates into short, conversational, and energetic podcast-style scripts.
Rules:
1. Maximum 2-3 sentences.
2. Focus on the core update and WHY it matters.
3. Be natural and easy to listen to.
4. DO NOT include any introductory filler (like "Here is the news" or "Welcome back").
5. DO NOT use any markdown formatting, asterisks, or bullet points. Just raw spoken text."""

async def generate_nlp_summary(company: str, title: str, summary: str) -> str:
    """
    Sends the raw data to local Ollama for podcast-style summarization.
    It automatically detects and uses whatever model is installed.
    If Ollama is offline or fails, falls back to the basic string.
    """
    fallback_text = f"Breaking news from {company}. {title}. {summary}"
    user_prompt = f"Company: {company}\nTitle: {title}\nSummary: {summary}"
    
    try:
        # Timeout set to 30s as local models can take time depending on hardware
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Dynamically fetch available models
            tags_response = await client.get(OLLAMA_TAGS_URL)
            tags_response.raise_for_status()
            models = tags_response.json().get("models", [])
            
            if not models:
                logger.warning("Ollama is running, but no models are installed. Falling back to basic text.")
                return fallback_text
                
            # Pick the first available model dynamically
            model_name = models[0].get("name") if models[0] else None
            if not model_name:
                logger.warning("Ollama model name not found in response. Falling back to basic text.")
                return fallback_text
            logger.info(f"Using Ollama model: {model_name}")
            
            payload = {
                "model": model_name,
                "system": SYSTEM_PROMPT,
                "prompt": user_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.6,
                    "top_p": 0.9
                }
            }
            
            # 2. Generate summary
            response = await client.post(OLLAMA_GENERATE_URL, json=payload)
            response.raise_for_status()
            
            data = response.json()
            script = data.get("response", "").strip()
            
            if script:
                return script
                
    except httpx.ConnectError:
        logger.warning("Ollama is not running locally. Falling back to basic text.")
    except Exception as e:
        logger.error(f"NLP Summarization failed: {e}. Falling back to basic text.")
        
    # Fallback if Ollama fails or is not installed
    return fallback_text
