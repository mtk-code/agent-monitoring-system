# Agent Monitoring System

Distributed agent monitoring system with heartbeat, metrics collection, offline detection and remote command support.

## Components
- agent/ : device agent (sends metrics + receives commands)
- server/ : FastAPI ingest + registry
- shared/ : shared protocol/models
- docs/ : architecture notes
- docker compose up --build
