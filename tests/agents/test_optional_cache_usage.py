import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from utils.history_util import MessageHistory


@pytest.mark.parametrize(
    "read,created,expected",
    [(None, None, 12), (None, 5, 17), (5, None, 17), (3, 4, 19), (0, 0, 12)],
)
def test_optional_cache_counters(read, created, expected):
    client = Mock()
    client.messages.count_tokens.return_value.input_tokens = 1
    history = MessageHistory("example-model", "", 100, client)
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=2,
        cache_read_input_tokens=read,
        cache_creation_input_tokens=created,
    )
    asyncio.run(history.add_message("assistant", "reply", usage))
    assert history.total_tokens == expected


def test_usage_without_cache_fields():
    client = Mock()
    client.messages.count_tokens.return_value.input_tokens = 1
    history = MessageHistory("example-model", "", 100, client)
    asyncio.run(
        history.add_message(
            "assistant", "reply", SimpleNamespace(input_tokens=10, output_tokens=2)
        )
    )
    assert history.total_tokens == 12
