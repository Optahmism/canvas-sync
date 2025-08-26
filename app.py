import os
from flask import Flask, jsonify, request
from canvas_client import list_assignments
from google_clients import upsert_sheet_rows, upsert_calendar, read_manual_events, upsert_calendar_events

SHEET_ID = os.environ.get("SHEET_ID","").strip()
CAL_ID   = os.environ.get("CALENDAR_ID","").strip()

app = Flask(__name__)

def sync_all():
    course_ids = [c.strip() for c in os.environ["CANVAS_COURSE_IDS"].split(",") if c.strip()]
    all_rows = []
    for cid in course_ids:
        all_rows.extend(list_assignments(cid))
    if SHEET_ID:
        upsert_sheet_rows(SHEET_ID, all_rows, sheet_name="All")
    if CAL_ID:
        upsert_calendar(CAL_ID, all_rows)
        # also sync manual events from the 'Manual' tab
        manual = read_manual_events(SHEET_ID) if SHEET_ID else []
        if manual:
            upsert_calendar_events(CAL_ID, manual)
    return {"synced_assignments": len(all_rows), "courses": course_ids, "manual_events": len(manual) if SHEET_ID else 0}

@app.get("/healthz")
def health():
    return jsonify({"ok": True})

@app.post("/sync")
def manual_sync():
    res = sync_all()
    return jsonify(res)

if __name__ == "__main__":
    # local one-off run for convenience
    print(sync_all())
