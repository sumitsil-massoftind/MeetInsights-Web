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

Access tokens are encrypted JWTs (pattern from `src/helper/jwt_helper.ts`). Browser API calls send them as `Authorization: Bearer <token>`; the server verifies the token and user on every business `/api/*` request. The opaque refresh token remains in MongoDB and an HttpOnly cookie. `/api/auth/refresh` validates that session and returns a new short-lived access token.

Internal HTML links use soft navigation: the next server-rendered shell is fetched and swapped while browser history/back-forward navigation is preserved.

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
  "source": "bot",
  "created_at": { "$date": "..." },
  "updated_at": { "$date": "..." }
}
```

The meeting `_id` is published to RabbitMQ queue `meetinsights.meetings` as:

```json
{"id": "<meeting_id>"}
```

MeetRecorder consumes that queue, joins the live call, and writes an MP4 into `RECORDINGS_DIR`.

### Uploaded recordings

Users can also upload a previous recording. The file is stored in the **same local folder** MeetRecorder uses (`RECORDINGS_DIR`, default `../MeetRecorder/recordings`) with a unique name such as `upload-<uuid>.mp4` (not S3 yet).

MongoDB document:

```json
{
  "_id": { "$oid": "..." },
  "user_id": { "$oid": "..." },
  "platform": "google_meet",
  "meeting_url": null,
  "title": "Weekly sync",
  "status": "queued",
  "source": "upload",
  "storage": "local",
  "recording_filename": "upload-a1b2c3d4e5f6.mp4",
  "recording_path": "D:/home/developer/html/meet/MeetRecorder/recordings/upload-a1b2c3d4e5f6.mp4",
  "original_filename": "weekly-sync.mp4",
  "file_size_bytes": 12345678,
  "created_at": { "$date": "..." },
  "updated_at": { "$date": "..." }
}
```

The meeting `_id` is then published to RabbitMQ queue `meetinsights.recordings` (for MeetInsight, not the bot join queue):

```json
{"id": "<meeting_id>"}
```

MeetInsight consumes that queue, transcribes the file, and writes `transcript`, `transcript_segments`, and `status: completed` back onto the same meeting document.

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

`POST /api/meetings` — `Content-Type: application/json` and `Authorization: Bearer <access-token>`

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

Live bot invites go to queue `meetinsights.meetings`. Uploaded recordings go to queue `meetinsights.recordings` so MeetInsight can process them without MeetRecorder trying to join a call.

**Regenerate summary**, **Ask about this meeting**, and **Ask about this project** use Socket.IO (`MEETINSIGHT_SOCKET_URL`, default `http://127.0.0.1:8001`) with Bearer auth. Summary regeneration emits `summary:generate`. Chat emits `chat:message` with in-page history only (nothing stored in MongoDB). Project chat sends the selected meeting ids. MeetInsight answers from stored AI summaries with Gemini.

All JSON APIs:

| Method | Path | Body |
|--------|------|------|
| POST | `/api/auth/refresh` | none (HttpOnly refresh session) |
| POST | `/api/meetings` | platform, meeting_url, title, project_id? |
| POST | `/api/meetings/upload` | multipart: file, title?, platform?, project_id? |
| POST | `/api/meetings/{id}/project` | project_id (null to unassign) |
| POST | `/api/meetings/{id}/regenerate-transcript` | none |
| POST | `/api/projects` | name, description |

JSON APIs use `application/json`. Video upload is the only `multipart/form-data` endpoint.

### Upload recording API

`POST /api/meetings/upload` — `Content-Type: multipart/form-data` and `Authorization: Bearer <access-token>`

Fields: `file` (required video), `title`, `platform` (`google_meet` \| `zoom` \| `teams`), `project_id`.

Accepted types: `.mp4`, `.webm`, `.mov`, `.mkv`. Max size from `MAX_UPLOAD_BYTES` (default 2GB).

Response example:

```json
{
  "response": {
    "data": {
      "id": "...",
      "platform": "google_meet",
      "platform_label": "Google Meet",
      "title": "Weekly sync",
      "status": "queued",
      "source": "upload",
      "recording_filename": "upload-a1b2c3d4e5f6.mp4",
      "original_filename": "weekly-sync.mp4",
      "project_id": "...",
      "project_name": "Product Launch"
    },
    "status": {
      "msg": "Recording uploaded and queued for processing.",
      "action_status": true
    }
  }
}
```

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
