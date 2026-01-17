"""Unit tests for send_whatsapp.py, covering holiday logic, logging, and WhatsApp message sending functions."""

import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import IO
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

import send_whatsapp


def test_write_github_summary(tmp_path: Path) -> None:
    """Test write_github_summary writes the given text to the summary file."""
    summary_path = tmp_path / "mock_summary.md"
    test_content = "Success"
    with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_path)}):
        send_whatsapp.write_github_summary(test_content)
        written = summary_path.read_text()
        assert test_content in written


@patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": "/some/path"})
@patch("send_whatsapp.log")
def test_write_github_summary_file_write_failure(mock_log: MagicMock) -> None:
    """Test write_github_summary logs failure if file write fails."""
    send_whatsapp.write_github_summary("Test message")
    mock_log.assert_called_once()
    args, _kwargs = mock_log.call_args
    assert "Failed to write GitHub summary" in args[0]


@patch("time.sleep", return_value=None)  # patch sleep to skip real waiting
@patch("requests.post")
def test_send_request_with_retries_backoff_and_retries(mock_post: MagicMock, mock_sleep: MagicMock) -> None:
    # Simulate two failed attempts then success
    """Test send_request_with_retries sleeps with exponential backoff on failed attempts."""
    responses = []
    failed_response = MagicMock()
    failed_response.ok = False
    failed_response.status_code = 500
    failed_response.text = "Error"
    success_response = MagicMock()
    success_response.ok = True
    success_response.status_code = 200
    success_response.text = "OK"
    responses = [failed_response, failed_response, success_response]
    mock_post.side_effect = responses
    result = send_whatsapp.send_request_with_retries("http://fake.url", {"k": "v"})
    assert result.ok
    # sleep called twice: after first and second failed attempt
    mock_sleep_call_count = 2
    assert mock_sleep.call_count == mock_sleep_call_count
    # check exponential backoff times (2 and 4 seconds)
    mock_sleep.assert_any_call(2)
    mock_sleep.assert_any_call(4)


@patch("send_whatsapp.write_github_summary")
@patch("send_whatsapp.send_reminder")
@patch("send_whatsapp.send_poll")
@patch("send_whatsapp.datetime")
def test_main_successful_flow(
    mock_datetime: MagicMock, mock_poll: MagicMock, mock_reminder: MagicMock, mock_summary: MagicMock
) -> None:
    """Test that main writes failed summary first, then success on successful run."""
    fixed_time_not_holiday = datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_datetime.now.return_value = fixed_time_not_holiday
    mock_poll.return_value = None
    mock_reminder.return_value = None
    with patch.dict("os.environ", {"ACTION_TYPE": "poll"}):
        send_whatsapp.main()
    mock_summary.assert_any_call("❌ WhatsApp message send failed.")
    mock_summary.assert_called_with("✅ WhatsApp poll message sent successfully.")


def open_test_file(file_path: Path) -> Callable[..., IO[str]]:
    """Create a mock-compatible function that opens the given file with any arguments.

    This is useful as a mock side_effect for Path.open in unit tests. It ensures
    that encoding and mode arguments are respected while avoiding type checker errors.
    """

    def opener(*args: object, **kwargs: object) -> IO[str]:
        # We assume text mode here (which is the default for Path.open)
        return file_path.open(*args, **kwargs)  # type: ignore[call-overload]

    return opener


