# Paperbow CRM / Order Management PRD

## Original problem statement
Build a full-stack internal CRM and order-management application for Paperbow, a pan-India personalized gifting and printing brand. The system starts only after a confirmed customer order and manages customers, SKUs, orders, payments, customization, production, quality checks, shipping, reporting, search, filters, roles, audit history, Indian currency/address conventions, CSV-ready operations, and realistic demo data.

## Architecture decisions
- React (CRA + CRACO) frontend + FastAPI (Motor async MongoDB) backend.
- MongoDB document model (approved by user).
- File storage: MongoDB GridFS by default; S3-compatible storage (AWS S3 / Cloudflare R2 / Backblaze / MinIO / Supabase) activates when `S3_BUCKET` env is set. No local filesystem persistence.
- Auth: JWT in httpOnly cookies, admin seed, login-attempt lockout.
- Portable deployment: everything configurable via env vars, no Emergent-only dependencies in runtime code, Vercel-ready (`CI=true yarn build` passes).

## User personas
- Admin: owns the Paperbow workspace, financial visibility, operational oversight.
- Manager: reviews order flow, customers, products, payments, reports.
- Staff: works the daily order, production, QC, shipping queue.

## What's implemented

### 2026-10-08 (initial MVP)
- Login + CRM shell, dashboard, customers, products, orders, order detail modal, retention report, demo data.

### 2026-10-08 (this iteration)
- Backend rewrite for portability: removed `emergentintegrations`, removed Emergent proxy upload path, added S3-compatible + GridFS storage adapter, added `/api/files/{id}` download endpoint (presigned URL for S3, streaming for GridFS).
- CORS now env-driven only (`CORS_ORIGINS`); cookies configurable (`COOKIE_SECURE`, `COOKIE_SAMESITE`) for cross-domain Vercel deploys.
- Dashboard metrics now include today/week/month revenue, avg order value, and a real 7-day revenue series.
- Fixed critical bug: "Add note" button on the order detail now actually calls `POST /api/orders/{id}/notes` and refreshes the timeline.
- New CSV import wizard with 3 steps (upload → review with validation errors & duplicates → confirm) backed by `POST /api/import/{kind}/preview` and `POST /api/import/{kind}`.
- Status filter on Orders page is wired to the backend.
- Order detail now has file category selector, courier/tracking inputs (persist on blur), and clickable file chips that download via `/api/files/{id}`.
- Dashboard greeting now uses the logged-in user and today's real date.
- Added `.env.example` for backend and frontend plus a deployment README (Vercel + any Python host).
- Testing agent: 18/18 pytest cases pass + full frontend Playwright flow passes.
- Vercel-ready: `CI=true yarn build` compiles with no ESLint errors.

## Prioritized backlog

### P1
- Multi-line order creation flow with customer selection, customization files, payment entry, and automatic production task creation.
- Full RBAC with Admin/Manager/Staff permissions on sensitive endpoints.
- Production Kanban board, QC pass/fail enforcement (block "Ready to Ship" until QC passed).
- Dedicated reports section: revenue by SKU / category / month, gross margin per SKU, fulfillment time analytics, date range filters.

### P2
- Audit log view, archive/undo for customers/SKUs/orders.
- Future integration adapters: WhatsApp Business, Instagram, Shopify, Razorpay, Shiprocket, email/accounting.
- Role management screen in Settings, printable invoice/PO view.
- Split `src/App.js` into per-component files for maintainability.
- Add `payment_status/priority/channel/status` defaults when importing orders CSV so documents land in a consistent shape.
