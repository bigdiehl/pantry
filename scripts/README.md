# Utility Scripts

This directory contains utility scripts for managing Pantry.

## list_gemini_models.py

Lists available Gemini API models and tests connectivity.

**Usage:**

```bash
# Set your API key
export GEMINI_API_KEY="your-key-here"

# List all available models (grouped by type)
uv run python scripts/list_gemini_models.py

# Show recommended models for recipe extraction
uv run python scripts/list_gemini_models.py --recommended

# Test a specific model
uv run python scripts/list_gemini_models.py --test gemini-2.5-flash

# Show detailed model information
uv run python scripts/list_gemini_models.py --verbose
```

**When to use:**
- After model API changes
- To verify your API key is working
- To find the latest/best model for recipe extraction
- When debugging model availability errors

**Updating the importer:**
Models are set in `recipe_core/gemini.py` (override with `GEMINI_MODEL` / `GEMINI_FALLBACK_MODELS` env vars).

## Service install

| Script | Purpose |
|--------|---------|
| `install_service.sh [--port N] [--update-interval 5min] [--backup-schedule 'Sun 03:00']` | Install deps, create `/etc/pantry.env`, install and start `pantry.service` + update and backup timers. Idempotent. |
| `auto_update.sh` | Run by `pantry-update.timer`: pull app + data repos, test, restart. See `docs/DEPLOYMENT.md`. |
| `backup_data.sh` | Run weekly by `pantry-backup.timer`: commit and push recipe edits to diehl_recipes. |
| `setup_tailscale.sh [--port N]` | Serve the app at `https://<host>.<tailnet>.ts.net` (required for PWA install). |
| `uninstall_service.sh` | Stop and remove the service and timer. Keeps env file and data. |
