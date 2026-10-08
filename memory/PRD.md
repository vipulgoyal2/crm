# Paperbow CRM / Order Management PRD

## Original problem statement
Build a full-stack internal CRM and order-management application for Paperbow, a pan-India personalized gifting and printing brand. The system starts only after a confirmed customer order and manages customers, SKUs, orders, payments, customization, production, quality checks, shipping, reporting, search, filters, roles, audit history, Indian currency/address conventions, CSV-ready operations, and realistic demo data.

## Architecture decisions
- React frontend with responsive desktop-first CRM navigation and FastAPI backend.
- Existing MongoDB environment is used for the first release to preserve the configured runtime.
- JWT email/password authentication uses httpOnly cookies, an Admin seed account, role field, and login-attempt lockout.
- Domain records use explicit Paperbow order IDs (`PB-YYYY-####`) while Mongo `_id` remains internal.
- Dashboard, customers, products, orders, payments/production/shipping placeholders share the same API-backed workspace.

## User personas
- Admin: owns the Paperbow workspace, financial visibility, and operational oversight.
- Manager: reviews order flow, customers, products, payments, and reports.
- Staff: works the daily order, production, QC, and shipping queue.

## Core requirements (static)
- Confirmed/paid customer and order management only; no leads, inquiries, or sales pipeline.
- Fast navigation through Dashboard, Orders, Customers, Products/SKUs, Production, Payments, Shipping, Reports, and Settings.
- INR formatting, Indian phone/address conventions, clear workflow badges, persistent timelines, and responsive layouts.
- Demo workspace with realistic Indian records and secure admin login.

## What's implemented

### 2026-10-08
- Built premium Paperbow login and CRM shell with sidebar navigation, metrics, revenue chart, order-flow summary, recent orders, tables, responsive mobile sidebar, and polished empty states.
- Implemented Mongo-backed auth, admin seeding, httpOnly sessions, refresh-ready token structure, protected APIs, brute-force lockout, and idempotent password seeding.
- Implemented dashboard, customers, products/SKUs, orders, global search endpoint, order creation, PB order IDs, payment status calculation, customer stats updates, order status updates, and timeline events.
- Added functional customer and SKU creation modals with validation and unique status/payment test IDs.
- Seeded realistic Paperbow demo data and verified login, protected endpoints, customer/product/order APIs, order lifecycle, responsive UI, and production build.

## Prioritized backlog

### P0 — next tasks
- Complete multi-line order creation with customer selection, customization files, payment entry, and automatic production task creation.
- Add dedicated order detail route with editable payment, customization, QC, shipping, and timeline panels.
- Add real role-based permissions for Admin, Manager, and Staff.

### P1
- Add object storage for customer, reference, design, approved-design, and production files.
- Implement production Kanban, QC pass/fail workflow, shipping records, tracking copy, and delivered transitions.
- Build report aggregation endpoints, CSV exports, date filters, and SKU margin reporting.

### P2
- Add CSV import mapping/validation for customers, products, and orders.
- Add audit log pages and archive controls for business records.
- Add future adapter interfaces for WhatsApp, Shopify, courier, accounting, and email integrations without fake live integrations.