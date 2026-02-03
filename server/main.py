from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone 
from datetime import timedelta
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "devices.db"
EXPECTED_TOKEN = "dev-token-123"

app = FastAPI(title="Agent Monitoring Server")


class AgentPayload(BaseModel):
    device_id: str
    hostname: str
    cpu: float
    ram: float
    disk: float
    uptime_sec: int


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            hostname TEXT,
            last_seen TEXT,
            last_payload_json TEXT
        )
        """
    )
    con.commit()
    con.close()


@app.on_event("startup")
def startup():
    init_db()


@app.post("/ingest")
@app.post("/ingest")
def ingest(payload: AgentPayload, x_auth_token: str = Header(default="")):
    if x_auth_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO devices (device_id, hostname, last_seen, last_payload_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            hostname=excluded.hostname,
            last_seen=excluded.last_seen,
            last_payload_json=excluded.last_payload_json
        """,
        (payload.device_id, payload.hostname, now, json.dumps(payload.dict())),
    )

    con.commit()
    con.close()
    return {"ok": True, "ts_utc": now}


@app.get("/devices")
def devices():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT device_id, hostname, last_seen, last_payload_json FROM devices")
    rows = cur.fetchall()
    con.close()

    now = datetime.now(timezone.utc)
    offline_after = timedelta(seconds=30)

    result = []

    for r in rows:
        last_seen_dt = datetime.fromisoformat(r[2])
        online = (now - last_seen_dt) <= offline_after

        result.append(
            {
                "device_id": r[0],
                "hostname": r[1],
                "last_seen": r[2],
                "online": online,
                "last_payload": json.loads(r[3]) if r[3] else None,
            }
        )

    return result

