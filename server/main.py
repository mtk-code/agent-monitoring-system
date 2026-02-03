import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

DB_PATH = Path(__file__).parent / "devices.db"
EXPECTED_TOKEN = os.getenv("EXPECTED_TOKEN", "dev-token-123")

app = FastAPI(title="Agent Monitoring Server")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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


class CommandCreate(BaseModel):
    command: str
    args: Optional[dict] = None


class CommandAck(BaseModel):
    success: bool
    message: Optional[str] = ""


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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            command TEXT,
            args_json TEXT,
            status TEXT,
            created_at TEXT,
            ack_at TEXT,
            result_json TEXT
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


@app.post("/devices/{device_id}/commands")
def enqueue_command(device_id: str, payload: CommandCreate, x_auth_token: str = Header(default="")):
    if x_auth_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

    now = datetime.now(timezone.utc).isoformat()
    args_json = json.dumps(payload.args or {})

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO commands (device_id, command, args_json, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (device_id, payload.command, args_json, now),
    )
    cmd_id = cur.lastrowid
    con.commit()
    con.close()

    return {"ok": True, "id": cmd_id, "created_at": now}


@app.get("/devices/{device_id}/commands/next")
def get_next_command(device_id: str, x_auth_token: str = Header(default="")):
    if x_auth_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        SELECT id, command, args_json, created_at FROM commands
        WHERE device_id = ? AND status = 'pending'
        ORDER BY id ASC LIMIT 1
        """,
        (device_id,)
    )
    row = cur.fetchone()
    con.close()

    if not row:
        return None

    cmd_id, command, args_json, created_at = row
    try:
        args = json.loads(args_json) if args_json else {}
    except Exception:
        args = {}

    return {"id": cmd_id, "command": command, "args": args, "created_at": created_at}


@app.post("/devices/{device_id}/commands/{command_id}/ack")
def ack_command(device_id: str, command_id: int, payload: CommandAck, x_auth_token: str = Header(default="")):
    if x_auth_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

    now = datetime.now(timezone.utc).isoformat()
    result_json = json.dumps({"success": payload.success, "message": payload.message or ""})

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        UPDATE commands SET status = 'acked', ack_at = ?, result_json = ?
        WHERE id = ? AND device_id = ?
        """,
        (now, result_json, command_id, device_id),
    )
    changed = cur.rowcount
    con.commit()
    con.close()

    if changed == 0:
        raise HTTPException(status_code=404, detail="command not found")

    return {"ok": True, "ack_at": now}


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


@app.get("/ui")
def ui(request: Request):
    # reuse devices logic to build display rows
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT device_id, hostname, last_seen, last_payload_json FROM devices")
    rows = cur.fetchall()
    con.close()

    now = datetime.now(timezone.utc)
    offline_after = timedelta(seconds=30)

    devices_list = []
    for device_id, hostname, last_seen, last_payload_json in rows:
        last_seen_dt = datetime.fromisoformat(last_seen)
        online = (now - last_seen_dt) <= offline_after
        last_payload = json.loads(last_payload_json) if last_payload_json else None

        devices_list.append({
            "device_id": device_id,
            "hostname": hostname,
            "last_seen": last_seen,
            "online": online,
            "last_payload": last_payload,
        })

    return templates.TemplateResponse("ui.html", {"request": request, "devices": devices_list, "token": EXPECTED_TOKEN})
