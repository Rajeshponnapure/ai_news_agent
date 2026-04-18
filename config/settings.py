import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project dir, then parent dirs
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env", override=False)


class Settings:
    # Database
    DB_ENGINE: str = os.getenv("DB_ENGINE", "sqlite")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "ai_updates.db"))
    POSTGRES_DSN: str = os.getenv(
        "POSTGRES_DSN", "postgresql://user:pass@localhost:5432/ai_updates"
    )

    # WhatsApp Cloud API (optional — if you have a Meta Business token)
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_RECIPIENT_WA_ID: str = os.getenv("WHATSAPP_RECIPIENT_WA_ID", "")
    WHATSAPP_API_URL: str = os.getenv(
        "WHATSAPP_API_URL",
        "https://graph.facebook.com/v18.0",
    )

    # WhatsApp direct (pywhatkit — sends via WhatsApp Web, no API needed)
    WHATSAPP_DIRECT_ENABLED: bool = os.getenv("WHATSAPP_DIRECT_ENABLED", "true").lower() == "true"
    WHATSAPP_DIRECT_PHONE: str = os.getenv("WHATSAPP_DIRECT_PHONE", "")  # e.g. +919876543210

    # Email fallback (SMTP — used when WhatsApp fails)
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
    EMAIL_SMTP_HOST: str = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    EMAIL_SMTP_PORT: int = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "")       # your-email@gmail.com
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")   # app password (not your login password)
    EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "")  # where to send the digest

    # Scheduler
    INGESTION_INTERVAL_MINUTES: int = int(os.getenv("INGESTION_INTERVAL_MINUTES", "12"))
    COMPILE_TIME_IST: str = os.getenv("COMPILE_TIME_IST", "05:55")
    SEND_TIME_IST: str = os.getenv("SEND_TIME_IST", "06:00")

    # GitHub token (optional, raises rate limit)
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # NewsAPI.org (free tier: 100 requests/day)
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

    # Notification
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY_SECONDS: int = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

    # Message
    MAX_MESSAGE_CHARS: int = int(os.getenv("MAX_MESSAGE_CHARS", "1200"))

    @property
    def db_url(self) -> str:
        if self.DB_ENGINE == "postgres":
            return self.POSTGRES_DSN
        return f"sqlite:///{self.SQLITE_PATH}"


settings = Settings()
