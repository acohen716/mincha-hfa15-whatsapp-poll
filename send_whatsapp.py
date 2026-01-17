"""Send WhatsApp poll or reminder messages to a group using the WHAPI cloud API.

This script selects a room based on the day of the week and sends either a poll or a reminder message
to a WhatsApp group.
Environment variables required: WHAPI_TOKEN, WHATSAPP_GROUP_ID, ACTION_TYPE.
"""
# pyright: reportUnknownVariableType=false, reportMissingTypeArgument=false, reportUnnecessaryCast=false

import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

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
    except Exception as exc:
        log(f"Missing required environment variable: {name}. Exception: {exc}", "error")
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
MINYAN_THRESHOLD = 10
NOT_FOUND_CODE = 404
FORBIDDEN_CODE = 403


def get_room_for_today(now: datetime) -> str:
    """Determine the room based on the day of week."""
    weekday = now.weekday()  # Monday=0, Sunday=6
    # Reserved 06.502 as of Thurs Jan 1 2026 for all Sun - Thurs until Dec 31 2026
    # Reserved 03.500 as of Thurs Jan 1 2026 for all Sun, Mon, Wed, Thurs until Dec 31 2026
    # Except Tues Jan 20 2026, reserved 03.501 as of Thurs Jan 1 2026 for all Tues until Dec 31 2026
    # Was asked to free 03.500 on ALL Tues so we will try 06.502 for the upcoming week, if good then we'll
    #  cancel everything else, else revert back to 03.500 for Sun, Mon, Wed, Thurs and 03.501 for Tues
    # Was asked to free 06.502 on Thurs Jan 15 2026 for that day only but GREF mentioned that floor 6 often
    #  has visitors so they recommended just using the north shelter on floor 6 (06.709) instead, we will
    #  try and see how it goes
    room = "03.501" if weekday in {} else '06.709 (ממ"ק הצפוני)'
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
        except Exception as exc:
            log(f"Attempt {attempt}: Request failed - {exc}", "warning")

        if attempt < MAX_RETRIES:
            time.sleep(backoff)
            backoff *= 2

    log("All retry attempts failed.", "error")
    sys.exit(1)


def send_poll(room: str) -> None:
    """Send a poll message to the WhatsApp group with room and time information.

    Persist the poll send response so the reminder run can reference and quote the poll message.
    """
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
        try:
            rjson: Any = response.json()  # type: ignore[reportUnknownVariableType]
            # Persist only the message id via write_last_poll_id
            # (writes .env locally or GitHub variable in Actions)
            msg_id: str | None = None
            if isinstance(rjson, dict):
                ms = rjson.get("message")  # type: ignore[reportUnknownVariableType]
                if isinstance(ms, dict):
                    msg_id = ms.get("id")  # type: ignore[reportUnknownVariableType]
                if not msg_id:
                    msg_id = (
                        rjson.get("id")  # type: ignore[reportUnknownVariableType]
                        or rjson.get("messageId")  # type: ignore[reportUnknownVariableType]
                        or rjson.get("message_id")  # type: ignore[reportUnknownVariableType]
                    )  # type: ignore[reportUnknownVariableType]
            if msg_id:
                write_last_poll_id(str(msg_id))  # type: ignore[reportUnknownVariableType]
            else:
                log("Poll response missing message id; not persisting.", "warning")
        except Exception as exc:
            log(f"Failed to persist poll response: {exc}", "warning")


def _get_message_with_retries(message_id: str) -> requests.Response | None:
    """GET a message by ID with retry/backoff semantics. Returns last response or None on exception."""
    url = f"{BASE_URL}/messages/{message_id}"
    backoff = INITIAL_BACKOFF
    last_response: requests.Response | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"Fetching message {message_id} from {url}")
            response = requests.get(url, headers=HEADERS, timeout=10)
            last_response = response
            if response.ok:
                log(f"Fetched message: HTTP {response.status_code}")
                return response
            log(f"Attempt {attempt}: HTTP {response.status_code} - {response.text}", "warning")
        except Exception as exc:
            log(f"Attempt {attempt}: GET failed - {exc}", "warning")
        if attempt < MAX_RETRIES:
            time.sleep(backoff)
            backoff *= 2
    log("All GET retry attempts exhausted; returning last response if any.", "warning")
    return last_response


