# Meet Insights Web

FastAPI UI for **Meet Insights** with **Google Sign-In**, **MongoDB** sessions, Jinja2, HTMX, and Bootstrap 5.3.

Meeting/project pages still use mock JSON. Authentication is real (OAuth + MongoDB).

## Setup

```bash
cd MeetInsights-Web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set MongoDB + Google OAuth credentials
```

### Google Cloud Console

1. Create an OAuth 2.0 Client (Web application).
2. Add authorized redirect URI from `GOOGLE_REDIRECT_URI` (default `http://127.0.0.1:8000/auth/google/callback`).
3. Put Client ID / Secret into `.env`.

### MongoDB collections

**users**
```json
{
  "_id": { "$oid": "66a1b2c3d4e5f67890123456" },
  "email": "user@example.com",
  "name": "User Name",
  "created_at": { "$date": "2026-07-28T11:30:55.233Z" },
  "updated_at": { "$date": "2026-08-27T11:30:55.239Z" }
}
```

**user_sessions**
```json
{
  "user_id": { "$oid": "66a1b2c3d4e5f67890123456" },
  "refresh_token": "67a41ac058dc8353ebad7c5f0ffb6ac2b49b9a3cb346aadc29170f8e989f1ab3",
  "expires_at": { "$date": "2026-08-27T11:30:55.239Z" },
  "created_at": { "$date": "2026-07-28T11:30:55.233Z" },
  "revoked": false
}
```

Access tokens are encrypted JWTs (pattern from `src/helper/jwt_helper.ts`) and stored in the `mi_access_token` httpOnly cookie. The opaque refresh token is stored in MongoDB `user_sessions` and the `mi_refresh_token` cookie.

### Meetings collection

When a user starts a meeting:

```json
{
  "_id": { "$oid": "..." },
  "user_id": { "$oid": "..." },
  "platform": "google_meet",
  "meeting_url": "https://meet.google.com/abc-defg-hij",
  "title": "Weekly sync",
  "status": "queued",
  "created_at": { "$date": "..." },
  "updated_at": { "$date": "..." }
}
```

The meeting `_id` is published to RabbitMQ queue `meetinsights.meetings` as:

```json
{"id": "<meeting_id>"}
```

### API response format

All `/api/*` responses use this envelope (payload lives under `data`):

```json
{
  "response": {
    "data": {},
    "status": {
      "msg": "<Success Message>",
      "action_status": true
    }
  }
}
```

Errors use the same shape with `action_status: false` and an error `msg`.

### Start meeting API

`POST /api/meetings` — `Content-Type: application/json` (auth cookie required)

Request:

```json
{
  "platform": "google_meet",
  "meeting_url": "https://meet.google.com/abc-defg-hij",
  "title": "Weekly sync",
  "project_id": "<optional project ObjectId>"
}
```

Response example:

```json
{
  "response": {
    "data": {
      "id": "...",
      "platform": "google_meet",
      "platform_label": "Google Meet",
      "meeting_url": "https://meet.google.com/abc-defg-hij",
      "title": "Weekly sync",
      "status": "queued",
      "project_id": "...",
      "project_name": "Product Launch"
    },
    "status": {
      "msg": "Bot invited to join the meeting.",
      "action_status": true
    }
  }
}
```

Meetings and projects lists are loaded from MongoDB for the signed-in user. Mapping is **meeting → project** via optional `project_id` on the meeting.

All JSON APIs:

| Method | Path | Body |
|--------|------|------|
| POST | `/api/meetings` | platform, meeting_url, title, project_id? |
| POST | `/api/meetings/{id}/project` | project_id (null to unassign) |
| POST | `/api/meetings/{id}/chat` | message |
| POST | `/api/projects` | name, description |
| POST | `/api/projects/{id}/chat` | message, meeting_ids[] |

No form-data is used (reserved for future image uploads only).

## Run

```bash
# MongoDB and RabbitMQ must be running
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) → redirects to login (Google), then dashboard.

## Auth flow

1. `/login` — Continue with Google  
2. `/auth/google` — OAuth redirect  
3. `/auth/google/callback` — upsert user, create session, set cookies  
4. Protected UI routes require a valid access cookie (refresh session used when access expires)  
5. `/logout` — revoke session + clear cookies  

## Structure

```
app/
  main.py
  auth/          # config, jwt_helper, google login service
  db/            # mongodb, users, sessions
  routers/
  templates/
  static/
  mock_data/
```