def test_is_today_holiday_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_today_holiday returns the holiday name if today is a holiday."""
    aware_now = datetime(2025, 8, 4, tzinfo=UTC)

    # Prepare the assets directory and holiday file with today's date
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    holiday_file = assets_dir / "holidays_2025.json"
    holiday_file.write_text(json.dumps({"2025-08-04": "Test Holiday"}))
    # Change working directory to tmp_path so relative paths work as expected
    monkeypatch.chdir(tmp_path)
    # Call the function under test
    result = send_whatsapp.is_today_holiday(aware_now)
    assert result == "Test Holiday"


def test_is_today_holiday_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_today_holiday returns None if today is not a holiday."""
    aware_now = datetime(2025, 8, 4, tzinfo=UTC)
    # Prepare the assets directory and holiday file with a different date
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    holiday_file = assets_dir / "holidays_2025.json"
    holiday_file.write_text(json.dumps({"2025-08-05": "Other Holiday"}))  # Not today
    monkeypatch.chdir(tmp_path)
    result = send_whatsapp.is_today_holiday(aware_now)
    assert result is None


def test_is_today_holiday_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_today_holiday returns None and logs warning if file is missing."""
    aware_now = datetime(2025, 8, 4, tzinfo=UTC)
    # Create the assets directory but do NOT create the holiday file
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    with patch("send_whatsapp.log") as mock_log:
        result = send_whatsapp.is_today_holiday(aware_now)
    assert result is None
    mock_log.assert_called()


def test_get_room_for_today_various_days() -> None:
    """Test get_room_for_today returns correct room based on weekday."""
    # Sunday (6) -> '06.709 (ממ"ק הצפוני)'
    assert send_whatsapp.get_room_for_today(datetime(2025, 8, 3, tzinfo=UTC)) == '06.709 (ממ"ק הצפוני)'
    # Monday (0) -> '06.709 (ממ"ק הצפוני)'
    assert send_whatsapp.get_room_for_today(datetime(2025, 8, 4, tzinfo=UTC)) == '06.709 (ממ"ק הצפוני)'
    # Thursday (3) -> '06.709 (ממ"ק הצפוני)'
    assert send_whatsapp.get_room_for_today(datetime(2025, 8, 7, tzinfo=UTC)) == '06.709 (ממ"ק הצפוני)'


@patch("send_whatsapp.write_github_summary")
@patch("send_whatsapp.send_reminder")
@patch("send_whatsapp.datetime")
def test_main_reminder_branch(mock_datetime: MagicMock, mock_reminder: MagicMock, mock_summary: MagicMock) -> None:
    """Test main writes failed summary first, then success on successful run with reminder branch."""
    fixed_time_not_holiday = datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_datetime.now.return_value = fixed_time_not_holiday
    mock_reminder.return_value = None
    with patch.dict("os.environ", {"ACTION_TYPE": "reminder"}):
        send_whatsapp.main()
    mock_summary.assert_any_call("❌ WhatsApp message send failed.")
    mock_summary.assert_called_with("✅ WhatsApp reminder message sent successfully.")
    mock_reminder.assert_called_once()


@patch("send_whatsapp.write_github_summary")
@patch("send_whatsapp.log")
@patch("send_whatsapp.is_today_holiday", return_value="Mock Holiday")
@patch("sys.exit")
def test_main_exits_if_holiday(
    mock_exit: MagicMock,
    mock_is_holiday: MagicMock,
    mock_log: MagicMock,
    mock_summary: MagicMock,
) -> None:
    """Test main exits early if today is a holiday."""
    # Make mock_exit raise SystemExit to stop execution like real sys.exit
    mock_exit.side_effect = SystemExit(0)
    with pytest.raises(SystemExit) as exc_info, patch.dict("os.environ", {"ACTION_TYPE": "reminder"}):
        send_whatsapp.main()
    assert exc_info.value.code == 0
    mock_summary.assert_any_call("❌ WhatsApp message send failed.")
    mock_is_holiday.assert_called_once()
    mock_log.assert_called_with("Today is a holiday: Mock Holiday. Skipping WhatsApp message.", "notice")
    mock_summary.assert_any_call("🌴 Today is a holiday: Mock Holiday. No WhatsApp message sent.")
    mock_exit.assert_called_once_with(0)


load_dotenv()  # take environment variables from .env file for local development
sys.path.insert(0, str(Path(__file__).parent.resolve()))


def test_log_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that log outputs to stdout for notice level."""
    send_whatsapp.log("test notice", "notice")
    out, _ = capsys.readouterr()
    assert "test notice" in out


