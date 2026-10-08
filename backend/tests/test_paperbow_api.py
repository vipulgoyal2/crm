import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
EMAIL = "admin@paperbow.in"
PASSWORD = "Paperbow2026!"


@pytest.fixture
def client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated(client):
    response = client.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.cookies.get("access_token")
    return client


def test_protected_endpoints_reject_anonymous(client):
    for endpoint in ("dashboard", "customers", "products", "orders"):
        response = client.get(f"{BASE_URL}/api/{endpoint}")
        assert response.status_code == 401, (endpoint, response.text)


def test_auth_login_me_logout(authenticated):
    me = authenticated.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    assert me.json()["role"] == "admin"
    logout = authenticated.post(f"{BASE_URL}/api/auth/logout")
    assert logout.status_code == 200 and logout.json()["ok"] is True
    assert authenticated.get(f"{BASE_URL}/api/auth/me").status_code == 401


def test_dashboard_records_and_search(authenticated):
    dashboard = authenticated.get(f"{BASE_URL}/api/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert all(key in payload for key in ("revenue", "orders", "customers", "products", "statuses"))
    assert isinstance(payload["recent_orders"], list)
    for endpoint, key in (("customers", "name"), ("products", "sku"), ("orders", "id")):
        response = authenticated.get(f"{BASE_URL}/api/{endpoint}")
        assert response.status_code == 200 and response.json()
        assert key in response.json()[0]


def test_customer_product_order_and_status_flow(authenticated):
    suffix = uuid.uuid4().hex[:8]
    customer = authenticated.post(
        f"{BASE_URL}/api/customers",
        json={"name": f"TEST_{suffix}", "phone": f"90000{suffix[:5]}", "email": f"test_{suffix}@example.com"},
    )
    assert customer.status_code == 200 and customer.json()["name"].startswith("TEST_")
    customer_id = customer.json()["id"]
    product = authenticated.post(
        f"{BASE_URL}/api/products",
        json={"sku": f"TEST-{suffix}", "name": "Test Product", "category": "Testing", "selling_price": 100},
    )
    assert product.status_code == 200 and product.json()["sku"] == f"TEST-{suffix}"
    product_id = product.json()["id"]
    order = authenticated.post(
        f"{BASE_URL}/api/orders",
        json={"customer_id": customer_id, "product_id": product_id, "quantity": 2, "amount_paid": 200},
    )
    assert order.status_code == 200
    order_data = order.json()
    assert order_data["payment_status"] == "Paid"
    assert order_data["timeline"] and order_data["customer_name"].startswith("TEST_")
    order_id = order_data["id"]
    changed = authenticated.patch(f"{BASE_URL}/api/orders/{order_id}/status", params={"status": "Production"})
    assert changed.status_code == 200 and changed.json()["status"] == "Production"
    found = authenticated.get(f"{BASE_URL}/api/orders", params={"search": order_id})
    assert found.status_code == 200 and found.json()[0]["id"] == order_id