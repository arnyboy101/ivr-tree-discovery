"""Tests for transcript_parser — deduplication, filtering, and Claude response parsing."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

import transcript_parser
from transcript_parser import (
    _deduplicate_options,
    _normalize_label,
    parse_transcript,
)


# --- Unit tests for helper functions (no mocking needed) ---


class TestNormalizeLabel:
    def test_strips_whitespace(self):
        assert _normalize_label("  Billing  ") == "billing"

    def test_lowercases(self):
        assert _normalize_label("Technical Support") == "technical support"

    def test_empty(self):
        assert _normalize_label("") == ""


class TestDeduplicateOptions:
    def test_removes_navigation_options(self):
        options = [
            {"dtmf_key": "1", "label": "Billing"},
            {"dtmf_key": "9", "label": "Repeat"},
            {"dtmf_key": "0", "label": "Main Menu"},
        ]
        result = _deduplicate_options(options)
        assert len(result) == 1
        assert result[0]["label"] == "Billing"

    def test_prefers_dtmf_over_voice(self):
        options = [
            {"dtmf_key": "say1", "label": "Billing"},
            {"dtmf_key": "1", "label": "Billing"},
        ]
        result = _deduplicate_options(options)
        assert len(result) == 1
        assert result[0]["dtmf_key"] == "1"

    def test_keeps_voice_if_no_dtmf(self):
        options = [
            {"dtmf_key": "say1", "label": "Track a package"},
        ]
        result = _deduplicate_options(options)
        assert len(result) == 1
        assert result[0]["dtmf_key"] == "say1"

    def test_case_insensitive_dedup(self):
        options = [
            {"dtmf_key": "1", "label": "billing"},
            {"dtmf_key": "say1", "label": "Billing"},
        ]
        result = _deduplicate_options(options)
        assert len(result) == 1
        assert result[0]["dtmf_key"] == "1"

    def test_empty_list(self):
        assert _deduplicate_options([]) == []

    def test_all_navigation(self):
        options = [
            {"dtmf_key": "9", "label": "Repeat"},
            {"dtmf_key": "0", "label": "Go back"},
            {"dtmf_key": "*", "label": "Start over"},
        ]
        result = _deduplicate_options(options)
        assert len(result) == 0


# --- Integration tests with mocked Claude ---


def make_claude_response(content: dict) -> MagicMock:
    """Build a mock Claude API response."""
    msg = MagicMock()
    block = MagicMock()
    block.text = json.dumps(content)
    msg.content = [block]
    return msg


@pytest.mark.asyncio
class TestParseTranscript:
    async def test_empty_transcript(self):
        result = await parse_transcript("")
        assert result == {"prompt_text": "", "options": []}

    async def test_short_transcript(self):
        result = await parse_transcript("hi")
        assert result == {"prompt_text": "", "options": []}

    @patch.object(transcript_parser, "client")
    async def test_parses_dtmf_menu(self, mock_client):
        mock_client.messages.create = AsyncMock(
            return_value=make_claude_response({
                "prompt_text": "Welcome to USPS",
                "human_transfer": False,
                "options": [
                    {"dtmf_key": "1", "label": "Track a package"},
                    {"dtmf_key": "2", "label": "Buy stamps"},
                    {"dtmf_key": "3", "label": "Schedule pickup"},
                ],
            })
        )
        result = await parse_transcript("user: Press 1 for tracking, 2 for stamps, 3 for pickup")
        assert result["prompt_text"] == "Welcome to USPS"
        assert len(result["options"]) == 3
        assert result["options"][0]["dtmf_key"] == "1"
        assert result["human_transfer"] is False

    @patch.object(transcript_parser, "client")
    async def test_human_transfer_detected(self, mock_client):
        mock_client.messages.create = AsyncMock(
            return_value=make_claude_response({
                "prompt_text": "Connecting you to a representative",
                "human_transfer": True,
                "options": [],
            })
        )
        result = await parse_transcript("user: Please hold while I connect you to a representative")
        assert result["human_transfer"] is True
        assert result["options"] == []

    @patch.object(transcript_parser, "client")
    async def test_filters_navigation_from_claude(self, mock_client):
        mock_client.messages.create = AsyncMock(
            return_value=make_claude_response({
                "prompt_text": "Main menu",
                "human_transfer": False,
                "options": [
                    {"dtmf_key": "1", "label": "Billing"},
                    {"dtmf_key": "9", "label": "Repeat"},
                    {"dtmf_key": "*", "label": "Main Menu"},
                ],
            })
        )
        result = await parse_transcript("user: Press 1 for billing, 9 to repeat, star for main menu")
        assert len(result["options"]) == 1
        assert result["options"][0]["label"] == "Billing"

    @patch.object(transcript_parser, "client")
    async def test_handles_markdown_code_block(self, mock_client):
        content = {
            "prompt_text": "Welcome",
            "human_transfer": False,
            "options": [{"dtmf_key": "1", "label": "Help"}],
        }
        msg = MagicMock()
        block = MagicMock()
        block.text = f"```json\n{json.dumps(content)}\n```"
        msg.content = [block]
        mock_client.messages.create = AsyncMock(return_value=msg)

        result = await parse_transcript("user: Press 1 for help")
        assert len(result["options"]) == 1

    @patch.object(transcript_parser, "client")
    async def test_handles_invalid_json(self, mock_client):
        msg = MagicMock()
        block = MagicMock()
        block.text = "this is not json"
        msg.content = [block]
        mock_client.messages.create = AsyncMock(return_value=msg)

        result = await parse_transcript("user: some transcript text here that is long enough")
        assert result["options"] == []
        assert len(result["prompt_text"]) > 0  # Falls back to transcript[:200]

    @patch.object(transcript_parser, "client")
    async def test_handles_api_error(self, mock_client):
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))

        result = await parse_transcript("user: Press 1 for billing")
        assert result == {"prompt_text": "", "options": []}
