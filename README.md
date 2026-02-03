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

## Roadmap

- Command execution from server
- OTA updates
- Web dashboard
- TLS support
- Multi-agent simulation