def _persist_github_variable(owner: str, repo: str, token: str, msg_id: str) -> bool:
    """Try to PATCH the repository variable, and POST it if not found. Returns True on success."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    patch_url = f"https://api.github.com/repos/{owner}/{repo}/actions/variables/LAST_POLL_MESSAGE_ID"
    resp = requests.patch(patch_url, headers=headers, json={"value": str(msg_id)}, timeout=10)
    if resp.status_code in (200, 201, 204):
        log("Updated GitHub Actions variable LAST_POLL_MESSAGE_ID (patched)", "notice")
        os.environ["LAST_POLL_MESSAGE_ID"] = str(msg_id)
        return True
    if resp.status_code == NOT_FOUND_CODE:
        post_url = f"https://api.github.com/repos/{owner}/{repo}/actions/variables"
        post_payload = {"name": "LAST_POLL_MESSAGE_ID", "value": str(msg_id)}
        post_resp = requests.post(post_url, headers=headers, json=post_payload, timeout=10)
        if post_resp.status_code in (200, 201, 204):
            log("Created GitHub Actions variable LAST_POLL_MESSAGE_ID", "notice")
            os.environ["LAST_POLL_MESSAGE_ID"] = str(msg_id)
            return True
        if post_resp.status_code == FORBIDDEN_CODE:
            log(
                f"Failed to create GitHub variable: HTTP {FORBIDDEN_CODE} - {post_resp.text}. "
                "This likely means the workflow token lacks 'actions: write' permission; "
                "add the permissions section to your workflow: actions: write",
                "warning",
            )
        else:
            log(
                f"Failed to create GitHub variable: HTTP {post_resp.status_code} - {post_resp.text}",
                "warning",
            )
        return False
    if resp.status_code == FORBIDDEN_CODE:
        log(
            f"Failed to update GitHub variable: HTTP {FORBIDDEN_CODE} - {resp.text}. "
            "This likely means the workflow token lacks 'actions: write' permission; "
            "add the permissions section to your workflow: actions: write",
            "warning",
        )
        return False
    log(
        f"Failed to update GitHub variable: HTTP {resp.status_code} - {resp.text}",
        "warning",
    )
    return False


def write_last_poll_id(msg_id: str) -> None:
    """Persist the last poll message id either to GitHub Actions repository variables (when running in Actions).

    Or to a local .env file for local development.

    The reminder reads os.environ["LAST_POLL_MESSAGE_ID"] so this helper also sets the env var for the current process.
    """
    try:
        github_repo = os.environ.get("GITHUB_REPOSITORY")
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_repo and github_token:
            owner, repo = github_repo.split("/", 1)
            try:
                if _persist_github_variable(owner, repo, github_token, msg_id):
                    return
            except Exception as exc:
                log(f"Failed to persist GitHub variable: {exc}", "warning")
        # Fallback: write to .env in repo root
        env_path = Path(".env")
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith("LAST_POLL_MESSAGE_ID="):
                    lines[i] = f"LAST_POLL_MESSAGE_ID={msg_id}"
                    found = True
                    break
            if not found:
                lines.append(f"LAST_POLL_MESSAGE_ID={msg_id}")
        else:
            lines = [f"LAST_POLL_MESSAGE_ID={msg_id}"]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["LAST_POLL_MESSAGE_ID"] = str(msg_id)
        log("Wrote LAST_POLL_MESSAGE_ID to .env", "notice")
    except Exception as exc:
        log(f"Failed to persist LAST_POLL_MESSAGE_ID: {exc}", "warning")


def _clear_local_last_poll_id() -> None:
    """Remove LAST_POLL_MESSAGE_ID from local .env and the current process environment."""
    try:
        env_path = Path(".env")
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            new_lines = [line for line in lines if not line.strip().startswith("LAST_POLL_MESSAGE_ID=")]
            env_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
        os.environ.pop("LAST_POLL_MESSAGE_ID", None)
    except Exception as exc:
        log(f"Failed to clear LAST_POLL_MESSAGE_ID from .env: {exc}", "warning")


def send_reminder(room: str) -> None:
    """Send a reminder message to the WhatsApp group if the poll has not been answered.

    If a persisted poll exists, fetch it and count positive responses to vary the body text.
    Always send the reminder quoted as the poll message when possible.
    """
    # Default reminder text
    default_body = f"🔔 תזכורת: אם עוד לא עניתם לסקר - זה הזמן! נתראה ב-13:30, חדר {room}\n\n_ההודעה נשלחה אוטומטית_"

    # Get persisted poll message id from environment; do not rely on last_poll.json.
    poll_id = os.environ.get("LAST_POLL_MESSAGE_ID")
    if not poll_id:
        log(
            "LAST_POLL_MESSAGE_ID not found in environment; reminder will use default text unless GET succeeds.",
            "warning",
        )

    # Do not rely on persisted payload for counts. Only use persisted env to get message id for quoting.
    positive_count = None

    # Always try to GET the latest message counts when we have a message id
    if poll_id:
        pid_str = str(poll_id)
        # Validate msg id format to avoid calling GET with junk (e.g., MagicMock string) during tests
        if not _is_valid_msg_id(pid_str):
            log("LAST_POLL_MESSAGE_ID looks invalid; ignoring it for this run.", "warning")
            # If running locally, clear the .env entry so we don't keep persisting bad values
            if not os.environ.get("GITHUB_REPOSITORY"):
                _clear_local_last_poll_id()
                log("Cleared LAST_POLL_MESSAGE_ID from .env and environment (invalid value).", "notice")
            # Always ignore invalid id for sending
            poll_id = None
        else:
            positive_count = _fetch_positive_count(pid_str)

    # Build reminder body based on positive_count using helper
    body = _build_reminder_body(positive_count, room, default_body)

    payload = {
        "to": WHATSAPP_GROUP_ID,
        "body": body,
    }

    if poll_id:
        payload["quoted"] = str(poll_id)

    response = send_request_with_retries(f"{BASE_URL}/messages/text", payload)
    if response:
        log(f"Reminder sent successfully: HTTP {response.status_code}")


def _parse_positive_count_from_response(resp: requests.Response) -> int | None:
    """Parse a WHAPI message response and return the positive vote count (first option) or None."""
    result: int | None = None
    try:
        if not resp.ok:
            try:
                err = resp.json()
            except Exception as exc:
                log(f"Failed to parse error response JSON: {exc}", "warning")
                err = None
            if isinstance(err, dict):
                err_dict = cast("dict[str, Any]", err)
                code = err_dict.get("error", {}).get("code")
                message = err_dict.get("error", {}).get("message", "")
                if code == NOT_FOUND_CODE and "specified message not found" in message:
                    log("Poll message not found (404); using default reminder.", "notice")
                else:
                    log(f"GET returned non-OK {resp.status_code}; skipping counts.", "warning")
            else:
                log(f"GET returned non-OK {resp.status_code}; skipping counts.", "warning")
        else:
            msg: Any = resp.json()  # type: ignore[reportUnknownVariableType]
            parsed = _extract_positive_count_from_msg(msg)
            result = parsed
    except Exception as exc:
        log(f"Failed to parse poll message: {exc}", "warning")
        result = None

    return result


def _extract_positive_count_from_msg(msg: object) -> int | None:
    """Given a parsed message object, extract the positive count if present."""
    if isinstance(msg, dict) and "message" in msg and isinstance(msg["message"], dict):
        msg = msg["message"]
    if not isinstance(msg, dict):
        return None
    msg = cast("dict[str, Any]", msg)
    poll_section = msg.get("poll") or msg.get("interactive") or msg  # type: ignore[reportUnknownVariableType]
    if not isinstance(poll_section, dict):
        return None
    results = poll_section.get("results") or None  # type: ignore[reportUnknownVariableType]
    if isinstance(results, list):
        votes = [r.get("count") or 0 for r in results if isinstance(r, dict)]  # type: ignore[reportUnknownVariableType]
    else:
        opts = poll_section.get("options") or None  # type: ignore[reportUnknownVariableType]
        votes = [o.get("votes") or o.get("count") or 0 for o in (opts or []) if isinstance(o, dict)]  # type: ignore[reportUnknownVariableType]
    return votes[0] if votes else None


def _fetch_positive_count(message_id: str) -> int | None:  # type: ignore[reportUnknownVariableType]
    """Fetch a message by id and return the positive vote count for the first option if available."""
    try:
        get_resp = _get_message_with_retries(message_id)
    except Exception as exc:
        log(f"GET request failed: {exc}", "warning")
        return None
    if get_resp is None:
        return None
    return _parse_positive_count_from_response(get_resp)


def _build_reminder_body(positive_count: int | None, room: str, default_body: str) -> str:
    """Return the reminder body for given positive_count and room.

    Two paths: if positive_count is at least MINYAN_THRESHOLD, announce minyan; otherwise
    prepend the missing count to the default body.
    """
    if positive_count is None:
        return default_body
    if positive_count >= MINYAN_THRESHOLD:
        return f"יש מניין! כל מי שרוצה להצטרף יותר ממוזמן. נתראה ב-13:30, חדר {room}\n\n_ההודעה נשלחה אוטומטית_"
    missing = MINYAN_THRESHOLD - (positive_count or 0)
    return f"חסר {missing} — " + default_body


# WHAPI MessageID pattern per their docs
MSG_ID_PATTERN = re.compile(r"^[A-Za-z0-9._]{4,30}-[A-Za-z0-9._]{4,14}(-[A-Za-z0-9._]{4,10})?(-[A-Za-z0-9._]{2,10})?$")


def _is_valid_msg_id(msg_id: str) -> bool:
    """Return True if msg_id matches the WHAPI MessageID pattern."""
    return bool(MSG_ID_PATTERN.fullmatch(msg_id))


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
    except Exception as exc:
        log(f"Failed to write GitHub summary: {exc}", "warning")


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
