import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "devices.db"
EXPECTED_TOKEN = os.getenv("EXPECTED_TOKEN", "dev-token-123")

app = FastAPI(title="Agent Monitoring Server")


class AgentPayload(BaseModel):
    agent_version: str
    status: str
    last_error: str

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


@app.get("/health")
def health():
    return {"ok": True}


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
    for device_id, hostname, last_seen, last_payload_json in rows:
        last_seen_dt = datetime.fromisoformat(last_seen)
        online = (now - last_seen_dt) <= offline_after

        result.append(
            {
                "device_id": device_id,
                "hostname": hostname,
                "last_seen": last_seen,
                "online": online,
                "last_payload": json.loads(last_payload_json) if last_payload_json else None,
            }
        )

    return result
