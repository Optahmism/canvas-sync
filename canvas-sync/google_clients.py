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
