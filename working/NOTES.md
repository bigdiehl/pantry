# Working Notes

Design reference lives in `docs/`. This file keeps history and open questions.

## History

**2026-11-22**
- Recipe data purged from this repo's history (git-filter-repo), `dev` folded into
  `master`, repo renamed `recipes` -> `pantry`. Pre-rewrite backups:
  `~/projects/recipes_prefilter_20261122.bundle`, `~/projects/recipes_git_backup_20261122`.
- frank moved from the hand-made `frank_web_server.service` (debug mode, old checkout)
  to `pantry.service` + update timer. Its `state.json` had been corrupted by two
  processes writing at once; writes are now atomic.
- `/etc/recipes_app.env` used `export KEY=...` lines, which systemd ignores, so email
  was silently off on the old service too.
- UI redesign, chat, photo import, weekly plan + push, data backup job.

**2026-10-10 PWA review**
- Service worker had been served from `/static/`, so it controlled no pages. Now `/service-worker.js`.
- `debug=True` on `0.0.0.0` exposed the Werkzeug debugger to the LAN. Now `RECIPES_DEBUG`, off on the server.
- Lighthouse (`http://192.168.1.139:5000`, before HTTPS): perf 0.96, a11y 0.90,
  best-practices 0.74, SEO 0.90.

## Open Questions

- Enable/disable + `min_period_weeks`: keep in `recipe.yaml` or move to `state.json`?
- Keep meal/category, or a freeform "section" field? Multiple meals per recipe?
- Store layout for shopping list ordering (aisle order)?
- Should the weekly plan learn from what actually gets cooked?
