"""Tests for conversation persistence and strict account isolation."""

from orinoco.db import (
    add_conversation_message,
    create_conversation,
    create_user,
    get_conversation,
    get_recent_messages,
    initialise_database,
    list_conversations,
)


def test_conversation_history_is_saved_and_ordered(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    user = create_user("nugget", "a-long-test-password-123", database_path=database)
    conversation_id = create_conversation(
        user.id,
        title="A first chat",
        database_path=database,
    )

    add_conversation_message(user.id, conversation_id, "user", "Hello", database_path=database)
    add_conversation_message(
        user.id, conversation_id, "assistant", "Hello there!", database_path=database
    )

    conversation = get_conversation(user.id, conversation_id, database_path=database)
    assert conversation is not None
    assert conversation["title"] == "A first chat"
    assert [message["role"] for message in conversation["messages"]] == [
        "user",
        "assistant",
    ]
    assert get_recent_messages(user.id, conversation_id, database_path=database) == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello there!"},
    ]


def test_users_cannot_list_read_or_append_to_another_users_conversation(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    owner = create_user("owner", "a-long-test-password-123", database_path=database)
    other = create_user("other", "another-long-password-456", database_path=database)
    conversation_id = create_conversation(
        owner.id,
        title="Private chat",
        database_path=database,
    )

    assert list_conversations(other.id, database_path=database) == []
    assert get_conversation(other.id, conversation_id, database_path=database) is None
    assert (
        add_conversation_message(
            other.id,
            conversation_id,
            "assistant",
            "This must not be stored",
            database_path=database,
        )
        is None
    )
    assert get_conversation(owner.id, conversation_id, database_path=database)["messages"] == []


def test_message_content_and_role_are_validated(tmp_path) -> None:
    database = tmp_path / "orinoco.sqlite3"
    initialise_database(database)
    user = create_user("nugget", "a-long-test-password-123", database_path=database)
    conversation_id = create_conversation(user.id, database_path=database)

    try:
        add_conversation_message(user.id, conversation_id, "system", "not allowed", database_path=database)
    except ValueError as exc:
        assert "role" in str(exc)
    else:
        raise AssertionError("unsupported message role was accepted")

    try:
        add_conversation_message(user.id, conversation_id, "user", " ", database_path=database)
    except ValueError as exc:
        assert "message" in str(exc)
    else:
        raise AssertionError("empty message was accepted")
