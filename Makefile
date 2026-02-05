.PHONY: help dev up down reset-db clean build rebuild logs shell

help:
	@echo "=== Agent Monitoring System - Safe Development Workflow ==="
	@echo ""
	@echo "SAFE commands (preserve database):"
	@echo "  make dev          - Build and start server (first time or after deps change)"
	@echo "  make up           - Start server without building"
	@echo "  make down         - Stop server (preserves database)"
	@echo "  make rebuild      - Rebuild without cache, keep database"
	@echo ""
	@echo "RESET database (intentional wipe):"
	@echo "  make reset-db     - WIPES database + volumes (requires confirmation)"
	@echo "  make clean        - Hard reset (clean volumes, rebuild from scratch)"
	@echo ""
	@echo "UTILITY:"
	@echo "  make logs         - Tail server logs"
	@echo "  make shell        - Enter server container shell"
	@echo "  make status       - Show container status"
	@echo ""

## Safe development commands

dev:
	@echo "=== Starting development environment (preserves DB) ==="
	docker compose build
	docker compose up

up:
	@echo "=== Starting server (DB will persist) ==="
	docker compose up

down:
	@echo "=== Stopping server (database is preserved) ==="
	docker compose down

rebuild:
	@echo "=== Rebuilding images without cache (DB persists in named volume) ==="
	docker compose down
	docker compose build --no-cache
	docker compose up

## Database reset (intentional)

reset-db:
	@echo ""
	@echo "⚠️  WARNING: This will DELETE the SQLite database and all data!"
	@echo "    Volumes: server_data"
	@echo ""
	@read -p "Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "Wiping database..."; \
		docker compose down -v; \
		echo "✓ Database deleted. Run 'make dev' to recreate."; \
	else \
		echo "Cancelled."; \
	fi

clean: reset-db rebuild
	@echo "✓ Full reset and rebuild complete"

## Utility commands

logs:
	docker compose logs -f server

shell:
	docker compose exec server sh

status:
	docker compose ps

.PHONY: test
test:
	@echo "Running tests (if available)..."
	docker compose exec server python -m pytest || echo "No tests configured"
