# NeuroFab AI

### The Industrial Intelligence Fabric

Turn industrial documents into a queryable knowledge graph, then ask questions
that are answered from those documents and cite them.

Upload a PDF (manual, SOP, inspection report). NeuroFab extracts the text,
indexes it for semantic search, and uses an LLM to extract entities and
relationships into a knowledge graph. The Copilot answers questions by
retrieving relevant passages and graph paths, then reasoning over that evidence.

**Answers are AI drafts for review.** Every nonempty answer field must cite a
passage supplied to the model, with a matching verbatim quote. Missing or invalid
references produce an insufficient-evidence response. A quote match verifies
attribution, not whether a claim follows from the quote: confidence is therefore
null and `grounded` is false; insufficient-evidence responses also have no risk
rating. Check original sources before acting. Provider
failures return a clear, retryable error.

---

## Key features

- Upload and process industrial manuals, SOPs, and inspection reports
- Search document passages with Qdrant and explore relationships in Neo4j
- Ask the Copilot questions with document citations and evidence quotes
- Manage authenticated users, workspaces, and role-based access
- Run PostgreSQL, Qdrant, and Neo4j locally with Docker Compose

## Tech stack

| Area | Technologies |
|---|---|
| Frontend | Next.js 16 App Router, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, SQLAlchemy, LangGraph |
| Data | PostgreSQL, Qdrant, Neo4j |
| AI | Google Gemini for reasoning and embeddings |
| Infrastructure | Docker and Docker Compose |

## Project structure

```text
NeuroFabAI/
├── frontend/              # Next.js application
├── backend/               # FastAPI API, migrations, and tests
├── docker-compose.yml     # Local database services
└── README.md
```

---

## Architecture

```
┌───────────────────────────────┐        ┌──────────────────────────────────┐
│  Next.js 16 (App Router)      │        │  FastAPI                         │
│                               │        │                                  │
│  (auth)/  login, register     │  HTTPS │  /auth      JWT + refresh cookie  │
│  (app)/   dashboard, copilot, │◄──────►│  /workspaces  tenancy + members   │
│           hub, graph,         │  JSON  │  /documents   upload + pipeline   │
│           analytics, settings │  SSE   │  /graph       entities + edges    │
│                               │        │  /search      hybrid retrieval    │
│  verified session guards      │        │  /chat        Copilot + history   │
└───────────────────────────────┘        └────────────┬─────────────────────┘
                                                      │
              ┌───────────────────────┬───────────────┼───────────────┐
              ▼                       ▼               ▼               ▼
      ┌───────────────┐      ┌───────────────┐ ┌───────────┐  ┌─────────────┐
      │  PostgreSQL   │      │    Qdrant     │ │   Neo4j   │  │  Gemini API │
      │ source of     │      │ passage       │ │ knowledge │  │ reasoning + │
      │ truth         │      │ vectors       │ │ graph     │  │ embeddings  │
      └───────────────┘      └───────────────┘ └───────────┘  └─────────────┘
```

**PostgreSQL is the source of truth.** Qdrant and Neo4j are derived indexes:
`documents.extracted_knowledge` holds every entity ever extracted, so the graph
can be rebuilt from the database.

### Backend layers

| Layer | Path | Responsibility |
|---|---|---|
| API | `app/api/v1/endpoints/` | HTTP, validation, status codes. No business logic. |
| Dependencies | `app/api/deps.py` | Session, authentication, **workspace authorisation** |
| Services | `app/services/` | Business logic, one service per domain |
| Providers | `app/services/{llm,embeddings,vectorstore,graph,storage}/` | Swappable integrations behind an interface |
| Agents | `app/services/agents/` | Retrieval → analysis → synthesis workflow |
| Repositories | `app/repositories/` | Reusable query helpers |
| Models | `app/models/` | SQLAlchemy 2.0 ORM |
| Schemas | `app/schemas/` | Pydantic request/response contracts |
| Tasks | `app/tasks/` | Ingestion pipeline |

Every integration sits behind an abstract base class, so swapping Gemini for
another model, or Qdrant for another vector store, means adding one file and
changing one setting.

### The Copilot workflow

```
Coordinator ──plan──► SearchAgent ──► GraphAgent ──► ReliabilityAgent ──► Coordinator
              (resolve  (vector       (traverse       (classify graph      (synthesise
               entities) retrieval)    subgraph)       facts)               with LLM)
```

The first four steps are deterministic retrieval and classification. Only the
final synthesis step calls the language model, and it is constrained to a
validated JSON schema. The server checks claim coverage, source IDs, and quoted
text. Only references used by the answer are returned as citations. Graph
extraction also rejects evidence quotes absent from the supplied document text.

---

## Setup

### Requirements

- Python 3.12+
- Node.js 20+
- Docker (for PostgreSQL, Qdrant, Neo4j)
- A Google Gemini API key — https://aistudio.google.com/apikey

Clone the repository before following the setup steps:

```bash
git clone https://github.com/Prashantasp/NeuroFabAI.git
cd NeuroFabAI
```

### 1. Infrastructure

```bash
docker compose up -d
```

