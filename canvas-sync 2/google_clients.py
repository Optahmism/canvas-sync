import os, json, base64
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateutil import parser as dtp
import pytz

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar"
]

def _creds():
    raw = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_JSON_B64"])
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

def sheets_client():
    return build("sheets", "v4", credentials=_creds()).spreadsheets()

def calendar_client():
    return build("calendar", "v3", credentials=_creds())

def upsert_sheet_rows(sheet_id, rows, sheet_name="All"):
    header = ["canvas_id","course_id","name","due_at","points","submission_types","html_url","calendar_event_id"]
    values = [header]
    for r in rows:
        values.append([
            r["canvas_id"], r["course_id"], r["name"], r["due_at"] or "",
            r.get("points",""), r.get("submission_types",""), r.get("html_url",""),
            f"canvas-{r['course_id']}-{r['canvas_id']}"
        ])
    svc = sheets_client()
    # create sheet/tab if needed
    try:
        svc.batchUpdate(spreadsheetId=sheet_id, body={
            "requests":[{"addSheet":{"properties":{"title":sheet_name}}}]
        }).execute()
    except Exception:
        pass  # already exists
    # clear + write
    svc.values().clear(spreadsheetId=sheet_id, range=f"{sheet_name}!A:Z").execute()
    svc.values().update(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

def _event_times(due_iso):
    tz = pytz.timezone(os.getenv("TZ","America/Chicago"))
    if not due_iso:
        # placeholder all-day: one week out
        start = (datetime.now(tz) + timedelta(days=7)).date().isoformat()
        return {"allDay": True, "start": {"date": start}, "end": {"date": start}}
    dt = dtp.parse(due_iso)
    if not dt.tzinfo:
        dt = tz.localize(dt)
    start = dt.isoformat()
    end = (dt + timedelta(minutes=30)).isoformat()
    return {"allDay": False, "start": {"dateTime": start}, "end": {"dateTime": end}}

def upsert_calendar(calendar_id, items):
    cal = calendar_client()
    for r in items:
        eid = f"canvas-{r['course_id']}-{r['canvas_id']}"
        times = _event_times(r["due_at"])
        body = {
            "id": eid[:1024],
            "summary": f"[{r['course_id']}] {r['name']}",
            "description": (r.get("html_url") or ""),
            "source": {"title":"Canvas", "url": r.get("html_url")},
            "extendedProperties": {"private": {"canvas_id": r["canvas_id"], "course_id": r["course_id"]}},
        }
        if times["allDay"]:
            body["start"] = times["start"]
            body["end"] = times["end"]
        else:
            body["start"] = times["start"]
            body["end"] = times["end"]
        try:
            cal.events().insert(calendarId=calendar_id, body=body, conferenceDataVersion=0).execute()
        except Exception:
            # event exists -> update basic fields
            cal.events().patch(calendarId=calendar_id, eventId=eid, body=body).execute()


def read_manual_events(sheet_id, sheet_name="Manual"):
    svc = sheets_client()
    try:
        res = svc.values().get(spreadsheetId=sheet_id, range=f"{sheet_name}!A:Z").execute()
    except Exception:
        return []  # no Manual tab yet
    values = res.get("values", [])
    if not values:
        return []
    header = [h.strip() for h in values[0]]
    rows = []
    for v in values[1:]:
        row = {header[i]: (v[i] if i < len(v) else "") for i in range(len(header))}
        # expected columns: name, date, start_time, end_time, all_day, course_id, location, description, event_id
        name = row.get("name") or "(untitled)"
        date = row.get("date") or ""
        start_time = row.get("start_time") or ""
        end_time = row.get("end_time") or ""
        all_day = (row.get("all_day","no").strip().lower() in ["yes","true","1","y"]) or (not start_time)
        course_id = row.get("course_id") or "manual"
        location = row.get("location") or ""
        description = row.get("description") or ""
        eid = row.get("event_id") or f"manual-{course_id}-{re.sub('[^a-zA-Z0-9]+','-', name.lower()).strip('-')}-{date}"
        # build ISO times; assume TZ is handled by Calendar on insert if dateTime naive
        if all_day:
            ev = {
                "id": eid[:1024],
                "summary": f"[{course_id}] {name}",
                "location": location,
                "description": description,
                "start": {"date": date},
                "end": {"date": date},
                "extendedProperties": {"private": {"manual": "true", "course_id": course_id}}
            }
        else:
            # combine date and times
            start_dt = f"{date}T{start_time}"
            end_dt = f"{date}T{end_time}" if end_time else f"{date}T{start_time}"
            ev = {
                "id": eid[:1024],
                "summary": f"[{course_id}] {name}",
                "location": location,
                "description": description,
                "start": {"dateTime": start_dt},
                "end": {"dateTime": end_dt},
                "extendedProperties": {"private": {"manual": "true", "course_id": course_id}}
            }
        rows.append(ev)
    return rows


def upsert_calendar_events(calendar_id, events):
    cal = calendar_client()
    for body in events:
        eid = body.get("id")
        try:
            cal.events().insert(calendarId=calendar_id, body=body, conferenceDataVersion=0).execute()
        except Exception:
            cal.events().patch(calendarId=calendar_id, eventId=eid, body=body).execute()
