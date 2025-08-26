# Canvas → Google Sheets → Google Calendar Sync (Render)

Automate your semester: pull assignments from Canvas, log them to Google Sheets,
and create/update events in Google Calendar. Deployable on Render with a daily cron.

## What you get
- **Idempotent sync** (no duplicate events)
- **One sheet** ("All" tab) showing assignments + links
- **Deterministic event IDs**: `canvas-<courseId>-<assignmentId>`
- **Daily cron** @ 7:00 AM America/Chicago (editable in `render.yaml`)
- **Manual sync endpoint**: `POST /sync`
- **Health check**: `GET /healthz`

## Quickstart
1. **Create Google Service Account**
   - Enable **Google Sheets API** and **Google Calendar API**.
   - Download JSON and base64-encode it:
     - macOS/Linux: `base64 credentials.json | pbcopy`
     - Windows PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes('credentials.json'))`
2. **Share resources with service account email**
   - Share your target **Google Sheet** and **Calendar** (Editor access).
3. **Canvas Personal Access Token**
   - Canvas → *Account* → *Settings* → *New Access Token*.
4. **Course IDs**
   - Open each Canvas course; copy the numeric ID from the URL `/courses/<ID>`.
5. **Deploy on Render**
   - Push this folder to a Git repo (GitHub).
   - In Render: **New → Blueprint** → select your repo. Render reads `render.yaml`.
   - Add environment variables for both services (`canvas-sync-web` and `canvas-sync-cron`):
     - `CANVAS_BASE_URL`, `CANVAS_TOKEN`, `CANVAS_COURSE_IDS`
     - `SHEET_ID`, `CALENDAR_ID`, `GOOGLE_CREDENTIALS_JSON_B64`, `TZ`
6. **Test**
   - Visit `https://<your-web-service>.onrender.com/healthz` → `{"ok": true}`
   - Trigger: `curl -X POST https://<your-web-service>.onrender.com/sync`

## Local Dev
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export $(cat .env.example | xargs)  # or set vars manually
python app.py  # runs a one-time sync then exits
```

## Notes
- Canvas sometimes omits `due_at`. In that case we create an **all-day** event on a placeholder date (one week out). Edit it later if needed.
- If `due_at` exists but has no timezone, we assume `TZ` (default **America/Chicago**).
