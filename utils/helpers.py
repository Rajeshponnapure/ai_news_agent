from datetime import datetime, timezone, timedelta


IST = timezone(timedelta(hours=5, minutes=30))


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def ist_now() -> datetime:
    """Return current time in IST timezone."""
    return datetime.now(IST)
