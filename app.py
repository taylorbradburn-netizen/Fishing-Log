import os
import json
import sqlite3
import requests
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request, redirect, url_for

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "fishing_log.db")

RIVERS = [
    {"id": "13190500", "name": "SF Boise River",  "lat": 43.5,  "lon": -115.8},
    {"id": "13183000", "name": "Owyhee River",     "lat": 43.65, "lon": -117.23},
    {"id": "13150430", "name": "Silver Creek",     "lat": 43.3,  "lon": -114.1},
    {"id": "09188500", "name": "Green River (WY)", "lat": 42.93, "lon": -109.97},
    {"id": "09205000", "name": "New Fork River",   "lat": 42.62, "lon": -110.11},
    {"id": "09211200", "name": "Seedskadee",       "lat": 41.97, "lon": -109.57},
]
RIVER_MAP = {r["id"]: r for r in RIVERS}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    TEXT    NOT NULL,
                date          TEXT    NOT NULL,
                river_name    TEXT    NOT NULL,
                river_id      TEXT,
                pressure_inhg REAL,
                pressure_trend TEXT,
                cfs           REAL,
                water_temp_f  REAL,
                clarity       TEXT,
                flies         TEXT,
                methods       TEXT,
                species       TEXT,
                fish_count    INTEGER DEFAULT 0,
                notes         TEXT
            )
        """)


init_db()


def fetch_usgs(site_id):
    try:
        r = requests.get(
            "https://waterservices.usgs.gov/nwis/iv/",
            params={"format": "json", "sites": site_id, "parameterCd": "00060,00010", "period": "PT2H"},
            timeout=10,
        )
        ts = r.json()["value"]["timeSeries"]
        cfs = temp_f = None
        for series in ts:
            cd = series["variable"]["variableCode"][0]["value"]
            vals = series["values"][0]["value"]
            if vals:
                v = float(vals[-1]["value"])
                if cd == "00060":
                    cfs = round(v, 1)
                elif cd == "00010":
                    temp_f = round(v * 9 / 5 + 32, 1)
        return {"cfs": cfs, "water_temp_f": temp_f}
    except Exception:
        return {"cfs": None, "water_temp_f": None}


def fetch_pressure(lat, lon):
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "hourly": "surface_pressure",
                    "forecast_days": 1, "timezone": "auto"},
            timeout=10,
        )
        pressures = r.json()["hourly"]["surface_pressure"]
        h = datetime.now().hour
        p_inhg = round(pressures[h] * 0.02953, 2) if pressures else None
        if h >= 3:
            diff = pressures[h] - pressures[h - 3]
            trend = "Rising" if diff > 0.5 else "Falling" if diff < -0.5 else "Steady"
        else:
            trend = "Steady"
        return {"pressure_inhg": p_inhg, "pressure_trend": trend}
    except Exception:
        return {"pressure_inhg": None, "pressure_trend": None}


@app.route("/")
def index():
    with get_db() as db:
        entries = db.execute("SELECT * FROM entries ORDER BY date DESC, id DESC").fetchall()
    parsed = []
    for e in entries:
        row = dict(e)
        row["flies"] = json.loads(e["flies"] or "[]")
        row["methods"] = json.loads(e["methods"] or "[]")
        parsed.append(row)
    return render_template("index.html", entries=parsed, rivers=RIVERS)


@app.route("/new")
def new_entry():
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("log.html", rivers=RIVERS, today=today)


@app.route("/api/river-conditions/<site_id>")
def river_conditions(site_id):
    river = RIVER_MAP.get(site_id)
    if not river:
        return jsonify({"error": "Unknown river"}), 404
    usgs = fetch_usgs(site_id)
    pressure = fetch_pressure(river["lat"], river["lon"])
    return jsonify({**usgs, **pressure})


@app.route("/save", methods=["POST"])
def save():
    f = request.form
    flies = json.dumps([x.strip() for x in f.get("flies", "").split(",") if x.strip()])
    methods = json.dumps(request.form.getlist("methods"))
    with get_db() as db:
        db.execute("""
            INSERT INTO entries
              (created_at, date, river_name, river_id, pressure_inhg, pressure_trend,
               cfs, water_temp_f, clarity, flies, methods, species, fish_count, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            f.get("date"),
            f.get("river_name"),
            f.get("river_id") or None,
            float(f["pressure_inhg"]) if f.get("pressure_inhg") else None,
            f.get("pressure_trend") or None,
            float(f["cfs"]) if f.get("cfs") else None,
            float(f["water_temp_f"]) if f.get("water_temp_f") else None,
            f.get("clarity") or None,
            flies,
            methods,
            f.get("species") or None,
            int(f.get("fish_count") or 0),
            f.get("notes") or None,
        ))
    return redirect(url_for("index"))


@app.route("/delete/<int:entry_id>", methods=["POST"])
def delete(entry_id):
    with get_db() as db:
        db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
