from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import logging
import os
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field, EmailStr

ROOT_DIR = Path(__file__).parent
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="paperbow_files")
app = FastAPI(title="Paperbow Operations")
api = APIRouter(prefix="/api")
JWT_ALGORITHM = "HS256"
logger = logging.getLogger("paperbow")

# ---------- helpers ----------
def now():
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def token_for(user_id: str, email: str, kind: str, minutes: int):
    return jwt.encode(
        {"sub": user_id, "email": email, "type": kind,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)},
        os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

async def current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token and request.headers.get("Authorization", "").startswith("Bearer "):
        token = request.headers["Authorization"][7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])}, {"password_hash": 0})
        if not user:
            raise HTTPException(401, "User not found")
        user["id"] = str(user.pop("_id"))
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Session expired")

def clean(doc):
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        mongo_id = str(doc.pop("_id"))
        if "id" not in doc:
            doc["id"] = mongo_id
    return doc

# ---------- storage adapter (S3-compatible if configured, else GridFS) ----------
S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "").strip() or None
S3_REGION = os.environ.get("S3_REGION", "").strip() or None
S3_PUBLIC_URL = os.environ.get("S3_PUBLIC_URL", "").strip().rstrip("/") or None
_s3_client = None

def s3_client():
    global _s3_client
    if _s3_client is not None or not S3_BUCKET:
        return _s3_client
    import boto3  # lazy import
    _s3_client = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY") or None,
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY") or None,
    )
    return _s3_client

async def storage_put(path: str, data: bytes, content_type: str) -> dict:
    """Returns {'backend': 's3'|'gridfs', 'path': <path>|<file_id>, 'size': int}."""
    if S3_BUCKET and s3_client():
        s3_client().put_object(Bucket=S3_BUCKET, Key=path, Body=data, ContentType=content_type)
        return {"backend": "s3", "path": path, "size": len(data)}
    file_id = await fs_bucket.upload_from_stream(
        path, io.BytesIO(data), metadata={"content_type": content_type}
    )
    return {"backend": "gridfs", "path": str(file_id), "size": len(data)}

async def storage_download(record: dict):
    """Returns StreamingResponse or RedirectResponse for a stored file."""
    content_type = record.get("content_type") or "application/octet-stream"
    filename = record.get("original_filename") or "file"
    if record.get("storage_backend") == "s3":
        if S3_PUBLIC_URL:
            return RedirectResponse(f"{S3_PUBLIC_URL}/{record['storage_path']}")
        if not S3_BUCKET or not s3_client():
            raise HTTPException(503, "File storage is not configured")
        url = s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": record["storage_path"],
                    "ResponseContentDisposition": f'attachment; filename="{filename}"'},
            ExpiresIn=3600,
        )
        return RedirectResponse(url)
    try:
        gridout = await fs_bucket.open_download_stream(ObjectId(record["storage_path"]))
    except Exception:
        raise HTTPException(404, "File not found")

    async def iter_file():
        while True:
            chunk = await gridout.readchunk()
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# ---------- models ----------
class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)

