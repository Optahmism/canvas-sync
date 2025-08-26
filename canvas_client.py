import os, requests
from dateutil import parser as dtp

BASE = os.environ["CANVAS_BASE_URL"].rstrip("/")
TOKEN = os.environ["CANVAS_TOKEN"]

def _get(url, params=None):
    r = requests.get(url, headers={"Authorization": f"Bearer {TOKEN}"}, params=params, timeout=30)
    r.raise_for_status()
    return r.json(), r.headers.get("Link", "")

def list_assignments(course_id):
    url = f"{BASE}/api/v1/courses/{course_id}/assignments"
    params = {"per_page": 100}
    items = []
    while True:
        data, link = _get(url, params)
        items.extend(data)
        link = (link or "")
        if 'rel="next"' not in link.lower():
            break
        # parse next link (Canvas style)
        next_url = [p.split(';')[0].strip(' <>') for p in link.split(',') if 'rel="next"' in p.lower()]
        if not next_url:
            break
        url, params = next_url[0], None
    norm = []
    for a in items:
        due = a.get("due_at")
        norm.append({
            "canvas_id": str(a["id"]),
            "name": a.get("name","(no title)"),
            "html_url": a.get("html_url"),
            "course_id": str(course_id),
            "points": a.get("points_possible"),
            "due_at": due,  # keep original string (could be None)
            "submission_types": ",".join(a.get("submission_types") or []),
        })
    return norm
