# Quick Start: Safe Development

## TL;DR - What Changed?

The database now **persists across rebuilds** automatically. You no longer need to worry about accidental data loss.

## Safe Commands (Use These)

### Linux/Mac with Make
```bash
make dev           # First time setup
make rebuild       # Rebuild, keep database
make down          # Stop (keeps database)
make reset-db      # Wipe database (asks for confirmation)
make logs          # View logs
make shell         # Enter container
```

### Windows with PowerShell
```powershell
./dev.ps1 dev           # First time setup
./dev.ps1 rebuild       # Rebuild, keep database
./dev.ps1 down          # Stop (keeps database)
./dev.ps1 reset-db      # Wipe database (asks for confirmation)
./dev.ps1 logs          # View logs
./dev.ps1 shell         # Enter container
```

### All Platforms (Docker Compose)
```bash
# Safe: starts server, keeps database
docker compose up --build

# Safe: stops server, keeps database
docker compose down

# Safe: rebuild without cache, keeps database
docker compose build --no-cache
docker compose up

# DANGEROUS: wipes database (only use intentionally)
docker compose down -v
```

## What's Different?

### Before
```bash
docker compose down -v       # Wipes database! ❌
docker compose build --no-cache
docker compose up
```

### Now
```bash
docker compose down          # Keeps database ✓
docker compose build --no-cache
docker compose up
```

## Where's the Database?

- **Location**: Docker named volume `server_data` mounted to `/data/devices.db`
- **Persists**: Yes, across container restarts and rebuilds
- **Survives**: `docker compose down` (safe)
- **Deleted by**: `docker compose down -v` (the `-v` flag)

## First Time Setup

### Option 1: Using Make (Recommended)
```bash
# Linux/Mac
make dev

# Starts server at http://127.0.0.1:8000/ui
```

### Option 2: Windows PowerShell
```powershell
./dev.ps1 dev

# Starts server at http://127.0.0.1:8000/ui
```

### Option 3: Manual
```bash
docker compose up --build
```

## Default Credentials

- Email: `admin@local`
- Password: `admin`
- API Token (for agents): Auto-generated, view in Admin → Organizations

## Common Tasks

### Stop and start (database preserved)
```bash
docker compose down      # Stop
docker compose up        # Start (no rebuild needed)
```

### Edit code and test
- Code changes auto-reload via `uvicorn --reload`
- No docker commands needed
- Changes appear within seconds

### Rebuild after changing requirements.txt
```bash
make rebuild            # Linux/Mac
./dev.ps1 rebuild       # Windows
# Or manual: docker compose build --no-cache && docker compose up
```

### Completely reset (wipe everything)
```bash
make reset-db           # Linux/Mac (asks for confirmation)
./dev.ps1 reset-db      # Windows (asks for confirmation)
# Or manual: docker compose down -v && docker compose up --build
```

## Schema Migrations

- **Automatic**: Database schema is created/updated on startup
- **Idempotent**: Safe to run multiple times
- **No external tool**: Built into `server/main.py`
- **How it works**: 
  - Creates tables if missing
  - Adds columns via `ALTER TABLE` if missing
  - Seeds default org/admin only if DB is new

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Database file not found" | Run `make dev` to create fresh DB |
| "Server won't start" | Check logs with `make logs` |
| "Code changes not showing up" | Restart with `docker compose restart` |
| "I accidentally deleted the DB" | Run `make dev` to recreate |

## Documentation

- **Full details**: See [DOCKER_WORKFLOW.md](DOCKER_WORKFLOW.md)
- **Development guide**: See [README.md](README.md)