class CustomerIn(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    city: str = ""
    state: str = ""
    instagram: str = ""

class ProductIn(BaseModel):
    sku: str
    name: str
    category: str
    selling_price: float
    cost_price: float = 0
    stock: int = 0
    production_method: str = "Sublimation"
    status: str = "Active"

class OrderIn(BaseModel):
    customer_id: str
    product_id: str
    quantity: int = Field(default=1, ge=1)
    customization: str = ""
    channel: str = "WhatsApp"
    payment_method: str = "UPI"
    amount_paid: float = 0
    priority: str = "Normal"

class PaymentUpdate(BaseModel):
    amount_paid: float
    payment_method: str = "UPI"
    transaction_id: str = ""
    payment_notes: str = ""

class OperationsUpdate(BaseModel):
    production_status: Optional[str] = None
    qc_status: Optional[str] = None
    qc_notes: Optional[str] = None
    shipping_status: Optional[str] = None
    courier: Optional[str] = None
    tracking: Optional[str] = None

class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

class ImportCommit(BaseModel):
    rows: List[dict]
    skip_duplicates: bool = True

# ---------- routes ----------
@api.get("/")
async def root():
    return {"message": "Paperbow Operations API"}

@api.post("/auth/login")
async def login(body: Login, response: Response):
    identifier = body.email.lower()
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("locked_until", "") > now():
        raise HTTPException(429, "Too many attempts. Try again shortly.")
    user = await db.users.find_one({"email": identifier})
    if not user or not verify_password(body.password, user["password_hash"]):
        failed = (attempt or {}).get("failed", 0) + 1
        locked = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat() if failed >= 5 else ""
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$set": {"failed": failed, "locked_until": locked}}, upsert=True,
        )
        raise HTTPException(401, "Incorrect email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    access = token_for(str(user["_id"]), user["email"], "access", 15)
    refresh = token_for(str(user["_id"]), user["email"], "refresh", 10080)
    secure_cookies = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    samesite = os.environ.get("COOKIE_SAMESITE", "lax")
    response.set_cookie("access_token", access, httponly=True, samesite=samesite, secure=secure_cookies, max_age=900)
    response.set_cookie("refresh_token", refresh, httponly=True, samesite=samesite, secure=secure_cookies, max_age=604800)
    return clean({"_id": user["_id"], "name": user["name"], "email": user["email"], "role": user["role"]})

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"ok": True}

@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return user

# ---------- dashboard ----------
@api.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    orders = await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    customers = await db.customers.count_documents({"archived": {"$ne": True}})
    products = await db.products.count_documents({"status": "Active"})
    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)
    today_rev = week_rev = month_rev = 0.0
    revenue = 0.0
    paid_count = 0
    for o in orders:
        if o.get("payment_status") == "Pending":
            continue
        amount = float(o.get("amount_paid") or o.get("total") or 0)
        revenue += amount
        paid_count += 1
        try:
            dt = datetime.fromisoformat(str(o.get("created_at", "")).replace("Z", "+00:00")).date()
        except Exception:
            continue
        if dt == today:
            today_rev += amount
        if dt >= week_start:
            week_rev += amount
        if dt >= month_start:
            month_rev += amount
    statuses = {}
    for order in orders:
        s = order.get("status", "Confirmed")
        statuses[s] = statuses.get(s, 0) + 1
    avg = round(revenue / paid_count, 2) if paid_count else 0
    # revenue series over last 7 days
    buckets = {(today - timedelta(days=i)).isoformat(): 0.0 for i in range(6, -1, -1)}
    for o in orders:
        try:
            dt = datetime.fromisoformat(str(o.get("created_at", "")).replace("Z", "+00:00")).date().isoformat()
        except Exception:
            continue
        if dt in buckets:
            buckets[dt] += float(o.get("amount_paid") or o.get("total") or 0)
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    series = []
    for i, (day, value) in enumerate(buckets.items()):
        d = datetime.fromisoformat(day).weekday()
        series.append({"label": labels[d], "value": round(value, 2)})
    return {
        "revenue": round(revenue, 2),
        "today_revenue": round(today_rev, 2),
        "week_revenue": round(week_rev, 2),
        "month_revenue": round(month_rev, 2),
        "avg_order_value": avg,
        "orders": len(orders),
        "customers": customers,
        "products": products,
        "statuses": statuses,
        "recent_orders": orders[:6],
        "revenue_series": series,
    }

# ---------- customers ----------
@api.get("/customers")
async def customers(search: str = "", user=Depends(current_user)):
    query = {"archived": {"$ne": True}}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    rows = await db.customers.find(
        query,
        {"_id": 1, "name": 1, "phone": 1, "email": 1, "city": 1, "state": 1, "orders": 1, "spent": 1, "type": 1},
    ).sort("spent", -1).to_list(200)
    return [clean(x) for x in rows]

@api.post("/customers")
async def create_customer(body: CustomerIn, user=Depends(current_user)):
    if await db.customers.find_one({"phone": body.phone, "archived": {"$ne": True}}):
        raise HTTPException(409, "A customer with this phone already exists")
    doc = body.model_dump()
    doc.update({"orders": 0, "spent": 0, "type": "New", "created_at": now(), "archived": False})
    result = await db.customers.insert_one(doc)
    doc["_id"] = result.inserted_id
    return clean(doc)