Starts PostgreSQL (5432), Qdrant (6333) and Neo4j (7687).

### 2. Backend

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env          # then set GOOGLE_API_KEY
alembic upgrade head          # create the schema
uvicorn app.main:app --reload
```

API: http://localhost:8000 — interactive docs at http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

> **Use one hostname consistently.** Browsers treat `localhost` and `127.0.0.1`
> as different sites, which makes the `SameSite=Lax` session cookie cross-site
> and silently unsettable — login appears to succeed, then bounces back. With
> `NEXT_PUBLIC_API_URL` unset the client derives the API host from the page, so
> either works as long as you do not mix them.

### Commands

| | Backend | Frontend |
|---|---|---|
| Develop | `uvicorn app.main:app --reload` | `npm run dev` |
| Test | `pytest` | — |
| Lint | — | `npm run lint` |
| Type check | — | `npm run typecheck` |
| Build | — | `npm run build` |
| Start | `uvicorn app.main:app` | `npm run start` |
| Migrate | `alembic upgrade head` | — |

Backend tests need no external services: they run against SQLite with a stubbed
model provider, so they are fast and cost nothing.

---

## Configuration

Full documentation with defaults: [`backend/.env.example`](backend/.env.example)
and [`frontend/.env.example`](frontend/.env.example).

### Required

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | backend | PostgreSQL connection string |
| `GOOGLE_API_KEY` | backend | Gemini key. **Server-side only — never sent to the browser.** |
| `SECRET_KEY` | backend | Signs access tokens. 32+ random chars. |
| `JWT_SECRET` | backend | Signs refresh tokens. 32+ random chars, **different** from `SECRET_KEY`. |
| `BACKEND_CORS_ORIGINS` | backend | Exact frontend origins |
| `NEXT_PUBLIC_API_URL` | frontend | API base URL (required in production) |

Generate secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Without a Gemini key

Everything except AI still works: sign-in, uploads, text extraction, chunking,
local deterministic embeddings, vector search, and the whole UI. The Copilot
returns *"AI features are not configured on this server"* and graph extraction
is skipped. Nothing is faked or stubbed to look like it worked.

---

## Deployment

### Production checklist

The app **refuses to start** with `ENVIRONMENT=production` unless:

- `SECRET_KEY` and `JWT_SECRET` are unique, 32+ characters, and differ
- `COOKIE_SECURE=true`
- A PostgreSQL `DATABASE_URL` for shared job ownership
- A shared `QDRANT_URL` and `GRAPH_BACKEND=neo4j`; production never silently falls back to local indexes
- `BACKEND_CORS_ORIGINS` contains no `http://` origins and no wildcard

This is deliberate: booting with the placeholder secrets from `.env.example`
would let anyone forge a session token.

Also do:

