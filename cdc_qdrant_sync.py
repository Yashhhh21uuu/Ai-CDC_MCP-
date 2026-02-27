
import os
import json
import re
import time
import signal
from datetime import timezone
from dateutil import parser

import psycopg2
from psycopg2.extras import RealDictCursor
from kafka import KafkaConsumer

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, PointStruct, Distance, PointIdsList

from google import genai
from dotenv import load_dotenv

load_dotenv()

# ==============================
# CONFIGURATION
# ==============================
DB_HOST = "your host"
DB_PORT = 54321
DB_USER = "your user"
DB_PWD = "your password"
DB_NAME = "your database name"
SCHEMA = "your schema name"

QDRANT_URL = "your qdrant url"
QDRANT_COLLECTION = "your collection name"
VECTOR_SIZE = 3072

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
EMBEDDING_MODEL = "your embedding model"

KAFKA_TOPIC = "your kafka topic"
KAFKA_BOOTSTRAP = "your kafka bootstrap servers"

HEARTBEAT_INTERVAL = 30

# ==============================
# ENUM MAPS (DB → STRING)
# ==============================
PRIORITY_MAP = {
    1: "low",
    2: "medium",
    3: "high",
    4: "urgent"
}

STATUS_MAP = {
    0: "deleted",
    1: "active",
    2: "pending",
    3: "declined",
    4: "rejected",
    5: "draft",
    6: "schedule_later"
}

PROGRESS_MAP = {
    0: "todo",
    1: "doing",
    2: "done"
}

# ==============================
# GLOBAL STATE
# ==============================
running = True
processed_events = 0

# ==============================
# SIGNAL HANDLING
# ==============================
def shutdown_handler(sig, frame):
    global running
    print("🛑 Graceful shutdown requested...")
    running = False

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ==============================
# CLIENTS
# ==============================
qdrant = QdrantClient(url=QDRANT_URL)
genai_client = genai.Client(api_key=GENAI_API_KEY)

# ==============================
# HELPERS
# ==============================
def to_epoch(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        try:
            dt = parser.isoparse(dt)
        except Exception:
            return None
    return int(dt.replace(tzinfo=timezone.utc).timestamp())

def generate_embedding(text, retries=3):
    for i in range(retries):
        try:
            return genai_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text
            ).embeddings[0].values
        except Exception as e:
            print(f"⚠ Embedding retry {i+1}: {e}")
            time.sleep(1)
    return None

# ==============================
# QDRANT SETUP
# ==============================
def setup_qdrant():
    if not qdrant.collection_exists(QDRANT_COLLECTION):
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        print("🆕 Qdrant collection created")
    else:
        print("✅ Qdrant collection exists")

# ==============================
# SEMANTIC TEXT (FOR EMBEDDINGS)
# ==============================
def build_semantic_text(task):
    description = re.sub('<[^<]+?>', '', task.get("description") or "")
    return f"""
    Task title: {task.get("title", "")}
    Description: {description}
    Priority: {PRIORITY_MAP.get(task.get("priority"), "")}
    Status: {STATUS_MAP.get(task.get("status"), "")}
    """.strip()

# ==============================
# QDRANT PAYLOAD (UI READY)
# ==============================
def build_task_payload(task):
    return {
        # identity
        "task_id": task["id"],

        # 🔥 UI DISPLAY FIELDS (STRINGS)
        "title": task.get("title"),
        "description": task.get("description"),

        "priority": PRIORITY_MAP.get(task.get("priority")),
        "status": STATUS_MAP.get(task.get("status")),
        "progress": PROGRESS_MAP.get(task.get("progress")),

        # 🔥 USER NAMES (STRINGS)
        "assigned_by_name": task.get("assigned_by_name"),
        "assigned_to_name": task.get("assigned_to_name"),

        # dates
        "target_date_ts": to_epoch(task.get("target_date")),
        "updated_at_ts": to_epoch(task.get("updated_at")),
    }

# ==============================
# USER NAME ENRICHMENT (CDC)
# ==============================
def enrich_user_names(task, cursor):
    if task.get("by_user_id"):
        cursor.execute(
            f"SELECT name FROM {SCHEMA}._user WHERE id = %s",
            (task["by_user_id"],)
        )
        r = cursor.fetchone()
        task["assigned_by_name"] = r["name"] if r else None

    if task.get("to_user_id"):
        cursor.execute(
            f"SELECT name FROM {SCHEMA}._user WHERE id = %s",
            (task["to_user_id"],)
        )
        r = cursor.fetchone()
        task["assigned_to_name"] = r["name"] if r else None

    return task

# ==============================
# UPSERT / DELETE
# ==============================
def upsert_task(task):
    global processed_events

    semantic_text = build_semantic_text(task)
    embedding = generate_embedding(semantic_text)

    if not embedding:
        print(f"❌ Embedding failed for task {task['id']}")
        return

    payload = build_task_payload(task)

    qdrant.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            PointStruct(
                id=task["id"],
                vector=embedding,
                payload=payload
            )
        ]
    )

    processed_events += 1
    print(f"✅ Upserted task {task['id']}")

def delete_task(task_id):
    qdrant.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=PointIdsList(points=[task_id])
    )
    print(f"🗑️ Deleted task {task_id}")

# ==============================
# MAIN
# ==============================
def main():
    setup_qdrant()

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PWD,
        dbname=DB_NAME
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # ---------- BULK INDEX (JOIN _user) ----------
    cursor.execute(f"""
    SELECT
      t.*,
      u1.name AS assigned_by_name,
      u2.name AS assigned_to_name
    FROM {SCHEMA}.task t
    LEFT JOIN {SCHEMA}._user u1 ON u1.id = t.by_user_id
    LEFT JOIN {SCHEMA}._user u2 ON u2.id = t.to_user_id
    """)

    rows = cursor.fetchall()
    print(f"🚀 Bulk indexing {len(rows)} tasks")

    for task in rows:
        upsert_task(task)

    # ---------- CDC CONSUMER ----------
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda x: json.loads(x.decode()),
        group_id="qdrant-cdc-v1",
        auto_offset_reset="latest",
        enable_auto_commit=True
    )

    last_heartbeat = time.time()
    print("🚀 CDC listener started")

    while running:
        records = consumer.poll(timeout_ms=1000, max_records=10)
        for batch in records.values():
            for record in batch:
                value = record.value
                payload = value.get("payload") if value else None
                if not payload:
                    continue

                if payload.get("op") == "d":
                    before = payload.get("before")
                    if before:
                        delete_task(before["id"])
                else:
                    after = payload.get("after")
                    if after:
                        after = enrich_user_names(after, cursor)
                        upsert_task(after)

        if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
            last_heartbeat = time.time()
            print(f"💓 Alive | Events processed: {processed_events}")

    consumer.close()
    cursor.close()
    conn.close()
    print("✅ Shutdown complete")

if __name__ == "__main__":
    main()

