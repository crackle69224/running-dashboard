from datetime import datetime, timezone
from fitparse import FitFile

from app.zones import zone_breakdown


def parse_fit_file(file_path: str, filename: str) -> tuple[dict, list[dict]]:
    """Parse a Garmin FIT file into a run summary dict and a list of record dicts."""
    fitfile = FitFile(file_path)

    records = []
    hr_values = []

    for msg in fitfile.get_messages("record"):
        data = {f.name: f.value for f in msg}
        ts = data.get("timestamp")
        hr = data.get("heart_rate")
        distance_m = data.get("distance")
        speed = data.get("speed") or data.get("enhanced_speed")

        records.append({
            "timestamp": ts.isoformat() if isinstance(ts, datetime) else ts,
            "heart_rate": hr,
            "distance_km": round(distance_m / 1000, 4) if distance_m is not None else None,
            "speed": speed,
        })
        if hr is not None:
            hr_values.append(hr)

    session = {}
    for msg in fitfile.get_messages("session"):
        for f in msg:
            session[f.name] = f.value

    total_distance_m = session.get("total_distance")
    total_timer_time_s = session.get("total_timer_time")
    avg_hr = session.get("avg_heart_rate")
    max_hr = session.get("max_heart_rate")
    start_time = session.get("start_time")

    # Fallbacks if session message is missing/incomplete
    if total_distance_m is None and records:
        valid = [r["distance_km"] for r in records if r["distance_km"] is not None]
        total_distance_m = (max(valid) * 1000) if valid else 0
    if avg_hr is None and hr_values:
        avg_hr = sum(hr_values) / len(hr_values)
    if max_hr is None and hr_values:
        max_hr = max(hr_values)
    if start_time is None and records and records[0]["timestamp"]:
        start_time = records[0]["timestamp"]

    zones = zone_breakdown(hr_values)

    run_summary = {
        "filename": filename,
        "start_time": start_time.isoformat() if isinstance(start_time, datetime) else (start_time or datetime.now(timezone.utc).isoformat()),
        "distance_km": round((total_distance_m or 0) / 1000, 3),
        "moving_time_min": round((total_timer_time_s or 0) / 60, 2),
        "avg_hr": round(avg_hr, 1) if avg_hr is not None else None,
        "max_hr": round(max_hr) if max_hr is not None else None,
        **zones,
    }

    return run_summary, records
