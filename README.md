# Agent Monitoring System

Distributed agent monitoring system with heartbeat, metrics collection, offline detection, authentication and remote command support.

## Components
- agent/ : device agent (sends metrics + receives commands)
- server/ : FastAPI ingest + registry API
- shared/ : shared protocol/models
- docs/ : architecture notes

---

## Run with Docker

### Requirements
- Docker Desktop

### Start server

```bash
docker compose up --build
```

### Health check

```bash
curl http://127.0.0.1:8000/health
```

---

## Web UI

Open the web dashboard at:

```
http://127.0.0.1:8000/ui
```

The UI shows devices and allows sending a "restart" command per device (uses the server's token internally for the API call).

---

## Run Agent Locally

```bash
cd agent
pip install -r requirements.txt
py -3.10 .\agent.py
```

---

## List Devices

```bash
curl http://127.0.0.1:8000/devices
```

---

## Features

- Heartbeat & metrics ingestion
- Online/offline detection
- Auth token protection
- Agent versioning
- Error reporting
- Dockerized server
- SQLite persistence

---

## Remote Commands

The server supports enqueuing remote commands per device. Commands are stored in SQLite and served FIFO to agents. All command endpoints require the `X-Auth-Token` header (same token used for `/ingest`).

Examples:

- Enqueue a command:

```bash
curl -X POST http://127.0.0.1:8000/devices/demo-001/commands \
	-H "X-Auth-Token: dev-token-123" \
	-H "Content-Type: application/json" \
	-d '{"command":"restart","args":{"now":true}}'
```

- Agent polling (server -> agent):

Agents should call `GET /devices/{device_id}/commands/next` to obtain the next pending command. If a command is returned the agent should `POST /devices/{device_id}/commands/{command_id}/ack` with the execution result. Example (manual):

```bash
curl -H "X-Auth-Token: dev-token-123" http://127.0.0.1:8000/devices/demo-001/commands/next

# ack a command with id 5
curl -X POST http://127.0.0.1:8000/devices/demo-001/commands/5/ack \
	-H "X-Auth-Token: dev-token-123" \
	-H "Content-Type: application/json" \
	-d '{"success":true,"message":"executed (mock)"}'
```

Notes:
- Commands are delivered FIFO per device.
- Once acknowledged the command is marked `acked` and will not be returned again.
- Wrong or missing token returns HTTP 401.

---

## Roadmap

- Command execution from server
- OTA updates
- Web dashboard
- TLS support
- Multi-agent simulation