# ---------- products ----------
@api.get("/products")
async def products(search: str = "", user=Depends(current_user)):
    query = {"status": {"$ne": "Archived"}}
    if search:
        query["$or"] = [
            {"sku": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]
    rows = await db.products.find(query).sort("sku", 1).to_list(200)
    return [clean(x) for x in rows]

@api.post("/products")
async def create_product(body: ProductIn, user=Depends(current_user)):
    if await db.products.find_one({"sku": body.sku}):
        raise HTTPException(409, "SKU already exists")
    doc = body.model_dump()
    doc.update({"created_at": now()})
    result = await db.products.insert_one(doc)
    doc["_id"] = result.inserted_id
    return clean(doc)

# ---------- orders ----------
@api.get("/orders")
async def orders(search: str = "", status: str = "All", user=Depends(current_user)):
    query = {}
    if status and status != "All":
        query["status"] = status
    if search:
        query["$or"] = [
            {"id": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"tracking": {"$regex": search, "$options": "i"}},
        ]
    rows = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)
    return [clean(x) for x in rows]

@api.post("/orders")
async def create_order(body: OrderIn, user=Depends(current_user)):
    try:
        customer = await db.customers.find_one({"_id": ObjectId(body.customer_id)})
        product = await db.products.find_one({"_id": ObjectId(body.product_id)})
    except Exception:
        raise HTTPException(400, "Invalid customer or product id")
    if not customer or not product:
        raise HTTPException(404, "Customer or product not found")
    count = await db.orders.count_documents({}) + 1
    order_id = f"PB-{datetime.now().year}-{count:04d}"
    total = body.quantity * float(product["selling_price"])
    paid = min(max(body.amount_paid, 0), total)
    payment_status = "Paid" if paid >= total else ("Partially Paid" if paid else "Pending")
    doc = {
        "id": order_id,
        "customer_id": body.customer_id,
        "customer_name": customer["name"],
        "product_id": body.product_id,
        "product_name": product["name"],
        "sku": product["sku"],
        "quantity": body.quantity,
        "customization": body.customization,
        "channel": body.channel,
        "priority": body.priority,
        "total": total,
        "amount_paid": paid,
        "pending": total - paid,
        "payment_method": body.payment_method,
        "payment_status": payment_status,
        "status": "Confirmed",
        "production_status": "Waiting",
        "shipping_status": "Not Ready",
        "created_at": now(),
        "timeline": [{"event": "Order created", "date": now(), "user": user["name"]}],
    }
    await db.orders.insert_one(doc)
    await db.customers.update_one(
        {"_id": customer["_id"]},
        {"$inc": {"orders": 1, "spent": total}, "$set": {"type": "Returning"}},
    )
    return clean(doc)

@api.get("/orders/{order_id}")
async def order_detail(order_id: str, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    order["files"] = await db.files.find(
        {"order_id": order_id, "is_deleted": False}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return order

@api.patch("/orders/{order_id}/status")
async def update_status(order_id: str, status: str, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    event = {"event": f"Order marked {status}", "date": now(), "user": user["name"]}
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"status": status}, "$push": {"timeline": event}},
    )
    return {"ok": True, "status": status}

@api.patch("/orders/{order_id}/payment")
async def update_payment(order_id: str, body: PaymentUpdate, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    total = float(order.get("total", 0))
    paid = min(max(body.amount_paid, 0), total)
    status = "Paid" if paid >= total else ("Partially Paid" if paid else "Pending")
    event = {"event": "Payment updated", "date": now(), "user": user["name"],
             "notes": f"{status} via {body.payment_method}"}
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "amount_paid": paid, "pending": total - paid, "payment_status": status,
            "payment_method": body.payment_method, "transaction_id": body.transaction_id,
            "payment_notes": body.payment_notes,
        }, "$push": {"timeline": event}},
    )
    return {"ok": True, "payment_status": status, "amount_paid": paid, "pending": total - paid}

