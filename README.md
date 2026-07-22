# 🧠 NeuroFab AI
### The Industrial Intelligence Fabric

NeuroFab AI is an advanced **GraphRAG-powered AI platform** that transforms disconnected industrial knowledge—such as Standard Operating Procedures (SOPs), maintenance logs, technical manuals, and reports—into an intelligent, searchable **Knowledge Graph**.

Instead of relying solely on vector search, NeuroFab AI combines **Graph Retrieval-Augmented Generation (GraphRAG)** with specialized AI agents to understand relationships between machines, procedures, components, and documents, enabling accurate and context-aware responses for industrial workflows.

---

## ✨ Key Features

- 📄 Upload and process industrial documents
- 🕸️ GraphRAG-based knowledge retrieval
- 🧠 Knowledge Graph powered by Neo4j
- 🔍 Semantic search using Qdrant vector database
- 🤖 AI agents orchestrated with LangGraph
- 💬 Context-aware conversational assistant
- ⚡ FastAPI backend with REST APIs
- 🎨 Modern Next.js dashboard
- 🐳 Dockerized infrastructure

---

# 🏗️ Architecture

```
                 Industrial Documents
          (SOPs • Manuals • Reports • Logs)
                          │
                          ▼
                Document Processing Pipeline
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
 Vector Embeddings                 Entity Extraction
          │                               │
          ▼                               ▼
      Qdrant DB                    Neo4j Knowledge Graph
          └───────────────┬───────────────┘
                          ▼
                 LangGraph AI Agents
                          ▼
               GraphRAG Retrieval Engine
                          ▼
                  Context-Aware Answers
```

---

# 🚀 Tech Stack

### Frontend

- Next.js 14 (App Router)
- React
- TypeScript
- Tailwind CSS
- Shadcn UI

### Backend

- FastAPI
- LangGraph
- LangChain
- Python

### Databases

- Neo4j
- Qdrant
- PostgreSQL

### AI

- Google Gemini
- GraphRAG
- Vector Search

### DevOps

- Docker
- Docker Compose

---

# 📂 Project Structure

```
NeuroFabAI/
│
├── frontend/              # Next.js application
├── backend/               # FastAPI backend
├── docker-compose.yml     # Infrastructure services
└── README.md
```

---

# ⚙️ Quick Start

## 1. Clone the Repository

```bash
git clone https://github.com/Prashantasp/NeuroFabAI.git
cd NeuroFabAI
```

---

## 2. Start Infrastructure

```bash
docker-compose up -d
```

This launches:

- PostgreSQL
- Neo4j
- Qdrant

---

## 3. Start the Backend

```bash
cd backend

python -m venv venv
```

### Windows

```bash
.\venv\Scripts\Activate.ps1
```

### macOS/Linux

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn api.main:app --reload
```

---

## 4. Start the Frontend

```bash
cd frontend

npm install
npm run dev
```

---

## 🌐 Open the Application

Frontend

```
http://localhost:3000
```

Backend API

```
http://localhost:8000
```

API Documentation

```
http://localhost:8000/docs
```

---

# 📸 Screenshots


- Dashboard
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041307" src="https://github.com/user-attachments/assets/2283094b-01da-4fd7-a50b-12c0dc8afe95" />

- Document Upload
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041329" src="https://github.com/user-attachments/assets/f1d41630-e3b7-44a6-9f00-1636a820777b" />

- Knowledge Graph
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041335" src="https://github.com/user-attachments/assets/7361cfbe-8caf-4ef3-9512-a1857df49720" />

- AI Chat Interface
  <img width="1920" height="1080" alt="Screenshot 2026-07-22 041324" src="https://github.com/user-attachments/assets/f47c21f8-2cf9-4751-88ab-a3dfa03f94b0" />


---

# 🔮 Roadmap

- Multi-user authentication
- Role-based access control
- Streaming AI responses
- Document versioning
- Multi-agent collaboration
- Deployment on Kubernetes
- Support for additional LLM providers

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request

---

# 👨‍💻 Author

**Prashant Nigam**

- GitHub: https://github.com/Prashantasp

---
