from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import logging
import os
import secrets
import csv
import io
import uuid
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

ROOT_DIR = Path(__file__).parent
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Paperbow Operations")
api = APIRouter(prefix="/api")
JWT_ALGORITHM = "HS256"
logger = logging.getLogger("paperbow")

def now():
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def token_for(user_id: str, email: str, kind: str, minutes: int):
    return jwt.encode({"sub": user_id, "email": email, "type": kind, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

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
    except (jwt.InvalidTokenError, Exception) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(401, "Session expired")

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

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
storage_key = None

def init_storage():
    global storage_key
    if storage_key or not os.environ.get("EMERGENT_LLM_KEY"):
        return storage_key
    result = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    result.raise_for_status(); storage_key = result.json()["storage_key"]
    return storage_key

def put_object(path, data, content_type):
    key = init_storage()
    if not key: raise HTTPException(503, "File storage is not configured")
    result = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    result.raise_for_status(); return result.json()

def clean(doc):
    if not doc: return doc
    doc = dict(doc)
    if "_id" in doc:
        mongo_id = str(doc.pop("_id"))
        if "id" not in doc:
            doc["id"] = mongo_id
    return doc

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
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": {"failed": failed, "locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat() if failed >= 5 else ""}}, upsert=True)
        raise HTTPException(401, "Incorrect email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    access = token_for(str(user["_id"]), user["email"], "access", 15)
    refresh = token_for(str(user["_id"]), user["email"], "refresh", 10080)
    response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=900)
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax", max_age=604800)
    return clean({"_id": user["_id"], "name": user["name"], "email": user["email"], "role": user["role"]})

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token"); response.delete_cookie("refresh_token")
    return {"ok": True}

@api.get("/auth/me")
async def me(user=Depends(current_user)): return user

@api.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    orders = await db.orders.find({}, {"_id": 0}).to_list(500)
    customers = await db.customers.count_documents({"archived": {"$ne": True}})
    products = await db.products.count_documents({"status": "Active"})
    revenue = sum(float(o.get("total", 0)) for o in orders if o.get("payment_status") != "Pending")
    statuses = {}
    for order in orders: statuses[order.get("status", "Confirmed")] = statuses.get(order.get("status", "Confirmed"), 0) + 1
    return {"revenue": revenue, "orders": len(orders), "customers": customers, "products": products, "statuses": statuses,
            "recent_orders": orders[:6], "revenue_series": [{"label": x, "value": revenue * v} for x, v in [("Mon", .12), ("Tue", .18), ("Wed", .15), ("Thu", .22), ("Fri", .16), ("Sat", .1), ("Sun", .07)]]}

@api.get("/customers")
async def customers(search: str = "", user=Depends(current_user)):
    query = {"archived": {"$ne": True}}
    if search: query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"phone": {"$regex": search}}, {"email": {"$regex": search, "$options": "i"}}]
    return [clean(x) for x in await db.customers.find(query, {"_id": 1, "name": 1, "phone": 1, "email": 1, "city": 1, "orders": 1, "spent": 1, "type": 1}).sort("spent", -1).to_list(200)]

@api.post("/customers")
async def create_customer(body: CustomerIn, user=Depends(current_user)):
    doc = body.model_dump(); doc.update({"orders": 0, "spent": 0, "type": "New", "created_at": now(), "archived": False})
    result = await db.customers.insert_one(doc); doc["_id"] = result.inserted_id
    return clean(doc)

@api.get("/products")
async def products(search: str = "", user=Depends(current_user)):
    query = {"status": {"$ne": "Archived"}}
    if search: query["$or"] = [{"sku": {"$regex": search, "$options": "i"}}, {"name": {"$regex": search, "$options": "i"}}]
    return [clean(x) for x in await db.products.find(query).sort("sku", 1).to_list(200)]

@api.post("/products")
async def create_product(body: ProductIn, user=Depends(current_user)):
    if await db.products.find_one({"sku": body.sku}): raise HTTPException(409, "SKU already exists")
    doc = body.model_dump(); doc.update({"created_at": now()}); result = await db.products.insert_one(doc); doc["_id"] = result.inserted_id
    return clean(doc)

@api.get("/orders")
async def orders(search: str = "", status: str = "All", user=Depends(current_user)):
    query = {}
    if status != "All": query["status"] = status
    if search: query["$or"] = [{"id": {"$regex": search, "$options": "i"}}, {"customer_name": {"$regex": search, "$options": "i"}}]
    return [clean(x) for x in await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)]

