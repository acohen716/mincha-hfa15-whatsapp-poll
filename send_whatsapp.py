import os
import sys
import time
from datetime import datetime, timezone
from typing import Literal, Optional

import requests

WHAPI_TOKEN = os.environ["WHAPI_TOKEN"]
WHATSAPP_GROUP_ID = os.environ["WHATSAPP_GROUP_ID"]
ACTION_TYPE = os.environ["ACTION_TYPE"]  # "poll" or "reminder"

BASE_URL = "https://gate.whapi.cloud"
HEADERS = {
    "Authorization": f"Bearer {WHAPI_TOKEN}",
    "Content-Type": "application/json",
}

MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds


def log(msg: str, level: Literal["error", "warning", "notice"] = "notice") -> None:
    """Log with GitHub Actions annotation + UTC timestamp."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    annotation = f"::{level}::[{timestamp}] {msg}"
    output_stream = sys.stderr if level == "error" else sys.stdout
    print(annotation, file=output_stream, flush=True)


# Determine room based on day of week
DAY_OF_WEEK = datetime.now(timezone.utc).weekday()  # Monday=0, Sunday=6
ROOM = "03.500" if DAY_OF_WEEK in [6, 0, 3] else "03.501"
log(f"Today is weekday {DAY_OF_WEEK}. Selected room: {ROOM}")


def send_request_with_retries(url: str, payload: dict) -> Optional[requests.Response]:
    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
            if response.ok:
                return response
            log(
                f"Attempt {attempt}: HTTP {response.status_code} - {response.text}",
                "warning",
            )
        except requests.RequestException as e:
            log(f"Attempt {attempt}: Request failed - {e}", "warning")

        if attempt < MAX_RETRIES:
            time.sleep(backoff)
            backoff *= 2

    log("All retry attempts failed.", "error")
    sys.exit(1)


def send_poll():
    url = f"{BASE_URL}/messages/poll"
    payload = {
        "to": WHATSAPP_GROUP_ID,
        "title": f"מנחה ב-13:30, חדר {ROOM}",
        "options": ["מגיע", "תקראו לי אם חסר"],
        "count": 1,
    }
    response = send_request_with_retries(url, payload)
    if response:
        log(f"Poll sent successfully: HTTP {response.status_code}")


def send_reminder():
    url = f"{BASE_URL}/messages/text"
    payload = {
        "to": WHATSAPP_GROUP_ID,
        "body": f"תזכורת: אם עוד לא עניתם לסקר – זה הזמן! נתראה ב-13:30, חדר {ROOM}",
    }
    response = send_request_with_retries(url, payload)
    if response:
        log(f"Reminder sent successfully: HTTP {response.status_code}")


# --- Main Action ---
if ACTION_TYPE == "poll":
    send_poll()
elif ACTION_TYPE == "reminder":
    send_reminder()
else:
    log(f"Unknown action: {ACTION_TYPE}", "error")
    sys.exit(1)
