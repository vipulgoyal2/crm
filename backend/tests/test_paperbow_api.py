"""Paperbow backend regression tests.

Covers auth, dashboard, orders CRUD + filters, order detail (notes/payment/operations/status),
file upload + download via GridFS, CSV export, CSV import wizard (preview+commit),
retention insights, duplicate protection, auth guards, logout, and brute-force lockout
(scratch email so the admin stays usable).
"""
import io
import os
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL = "admin@paperbow.in"
PASSWORD = "Paperbow2026!"
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\x9a\xd7\x80\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------- fixtures ----------
@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def authed(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.cookies.get("access_token")
    return client


@pytest.fixture
def sample_order_id(authed):
    orders = authed.get(f"{BASE_URL}/api/orders").json()
    assert orders, "Seed orders missing"
    return orders[0]["id"]


# ---------- auth ----------
def test_unauthenticated_rejects(client):
    for ep in ("dashboard", "customers", "products", "orders", "orders/PB-2026-0001"):
        r = client.get(f"{BASE_URL}/api/{ep}")
        assert r.status_code == 401, (ep, r.status_code)
    r = client.get(f"{BASE_URL}/api/files/{uuid.uuid4()}")
    assert r.status_code == 401


def test_login_me_logout(authed):
    me = authed.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == EMAIL and body["role"] == "admin"
    assert "_id" not in body and "password_hash" not in body
    out = authed.post(f"{BASE_URL}/api/auth/logout")
    assert out.status_code == 200
    # After logout cookies cleared
    s2 = requests.Session()
    assert s2.get(f"{BASE_URL}/api/auth/me").status_code == 401


def test_login_lockout_scratch_email():
    """Use a scratch email so admin isn't locked."""
    scratch = f"scratch_{uuid.uuid4().hex[:8]}@example.com"
    saw_429 = False
    for i in range(6):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": scratch, "password": "wrongpass123"})
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "Expected 429 after 5 bad attempts"


# ---------- dashboard ----------
def test_dashboard_shape(authed):
    r = authed.get(f"{BASE_URL}/api/dashboard")
    assert r.status_code == 200
    d = r.json()
    for key in ("today_revenue", "week_revenue", "month_revenue", "avg_order_value",
                "revenue_series", "statuses", "recent_orders"):
        assert key in d, f"missing {key}"
    assert len(d["revenue_series"]) == 7
    for o in d["recent_orders"]:
        assert "_id" not in o
        assert str(o.get("id", "")).startswith("PB-")


# ---------- orders filters & detail ----------
def test_orders_filter_delivered(authed):
    r = authed.get(f"{BASE_URL}/api/orders", params={"status": "Delivered"})
    assert r.status_code == 200
    rows = r.json()
    assert rows, "Expected at least one Delivered order from seed"
    assert all(o["status"] == "Delivered" for o in rows)


def test_orders_search(authed, sample_order_id):
    r = authed.get(f"{BASE_URL}/api/orders", params={"search": sample_order_id})
    assert r.status_code == 200
    assert any(o["id"] == sample_order_id for o in r.json())


def test_order_detail_has_files_and_timeline(authed, sample_order_id):
    r = authed.get(f"{BASE_URL}/api/orders/{sample_order_id}")
    assert r.status_code == 200
    data = r.json()
    assert "_id" not in data
    assert isinstance(data["files"], list)
    assert isinstance(data["timeline"], list) and data["timeline"]


# ---------- notes/payment/operations/status ----------
def test_add_note_appends_timeline(authed, sample_order_id):
    before = len(authed.get(f"{BASE_URL}/api/orders/{sample_order_id}").json()["timeline"])
    r = authed.post(f"{BASE_URL}/api/orders/{sample_order_id}/notes",
                    json={"text": "TEST note from pytest"})
    assert r.status_code == 200 and r.json()["ok"] is True
    tl = authed.get(f"{BASE_URL}/api/orders/{sample_order_id}").json()["timeline"]
    assert len(tl) == before + 1
    assert tl[-1]["event"] == "Internal note added"
    assert tl[-1]["notes"] == "TEST note from pytest"


def test_payment_update_marks_paid(authed):
    # Make a scratch order with partial payment then full pay it
    suf = uuid.uuid4().hex[:6]
    cust = authed.post(f"{BASE_URL}/api/customers",
                       json={"name": f"TEST_{suf}", "phone": f"800{suf}00"}).json()
    prod = authed.post(f"{BASE_URL}/api/products",
                       json={"sku": f"TESTPAY-{suf}", "name": "x", "category": "c",
                             "selling_price": 500}).json()
    order = authed.post(f"{BASE_URL}/api/orders",
                        json={"customer_id": cust["id"], "product_id": prod["id"],
                              "quantity": 1, "amount_paid": 100}).json()
    assert order["payment_status"] == "Partially Paid"
    r = authed.patch(f"{BASE_URL}/api/orders/{order['id']}/payment",
                     json={"amount_paid": 500, "payment_method": "UPI"})
    assert r.status_code == 200 and r.json()["payment_status"] == "Paid"
    tl = authed.get(f"{BASE_URL}/api/orders/{order['id']}").json()["timeline"]
    assert any(e["event"] == "Payment updated" for e in tl)


def test_operations_and_status_updates(authed, sample_order_id):
    r = authed.patch(f"{BASE_URL}/api/orders/{sample_order_id}/operations",
                     json={"production_status": "In Production", "shipping_status": "Shipped",
                           "courier": "BlueDart", "tracking": "TRK123"})
    assert r.status_code == 200 and r.json()["ok"] is True
    detail = authed.get(f"{BASE_URL}/api/orders/{sample_order_id}").json()
    assert detail["courier"] == "BlueDart" and detail["tracking"] == "TRK123"
    s = authed.patch(f"{BASE_URL}/api/orders/{sample_order_id}/status",
                     params={"status": "Shipped"})
    assert s.status_code == 200 and s.json()["status"] == "Shipped"
    tl = authed.get(f"{BASE_URL}/api/orders/{sample_order_id}").json()["timeline"]
    assert any("Shipped" in e["event"] for e in tl)


# ---------- files ----------
def test_upload_and_download_file_gridfs(authed, sample_order_id):
    # must send multipart - temporarily drop content-type header
    s = requests.Session()
    s.cookies.update(authed.cookies.get_dict())
    files = {"file": ("test.png", PNG_BYTES, "image/png")}
    r = s.post(f"{BASE_URL}/api/orders/{sample_order_id}/files?category=Reference",
               files=files)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["storage_backend"] == "gridfs"
    assert rec["content_type"] == "image/png"
    file_id = rec["id"]
    # Shows up in order detail
    detail = authed.get(f"{BASE_URL}/api/orders/{sample_order_id}").json()
    assert any(f["id"] == file_id for f in detail["files"])
    assert any(e["event"] == "File uploaded" for e in detail["timeline"])
    # Download
    d = s.get(f"{BASE_URL}/api/files/{file_id}")
    assert d.status_code == 200
    assert "attachment" in d.headers.get("Content-Disposition", "")
    assert d.content == PNG_BYTES


def test_upload_rejects_bad_type(authed, sample_order_id):
    s = requests.Session()
    s.cookies.update(authed.cookies.get_dict())
    files = {"file": ("foo.txt", b"hello", "text/plain")}
    r = s.post(f"{BASE_URL}/api/orders/{sample_order_id}/files", files=files)
    assert r.status_code == 415


# ---------- csv export ----------
def test_export_csv(authed):
    for kind, header_col in (("customers", "name"), ("products", "sku"), ("orders", "id")):
        r = authed.get(f"{BASE_URL}/api/export/{kind}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert f'filename="paperbow-{kind}.csv"' in r.headers.get("Content-Disposition", "")
        first_line = r.text.splitlines()[0]
        assert header_col in first_line


# ---------- csv import ----------
def _upload_csv(authed, path, csv_text):
    s = requests.Session()
    s.cookies.update(authed.cookies.get_dict())
    files = {"file": ("input.csv", csv_text.encode("utf-8"), "text/csv")}
    return s.post(f"{BASE_URL}{path}", files=files)


def test_import_customers_preview_and_commit(authed):
    # Ensure a known duplicate phone exists (use first seeded customer phone)
    existing = authed.get(f"{BASE_URL}/api/customers").json()
    dup_phone = existing[0]["phone"]
    uniq = uuid.uuid4().hex[:6]
    csv_text = (
        "name,phone,email,city,state\n"
        f"TEST Import {uniq},900{uniq}11,imp_{uniq}@test.com,Mumbai,MH\n"
        f",900{uniq}22,noname@test.com,Pune,MH\n"
        f"Dup Customer,{dup_phone},dup@test.com,Delhi,DL\n"
    )
    r = _upload_csv(authed, "/api/import/customers/preview", csv_text)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["total"] == 3
    assert p["valid"] == 1
    assert any("name" in e.get("missing", []) for e in p["errors"])
    assert any(d.get("phone") == dup_phone for d in p["duplicates"])
    assert p["unique_field"] == "phone"
    valid_rows = p["rows"]
    # Commit
    c = authed.post(f"{BASE_URL}/api/import/customers",
                    json={"rows": valid_rows, "skip_duplicates": True})
    assert c.status_code == 200 and c.json()["inserted"] == 1
    # Re-commit skips as duplicate
    c2 = authed.post(f"{BASE_URL}/api/import/customers",
                     json={"rows": valid_rows, "skip_duplicates": True})
    assert c2.status_code == 200
    assert c2.json()["inserted"] == 0 and c2.json()["skipped_duplicates"] == 1


def test_import_products_and_orders(authed):
    uniq = uuid.uuid4().hex[:6]
    # Products
    pcsv = (
        "sku,name,category,selling_price\n"
        f"TESTIMP-{uniq},Imp Product,Testing,250\n"
    )
    r = _upload_csv(authed, "/api/import/products/preview", pcsv)
    assert r.status_code == 200 and r.json()["unique_field"] == "sku"
    rows = r.json()["rows"]
    assert authed.post(f"{BASE_URL}/api/import/products",
                       json={"rows": rows}).json()["inserted"] == 1
    # Orders
    ocsv = (
        "id,customer_name,product_name,sku,total,amount_paid,payment_status,status,created_at\n"
        f"PB-IMP-{uniq},Imp Cust,Imp Prod,TESTIMP-{uniq},500,500,Paid,Confirmed,2026-01-01T00:00:00+00:00\n"
    )
    r = _upload_csv(authed, "/api/import/orders/preview", ocsv)
    assert r.status_code == 200 and r.json()["unique_field"] == "id"
    rows = r.json()["rows"]
    assert authed.post(f"{BASE_URL}/api/import/orders",
                       json={"rows": rows}).json()["inserted"] == 1


# ---------- retention ----------
def test_retention(authed):
    r = authed.get(f"{BASE_URL}/api/retention")
    assert r.status_code == 200
    d = r.json()
    for k in ("total_customers", "returning_customers", "vip_customers", "repeat_rate",
              "top_customers"):
        assert k in d
    assert isinstance(d["top_customers"], list)


# ---------- duplicate protection ----------
def test_duplicate_customer_phone_409(authed):
    existing = authed.get(f"{BASE_URL}/api/customers").json()
    dup = existing[0]["phone"]
    r = authed.post(f"{BASE_URL}/api/customers",
                    json={"name": "TEST Dup", "phone": dup})
    assert r.status_code == 409


def test_duplicate_product_sku_409(authed):
    existing = authed.get(f"{BASE_URL}/api/products").json()
    dup = existing[0]["sku"]
    r = authed.post(f"{BASE_URL}/api/products",
                    json={"sku": dup, "name": "x", "category": "c", "selling_price": 1})
    assert r.status_code == 409


# ---------- multi-item orders (iteration 6) ----------
def _seed_two_products(authed, suf):
    """Create frame (899) and giftbox (1799) products for GST math test."""
    p1 = authed.post(f"{BASE_URL}/api/products", json={
        "sku": f"TESTFRAME-{suf}", "name": "Test Frame", "category": "Frames",
        "selling_price": 899,
    })
    p2 = authed.post(f"{BASE_URL}/api/products", json={
        "sku": f"TESTGIFT-{suf}", "name": "Test Giftbox", "category": "Gifts",
        "selling_price": 1799,
    })
    assert p1.status_code == 200 and p2.status_code == 200, (p1.text, p2.text)
    return p1.json()["id"], p2.json()["id"]


def test_multi_item_order_gst_math(authed):
    suf = uuid.uuid4().hex[:6]
    cust = authed.post(f"{BASE_URL}/api/customers",
                       json={"name": f"TEST_multi_{suf}", "phone": f"777{suf}00"}).json()
    frame_id, gift_id = _seed_two_products(authed, suf)
    payload = {
        "customer_id": cust["id"],
        "items": [
            {"product_id": frame_id, "quantity": 2, "discount": 50, "tax_rate": 18},
            {"product_id": gift_id, "quantity": 1, "tax_rate": 5},
        ],
        "shipping_cost": 80,
        "amount_paid": 1000,
    }
    r = authed.post(f"{BASE_URL}/api/orders", json=payload)
    assert r.status_code == 200, r.text
    order = r.json()
    assert len(order["items"]) == 2
    assert order["subtotal"] == pytest.approx(3547, abs=0.5)
    assert order["tax"] == pytest.approx(404.59, abs=0.5)
    assert order["shipping_cost"] == 80
    assert order["total"] == pytest.approx(4031.59, abs=0.5)
    assert order["amount_paid"] == 1000
    assert order["pending"] == pytest.approx(3031.59, abs=0.5)
    assert order["payment_status"] == "Partially Paid"
    # per-line math
    line1 = order["items"][0]
    assert line1["quantity"] == 2 and line1["unit_price"] == 899
    assert line1["tax"] == pytest.approx(314.64, abs=0.1)
    assert line1["line_total"] == pytest.approx(2062.64, abs=0.1)
    line2 = order["items"][1]
    assert line2["tax"] == pytest.approx(89.95, abs=0.1)
    assert line2["line_total"] == pytest.approx(1888.95, abs=0.1)
    # customer.spent incremented by GRAND total, not first item
    custs = authed.get(f"{BASE_URL}/api/customers", params={"search": cust["phone"]}).json()
    hit = next(c for c in custs if c["id"] == cust["id"])
    assert hit["spent"] == pytest.approx(4031.59, abs=0.5)
    # GET detail returns customer_phone/email
    detail = authed.get(f"{BASE_URL}/api/orders/{order['id']}").json()
    assert detail["customer_phone"] == cust["phone"]


def test_legacy_single_item_still_works(authed):
    suf = uuid.uuid4().hex[:6]
    cust = authed.post(f"{BASE_URL}/api/customers",
                       json={"name": f"TEST_legacy_{suf}", "phone": f"666{suf}00"}).json()
    prod = authed.post(f"{BASE_URL}/api/products", json={
        "sku": f"TESTLEG-{suf}", "name": "Legacy Prod", "category": "x",
        "selling_price": 500,
    }).json()
    r = authed.post(f"{BASE_URL}/api/orders", json={
        "customer_id": cust["id"], "product_id": prod["id"], "quantity": 2,
        "amount_paid": 1000,
    })
    assert r.status_code == 200, r.text
    order = r.json()
    assert len(order["items"]) == 1
    assert order["items"][0]["product_id"] == prod["id"]
    assert order["items"][0]["quantity"] == 2
    assert order["total"] == 1000
    assert order["payment_status"] == "Paid"


def test_order_without_items_or_product_id_rejected(authed):
    suf = uuid.uuid4().hex[:6]
    cust = authed.post(f"{BASE_URL}/api/customers",
                       json={"name": f"TEST_noprod_{suf}", "phone": f"555{suf}00"}).json()
    r = authed.post(f"{BASE_URL}/api/orders", json={"customer_id": cust["id"]})
    assert r.status_code == 400
    assert "at least one product" in r.text.lower()


def test_order_with_invalid_product_rejected(authed):
    suf = uuid.uuid4().hex[:6]
    cust = authed.post(f"{BASE_URL}/api/customers",
                       json={"name": f"TEST_badprod_{suf}", "phone": f"444{suf}00"}).json()
    # Invalid ObjectId format -> 400
    r = authed.post(f"{BASE_URL}/api/orders", json={
        "customer_id": cust["id"],
        "items": [{"product_id": "not-an-oid", "quantity": 1}],
    })
    assert r.status_code == 400
    # Valid ObjectId format but non-existent -> 404
    r2 = authed.post(f"{BASE_URL}/api/orders", json={
        "customer_id": cust["id"],
        "items": [{"product_id": "507f1f77bcf86cd799439011", "quantity": 1}],
    })
    assert r2.status_code in (400, 404)


def test_legacy_seeded_order_has_customer_phone(authed):
    """GET /api/orders/{PB-2026-0001} must join customer and return phone/email."""
    detail = authed.get(f"{BASE_URL}/api/orders/PB-2026-0001").json()
    assert "customer_phone" in detail
    assert detail["customer_phone"], "Legacy order should get phone joined from customer"
    assert "customer_email" in detail

