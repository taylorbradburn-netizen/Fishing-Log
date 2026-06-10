# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running locally

```bash
source venv/bin/activate
flask run --port 5001   # port 5000 is blocked by macOS AirPlay
```

Hard-refresh Chrome with Cmd+Shift+R after CSS/template changes to bust the browser cache.

## Deployment

Deployed on Railway. Push to `main` on GitHub (`taylorbradburn-netizen/Fishing-Log`) to trigger a redeploy. If Railway doesn't pick it up, create an empty commit:

```bash
git commit --allow-empty -m "Trigger Railway redeploy" && git push origin main
```

## Architecture

Single-file Flask app (`app.py`) with Jinja2 templates and no build step.

**Data persistence:** SQLite at `DB_PATH` (env var, defaults to `fishing_log.db`). On Railway, `DB_PATH=/data/fishing_log.db` points to a mounted Volume so data survives redeploys. `UPLOAD_DIR` is derived as a sibling `uploads/` directory next to the DB file — fly photos are stored there and served via the `/uploads/<filename>` route.

**Schema migrations** are handled inline in `init_db()` using `ALTER TABLE ... ADD COLUMN` wrapped in try/except. Add new columns this way — never drop or recreate the table.

**JSON columns:** `flies`, `methods`, and `fly_photos` are stored as JSON arrays. They are parsed in the index route before passing to templates.

**External APIs (live, called on each form submit):**
- USGS Water Services — CFS flow and water temp by USGS site ID (`parameterCd` 00060/00010)
- Open-Meteo — hourly surface pressure by lat/lon; trend computed as 3-hour delta

**Frontend:** Bootstrap 5.3.3 + custom CSS (`static/style.css`) using Oswald + Lato from Google Fonts. CSS variables in `:root` control the full color scheme — `--bg`, `--surface`, `--card-header-bg`, `--accent-teal`, `--accent-red`. No JS framework; vanilla JS in templates handles the river-select auto-fill and the collage ticker.

**Photo collage ticker** (`templates/index.html`): 18 fish photos in `static/images/`, 9 shown at a time in a 3-column grid. JS preloads the next image before fading to avoid flicker, then swaps every 3.5 seconds.

## Adding a new river

Add an entry to the `RIVERS` list in `app.py` with `id` (USGS site ID), `name`, `lat`, and `lon`. No other changes needed — the select dropdown and conditions API are driven from this list.