@api.patch("/orders/{order_id}/operations")
async def update_operations(order_id: str, body: OperationsUpdate, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        return {"ok": True, "updated": {}}
    events = [
        {"event": f"{k.replace('_', ' ').title()} updated", "date": now(),
         "user": user["name"], "notes": str(v)}
        for k, v in changes.items()
    ]
    await db.orders.update_one(
        {"id": order_id},
        {"$set": changes, "$push": {"timeline": {"$each": events}}},
    )
    return {"ok": True, "updated": changes}

@api.post("/orders/{order_id}/notes")
async def add_order_note(order_id: str, body: NoteIn, user=Depends(current_user)):
    if not await db.orders.find_one({"id": order_id}, {"_id": 1}):
        raise HTTPException(404, "Order not found")
    event = {"event": "Internal note added", "date": now(), "user": user["name"], "notes": body.text}
    await db.orders.update_one({"id": order_id}, {"$push": {"timeline": event}})
    return {"ok": True, "note": event}

# ---------- files ----------
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}

@api.post("/orders/{order_id}/files")
async def upload_order_file(
    order_id: str,
    file: UploadFile = File(...),
    category: str = Query("Customer Upload"),
    user=Depends(current_user),
):
    if not await db.orders.find_one({"id": order_id}, {"_id": 1}):
        raise HTTPException(404, "Order not found")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Files must be smaller than {MAX_UPLOAD_BYTES // (1024*1024)}MB")
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(415, "Allowed types: JPG, PNG, WEBP, GIF, PDF")
    ext = (file.filename or "file").rsplit(".", 1)[-1][:8] if "." in (file.filename or "") else "bin"
    path = f"paperbow/uploads/{order_id}/{uuid.uuid4()}.{ext}"
    result = await storage_put(path, content, file.content_type)
    doc = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "storage_backend": result["backend"],
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result["size"],
        "category": category,
        "is_deleted": False,
        "uploaded_by": user["name"],
        "created_at": now(),
    }
    await db.files.insert_one(doc)
    # add timeline event
    await db.orders.update_one(
        {"id": order_id},
        {"$push": {"timeline": {"event": "File uploaded", "date": now(),
                                 "user": user["name"], "notes": f"{category}: {file.filename}"}}},
    )
    return {k: v for k, v in doc.items() if k != "_id"}

@api.get("/files/{file_id}")
async def download_file(file_id: str, user=Depends(current_user)):
    record = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")
    return await storage_download(record)

# ---------- retention / search / csv ----------
@api.get("/retention")
async def retention(user=Depends(current_user)):
    customers = await db.customers.find(
        {"archived": {"$ne": True}},
        {"_id": 0, "name": 1, "orders": 1, "spent": 1, "type": 1},
    ).sort("spent", -1).to_list(100)
    total = len(customers)
    returning = len([c for c in customers if c.get("orders", 0) > 1])
    vip = len([c for c in customers if c.get("type") == "VIP" or c.get("spent", 0) >= 5000])
    return {
        "total_customers": total,
        "returning_customers": returning,
        "vip_customers": vip,
        "repeat_rate": round(returning / total * 100, 1) if total else 0,
        "top_customers": customers[:5],
    }

@api.get("/search")
async def search(q: str, user=Depends(current_user)):
    customers = await db.customers.find(
        {"$or": [{"phone": {"$regex": q}}, {"name": {"$regex": q, "$options": "i"}},
                 {"email": {"$regex": q, "$options": "i"}}]},
        {"_id": 1, "name": 1, "phone": 1, "email": 1},
    ).to_list(8)
    orders = await db.orders.find(
        {"$or": [{"id": {"$regex": q, "$options": "i"}},
                 {"tracking": {"$regex": q, "$options": "i"}},
                 {"customer_name": {"$regex": q, "$options": "i"}}]},
        {"_id": 0, "id": 1, "customer_name": 1, "status": 1},
    ).to_list(8)
    products = await db.products.find(
        {"$or": [{"sku": {"$regex": q, "$options": "i"}},
                 {"name": {"$regex": q, "$options": "i"}}]},
        {"_id": 1, "sku": 1, "name": 1},
    ).to_list(8)
    return {
        "customers": [clean(x) for x in customers],
        "orders": orders,
        "products": [clean(x) for x in products],
    }

