# tests/test_llm.py
"""Retry policy of chat_json(), with a fake client: no network, no API key, no real waiting."""
from types import SimpleNamespace

import openai
import pytest

from app import llm


def _error(cls):
    """An SDK error instance without a fake HTTP response; chat_json() only checks its class."""
    return cls.__new__(cls)


class FakeClient:
    """Plays back a list of outcomes: an exception to raise, or reply text to return."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=outcome))])


@pytest.fixture
def sleeps(monkeypatch):
    """Record the waits instead of sleeping."""
    recorded = []
    monkeypatch.setattr(llm.time, "sleep", recorded.append)
    return recorded


def use(monkeypatch, outcomes):
    fake = FakeClient(outcomes)
    monkeypatch.setattr(llm, "_client", lambda: fake)
    return fake


def test_retries_429_and_5xx_then_succeeds(monkeypatch, sleeps):
    fake = use(monkeypatch, [_error(openai.RateLimitError), _error(openai.InternalServerError), '{"ok": true}'])
    assert llm.chat_json([{"role": "user", "content": "hi"}]) == '{"ok": true}'
    assert fake.calls == 3
    assert sleeps == [2, 4]


def test_gives_up_after_three_retries(monkeypatch, sleeps):
    fake = use(monkeypatch, [_error(openai.RateLimitError)] * 4)
    with pytest.raises(llm.LLMUnavailable):
        llm.chat_json([{"role": "user", "content": "hi"}])
    assert fake.calls == 4
    assert sleeps == [2, 4, 8]


def test_timeout_is_not_retried(monkeypatch, sleeps):
    fake = use(monkeypatch, [_error(openai.APITimeoutError)])
    with pytest.raises(llm.LLMUnavailable):
        llm.chat_json([{"role": "user", "content": "hi"}])
    assert fake.calls == 1
    assert sleeps == []


def test_bad_key_propagates_unchanged(monkeypatch, sleeps):
    fake = use(monkeypatch, [_error(openai.AuthenticationError)])
    with pytest.raises(openai.AuthenticationError):
        llm.chat_json([{"role": "user", "content": "hi"}])
    assert fake.calls == 1