```bash
# 1. Apply migrations before starting the new version
alembic upgrade head

# 2. Serve behind TLS. Set COOKIE_SAMESITE=none only if the API and the app are
#    on different sites (then COOKIE_SECURE must be true).

# 3. Run the API with multiple workers behind a reverse proxy
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

`/docs`, `/redoc` and `/openapi.json` are disabled automatically in production.

### Frontend

```bash
cd frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1 npm run build
npm run start
```

Session restoration asks the API to validate its cookie; frontend cookie visibility
is not used as proof of login. Prefer app/API subdomains on the same site or a
same-origin reverse proxy. For genuinely different sites, set COOKIE_SAMESITE=none
and COOKIE_SECURE=true; browsers that block third-party cookies require the
same-site or same-origin arrangement. Set CORS to the exact frontend HTTPS origin.

### Scaling notes

Current scaling constraints:

- **Rate limiting** (`app/core/rate_limit.py`) is an in-process fixed window.
  Behind multiple replicas each enforces its own budget. Swap
  `InMemoryRateLimitBackend` for a Redis-backed one; the dependency signature
  does not change.
- **Ingestion jobs** are durable document rows, picked up immediately and polled
  every 10 seconds, including after restarts. A bounded thread pool executes them.
  PostgreSQL advisory locks serialize ingestion, reprocessing and deletion per
  workspace across API workers. Repeated crash recovery stops after three attempts
  and exposes a retryable failure. Vector point IDs are deterministic.
- **Storage** must be the same persistent volume on every API worker/replica.
  SQLite and the in-memory graph are development/test options only.
- **Deletion** commits a durable cleanup record with the database deletion.
  Pending records hide deleted material from vector and graph retrieval while
  the recovery loop retries index and file removal, including historical versions.
  Deleting or reprocessing during ingestion returns 409; retry after processing.
- **Graph ownership** is per workspace, document and canonical entity. Reads merge
  evidence without losing document provenance or parallel relationship types.
  Startup replays persisted extractions into both graph backends. Stop old workers
  before this upgrade so legacy writers cannot overwrite the new graph shape.

Apply `alembic upgrade head` before running this version; it adds the
`document_cleanup` outbox. Do not downgrade while pending cleanup records remain.

---

## Security

| Concern | Approach |
|---|---|
| Session storage | Access token in memory only; refresh token in an `HttpOnly` cookie. JavaScript cannot read the refresh cookie; access tokens are not persisted. |
| Token rotation | Refresh tokens rotate on use. Replaying a rotated token revokes every session for that user. |
| Passwords | bcrypt; 10+ chars with mixed case and a digit; common passwords rejected; account locks after 8 failures. |
| Tenancy | Every workspace-scoped endpoint resolves `X-Workspace-ID` through `get_workspace_context`, which verifies membership. Graph node identity is `(workspace_id, source_document_id, canonical_name)`, so two tenants never share an entity. |
| Authorisation | Enforced server-side on every request. The frontend's route guards are UX, not security. |
| Uploads | Extension, MIME type **and** magic bytes checked; filenames sanitised; paths confined to the storage root; size capped. |
| Rate limiting | Auth, chat and upload endpoints. Chat is limited because it costs money. |
| Errors | Internal details logged with a request ID; clients get a safe message and that ID. |
| Headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP, HSTS in production. |

---

## Testing

```bash
cd backend && pytest
cd frontend && npm test && npm run typecheck && npm run lint && npm run build
```

Backend coverage focuses on what would actually break a user:

| File | Covers |
|---|---|
| `test_auth.py` | Registration, password policy, login, lockout, refresh rotation and reuse detection, privilege escalation |
| `test_tenancy.py` | Anonymous access to every protected endpoint; cross-workspace reads; per-workspace graph isolation |
| `test_copilot.py` | Real model output vs. failure, persistence, history, mode prompts, citation validation and abstention, streaming |
| `test_documents.py` | Upload validation, magic bytes, path traversal, pagination totals, cross-tenant access, reprocess |
| `test_retrieval.py` | Ingest → embed → index → retrieve, and that retrieved text reaches the prompt |
| `test_pipeline.py` | Chunking, scanned-PDF failure, malformed model output, knowledge validation |
| `test_llm_provider.py` | Provider error classification and retry policy |
| `test_config.py` | Production startup hardening |

`frontend/e2e-verify.mjs` drives a real browser through the full journey
(register → login → navigate → theme → Copilot → responsive → sign out) and
captures screenshots. Run it with both servers up:

```bash
cd frontend && node e2e-verify.mjs
```


### Live database integration tests

Start the local services with `docker compose up -d --wait`, then run from
`backend` in PowerShell:

```powershell
$env:NEUROFAB_LIVE_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest integration_tests -q
```

The suite requires localhost PostgreSQL, Neo4j and Qdrant endpoints. It creates
and migrates a unique temporary PostgreSQL database, uses isolated graph
workspaces and a unique Qdrant collection, and removes its data afterward. It
covers a fresh migration chain, JSONB cleanup records, cross-process lock
exclusion and crash release, refresh rotation, graph provenance and atomic
replacement, ingestion/replay, and document/workspace cleanup. AI responses are
controlled fixtures; these tests do not call a paid model.


### Real-AI browser verification

The verified local configuration uses `LLM_MODEL=gemini-3.5-flash-lite` and
`EMBEDDING_MODEL=gemini-embedding-2`. The API key stays in `backend/.env`.
For the default API port 8000, leave `NEXT_PUBLIC_API_URL` empty so the browser
uses its own hostname. A changed public API URL requires a frontend rebuild.

With the backend and frontend running, run from `frontend`:

```powershell
$env:RUN_REAL_AI_E2E = "1"
node e2e-real-ai.mjs
```

This opt-in test makes real, potentially billed provider requests. It registers
an isolated test account, logs in, uploads `fixtures/verification-pump-manual.pdf`,
checks graph identities and provenance, and asks three questions with known
expected answers (including a fact the PDF does not specify). Test credentials,
reports and screenshots are saved only in ignored `frontend/test-results/real-ai/`.
Subsequent runs reuse that account and document. Set `REPROCESS_DOCUMENT=1` to
retry ingestion through the UI after changing provider settings.

Copilot sections not relevant to a question remain empty. Every populated
section must still have a valid source quote. Risk ratings require an explicit
classification in a cited source; factual answers do not default to Low risk.


---

## Screenshots

- Dashboard
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041307" src="https://github.com/user-attachments/assets/2283094b-01da-4fd7-a50b-12c0dc8afe95" />

- Document Upload
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041329" src="https://github.com/user-attachments/assets/f1d41630-e3b7-44a6-9f00-1636a820777b" />

- Knowledge Graph
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041335" src="https://github.com/user-attachments/assets/7361cfbe-8caf-4ef3-9512-a1857df49720" />

- AI Chat Interface
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041324" src="https://github.com/user-attachments/assets/f47c21f8-2cf9-4751-88ab-a3dfa03f94b0" />


---

## Roadmap

- Evaluate additional LLM providers
- Add shared rate limiting for multiple API replicas
- Package and validate Kubernetes deployment

Authentication, workspace roles, streaming responses, document versioning, and
the agent workflow are already implemented; see the sections above for their
current behavior and deployment constraints.

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request

---

## Author

**Prashant Nigam**

- GitHub: https://github.com/Prashantasp

---
