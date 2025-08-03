"""Unit tests for send_whatsapp.py, covering holiday logic, logging, and WhatsApp message sending functions."""

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import IO
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

import send_whatsapp


def open_test_file(file_path: Path) -> Callable[..., IO[str]]:
    """Create a mock-compatible function that opens the given file with any arguments.

    This is useful as a mock side_effect for Path.open in unit tests. It ensures
    that encoding and mode arguments are respected while avoiding type checker errors.
    """

    def opener(*args: object, **kwargs: object) -> IO[str]:
        # We assume text mode here (which is the default for Path.open)
        return file_path.open(*args, **kwargs)  # type: ignore[call-overload]

    return opener


@patch("send_whatsapp.Path")
@patch("send_whatsapp.datetime")
def test_is_today_holiday_found(mock_datetime: MagicMock, mock_path: MagicMock, tmp_path: Path) -> None:
    """Test is_today_holiday returns the holiday name if today is a holiday."""
    aware_now = datetime(2025, 8, 4, tzinfo=UTC)
    mock_datetime.now.return_value = aware_now
    mock_datetime.UTC = send_whatsapp.UTC
    # mock_datetime.side_effect not needed
    holidays_file = tmp_path / "holidays_2025.json"
    holidays_file.write_text(json.dumps({"2025-08-04": "Test Holiday"}))
    holidays_path_mock = MagicMock()
    holidays_path_mock.exists.return_value = True
    holidays_path_mock.open.side_effect = open_test_file(holidays_file)
    mock_path.return_value.__truediv__.return_value = holidays_path_mock
    result = send_whatsapp.is_today_holiday()
    assert result == "Test Holiday"


@patch("send_whatsapp.Path")
@patch("send_whatsapp.datetime")
def test_is_today_holiday_not_found(mock_datetime: MagicMock, mock_path: MagicMock, tmp_path: Path) -> None:
    """Test is_today_holiday returns None if today is not a holiday."""
    aware_now = datetime(2025, 8, 4, tzinfo=UTC)
    mock_datetime.now.return_value = aware_now
    mock_datetime.UTC = send_whatsapp.UTC
    # mock_datetime.side_effect not needed
    holidays_file = tmp_path / "holidays_2025.json"
    holidays_file.write_text(json.dumps({"2025-08-05": "Other Holiday"}))
    holidays_path_mock = MagicMock()
    holidays_path_mock.exists.return_value = True
    holidays_path_mock.open.side_effect = open_test_file(holidays_file)
    mock_path.return_value.__truediv__.return_value = holidays_path_mock
    result = send_whatsapp.is_today_holiday()
    assert result is None


@patch("send_whatsapp.Path")
@patch("send_whatsapp.datetime")
def test_is_today_holiday_file_missing(mock_datetime: MagicMock, mock_path: MagicMock) -> None:
    """Test is_today_holiday returns None and logs warning if file is missing."""
    aware_now = datetime(2025, 8, 4, tzinfo=UTC)
    mock_datetime.now.return_value = aware_now
    mock_datetime.UTC = send_whatsapp.UTC
    # mock_datetime.side_effect not needed
    mock_path().__truediv__().exists.return_value = False
    with patch("send_whatsapp.log") as mock_log:
        result = send_whatsapp.is_today_holiday()
        assert result is None
        assert mock_log.called


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
    send_whatsapp.send_poll()
    mock_send.assert_called()


@patch("send_whatsapp.send_request_with_retries")
def test_send_reminder(mock_send: MagicMock) -> None:
    """Test send_reminder calls send_request_with_retries and handles response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response
    send_whatsapp.send_reminder()
    mock_send.assert_called()
