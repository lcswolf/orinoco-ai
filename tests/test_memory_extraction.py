"""Tests for conservative model-generated memory extraction."""

from orinoco.chat.routes import extract_memory_candidates


def test_memory_extractor_keeps_only_safe_durable_facts() -> None:
    raw = """[
      "User prefers concise, practical answers.",
      "User's password is super-secret.",
      "User's email is person@example.com.",
      "User has a medical diagnosis."
    ]"""

    assert extract_memory_candidates(raw) == [
        "User prefers concise, practical answers."
    ]


def test_memory_extractor_handles_fenced_json_and_duplicates() -> None:
    raw = 'Here are memories:\n```json\n["Likes hiking", "Likes hiking.", "Enjoys cooking"]\n```'

    assert extract_memory_candidates(raw) == ["Likes hiking", "Enjoys cooking"]


def test_memory_extractor_rejects_invalid_or_non_array_output() -> None:
    assert extract_memory_candidates("I think the user likes music.") == []
    assert extract_memory_candidates('{"memory": "likes music"}') == []
