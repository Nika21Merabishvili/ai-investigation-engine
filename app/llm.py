# app/llm.py
"""The one place that talks to the LLM: Gemini through its OpenAI-compatible endpoint.

Retry policy (ours, so the SDK's own retries are off with max_retries=0):
- 429, 5xx and connection errors: retry after 2, 4 and 8 seconds, then give up.
- Timeout (30 s): give up at once; four 30-second waits would be worse than an error.
- Anything else (400 bad request, 401/403 bad key, 404 unknown model): our bug, so it
  propagates unchanged instead of hiding behind a "busy" message.
Giving up raises LLMUnavailable, whose message is safe to show to users.
"""
import logging
import time
from functools import lru_cache

import openai
from openai import OpenAI

from app import config

log = logging.getLogger(__name__)

FRIENDLY_MESSAGE = "The AI service is busy right now. Please try again in a minute."


class LLMUnavailable(Exception):
    """The LLM could not be reached. str(error) is safe to show to users."""


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    """Create the client once, on first use."""
    if not config.GEMINI_API_KEY or not config.GEMINI_MODEL:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_MODEL in .env (or the environment)")
    return OpenAI(
        api_key=config.GEMINI_API_KEY,
        base_url=config.GEMINI_BASE_URL,
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=0,  # one retry policy only: the loop in _create()
    )


def chat_json(messages: list[dict]) -> str:
    """Send the messages, ask for a JSON object, and return the reply text.

    Parsing stays with the caller (answer.py), because only the caller knows the expected shape.
    """
    response = _create(messages=messages, response_format={"type": "json_object"})
    return response.choices[0].message.content or ""


def chat_with_tools(messages: list[dict], tools: list[dict], tool_choice: str = "auto"):
    """Send the messages with tools and return the whole assistant message.

    msg.tool_calls is a list, or None when the model answers in msg.content.
    Append it with messages.append(msg.model_dump(exclude_none=True)), not rebuilt by hand:
    Gemini puts thought signatures in each tool call's extra_content and rejects a follow-up without them.
    No response_format here; agent.py asks for JSON in the prompt instead.
    """
    return _create(messages=messages, tools=tools, tool_choice=tool_choice).choices[0].message


def _create(**kwargs):
    """One chat completion with the retry policy in the module docstring."""
    waits = [*config.LLM_RETRY_WAITS, None]  # None marks the last attempt
    for attempt, wait in enumerate(waits, start=1):
        try:
            return _client().chat.completions.create(model=config.GEMINI_MODEL, **kwargs)
        except openai.APITimeoutError as error:
            # APITimeoutError is a subclass of APIConnectionError, so this clause must come first.
            log.warning("LLM timed out after %s s", config.LLM_TIMEOUT_SECONDS)
            raise LLMUnavailable(FRIENDLY_MESSAGE) from error
        except (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError) as error:
            if wait is None:
                log.warning("LLM failed %d times, giving up: %r", attempt, error)
                raise LLMUnavailable(FRIENDLY_MESSAGE) from error
            log.warning("LLM attempt %d failed (%r), retrying in %s s", attempt, error, wait)
            time.sleep(wait)
