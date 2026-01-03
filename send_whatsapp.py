"""Send WhatsApp poll or reminder messages to a group using the WHAPI cloud API.

This script selects a room based on the day of the week and sends either a poll or a reminder message
to a WhatsApp group.
Environment variables required: WHAPI_TOKEN, WHATSAPP_GROUP_ID, ACTION_TYPE.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import requests
from dotenv import load_dotenv

load_dotenv()  # take env vars from .env file for local development


def log(msg: str, level: Literal["error", "warning", "notice"] = "notice") -> None:
    """Log with GitHub Actions annotation + UTC timestamp."""
    timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")
    annotation = f"::{level}::[{timestamp}] {msg}"
    output_stream = sys.stderr if level == "error" else sys.stdout
    print(annotation, file=output_stream, flush=True)


def get_env_var(name: str) -> str:
    """Get an environment variable or raise an error if it's not set."""
    try:
        return os.environ[name]
    except KeyError:
        log(f"Missing required environment variable: {name}", "error")
        sys.exit(1)


WHAPI_TOKEN = get_env_var("WHAPI_TOKEN")
WHATSAPP_GROUP_ID = get_env_var("WHATSAPP_GROUP_ID")

BASE_URL = "https://gate.whapi.cloud"
HEADERS = {
    "Authorization": f"Bearer {WHAPI_TOKEN}",
    "Content-Type": "application/json",
}

MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds


def get_room_for_today(now: datetime) -> str:
    """Determine the room based on the day of week."""
    weekday = now.weekday()  # Monday=0, Sunday=6
    # Except Sun Jan 11 2026, reserved 06.502 as of Thurs Jan 1 2026 for all Sun - Thurs until Dec 31 2026
    # Reserved 03.500 as of Thurs Jan 1 2026 for all Sun, Mon, Wed, Thurs until Dec 31 2026
    # Except Tues Jan 20 2026, reserved 03.501 as of Thurs Jan 1 2026 for all Tues until Dec 31 2026
    # Was asked to free 03.500 on ALL Tues so we will try 06.502 for the upcoming week, if good then we'll
    #  cancel everything else, else revert back to 03.500 for Sun, Mon, Wed, Thurs and 03.501 for Tues
    room = "03.501" if weekday in {} else "06.502"
    log(f"Today is weekday {weekday}. Selected room: {room}")
    return room


def send_request_with_retries(url: str, payload: dict[Any, Any]) -> requests.Response:
    """Send a POST request with retries and exponential backoff.

    Logs warnings and errors if requests fail.
    Returns the response if successful, otherwise exits the program.
    """
    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"Sending request to {url} with payload: {json.dumps(payload, ensure_ascii=False)}")
            response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
            if response.ok:
                log(f"Success response: HTTP {response.status_code}, body: {response.text}")
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


def send_poll(room: str) -> None:
    """Send a poll message to the WhatsApp group with room and time information."""
    url = f"{BASE_URL}/messages/poll"
    payload = {
        "to": WHATSAPP_GROUP_ID,
        "title": f"🕍 מנחה ב-13:30, חדר {room}\n\n_ההודעה נשלחה אוטומטית_",
        "options": ['✅ מגיע בל"נ', "📞 תקראו לי אם חסר", "❌ לא מגיע (ישיבה, בבית, חולה, חופש וכו')"],
        "count": 1,
    }
    response = send_request_with_retries(url, payload)
    if response:
        log(f"Poll sent successfully: HTTP {response.status_code}")


def send_reminder(room: str) -> None:
    """Send a reminder message to the WhatsApp group if the poll has not been answered."""
    url = f"{BASE_URL}/messages/text"
    payload = {
        "to": WHATSAPP_GROUP_ID,
        "body": f"🔔 תזכורת: אם עוד לא עניתם לסקר - זה הזמן! נתראה ב-13:30, חדר {room}\n\n_ההודעה נשלחה אוטומטית_",
    }
    response = send_request_with_retries(url, payload)
    if response:
        log(f"Reminder sent successfully: HTTP {response.status_code}")


def is_today_holiday(now: datetime) -> str | None:
    """Return the friendly name if today is a holiday, else None. Looks in assets/holidays_<year>.json."""
    today = now.date()
    year = today.year
    holidays_file = Path(f"assets/holidays_{year}.json")
    if not holidays_file.exists():
        log(
            f"No holidays file found for {year} (expected: {holidays_file}), proceeding as if today is not a holiday.",
            "warning",
        )
        return None
    with holidays_file.open(encoding="utf-8") as f:
        holiday_map: dict[str, str] = json.load(f)
    return holiday_map.get(today.isoformat())


def write_github_summary(message: str) -> None:
    """Append a message to the GitHub Actions step summary file.

    If the environment variable GITHUB_STEP_SUMMARY is set, appends the given message
    to the file at that path. Useful for providing a summary of the action's execution
    to be displayed in the GitHub Actions UI.

    Args:
        message: The message to write to the summary file.

    """
    summary_path_str: str | None = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path_str is None:
        return
    summary_path = Path(summary_path_str)
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            f.write(message + "\n")
    except OSError as e:
        log(f"Failed to write GitHub summary: {e}", "warning")


# --- Main Action ---
def main() -> None:
    """Check if today is a holiday and exits if so. Otherwise, sends either a poll or a reminder message."""
    # NOTE: Successful execution will overwrite the failure summary
    write_github_summary("❌ WhatsApp message send failed.")
    now = datetime.now(UTC)
    holiday_name = is_today_holiday(now)
    if holiday_name:
        log(f"Today is a holiday: {holiday_name}. Skipping WhatsApp message.", "notice")
        write_github_summary(f"🌴 Today is a holiday: {holiday_name}. No WhatsApp message sent.")
        sys.exit(0)

    room = get_room_for_today(now)

    action = get_env_var("ACTION_TYPE")
    if action not in {"poll", "reminder"}:
        log(f"Invalid ACTION_TYPE: {action}", "error")
        sys.exit(1)
    action_type = action

    if action_type == "poll":
        send_poll(room)
        write_github_summary("✅ WhatsApp poll message sent successfully.")
    elif action_type == "reminder":
        send_reminder(room)
        write_github_summary("✅ WhatsApp reminder message sent successfully.")


if __name__ == "__main__":
    main()
