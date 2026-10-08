# Paperbow Operations

Internal CRM and order management for Paperbow — a pan-India personalized gifting & printing brand.
Manages confirmed customers, orders, payments, customization, production, QC, and shipping.

Not a lead/inquiry tool — the workflow starts the moment an order is confirmed.

## Stack

- **Frontend**: React (CRA + CRACO), Axios, Recharts, Lucide icons
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB
- **File storage**: MongoDB GridFS by default, S3-compatible (AWS S3 / Cloudflare R2 / Backblaze / MinIO / Supabase) when env vars are set
- **Auth**: JWT in httpOnly cookies with login lockout

No proprietary cloud SDKs; everything is configurable via environment variables so the app is portable
to GitHub, Vercel, Render, Fly.io, Railway, or self-hosted environments.

## Local development

```bash
# Backend
cd backend
cp .env.example .env           # fill in values
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend
cd frontend
cp .env.example .env           # point REACT_APP_BACKEND_URL at the backend
yarn install
yarn start
```

Visit `http://localhost:3000`. The seed admin is created on first boot from `ADMIN_EMAIL`/`ADMIN_PASSWORD`
in `backend/.env`.

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Purpose |
|---|---|---|
| `MONGO_URL` | yes | MongoDB connection string |
| `DB_NAME` | yes | MongoDB database name |
| `JWT_SECRET` | yes | Signs session cookies (use a long random string) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | yes | Seeded admin account (idempotent — password is re-hashed if changed) |
| `CORS_ORIGINS` | yes in prod | Comma-separated list of frontend origins allowed to call the API |
| `COOKIE_SECURE` | optional | `true` when backend+frontend are on different HTTPS domains |
| `COOKIE_SAMESITE` | optional | `none` when `COOKIE_SECURE=true` for cross-site; otherwise `lax` |
| `S3_BUCKET` | optional | Set to enable S3-compatible storage; leave empty to use GridFS |
| `S3_ENDPOINT_URL` | optional | Needed for non-AWS providers (R2, B2, MinIO, Supabase) |
| `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | with S3 | Standard credentials |
| `S3_PUBLIC_URL` | optional | CDN or public base URL — if set, downloads redirect here instead of using presigned URLs |
| `MAX_UPLOAD_BYTES` | optional | File size limit (default 10 MB) |

### Frontend (`frontend/.env`)

| Variable | Required | Purpose |
|---|---|---|
| `REACT_APP_BACKEND_URL` | yes | Absolute URL of the FastAPI backend, no trailing slash |

## Deploying

### Frontend → Vercel

1. Push the `frontend` directory as a Vercel project (framework preset: Create React App).
2. Set `REACT_APP_BACKEND_URL` to the public URL of your deployed backend.
3. Build command: `yarn build` · Output directory: `build`.

### Backend → any Python host (Render, Fly.io, Railway, Docker)

Any host that can run `uvicorn server:app --host 0.0.0.0 --port $PORT` works. Set the backend env vars
in your platform. When frontend and backend live on different domains:

- set `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none` so the session cookie is accepted cross-site;
- add the frontend origin to `CORS_ORIGINS`.

### Database

Any MongoDB provider (MongoDB Atlas, DigitalOcean managed, self-hosted). No GridFS setup required —
the app creates the bucket on first upload.

### File storage

Default = GridFS (requires nothing extra). To move to S3-compatible storage, set `S3_BUCKET` and the
matching credentials. Existing GridFS files remain downloadable through `/api/files/{id}` because the
backend remembers which backend each file was stored with.

## Nothing is persisted on disk

Uploaded files go to GridFS or S3, never to the local filesystem. The app has no `uploads/`, `data/`,
or `tmp/` directories to persist between deploys.

## Default login

`admin@paperbow.in` / `Paperbow2026!` — change `ADMIN_PASSWORD` in your `.env` before going live.
