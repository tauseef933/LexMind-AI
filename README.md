# LexMind AI

**Multi-agent legal intelligence platform for document analysis, risk detection, and hearing preparation.**

LexMind AI helps legal professionals turn case files into actionable insight. Upload contracts, evidence, and pleadings; ask questions in natural language; and get cited answers, risk assessments, timelines, and hearing prep — powered by a multi-agent RAG pipeline.

---

## Features

| Capability | Description |
|---|---|
| **Case management** | Create and organize matters with client, court, and document context |
| **Document intelligence** | Ingest PDFs/DOCX with OCR fallback; hybrid retrieval over case knowledge |
| **Streaming chat** | SSE responses with live agent-trace visibility as the system routes work |
| **Risk detection** | Surface HIGH / MEDIUM / LOW risks across evidence, procedure, and timeline |
| **Case summaries** | Extract parties, claims, key dates, evidence, and open issues |
| **Timeline builder** | Reconstruct chronological events from case documents |
| **Hearing prep** | Generate structured prep sheets with argument strategy |
| **Legal research** | Route precedent / statute queries to a dedicated research agent |
| **Source citations** | Answers grounded in retrieved document chunks with source references |

---

## Architecture

```
┌─────────────────┐     SSE / REST      ┌──────────────────────────────┐
│  React + Vite   │ ◄─────────────────► │  FastAPI + LangGraph         │
│  TypeScript UI  │                     │  Orchestrator                │
└─────────────────┘                     └──────────────┬───────────────┘
                                                       │
                    ┌──────────────────────────────────┼──────────────────────────────────┐
                    ▼                  ▼                ▼                  ▼
             Document Agent     Analytics Agent   Action Agent     Research Agent
                    │                  │                │                  │
                    └──────────────────┴────────────────┴──────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              ChromaDB           BM25 + Cohere           Groq LLM
           (dense vectors)         (rerank)         llama-3.3-70b
```

**Orchestrator flow:** `route_query` → `run_agents_parallel` → `merge_results` → stream tokens to the client.

| Agent | Responsibility |
|---|---|
| `document_agent` | Case files, facts, obligations, summaries, risks |
| `analytics_agent` | Billing, invoices, payments, financial totals |
| `action_agent` | Emails, calendar events, PDF generation |
| `research_agent` | Case law, statutes, external precedents |

**Retrieval stack:** Sentence-Transformers embeddings → ChromaDB + BM25 hybrid search → Cohere reranking → Groq generation.

---

## Tech Stack

| Layer | Stack |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router |
| **Backend** | Python, FastAPI, SQLAlchemy, Uvicorn |
| **Agents** | LangGraph, LangChain, Groq (`llama-3.3-70b-versatile`) |
| **RAG** | ChromaDB, Sentence-Transformers, Rank-BM25, Cohere Rerank |
| **Ingestion** | PyMuPDF, python-docx, Tesseract OCR |
| **Deploy** | Frontend → Vercel · Backend → Railway |

---

## Project Structure

```
LexMind-AI/
├── backend/
│   ├── api/                 # FastAPI app, middleware, routes
│   │   └── routes/          # chat, cases, documents, analytics
│   ├── agents/              # LangGraph orchestrator + specialised agents
│   ├── rag/                 # Ingestion, embeddings, retrieval, reranker
│   ├── services/            # Summary, risks, timeline, hearing prep
│   ├── models/              # SQLAlchemy models & DB session
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      # Chat, dashboard, document viewer
│   │   ├── pages/           # Case list & case dashboard
│   │   ├── hooks/           # Chat, cases, streaming
│   │   └── lib/             # API client & types
│   ├── package.json
│   └── .env.local.example
├── uploads/                 # Uploaded case documents (runtime)
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python** 3.11+
- **Node.js** 18+
- **Tesseract OCR** (for scanned PDFs)
- API keys: [Groq](https://console.groq.com/), [Cohere](https://dashboard.cohere.com/), [Serper](https://serper.dev/) (research)

### 1. Clone the repository

```bash
git clone https://github.com/your-org/LexMind-AI.git
cd LexMind-AI
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Edit `backend/.env` with your keys:

```env
GROQ_API_KEY=your-groq-api-key
COHERE_API_KEY=your-cohere-api-key
SERPER_API_KEY=your-serper-api-key
ALLOWED_ORIGINS=http://localhost:5173
SECRET_KEY=
```

Leave `SECRET_KEY` empty for local development (API-key auth disabled).

Start the API:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health)

### 3. Frontend setup

```bash
cd frontend
npm install
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS / Linux
```

Ensure `frontend/.env.local` points at the API:

```env
VITE_API_URL=http://localhost:8000
```

Start the UI:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET/POST` | `/cases` | List / create cases |
| `GET/DELETE` | `/cases/{id}` | Fetch / archive a case |
| `GET` | `/cases/{id}/messages` | Chat history |
| `GET` | `/cases/{id}/summary` | Structured case summary |
| `GET` | `/cases/{id}/timeline` | Event timeline |
| `GET` | `/cases/{id}/risks` | Risk analysis |
| `POST` | `/cases/{id}/prep` | Hearing preparation sheet |
| `POST` | `/upload` | Upload & ingest a document |
| `GET` | `/cases/{id}/documents` | List case documents |
| `POST` | `/chat` | Streaming multi-agent chat (SSE) |
| `GET` | `/billing` | Billing analytics |

Interactive docs (when the server is running): [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq LLM API key |
| `GROQ_MODEL` | No | Defaults to `llama-3.3-70b-versatile` |
| `COHERE_API_KEY` | Yes | Cohere rerank API key |
| `SERPER_API_KEY` | For research | Serper web search key |
| `DATABASE_URL` | No | Defaults to SQLite `./lexmind.db` |
| `CHROMA_PERSIST_PATH` | No | Defaults to `./chroma_db` |
| `ALLOWED_ORIGINS` | Yes (prod) | Comma-separated CORS origins |
| `SECRET_KEY` | Prod | Enables API-key middleware when set |
| `MAX_FILE_SIZE_MB` | No | Upload size limit (default `50`) |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Yes | Backend base URL |
| `VITE_API_KEY` | Prod | Must match backend `SECRET_KEY` when auth is enabled |

---

## Deployment

- **Backend:** Railway (`railway.toml` / `Procfile`) — set env vars in the Railway dashboard
- **Frontend:** Vercel — set `VITE_API_URL` to your Railway API URL; update `vercel.json` rewrite destination if used

In production, set a strong `SECRET_KEY` on the backend and the same value as `VITE_API_KEY` on the frontend.

---

## Usage Walkthrough

1. Create a new case (name, client, court).
2. Upload PDFs or DOCX files — they are chunked, embedded, and indexed per case.
3. Open the case dashboard and ask questions (e.g. *What are the key obligations in the contract?*).
4. Review streaming answers, agent traces, and cited sources.
5. Run **summary**, **risks**, **timeline**, or **hearing prep** from the analytics panel.

---

## License

Private / all rights reserved unless otherwise specified by the repository owner.

---

## Disclaimer

LexMind AI is an assistive tool for legal professionals. Outputs are AI-generated and may contain errors. Always verify citations, risks, and strategy against primary source documents and qualified legal judgment before relying on them in practice.
