"""
Shared Groq LLM access.

get_llm(temperature)      → cached ChatGroq client with timeout + retries
ask(llm, messages)        → reply text of one LLM call
ask_streaming(llm, messages, on_token) → same, streaming fragments to on_token
parse_json_response(text) → dict/list parsed from an LLM reply, tolerating
                            markdown code fences around the JSON
"""

import json
import os
import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from pydantic import SecretStr

from config import GROQ_MODEL

_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


@lru_cache(maxsize=8)
def get_llm(temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(
        model=GROQ_MODEL,
        api_key=SecretStr(os.getenv("GROQ_API_KEY", "")),
        temperature=temperature,
        timeout=_TIMEOUT,
        max_retries=_MAX_RETRIES,
    )


def message_text(message: BaseMessage) -> str:
    """Text of a chat message (content may be a string or a list of parts)."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        part if isinstance(part, str) else str(part.get("text", ""))
        for part in content
    )


def ask(llm: BaseChatModel, messages: Sequence[BaseMessage]) -> str:
    """Invoke the model and return its reply as stripped text."""
    return message_text(llm.invoke(list(messages))).strip()


TokenCallback = Callable[[str], None]


def ask_streaming(
    llm: BaseChatModel,
    messages: Sequence[BaseMessage],
    on_token: Optional[TokenCallback] = None,
) -> str:
    """
    Like ask(), but streams the reply: on_token is called with each text
    fragment as it arrives. Returns the full reply text.
    Falls back to a single non-streaming call when on_token is None.
    """
    if on_token is None:
        return ask(llm, messages)
    parts: list[str] = []
    for chunk in llm.stream(list(messages)):
        text = message_text(chunk)
        if text:
            parts.append(text)
            on_token(text)
    return "".join(parts)


def parse_json_response(raw: str) -> Any:
    """Parse JSON from an LLM reply; raises ValueError if none is found."""
    text = _FENCE.sub("", raw.strip()).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        # Fall back to the outermost {...} or [...] block in the reply
        starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
        if not starts:
            raise ValueError("No JSON found in LLM response") from err
        start = min(starts)
        end = text.rfind("}" if text[start] == "{" else "]")
        return json.loads(text[start:end + 1])