CSV_CONFIG = {
    "customers": {
        "fields": ["name", "phone", "email", "city", "state", "orders", "spent", "type"],
        "required": ["name", "phone"],
        "unique": "phone",
    },
    "products": {
        "fields": ["sku", "name", "category", "selling_price", "cost_price", "stock",
                   "production_method", "status"],
        "required": ["sku", "name", "category", "selling_price"],
        "unique": "sku",
    },
    "orders": {
        "fields": ["id", "customer_name", "product_name", "sku", "total",
                   "amount_paid", "payment_status", "status", "created_at"],
        "required": ["id", "customer_name", "total"],
        "unique": "id",
    },
}

@api.get("/export/{kind}")
async def export_csv(kind: str, user=Depends(current_user)):
    if kind not in CSV_CONFIG:
        raise HTTPException(400, "Export supports customers, products, and orders")
    collection = getattr(db, kind)
    fields = CSV_CONFIG[kind]["fields"]
    rows = await collection.find({}, {"_id": 0}).to_list(5000)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="paperbow-{kind}.csv"'},
    )

@api.post("/import/{kind}/preview")
async def import_preview(kind: str, file: UploadFile = File(...), user=Depends(current_user)):
    if kind not in CSV_CONFIG:
        raise HTTPException(400, "Import supports customers, products, and orders")
    try:
        raw = (await file.read()).decode("utf-8-sig")
        rows = list(csv.DictReader(raw.splitlines()))
    except Exception:
        raise HTTPException(400, "Upload a valid UTF-8 CSV file")
    if not rows:
        raise HTTPException(400, "CSV has no rows")
    cfg = CSV_CONFIG[kind]
    unique = cfg["unique"]
    collection = getattr(db, kind)
    existing = {d[unique] for d in await collection.find({unique: {"$ne": None}},
                                                        {"_id": 0, unique: 1}).to_list(10000)}
    seen = set()
    errors, duplicates, valid_rows = [], [], []
    for i, row in enumerate(rows, start=2):
        missing = [k for k in cfg["required"] if not row.get(k)]
        if missing:
            errors.append({"row": i, "missing": missing, "data": row})
            continue
        key = row.get(unique)
        if key in existing or key in seen:
            duplicates.append({"row": i, unique: key})
            continue
        seen.add(key)
        valid_rows.append(row)
    return {
        "columns": list(rows[0].keys()),
        "required": cfg["required"],
        "unique_field": unique,
        "total": len(rows),
        "valid": len(valid_rows),
        "errors": errors[:50],
        "duplicates": duplicates[:50],
        "sample_rows": valid_rows[:5],
        "rows": valid_rows,
    }

def _coerce_row(kind: str, row: dict) -> dict:
    row = {**row}
    if kind == "customers":
        row.update({"orders": int(float(row.get("orders") or 0)),
                    "spent": float(row.get("spent") or 0),
                    "type": row.get("type") or "New",
                    "archived": False,
                    "created_at": row.get("created_at") or now()})
    if kind == "products":
        for field in ("selling_price", "cost_price"):
            row[field] = float(row.get(field) or 0)
        row["stock"] = int(float(row.get("stock") or 0))
        row["status"] = row.get("status") or "Active"
        row["created_at"] = row.get("created_at") or now()
    if kind == "orders":
        row["total"] = float(row.get("total") or 0)
        row["amount_paid"] = float(row.get("amount_paid") or 0)
        row["pending"] = row["total"] - row["amount_paid"]
        row["created_at"] = row.get("created_at") or now()
        row.setdefault("timeline", [])
    return row

@api.post("/import/{kind}")
async def import_commit(kind: str, body: ImportCommit, user=Depends(current_user)):
    if kind not in CSV_CONFIG:
        raise HTTPException(400, "Import supports customers, products, and orders")
    cfg = CSV_CONFIG[kind]
    unique = cfg["unique"]
    collection = getattr(db, kind)
    inserted = 0
    skipped = 0
    for row in body.rows:
        missing = [k for k in cfg["required"] if not row.get(k)]
        if missing:
            continue
        key = row.get(unique)
        if body.skip_duplicates and await collection.find_one({unique: key}):
            skipped += 1
            continue
        await collection.insert_one(_coerce_row(kind, row))
        inserted += 1
    return {"status": "imported", "total": len(body.rows), "inserted": inserted,
            "skipped_duplicates": skipped}

