import os
import re
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
QDRANT_URL = "your qdrant url"
QDRANT_COLLECTION = "your collection name"
GENAI_API_KEY = os.getenv("GENAI_API_KEY")
EMBEDDING_MODEL = "your embedding model"

# ================= CLIENTS =================
qdrant = QdrantClient(url=QDRANT_URL)
genai_client = genai.Client(api_key=GENAI_API_KEY)

# ================= APP =================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= UI =================
@app.get("/")
def serve_ui():
    return FileResponse("frontend/index.html")

# ================= DEBUG =================
@app.get("/api/debug/all")
def debug_all():
    points, _ = qdrant.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=20,
        with_payload=True
    )
    return [p.payload for p in points]

# ================= HELPERS =================
def normalize_name(name: str | None):
    if not name:
        return None
    return re.sub(r"\s+", " ", name.strip().lower())

# ================= QUERY PARSER =================
def parse_query_to_filters(query: str):
    q = query.lower()
    words = set(re.findall(r"\b\w+\b", q))
    filters = {}

    # ---------- PRIORITY ----------
    for p in ["low", "medium", "high", "urgent"]:
        if p in words:
            filters["priority"] = p
            break

    # ---------- STATUS ----------
    for s in ["pending", "active", "declined", "rejected", "draft", "deleted"]:
        if s in words:
            filters["status"] = s
            break

    # ---------- ASSIGNED TO ----------
    m = re.search(r"assigned to ([a-zA-Z ]+)", q)
    if m:
        filters["assigned_to_name"] = normalize_name(m.group(1))

    # ---------- ASSIGNED BY ----------
    m = re.search(r"assigned by ([a-zA-Z ]+)", q)
    if m:
        filters["assigned_by_name"] = normalize_name(m.group(1))

    return filters

# ================= SEARCH API =================
@app.post("/api/search")
async def search(payload: dict):
    query = payload.get("query", "").strip()
    limit = payload.get("limit", 10)

    if not query:
        return {"tasks": []}

    filters = parse_query_to_filters(query)

    # ---------- BUILD FILTER ----------
    q_filter = None
    if filters:
        q_filter = Filter(
            must=[
                FieldCondition(
                    key=k,
                    match=MatchValue(value=v)
                )
                for k, v in filters.items()
            ]
        )

    # ---------- EMBEDDING ----------
    embedding = None
    try:
        resp = genai_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query
        )
        embedding = resp.embeddings[0].values
    except Exception as e:
        print("Embedding failed:", e)

    # ---------- SEARCH ----------
    hits = []

    if embedding:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=embedding,
            query_filter=q_filter,
            limit=limit,
            with_payload=True
        )
    else:
        points, _ = qdrant.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=limit,
            with_payload=True,
            scroll_filter=q_filter
        )
        hits = points

    # ---------- RESPONSE ----------
    tasks = []
    for h in hits:
        p = h.payload or {}
        tasks.append({
            "id": p.get("task_id"),
            "title": p.get("title"),
            "description": p.get("description"),
            "priority": p.get("priority"),
            "status": p.get("status"),
            "progress": p.get("progress"),
            "assigned_to": p.get("assigned_to_name"),
            "assigned_by": p.get("assigned_by_name"),
            "due_date": p.get("target_date_ts"),
        })

    return {"tasks": tasks}
