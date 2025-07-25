"""
Unit tests for send_whatsapp.py, covering logging and WhatsApp message sending functions.
"""

# pylint: disable=wrong-import-order

import os
import sys
from unittest.mock import patch, MagicMock

import send_whatsapp


from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env file for local development
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def test_log_stdout(capsys):
    """Test that log outputs to stdout for notice level."""
    send_whatsapp.log("test notice", "notice")
    out, _ = capsys.readouterr()
    assert "test notice" in out


def test_log_stderr(capsys):
    """Test that log outputs to stderr for error level."""
    send_whatsapp.log("test error", "error")
    _, err = capsys.readouterr()
    assert "test error" in err


@patch("requests.post")
def test_send_request_with_retries_success(mock_post):
    """Test send_request_with_retries returns response on success."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    result = send_whatsapp.send_request_with_retries(
        "http://fake.url", {"key": "value"}
    )
    assert result is not None and result.ok


@patch("requests.post")
def test_send_request_with_retries_failure(mock_post):
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
def test_send_poll(mock_send):
    """Test send_poll calls send_request_with_retries and handles response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response
    send_whatsapp.send_poll()
    mock_send.assert_called()


@patch("send_whatsapp.send_request_with_retries")
def test_send_reminder(mock_send):
    """Test send_reminder calls send_request_with_retries and handles response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response
    send_whatsapp.send_reminder()
    mock_send.assert_called()
