# BravousAI

> **Status**:  **In Improvement / Active Development**  
> *This project is actively being refined with ongoing architectural enhancements across multi-agent graph workflows, real-time reasoning streaming, and publication-grade research synthesis.*

---

## Overview

**BravousAI** is an enterprise-grade, autonomous multi-agent deep research and artifact-generation platform. It empowers researchers, technical strategists, and decision-makers by turning complex, open-ended inquiries into rigorously verified, citation-backed intelligence reports and interactive web artifacts.

Powered by **LangGraph**, **FastAPI**, and a modern **Next.js (React 19)** frontend, BravousAI coordinates a swarm of specialized AI agents to autonomously plan research, query the live internet, extract primary evidence, identify contradictions, and synthesize publication-ready reports with interactive source verification.

---

## Core Capabilities

### Autonomous Deep Research Engine
- **Multi-Iteration Scoping & Planning**: Formulates surgical sub-queries across distinct thematic angles.
- **Evidence Extraction**: Automatically reads, cleans, and tags claims, exact quotes, and quantitative metrics from web sources.
- **Contradiction Detection & Gap Resolution**: Surfaces conflicting claims across sources with intellectual honesty (e.g. diverging casualty figures or missile test counts).
- **Publication-Grade Synthesis**: Produces executive-level intelligence summaries, structured analytical chapters, and complete bibliographies.

### Modern Reasoning & Streaming UI (Claude-Style)
- **Unboxed Inline Reasoning**: Clean thought triggers (`Thought for 6s ›` or `Thinking... ⌄`) that sit natively on the canvas without visual clutter.
- **Interactive Tool Progress Cards**: Expandable `Searched the web ⌄` cards revealing discrete search queries and status telemetry.
- **Interactive Inline Citation Badges**: Inline source chips (`Wikipedia ↗`, `Congress.gov ↗`) featuring floating hover preview cards with document titles, favicons, and direct links.

### Live Interactive Artifacts
- **Sandboxed Dynamic Generation**: Autonomous generation of self-contained HTML/JS applications, data visualizations, and dashboards.
- **Live Preview Panel**: Built-in split-view panel with interactive iframe rendering, live reload, and code inspection.

### Enterprise Workspaces & Context Management
- **Project Isolation**: Organize chats and knowledge into dedicated project workspaces.
- **Context Injection**: Attach custom instructions and project files (PDFs, Markdown, text) that automatically steer research agents.
- **Resilient Checkpointing**: Session and graph checkpoints backed by PostgreSQL and MinIO for reliable state restoration.

---

## System Architecture

```mermaid
graph TD
    User([User Client]) --> NextJS[Next.js App Router Frontend]
    NextJS --> |REST & SSE Streams| FastAPI[FastAPI Backend Server]
    
    FastAPI --> |State Checkpoints| DB[(PostgreSQL)]
    FastAPI --> |Artifacts & Files| MinIO[(MinIO Storage)]
    FastAPI --> |Caching & Telemetry| Redis[(Redis)]
    
    FastAPI --> |Executes| AgentGraph[LangGraph Multi-Agent Workflow]
    
    subgraph AgentGraph [Stateful Multi-Agent Orchestration]
        direction TB
        Entry([Entrypoint]) --> Supervisor[Supervisor Agent]
        Supervisor -->|Direct Chat| Conversation[Conversation Agent]
        Supervisor -->|Deep Query| Researcher[Deep Research Subgraph]
        Supervisor -->|UI / Code Request| Presentation[Presentation Agent]
        
        subgraph Researcher [Research Subgraph]
            Plan[Scoping & Outline Planner] --> Search[Web Search & Query Broadening]
            Search --> Extraction[Source Extraction & Evidence Ledger]
            Extraction --> GapCheck[Gap & Contradiction Analyzer]
            GapCheck -->|Needs More Evidence| Search
            GapCheck -->|Sufficient Evidence| Synthesis[Publication Report Synthesis]
        end
        
        Presentation --> Artifacts[Sandboxed Interactive Artifacts]
    end
```

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Next.js 15+ (App Router), React 19, TypeScript, Vanilla CSS Design System, Remark GFM |
| **Backend API** | Python 3.12+, FastAPI, Uvicorn, Pydantic v2 |
| **Agent Orchestration** | LangGraph, LangChain Core, OpenAI API / OpenRouter (Nemotron, Claude, etc.) |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (Async), Alembic, asyncpg / psycopg3 |
| **Storage & Caching** | MinIO (S3-compatible Object Storage), Redis |
| **Web Research** | Tavily Search API, BeautifulSoup4, HTTPX |
| **Containerization** | Docker, Docker Compose |

