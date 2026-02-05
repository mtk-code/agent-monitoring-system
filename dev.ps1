#!/usr/bin/env pwsh

<#
.SYNOPSIS
Safe Docker Compose development workflow for agent-monitoring-system.

.DESCRIPTION
Provides safe commands to manage the development environment while preserving
the SQLite database across rebuilds. Use 'dev.ps1 -help' to see all commands.
#>

param(
    [string]$Command = "help"
)

function Show-Help {
    Write-Host ""
    Write-Host "=== Agent Monitoring System - Safe Development Workflow ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "SAFE commands (preserve database):" -ForegroundColor Green
    Write-Host "  ./dev.ps1 dev          - Build and start server (first time or after deps change)"
    Write-Host "  ./dev.ps1 up           - Start server without building"
    Write-Host "  ./dev.ps1 down         - Stop server (preserves database)"
    Write-Host "  ./dev.ps1 rebuild      - Rebuild without cache, keep database"
    Write-Host ""
    Write-Host "RESET database (intentional wipe):" -ForegroundColor Yellow
    Write-Host "  ./dev.ps1 reset-db     - WIPES database + volumes (requires confirmation)"
    Write-Host "  ./dev.ps1 clean        - Hard reset (clean volumes, rebuild from scratch)"
    Write-Host ""
    Write-Host "UTILITY:" -ForegroundColor Cyan
    Write-Host "  ./dev.ps1 logs         - Tail server logs"
    Write-Host "  ./dev.ps1 shell        - Enter server container shell"
    Write-Host "  ./dev.ps1 status       - Show container status"
    Write-Host ""
    Write-Host "EXAMPLES:"
    Write-Host "  ./dev.ps1 dev           # First-time setup"
    Write-Host "  ./dev.ps1 rebuild       # Safe rebuild with no-cache"
    Write-Host "  ./dev.ps1 reset-db      # Intentionally wipe everything"
    Write-Host ""
}

function Invoke-Dev {
    Write-Host "=== Starting development environment (preserves DB) ===" -ForegroundColor Green
    docker compose build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit 1
    }
    docker compose up
}

function Invoke-Up {
    Write-Host "=== Starting server (DB will persist) ===" -ForegroundColor Green
    docker compose up
}

function Invoke-Down {
    Write-Host "=== Stopping server (database is preserved) ===" -ForegroundColor Yellow
    docker compose down
}

function Invoke-Rebuild {
    Write-Host "=== Rebuilding images without cache (DB persists in named volume) ===" -ForegroundColor Green
    docker compose down
    docker compose build --no-cache
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit 1
    }
    docker compose up
}

function Invoke-ResetDb {
    Write-Host ""
    Write-Host "⚠️  WARNING: This will DELETE the SQLite database and all data!" -ForegroundColor Red
    Write-Host "    Volumes: server_data" -ForegroundColor Red
    Write-Host ""
    $confirm = Read-Host "Type 'yes' to confirm"
    
    if ($confirm -eq "yes") {
        Write-Host "Wiping database..." -ForegroundColor Red
        docker compose down -v
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Database deleted. Run './dev.ps1 dev' to recreate." -ForegroundColor Green
        }
    } else {
        Write-Host "Cancelled." -ForegroundColor Yellow
    }
}

function Invoke-Clean {
    Invoke-ResetDb
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Rebuilding from scratch..." -ForegroundColor Green
        docker compose build --no-cache
        docker compose up
    }
}

function Invoke-Logs {
    docker compose logs -f server
}

function Invoke-Shell {
    docker compose exec server sh
}

function Invoke-Status {
    docker compose ps
}

# Route command
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "dev" { Invoke-Dev }
    "up" { Invoke-Up }
    "down" { Invoke-Down }
    "rebuild" { Invoke-Rebuild }
    "reset-db" { Invoke-ResetDb }
    "clean" { Invoke-Clean }
    "logs" { Invoke-Logs }
    "shell" { Invoke-Shell }
    "status" { Invoke-Status }
    "-help" { Show-Help }
    "-?" { Show-Help }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