# ---------- app wiring ----------
app.include_router(api)

_default_origins = ["http://localhost:3000", "http://localhost:5173"]
_env_origins = [x.strip() for x in os.environ.get("CORS_ORIGINS", "").split(",")
                if x.strip() and x.strip() != "*"]
origins = list(dict.fromkeys(_env_origins + _default_origins))
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- seed ----------
async def seed_data():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier", unique=True)
    await db.customers.create_index("phone")
    await db.products.create_index("sku", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.files.create_index("order_id")
    email = os.environ["ADMIN_EMAIL"]
    password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "email": email, "password_hash": hash_password(password),
            "name": "Aarav Mehta", "role": "admin", "created_at": now(),
        })
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"password_hash": hash_password(password)}},
        )
    if await db.products.count_documents({}) == 0:
        products_seed = [
            ("FRAME-001", "Classic Photo Frame", "Frames", 899, 18, "Laser"),
            ("MUG-001", "Signature Couple Mug", "Mugs", 499, 42, "Sublimation"),
            ("UV-014", "Acrylic Memory Plaque", "UV Printed Products", 1299, 9, "UV"),
            ("GIFT-022", "Story Box Gift Set", "Personalized Gifts", 1799, 6, "Outsourced"),
            ("DTF-033", "Custom T-Shirt Print", "DTF Products", 599, 24, "DTF"),
        ]
        await db.products.insert_many([
            {"sku": sku, "name": name, "category": cat,
             "selling_price": price, "cost_price": price * .42,
             "stock": stock, "production_method": method, "status": "Active",
             "created_at": now()}
            for sku, name, cat, price, stock, method in products_seed
        ])
    if await db.customers.count_documents({}) == 0:
        names = [
            ("Riya Sharma", "9876543210", "Mumbai", "Maharashtra"),
            ("Kabir Singh", "9812345678", "Delhi", "Delhi"),
            ("Ananya Iyer", "9988776655", "Bengaluru", "Karnataka"),
            ("Vikram Rao", "9898989898", "Hyderabad", "Telangana"),
            ("Meera Kapoor", "9765432109", "Pune", "Maharashtra"),
        ]
        await db.customers.insert_many([
            {"name": n, "phone": p, "city": c, "state": s,
             "email": f"{n.split()[0].lower()}@example.com",
             "orders": 0, "spent": 0, "type": "New",
             "created_at": now(), "archived": False}
            for n, p, c, s in names
        ])
    if await db.orders.count_documents({}) == 0:
        custs = await db.customers.find().to_list(5)
        prods = await db.products.find().to_list(4)
        for i in range(8):
            c = custs[i % len(custs)]
            p = prods[i % len(prods)]
            total = p["selling_price"]
            created = (datetime.now(timezone.utc) - timedelta(days=i)).isoformat()
            order_doc = {
                "id": f"PB-2026-{i + 1:04d}",
                "customer_id": str(c["_id"]), "customer_name": c["name"],
                "product_id": str(p["_id"]), "product_name": p["name"], "sku": p["sku"],
                "quantity": 1, "total": total, "amount_paid": total, "pending": 0,
                "payment_status": "Paid", "payment_method": "UPI",
                "status": ["Production", "Quality Check", "Ready to Ship", "Shipped", "Delivered"][i % 5],
                "production_status": "In Production",
                "shipping_status": "Shipped" if i % 5 > 2 else "Not Ready",
                "customization": "Personalized name and date",
                "channel": "WhatsApp", "priority": "Normal",
                "created_at": created,
                "timeline": [{"event": "Order created", "date": created, "user": "Aarav Mehta"}],
            }
            await db.orders.insert_one(order_doc)
            await db.customers.update_one(
                {"_id": c["_id"]},
                {"$inc": {"orders": 1, "spent": total}, "$set": {"type": "Returning"}},
            )

@app.on_event("startup")
async def startup():
    await seed_data()

@app.on_event("shutdown")
async def shutdown():
    client.close()