---

## Project Structure

```text
bravous/
├── app/                               # Python Backend
│   ├── main.py                        # FastAPI entrypoint, lifecycle, and middleware
│   ├── ai/                            # Multi-Agent Architecture
│   │   ├── graph.py                   # Master LangGraph workflow definition
│   │   ├── agents/                    # Specialized agent modules
│   │   │   ├── main_agent/            # Supervisor & conversation orchestrator
│   │   │   ├── deep_research/         # Deep research subgraph (planner, search, synthesis)
│   │   │   └── presentation/          # Artifact generator
│   │   ├── states/                    # Graph states & memory definitions
│   │   └── tools/                     # Search, extraction, and artifact tools
│   ├── api/                           # Route Handlers
│   │   └── v1/                        # Chat, Projects, Files, Artifacts, Auth
│   ├── core/                          # LLM provider configs, security, settings
│   ├── db/                            # SQLAlchemy models, sessions, migrations
│   └── services/                      # File management, S3 storage, streaming
├── frontend/                          # Next.js React Frontend
│   ├── app/                           # App Router routes & layouts
│   ├── components/                    # Modular UI components
│   │   └── chat/                      # MessageList, ReasoningBlock, WorkflowTraceCard
│   │       └── renderers/             # InlineCitationPill, InlineVisualRenderer
│   ├── hooks/                         # useChatStream, useConversations, useProjects
│   └── lib/                           # API client, SSE streaming handlers
├── docs/                              # Technical guides and architecture documentation
├── docker-compose.yml                 # PostgreSQL, MinIO, and Redis services
├── pyproject.toml                     # Python dependencies (uv / pip)
└── Readme.md                          # Project documentation
```

---

## Getting Started

### 1. Prerequisites
- **Python**: 3.12 or higher
- **Node.js**: 18.x or 20.x+ (and `npm`)
- **Docker**: For running PostgreSQL, MinIO, and Redis
- **OpenRouter / OpenAI API Key**: With access to high-reasoning models (e.g. `nvidia/nemotron-3-super-120b-a12b:free` or Claude)
- **Tavily API Key**: For web search and content extraction

---

### 2. Infrastructure Setup (Docker Compose)
Start the background database, storage, and caching containers:
```bash
docker-compose up -d
```
This starts:
- **PostgreSQL** on port `5432`
- **MinIO** on port `9000` (Console: `9001`)
- **Redis** on port `6379`

---

### 3. Backend Setup

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # Linux / macOS
   source .venv/bin/activate
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -e .
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   *Essential variables*:
   ```env
   OPENROUTER_API_KEY=your_openrouter_key
   DO_MODEL=nvidia/nemotron-3-super-120b-a12b:free
   TAVILY_API_KEY=your_tavily_key
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bravous
   MINIO_ENDPOINT=localhost:9000
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin
   REDIS_URL=redis://localhost:6379/0
   ```

4. **Run Database Migrations**:
   ```bash
   alembic upgrade head
   ```

5. **Start the FastAPI Server**:
   ```bash
   python -m uvicorn app.main:app --port 8001 --reload
   ```
   The backend API will be live at `http://127.0.0.1:8001`.

---

### 4. Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the Next.js development server**:
   ```bash
   npm run dev
   ```
   The web application will be accessible at `http://localhost:3000`.

---

## Active Improvements & Roadmap

The project is under continuous development with the following active milestones:
- [x] **Claude-Style Response Flow**: Unboxed inline reasoning, live expandable tool telemetry, and interactive citation preview popovers.
- [x] **Real-Time Reasoning Streaming**: Sub-2s time-to-first-token reasoning streaming over Server-Sent Events (SSE).
- [ ] **Automated Section Deduplication**: Enforce singular executive summaries and eliminate repetitive post-synthesis sections.
- [ ] **Multi-Format Export**: Export research reports and artifacts directly to PDF, DOCX, and standalone HTML bundles.
- [ ] **Collaborative Workspaces**: Real-time multi-user project workspaces and shared research libraries.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
