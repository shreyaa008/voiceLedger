"""
Tool: get_current_datetime  (READ-ONLY)

Deterministic current date/time in Asia/Kolkata (IST) — the LLM must call
this instead of guessing "aaj ki date" or the day of the week. A language
model has no reliable sense of the real current date on its own.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def get_current_datetime() -> dict:
    now = datetime.now(IST)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "date_readable": now.strftime("%d %B %Y"),
        "day_of_week": now.strftime("%A"),
        "time_24h": now.strftime("%H:%M"),
        "timezone": "Asia/Kolkata",
        "iso": now.isoformat(),
    }