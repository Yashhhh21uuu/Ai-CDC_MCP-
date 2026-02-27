# 🚀 Taskity AI MCP Gemini Search

An AI-powered task search and prioritization system integrated with **Model Context Protocol (MCP)** and **OpenAI (Gemini-compatible LLM interface)**.

This project demonstrates advanced AI orchestration where natural language queries are converted into structured filters and executed via MCP tools.

---

## 🔥 Key Features

- Natural language task search
- AI-based filter extraction
- AI-powered task prioritization (0–100 scoring)
- MCP protocol integration (JSON-RPC)
- Dynamic tool invocation
- Client-side fallback filtering
- Production-ready FastAPI backend
- CORS-enabled frontend integration

---

## 🧠 System Architecture

```
Frontend (Search UI)
        ↓
FastAPI Backend
        ↓
AI Query Parser
        ↓
MCP Client (JSON-RPC)
        ↓
MCP Server Tools
        ↓
Task Data
```

---

## 🛠 Tech Stack

- Python 3.10+
- FastAPI
- OpenAI SDK
- MCP (Model Context Protocol)
- JSON-RPC
- Requests
- Python-dotenv
- Vanilla JS (Frontend)

---

## 🧠 AI Capabilities

### 1️⃣ Natural Language Filter Extraction

Examples:

- “tasks by meghana”
- “urgent tasks assigned to me due today”
- “high priority tasks from john in public pod”
- “overdue tasks from public pod”

Extracted filters:

```json
{
  "priority_labels": ["high"],
  "assigned_by": "john",
  "assigned_to": null,
  "due": null,
  "pod": "public",
  "only_overdue": false
}
```

---

### 2️⃣ AI Task Prioritization

Each task receives:

- `ai_priority_score` (0–100)
- `ai_priority_rank`

Scoring considers:

- Urgency (due dates)
- Importance
- Status
- Recency
- Query relevance
- User context

---

## 🔐 Environment Variables

Create a `.env` file:

```
OPENAI_API_KEY=your_key_here
MCP_URL=https://your-mcp-server.com
TASKITY_AUTH_TOKEN=your_token_here
MCP_PROTOCOL_VERSION=2025-03-26
```

Never commit `.env` to GitHub.

---

## 🚀 Running Locally

### 1️⃣ Install dependencies

```
pip install -r requirements.txt
```

### 2️⃣ Run backend

```
uvicorn backend.app:app --reload
```

### 3️⃣ Run frontend

```
cd frontend
python -m http.server 5500
```

Open:
```
http://127.0.0.1:5500
```

---

## 📡 API Endpoints

### POST `/ai/search`

Natural language search → MCP tool call → AI prioritization

### POST `/ai/prioritize`

Direct AI-based prioritization of provided tasks

---

## 🎯 Why This Project Is Impressive

This project demonstrates:

- AI agent-style architecture
- LLM-based filter extraction
- MCP protocol integration
- JSON-RPC communication
- Tool orchestration
- Production-safe fallbacks
- Backend engineering discipline

It combines:
- AI
- Systems design
- Protocol-level integration
- Real-world task automation

---

## 📌 Future Improvements

- Authentication layer
- Streaming AI responses
- Async MCP support
- Caching layer
- Docker deployment
- Multi-user support

---

## 👨‍💻 Author

Yashu  
AI/ML Engineer | Backend Developer

---

## ⚠️ Disclaimer

This project is for educational and portfolio purposes.
