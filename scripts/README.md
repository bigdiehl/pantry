# Utility Scripts

This directory contains utility scripts for managing the recipe application.

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
If you need to change the model used by the recipe importer, edit the `GEMINI_MODEL` constant in `recipe_core/gemini_importer.py`.

## Service install

| Script | Purpose |
|--------|---------|
| `install_service.sh [--port N]` | Install deps, create `/etc/recipes_app.env`, install and start `recipes.service`. Idempotent. |
| `setup_tailscale.sh [--port N]` | Serve the app at `https://<host>.<tailnet>.ts.net` (required for PWA install). |
| `uninstall_service.sh` | Stop and remove the service. Keeps env file and data. |

## Service install

| Script | Purpose |
|--------|---------|
| `install_service.sh [--port N]` | Install deps, create `/etc/recipes_app.env`, install and start `recipes.service`. Idempotent. |
| `setup_tailscale.sh [--port N]` | Serve the app at `https://<host>.<tailnet>.ts.net` (required for PWA install). |
| `uninstall_service.sh` | Stop and remove the service. Keeps env file and data. |