def test_log_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that log outputs to stderr for error level."""
    send_whatsapp.log("test error", "error")
    _, err = capsys.readouterr()
    assert "test error" in err


@patch("requests.post")
def test_send_request_with_retries_success(mock_post: MagicMock) -> None:
    """Test send_request_with_retries returns response on success."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    result = send_whatsapp.send_request_with_retries(
        "http://fake.url",
        {"key": "value"},
    )
    assert result is not None
    assert result.ok


@patch("requests.post")
def test_send_request_with_retries_failure(mock_post: MagicMock) -> None:
    """Test send_request_with_retries exits on repeated failure."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_response.text = "Server Error"
    mock_post.return_value = mock_response
    with patch("sys.exit") as mock_exit:
        send_whatsapp.send_request_with_retries("http://fake.url", {"key": "value"})
        mock_exit.assert_called_once_with(1)


@patch("send_whatsapp.send_request_with_retries")
def test_send_poll(mock_send: MagicMock) -> None:
    """Test send_poll calls send_request_with_retries and handles response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response
    send_whatsapp.send_poll("Room A")
    mock_send.assert_called()


@patch("send_whatsapp.send_request_with_retries")
def test_send_reminder(mock_send: MagicMock) -> None:
    """Test send_reminder calls send_request_with_retries and handles response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response
    send_whatsapp.send_reminder("Room A")
    mock_send.assert_called()


def test_write_last_poll_id_writes_env_locally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When not running in Actions, write_last_poll_id should write LAST_POLL_MESSAGE_ID to .env and to os.environ."""
    monkeypatch.chdir(tmp_path)
    # Ensure no GITHUB_* env vars
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    send_whatsapp.write_last_poll_id("TESTMSG123")
    env_path = tmp_path / ".env"
    assert env_path.exists()
    content = env_path.read_text(encoding="utf-8")
    assert "LAST_POLL_MESSAGE_ID=TESTMSG123" in content
    assert os.environ.get("LAST_POLL_MESSAGE_ID") == "TESTMSG123"


@patch("send_whatsapp.requests.put")
def test_write_last_poll_id_calls_github_api(mock_put: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """When running in Actions, write_last_poll_id should call the GitHub Actions Variables API."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_put.return_value = mock_resp
    send_whatsapp.write_last_poll_id("MSGID-GH-1")
    mock_put.assert_called_once()
    # verify env var was also set for current process
    assert os.environ.get("LAST_POLL_MESSAGE_ID") == "MSGID-GH-1"


@patch("send_whatsapp.send_request_with_retries")
@patch("send_whatsapp._get_message_with_retries")
def test_send_reminder_uses_get_counts(
    mock_get: MagicMock, mock_send: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """send_reminder should GET the message by id, parse counts and include quoted id and missing prefix when <10."""
    monkeypatch.setenv("LAST_POLL_MESSAGE_ID", "PsrIDamMcQrSYK8-wlMBq53kUCFYFA")
    # Mock GET response to include poll results with count=3
    mock_get_resp = MagicMock()
    mock_get_resp.json.return_value = {"message": {"poll": {"results": [{"count": 3}, {"count": 0}, {"count": 0}]}}}
    mock_get.return_value = mock_get_resp
    mock_send_resp = MagicMock()
    mock_send_resp.status_code = 200
    mock_send.return_value = mock_send_resp
    send_whatsapp.send_reminder("Room A")
    mock_send.assert_called_once()
    args, _ = mock_send.call_args
    # send_request_with_retries called with (url, payload)
    assert args[0].endswith("/messages/text")
    payload = args[1]
    assert payload["quoted"] == "PsrIDamMcQrSYK8-wlMBq53kUCFYFA"
    assert payload["body"].startswith("חסר ")
