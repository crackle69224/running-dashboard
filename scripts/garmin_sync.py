"""
Pulls new running activities from Garmin Connect and uploads them to the
running dashboard.

Run manually:
    python scripts/garmin_sync.py

Designed to also run unattended on a schedule (Windows Task Scheduler).
Credentials and config are read from a .env file in the project root —
see .env.example for the required keys.
"""
import json
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

from garminconnect import Garmin

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8000").rstrip("/")
DASHBOARD_EMAIL = os.environ.get("DASHBOARD_EMAIL")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
TOKEN_STORE = PROJECT_ROOT / ".garmin_tokens"
SYNCED_IDS_FILE = PROJECT_ROOT / "data" / "synced_activity_ids.json"


def load_synced_ids() -> set[str]:
    if SYNCED_IDS_FILE.exists():
        return set(json.loads(SYNCED_IDS_FILE.read_text()))
    return set()


def save_synced_ids(ids: set[str]) -> None:
    SYNCED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNCED_IDS_FILE.write_text(json.dumps(sorted(ids)))


def login() -> Garmin:
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        print("Missing GARMIN_EMAIL / GARMIN_PASSWORD in .env", file=sys.stderr)
        sys.exit(1)

    # login() loads cached tokens from TOKEN_STORE if present and still valid;
    # otherwise it logs in with the credentials and saves fresh tokens there,
    # so we only hit Garmin's password login on the very first run (or once
    # tokens expire) rather than every time the script runs.
    TOKEN_STORE.mkdir(parents=True, exist_ok=True)
    client = Garmin(email=GARMIN_EMAIL, password=GARMIN_PASSWORD)
    client.login(str(TOKEN_STORE))
    return client


RUNNING_TYPE_KEYS = {
    "running",
    "trail_running",
    "treadmill_running",
    "track_running",
    "street_running",
    "indoor_running",
    "virtual_run",
    "obstacle_run",
    "ultra_run",
}


def dashboard_session() -> requests.Session:
    if not DASHBOARD_EMAIL or not DASHBOARD_PASSWORD:
        print("Missing DASHBOARD_EMAIL / DASHBOARD_PASSWORD in .env", file=sys.stderr)
        sys.exit(1)

    session = requests.Session()
    resp = session.post(
        f"{DASHBOARD_URL}/api/login",
        json={"email": DASHBOARD_EMAIL, "password": DASHBOARD_PASSWORD},
    )
    if not resp.ok:
        print(f"Dashboard login failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    return session


def main():
    client = login()
    session = dashboard_session()
    synced = load_synced_ids()

    activities = client.get_activities(0, 20)
    running_activities = [
        a for a in activities
        if (a.get("activityType", {}).get("typeKey") or "") in RUNNING_TYPE_KEYS
    ]

    new_count = 0
    for activity in running_activities:
        activity_id = str(activity["activityId"])
        if activity_id in synced:
            continue

        print(f"Downloading activity {activity_id} ({activity.get('activityName')})...")
        fit_bytes = client.download_activity(
            activity_id, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL
        )

        resp = session.post(
            f"{DASHBOARD_URL}/api/upload",
            files={"files": (f"{activity_id}.zip", fit_bytes, "application/zip")},
        )
        if resp.ok:
            print(f"  Uploaded -> {resp.json()}")
            synced.add(activity_id)
            new_count += 1
        else:
            print(f"  Upload failed: {resp.status_code} {resp.text}", file=sys.stderr)

    save_synced_ids(synced)
    print(f"Done. {new_count} new run(s) uploaded.")


if __name__ == "__main__":
    main()
