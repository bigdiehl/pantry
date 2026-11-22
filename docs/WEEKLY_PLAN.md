# Weekly Plan

Automatically picks recipes on a schedule, puts them on the shopping list, and
reminds the household by push notification and/or email. Configured at
Manage > Weekly plan (`/plan`).

## Settings (`state.json` `_schedule_config`)

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | false | Run on schedule |
| `num_recipes` | 3 | 1-14 |
| `frequency_weeks` | 1 | 1 = weekly, 2 = every other week |
| `day_of_week`, `send_time` | 6 (Sun), `09:00` | APScheduler day (0 = Mon), server local time |
| `fresh_start` | true | Deselect everything first; false keeps current picks and tops up |
| `notify` | true | Push to all subscribed devices |
| `send_email`, `recipients` | false, "" | Email the PDF list |

`_get_schedule_config()` merges stored values over `PLAN_DEFAULTS`. Configs written
before the plan existed (email only) have no `send_email`; it is inferred as true when
they had recipients, so upgrading never silently stops an email.

## Run (`run_weekly_plan`)

1. Skip unless enabled, or forced ("Pick recipes now").
2. Every-other-week: skip if the last plan is less than 11 days old. The cron job
   fires weekly; this check makes it biweekly without a second trigger type.
3. If `fresh_start`, deselect all recipes.
4. `select_recipes_for_schedule(n)`: keep already selected recipes (up to n), fill the
   rest randomly from recipes that are `enabled` and last made at least
   `min_period_weeks` ago (never made counts as available).
5. Mark picks selected, set `last_used_date` to today, save `_week_plan`
   (`created`, `slugs`, `names`), invalidate the shopping list cache.
6. Push: "This week's recipes" / "A, B, C. Tap to review and shop.", opens `/`.
7. Email the PDF if enabled and email is configured on the server. Failures are logged,
   not raised, so a mail problem doesn't block the notification.

`_week_plan.created` doubles as the week ID the List page uses to reset checkmarks.

## Scheduling

`_reschedule_email_job()` (name kept from the email-only version) replaces the
`weekly_shopping_list` cron job from current settings. It runs at startup and after
every settings save. The job is in-memory: if the app is down at the scheduled
time, that run is missed (no catch-up).

## Known gaps

- `last_used_date` is set when a recipe is picked, not when it is cooked.
- A missed run (server down) is not made up.
- One schedule per household; no per-person settings.