@api.post("/orders")
async def create_order(body: OrderIn, user=Depends(current_user)):
    customer = await db.customers.find_one({"_id": ObjectId(body.customer_id)})
    product = await db.products.find_one({"_id": ObjectId(body.product_id)})
    if not customer or not product: raise HTTPException(404, "Customer or product not found")
    count = await db.orders.count_documents({}) + 1; order_id = f"PB-{datetime.now().year}-{count:04d}"
    total = body.quantity * product["selling_price"]; paid = min(body.amount_paid, total)
    doc = {"id": order_id, "customer_id": body.customer_id, "customer_name": customer["name"], "product_id": body.product_id, "product_name": product["name"], "sku": product["sku"], "quantity": body.quantity, "customization": body.customization, "channel": body.channel, "priority": body.priority, "total": total, "amount_paid": paid, "pending": total-paid, "payment_status": "Paid" if paid >= total else ("Partially Paid" if paid else "Pending"), "status": "Confirmed", "production_status": "Waiting", "shipping_status": "Not Ready", "created_at": now(), "timeline": [{"event": "Order created", "date": now(), "user": user["name"]}]}
    await db.orders.insert_one(doc)
    await db.customers.update_one({"_id": customer["_id"]}, {"$inc": {"orders": 1, "spent": total}, "$set": {"type": "Returning"}})
    return clean(doc)

