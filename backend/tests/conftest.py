"""
Shared test setup.

Everything runs against a throw-away SQLite DB, Chroma store and uploads dir,
and LLM calls go to FakeLLM — no network, no API keys, no real data touched.
"""

import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

# ---------------------------------------------------------------------------
# Isolate the environment BEFORE any app module is imported
# ---------------------------------------------------------------------------
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *a, **k: False  # never read the developer's real .env

TMP = Path(tempfile.mkdtemp(prefix="lexmind_tests_"))
os.environ.update(
    DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
    CHROMA_PERSIST_PATH=str(TMP / "chroma"),
    SECRET_KEY="",
    GROQ_API_KEY="test-key",
    COHERE_API_KEY="",
    SERPER_API_KEY="",
    LOG_LEVEL="WARNING",
    RATE_LIMIT_ENABLED="false",  # test_rate_limit.py turns it on for its own app
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage  # noqa: E402

import storage  # noqa: E402

storage.UPLOADS_DIR = TMP / "uploads"
storage.UPLOADS_DIR.mkdir()

from api.main import app  # noqa: E402
from models.database import init_db  # noqa: E402

init_db()


# ---------------------------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------------------------
Responder = Callable[[str], str]


class FakeLLM:
    """
    Stand-in for ChatGroq. `responder(prompt_text) -> reply` decides each
    answer; stream() splits the reply into a few chunks. Every prompt is
    recorded in .calls for assertions.
    """

    def __init__(self, responder: Responder) -> None:
        self.responder = responder
        self.calls: list[str] = []

    def _reply(self, messages: list[BaseMessage]) -> str:
        prompt = "\n".join(str(m.content) for m in messages)
        self.calls.append(prompt)
        return self.responder(prompt)

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        return AIMessage(content=self._reply(messages))

    def stream(self, messages: list[BaseMessage]) -> Iterator[AIMessageChunk]:
        reply = self._reply(messages)
        words = reply.split(" ")
        for i, word in enumerate(words):
            yield AIMessageChunk(content=word if i == len(words) - 1 else word + " ")


def default_responder(prompt: str) -> str:
    """Sensible replies for each kind of prompt the app sends."""
    if "routing orchestrator" in prompt:
        return json.dumps({"subtasks": [{"agent": "document_agent", "query": "q", "priority": 1}]})
    if "rewrite follow-up" in prompt:
        return "standalone question"
    return "Fake answer."


_LLM_MODULES = [
    "agents.orchestrator",
    "agents.document_agent",
    "agents.research_agent",
    "agents.action_agent",
    "agents.analytics_agent",
    "services.case_summary",
    "services.risk_detector",
    "services.timeline_builder",
    "services.hearing_prep",
]


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """Route every get_llm() call in the app to one FakeLLM."""
    import importlib

    llm = FakeLLM(default_responder)
    for name in _LLM_MODULES:
        monkeypatch.setattr(importlib.import_module(name), "get_llm", lambda temperature=0: llm)
    return llm


# ---------------------------------------------------------------------------
# App fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def case_id(client: TestClient) -> str:
    return client.post("/cases", json={"name": "Test case"}).json()["id"]


@pytest.fixture
def no_ingest(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Skip real ingestion on upload; returns the list of ingest calls."""
    from api.routes import documents

    calls: list[dict] = []

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        return {"chunks_stored": 3, "page_count": 2, "doc_id": kwargs["doc_id"]}

    monkeypatch.setattr(documents, "ingest_document", fake_ingest)
    return calls


def sse_events(body: str) -> list[dict]:
    return [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:")]
