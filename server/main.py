import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta, timedelta as td

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt

DB_PATH = Path(__file__).parent / "devices.db"
EXPECTED_TOKEN = os.getenv("EXPECTED_TOKEN", "dev-token-123")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-jwt-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

app = FastAPI(title="Agent Monitoring Server")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    # organizations and users
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            api_token TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT,
            org_id INTEGER
        )
        """
    )

    # add org_id column to devices and commands if missing
    def column_exists(table, column):
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        return column in cols

    if not column_exists('devices', 'org_id'):
        cur.execute("ALTER TABLE devices ADD COLUMN org_id INTEGER")
    if not column_exists('commands', 'org_id'):
        cur.execute("ALTER TABLE commands ADD COLUMN org_id INTEGER")

    # ensure a default organization exists with EXPECTED_TOKEN
    cur.execute("SELECT id FROM organizations WHERE api_token = ?", (EXPECTED_TOKEN,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO organizations (name, api_token) VALUES (?, ?)", ("default", EXPECTED_TOKEN))
        org_id = cur.lastrowid
        # create a default admin user
        default_pw = pwd_context.hash("admin")
        try:
            cur.execute("INSERT INTO users (email, password_hash, org_id) VALUES (?, ?, ?)", ("admin@local", default_pw, org_id))
        except Exception:
            pass
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
    # resolve organization by api token
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id FROM organizations WHERE api_token = ?", (x_auth_token,))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=401, detail="unauthorized")
    org_id = row[0]

    now = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """
        INSERT INTO devices (device_id, hostname, last_seen, last_payload_json, org_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            hostname=excluded.hostname,
            last_seen=excluded.last_seen,
            last_payload_json=excluded.last_payload_json,
            org_id=excluded.org_id
        """,
        (payload.device_id, payload.hostname, now, json.dumps(payload.dict()), org_id),
    )
    con.commit()
    con.close()

    return {"ok": True, "ts_utc": now}


@app.post("/devices/{device_id}/commands")
def enqueue_command(device_id: str, payload: CommandCreate, request: Request, x_auth_token: str = Header(default="")):
    # allow either org api token (agent) or logged-in user JWT
    org_id = resolve_org_from_request(request, x_auth_token)
    if not org_id:
        raise HTTPException(status_code=401, detail="unauthorized")

    now = datetime.now(timezone.utc).isoformat()
    args_json = json.dumps(payload.args or {})

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO commands (device_id, command, args_json, status, created_at, org_id)
        VALUES (?, ?, ?, 'pending', ?, ?)
        """,
        (device_id, payload.command, args_json, now, org_id),
    )
    cmd_id = cur.lastrowid
    con.commit()
    con.close()

    return {"ok": True, "id": cmd_id, "created_at": now}


@app.get("/devices/{device_id}/commands/next")
def get_next_command(device_id: str, x_auth_token: str = Header(default="")):
    # agent polls using X-Auth-Token; resolve org from token
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id FROM organizations WHERE api_token = ?", (x_auth_token,))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=401, detail="unauthorized")
    org_id = row[0]

    cur.execute(
        """
        SELECT id, command, args_json, created_at FROM commands
        WHERE device_id = ? AND status = 'pending' AND org_id = ?
        ORDER BY id ASC LIMIT 1
        """,
        (device_id, org_id)
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
    # allow either agent token or user JWT
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id FROM organizations WHERE api_token = ?", (x_auth_token,))
    row = cur.fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=401, detail="unauthorized")
    org_id = row[0]

    now = datetime.now(timezone.utc).isoformat()
    result_json = json.dumps({"success": payload.success, "message": payload.message or ""})

    cur.execute(
        """
        UPDATE commands SET status = 'acked', ack_at = ?, result_json = ?
        WHERE id = ? AND device_id = ? AND org_id = ?
        """,
        (now, result_json, command_id, device_id, org_id),
    )
    changed = cur.rowcount
    con.commit()
    con.close()

    if changed == 0:
        raise HTTPException(status_code=404, detail="command not found")

    return {"ok": True, "ack_at": now}


@app.get("/devices")
def devices(request: Request):
    # require JWT auth for listing devices (UI users)
    user = require_user_or_redirect(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return _devices_for_request(user)


def _devices_for_request(request_user):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if request_user:
        cur.execute("SELECT device_id, hostname, last_seen, last_payload_json FROM devices WHERE org_id = ?", (request_user['org_id'],))
    else:
        # no user -> return empty
        cur.execute("SELECT device_id, hostname, last_seen, last_payload_json FROM devices WHERE 0=1")
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


def resolve_org_from_request(request: Request, x_auth_token: str = ""):
    # prefer X-Auth-Token
    if x_auth_token:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("SELECT id FROM organizations WHERE api_token = ?", (x_auth_token,))
        r = cur.fetchone()
        con.close()
        if r:
            return r[0]

    # otherwise try JWT in cookie or header
    token = None
    auth = request.headers.get('Authorization')
    if auth and auth.lower().startswith('bearer '):
        token = auth.split(None, 1)[1]
    elif hasattr(request, 'cookies'):
        token = request.cookies.get('access_token')

    if not token:
        return None

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get('org_id')
    except Exception:
        return None


def create_access_token(data: dict, expires_minutes: int = JWT_EXPIRE_MINUTES):
    to_encode = data.copy()
    expire = datetime.utcnow() + td(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


@app.post('/auth/login')
def auth_login(body: dict, response: Response):
    email = body.get('email')
    password = body.get('password')
    if not email or not password:
        raise HTTPException(status_code=400, detail='missing email or password')

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT id, password_hash, org_id FROM users WHERE email = ?', (email,))
    row = cur.fetchone()
    con.close()
    if not row:
        raise HTTPException(status_code=401, detail='invalid credentials')
    user_id, password_hash, org_id = row
    if not pwd_context.verify(password, password_hash):
        raise HTTPException(status_code=401, detail='invalid credentials')

    token = create_access_token({"user_id": user_id, "org_id": org_id})
    # set cookie
    response.set_cookie('access_token', token, httponly=True)
    return {"access_token": token}


@app.get('/login')
def login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request})


def get_user_from_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    user_id = payload.get('user_id')
    if not user_id:
        return None
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT id, email, org_id FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {'id': row[0], 'email': row[1], 'org_id': row[2]}


def require_user_or_redirect(request: Request):
    # check Authorization header then cookie
    auth = request.headers.get('Authorization')
    token = None
    if auth and auth.lower().startswith('bearer '):
        token = auth.split(None, 1)[1]
    else:
        token = request.cookies.get('access_token')
    if not token:
        return None
    return get_user_from_token(token)


@app.get("/ui")
def ui(request: Request):
    # require logged-in user
    user = require_user_or_redirect(request)
    if not user:
        return RedirectResponse('/login')

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT device_id, hostname, last_seen, last_payload_json FROM devices WHERE org_id = ?", (user['org_id'],))
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

    return templates.TemplateResponse("ui.html", {"request": request, "devices": devices_list})
