# Safe Development Workflow Checklist

## Current Configuration

### Docker Compose (docker-compose.yml)
- ✓ Named volume `server_data` created and persisted
- ✓ `/data` directory mounted to `server_data` volume (where DB file lives)
- ✓ `./server` directory bind-mounted to `/app` (source code changes reflect instantly)
- ✓ `DB_PATH=/data/devices.db` environment variable set
- ✓ `uvicorn --reload` enabled for hot-reload on code changes

### Database Setup (server/main.py)
- ✓ `DB_PATH` reads from env var `DB_PATH`, falls back to `./devices.db`
- ✓ `init_db()` runs on startup via `@app.on_event("startup")`
- ✓ Schema creation is idempotent (uses `CREATE TABLE IF NOT EXISTS`)
- ✓ Column migrations via `ensure_column()` helper (idempotent ALTER TABLE)
- ✓ Default org/admin seeded if DB is new
- ✓ Startup logging shows DB path and initialization status

### Development Tools
- ✓ `Makefile` with safe commands (Linux/Mac)
  - `make dev` - First-time setup
  - `make rebuild` - Rebuild without cache (keeps DB)
  - `make down` - Stop (keeps DB)
  - `make reset-db` - Intentionally wipe DB (requires confirmation)
  
- ✓ `dev.ps1` PowerShell script with same commands (Windows)

### Documentation
- ✓ README.md updated with safe workflow
- ✓ Explains why `docker compose down -v` wipes DB
- ✓ Provides recommended commands
- ✓ Schema migration strategy documented

---

## How to Use (Safe Workflow)

### First Time
```bash
# Linux/Mac
make dev

# Windows
./dev.ps1 dev

# Or manual (all platforms)
docker compose up --build
```

### Normal Development
```bash
# Edit code, server auto-reloads via uvicorn --reload
# No docker commands needed unless you change requirements.txt

# When done, stop server (database PRESERVED)
make down                    # Linux/Mac
./dev.ps1 down               # Windows
docker compose down          # All platforms (no -v flag!)
```

### Rebuild Image (deps changed, code changes, etc.)
```bash
# Rebuild without cache, database PERSISTS
make rebuild                 # Linux/Mac
./dev.ps1 rebuild            # Windows

# Or manual
docker compose down
docker compose build --no-cache
docker compose up
```

### Intentionally Wipe Database
```bash
# Only when you really want to reset everything
make reset-db                # Linux/Mac (asks for confirmation)
./dev.ps1 reset-db           # Windows (asks for confirmation)

# Or manual (DANGEROUS - requires -v flag)
docker compose down -v       # Deletes all volumes + data
```

---

## What's Safe Now?

1. ✓ `docker compose down` - **SAFE** (keeps DB)
2. ✓ `docker compose down && docker compose up` - **SAFE** (keeps DB)
3. ✓ `docker compose down && docker compose build && docker compose up` - **SAFE** (keeps DB)
4. ✓ `docker compose build --no-cache && docker compose up` - **SAFE** (keeps DB)
5. ✗ `docker compose down -v` - **DANGEROUS** (wipes DB, only use intentionally)

---

## Key Architecture

```
docker-compose.yml
├── services.server.volumes
│   ├── ./server:/app (bind-mount, code changes live)
│   └── server_data:/data (named volume, persists DB)
└── environment
    └── DB_PATH=/data/devices.db (points to persistent volume)

server/main.py
├── init_db() (runs on startup)
│   ├── CREATE TABLE IF NOT EXISTS (idempotent)
│   ├── ALTER TABLE ... ADD COLUMN (safe migrations)
│   └── Seed default org/admin if new DB
└── DB_PATH from os.getenv('DB_PATH', fallback)
```

---

## Troubleshooting

### "Database file not found after rebuild"
→ Check that `docker volume ls` shows `agent-monitoring-system_server_data`
→ If missing, it was deleted by `down -v`. Recreate with `make dev`

### "Server won't start, says DB is locked"
→ Close any other connections or containers
→ Restart with `docker compose down && docker compose up`

### "I accidentally ran down -v and lost my data"
→ Database is gone (deleted by `-v` flag)
→ Run `make dev` or `./dev.ps1 dev` to recreate fresh DB

### "Code changes aren't showing up"
→ uvicorn --reload should catch them automatically
→ If not, restart container: `docker compose restart`

---

## Next Steps (Optional Enhancements)

- Add Docker health checks to docker-compose.yml
- Add .dockerignore to exclude unnecessary files from image
- Add persistent logging volume if needed
- Consider adding backup strategy for DB in production
- Add environment-specific docker-compose files (dev vs prod)

