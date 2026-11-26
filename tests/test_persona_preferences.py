"""Tests for private user preferences and administrator-managed persona settings."""

import pytest

from orinoco.db import (
    create_user,
    get_assistant_persona,
    get_user_preferences,
    initialise_database,
    update_assistant_persona,
    update_user_preferences,
)


def test_user_preferences_have_safe_defaults_and_are_account_scoped(tmp_path) -> None:
    """Each account starts with independent bright/friendly/balanced defaults."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    first = create_user("prefsfirst", "a-long-test-password-123", database_path=database)
    second = create_user("prefssecond", "another-long-password-456", database_path=database)

    assert get_user_preferences(first.id, database_path=database) == {
        "voice": "bright",
        "tone": "friendly",
        "answer_detail": "balanced",
        "language": "auto",
        "auto_save_memories": True,
    }
    updated = update_user_preferences(
        first.id,
        voice="calm",
        tone="direct",
        answer_detail="detailed",
        database_path=database,
    )

    assert updated == {"voice": "calm", "tone": "direct", "answer_detail": "detailed", "language": "auto", "auto_save_memories": True}
    assert get_user_preferences(first.id, database_path=database) == updated
    assert get_user_preferences(second.id, database_path=database)["voice"] == "bright"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("voice", "pirate"),
        ("tone", "hostile"),
        ("answer_detail", "infinite"),
        ("language", "fr"),
    ],
)
def test_user_preferences_reject_unsupported_values(tmp_path, field, value) -> None:
    """Only the small set of reviewed preference values can be stored."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    user = create_user("prefuser", "a-long-test-password-123", database_path=database)
    values = {"voice": "bright", "tone": "friendly", "answer_detail": "balanced", "language": "auto"}
    values[field] = value

    with pytest.raises(ValueError, match="Unsupported"):
        update_user_preferences(user.id, database_path=database, **values)


def test_admin_persona_defaults_and_update_persist(tmp_path) -> None:
    """The shared persona starts at 65% humour and persists administrator changes."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)

    default = get_assistant_persona(database_path=database)
    assert default["humour_level"] == 65
    assert "British English" in default["core_persona"]

    updated = update_assistant_persona(
        core_persona="Be calm, curious and practical. Use short examples.",
        humour_level=40,
        database_path=database,
    )
    assert updated == {
        "core_persona": "Be calm, curious and practical. Use short examples.",
        "humour_level": 40,
    }
    assert get_assistant_persona(database_path=database) == updated


@pytest.mark.parametrize(
    ("core_persona", "humour_level"),
    [
        (" ", 65),
        ("x" * 2001, 65),
        ("Valid persona", -1),
        ("Valid persona", 101),
        ("Valid persona", True),
    ],
)
def test_admin_persona_rejects_invalid_values(tmp_path, core_persona, humour_level) -> None:
    """Blank/oversized persona text and out-of-range humour settings are rejected."""
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)

    with pytest.raises(ValueError):
        update_assistant_persona(
            core_persona=core_persona,
            humour_level=humour_level,
            database_path=database,
        )