@api.patch("/orders/{order_id}/status")
async def update_status(order_id: str, status: str, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order: raise HTTPException(404, "Order not found")
    event = {"event": f"Order marked {status}", "date": now(), "user": user["name"]}
    await db.orders.update_one({"id": order_id}, {"$set": {"status": status}, "$push": {"timeline": event}})
    return {"ok": True, "status": status}

@api.get("/orders/{order_id}")
async def order_detail(order_id: str, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order: raise HTTPException(404, "Order not found")
    order["files"] = await db.files.find({"order_id": order_id, "is_deleted": False}, {"_id": 0}).to_list(100)
    return order

@api.patch("/orders/{order_id}/payment")
async def update_payment(order_id: str, body: PaymentUpdate, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order: raise HTTPException(404, "Order not found")
    paid = min(max(body.amount_paid, 0), float(order.get("total", 0)))
    status = "Paid" if paid >= order.get("total", 0) else ("Partially Paid" if paid else "Pending")
    event = {"event": "Payment updated", "date": now(), "user": user["name"], "notes": f"{status} via {body.payment_method}"}
    await db.orders.update_one({"id": order_id}, {"$set": {"amount_paid": paid, "pending": order.get("total", 0)-paid, "payment_status": status, "payment_method": body.payment_method, "transaction_id": body.transaction_id, "payment_notes": body.payment_notes}, "$push": {"timeline": event}})
    return {"ok": True, "payment_status": status, "amount_paid": paid, "pending": order.get("total", 0)-paid}

@api.patch("/orders/{order_id}/operations")
async def update_operations(order_id: str, body: OperationsUpdate, user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order: raise HTTPException(404, "Order not found")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    events = [{"event": f"{k.replace('_', ' ').title()} updated", "date": now(), "user": user["name"], "notes": v} for k, v in changes.items()]
    await db.orders.update_one({"id": order_id}, {"$set": changes, "$push": {"timeline": {"$each": events}}})
    return {"ok": True, "updated": changes}

@api.post("/orders/{order_id}/files")
async def upload_order_file(order_id: str, file: UploadFile = File(...), category: str = Query("Customer Upload"), user=Depends(current_user)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 1})
    if not order: raise HTTPException(404, "Order not found")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024: raise HTTPException(413, "Files must be smaller than 10MB")
    allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if file.content_type not in allowed: raise HTTPException(415, "Use JPG, PNG, WEBP, or PDF files")
    path = f"paperbow/uploads/{order_id}/{uuid.uuid4()}.{(file.filename or 'file').split('.')[-1]}"
    result = put_object(path, content, file.content_type)
    doc = {"id": str(uuid.uuid4()), "order_id": order_id, "storage_path": result["path"], "original_filename": file.filename, "content_type": file.content_type, "size": len(content), "category": category, "is_deleted": False, "created_at": now()}
    await db.files.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api.get("/retention")
async def retention(user=Depends(current_user)):
    customers = await db.customers.find({"archived": {"$ne": True}}, {"_id": 0, "name": 1, "orders": 1, "spent": 1, "type": 1}).sort("spent", -1).to_list(100)
    total = len(customers); returning = len([c for c in customers if c.get("orders", 0) > 1]); vip = len([c for c in customers if c.get("type") == "VIP" or c.get("spent", 0) >= 5000])
    return {"total_customers": total, "returning_customers": returning, "vip_customers": vip, "repeat_rate": round(returning / total * 100, 1) if total else 0, "top_customers": customers[:5]}

@api.get("/export/{kind}")
async def export_csv(kind: str, user=Depends(current_user)):
    configs = {"customers": (db.customers, ["name", "phone", "email", "city", "state", "orders", "spent", "type"]), "products": (db.products, ["sku", "name", "category", "selling_price", "cost_price", "stock", "production_method", "status"]), "orders": (db.orders, ["id", "customer_name", "product_name", "sku", "total", "amount_paid", "payment_status", "status", "created_at"])}
    if kind not in configs: raise HTTPException(400, "Export supports customers, products, and orders")
    collection, fields = configs[kind]; rows = await collection.find({}, {"_id": 0}).to_list(1000); stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=paperbow-{kind}.csv"})

@api.post("/import/{kind}")
async def import_csv(kind: str, file: UploadFile = File(...), user=Depends(current_user)):
    if kind not in {"customers", "products", "orders"}: raise HTTPException(400, "Import supports customers, products, and orders")
    try: rows = list(csv.DictReader((await file.read()).decode("utf-8-sig").splitlines()))
    except Exception: raise HTTPException(400, "Upload a valid UTF-8 CSV file")
    if not rows: raise HTTPException(400, "CSV has no rows")
    required = {"customers": ["name", "phone"], "products": ["sku", "name", "category", "selling_price"], "orders": ["id", "customer_name", "total"]}[kind]
    errors = [{"row": i + 2, "missing": [x for x in required if not row.get(x)]} for i, row in enumerate(rows) if any(not row.get(x) for x in required)]
    if errors: return {"status": "needs_review", "total": len(rows), "valid": len(rows)-len(errors), "errors": errors[:25]}
    collection = getattr(db, kind)
    inserted = 0; skipped = 0
    unique_field = {"customers": "phone", "products": "sku", "orders": "id"}[kind]
    for row in rows:
        if await collection.find_one({unique_field: row[unique_field]}): skipped += 1; continue
        if kind == "customers": row.update({"orders": 0, "spent": 0, "type": "New", "archived": False})
        if kind == "products":
            for field in ["selling_price", "cost_price", "stock"]:
                if field in row: row[field] = float(row[field] or 0) if field != "stock" else int(float(row[field] or 0))
        await collection.insert_one(row); inserted += 1
    return {"status": "imported", "total": len(rows), "inserted": inserted, "skipped_duplicates": skipped}

@api.get("/search")
async def search(q: str, user=Depends(current_user)):
    return {"customers": [clean(x) for x in await db.customers.find({"$or": [{"phone": {"$regex": q}}, {"name": {"$regex": q, "$options": "i"}}]}, {"name": 1, "phone": 1}).to_list(8)], "orders": await db.orders.find({"$or": [{"id": {"$regex": q, "$options": "i"}}, {"tracking": {"$regex": q, "$options": "i"}}]}, {"_id": 0, "id": 1, "customer_name": 1, "status": 1}).to_list(8)}

app.include_router(api)
origins = [x.strip() for x in os.environ.get("CORS_ORIGINS", "").split(",") if x.strip() and x.strip() != "*"]
origins += ["https://paperbow-ops.preview.emergentagent.com", "http://localhost:3000"]
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=list(set(origins)), allow_methods=["*"], allow_headers=["*"])

async def seed_data():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier", unique=True)
    email, password = os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing: await db.users.insert_one({"email": email, "password_hash": hash_password(password), "name": "Aarav Mehta", "role": "admin", "created_at": now()})
    elif not verify_password(password, existing["password_hash"]): await db.users.update_one({"_id": existing["_id"]}, {"$set": {"password_hash": hash_password(password)}})
    if await db.products.count_documents({}) == 0:
        products = [{"sku": f"{sku}", "name": name, "category": cat, "selling_price": price, "cost_price": price*.42, "stock": stock, "production_method": method, "status": "Active", "created_at": now()} for sku,name,cat,price,stock,method in [("FRAME-001","Classic Photo Frame","Frames",899,18,"Laser"),("MUG-001","Signature Couple Mug","Mugs",499,42,"Sublimation"),("UV-014","Acrylic Memory Plaque","UV Printed Products",1299,9,"UV"),("GIFT-022","Story Box Gift Set","Personalized Gifts",1799,6,"Outsourced")]]
        await db.products.insert_many(products)
    if await db.customers.count_documents({}) == 0:
        names = [("Riya Sharma","9876543210","Mumbai","Maharashtra"),("Kabir Singh","9812345678","Delhi","Delhi"),("Ananya Iyer","9988776655","Bengaluru","Karnataka"),("Vikram Rao","9898989898","Hyderabad","Telangana"),("Meera Kapoor","9765432109","Pune","Maharashtra")]
        await db.customers.insert_many([{"name":n,"phone":p,"city":c,"state":s,"email":f"{n.split()[0].lower()}@example.com","orders":0,"spent":0,"type":"New","created_at":now(),"archived":False} for n,p,c,s in names])
    if await db.orders.count_documents({}) == 0:
        custs = await db.customers.find().to_list(5); prods = await db.products.find().to_list(4)
        for i in range(8):
            c, p = custs[i % len(custs)], prods[i % len(prods)]; total = p["selling_price"]
            await db.orders.insert_one({"id":f"PB-2026-{i+1:04d}","customer_id":str(c["_id"]),"customer_name":c["name"],"product_name":p["name"],"sku":p["sku"],"quantity":1,"total":total,"amount_paid":total,"pending":0,"payment_status":"Paid","status":["Production","Quality Check","Ready to Ship","Shipped","Delivered"][i%5],"production_status":"In Production","shipping_status":"Shipped" if i%5>2 else "Not Ready","customization":"Personalized name and date","created_at":now(),"timeline":[]})
            await db.customers.update_one({"_id":c["_id"]},{"$inc":{"orders":1,"spent":total},"$set":{"type":"Returning"}})

@app.on_event("startup")
async def startup(): await seed_data()
@app.on_event("shutdown")
async def shutdown(): client.close()