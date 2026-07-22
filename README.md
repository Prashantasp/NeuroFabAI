# NeuroFab AI: The Industrial Intelligence Fabric

NeuroFab AI is an advanced GraphRAG-based AI platform that converts disconnected industrial documents (SOPs, logs, manuals) into a living Knowledge Graph, orchestrated by specialized AI agents.

## Project Structure
- `frontend/`: Next.js 14 App Router, Tailwind CSS, Shadcn UI
- `backend/`: FastAPI, LangGraph, Qdrant & Neo4j integration
- `docker-compose.yml`: Infrastructure services (Postgres, Qdrant, Neo4j)

## Quick Start

### 1. Start Infrastructure
```bash
docker-compose up -d
```

### 2. Start Backend
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn api.main:app --reload
```

### 3. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000
