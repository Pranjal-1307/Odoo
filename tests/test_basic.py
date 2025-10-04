import pytest, json
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_signup_login_me():
    r = client.post("/auth/signup", json={
        "email":"admin@example.com",
        "full_name":"Admin User",
        "password":"secret123",
        "company_name":"Acme Inc",
        "country_code":"US"
    })
    assert r.status_code == 200
    tok = r.json()["access_token"]

    r2 = client.post("/auth/login", json={"email":"admin@example.com","password":"secret123"})
    assert r2.status_code == 200
    tok2 = r2.json()["access_token"]
    assert tok2

    r3 = client.get("/auth/me", headers={"Authorization":"Bearer "+tok2})
    assert r3.status_code == 200
    me = r3.json()
    assert me["role"] == "admin"

def test_admin_create_user_and_submit_expense_flow():
    # login admin
    r = client.post("/auth/login", json={"email":"admin@example.com","password":"secret123"})
    tok = r.json()["access_token"]
    # create manager
    r = client.post("/admin/users", headers={"Authorization":"Bearer "+tok}, json={
        "email":"manager@example.com","full_name":"Mgr One","password":"p@ss",
        "role":"manager","manager_id":None,"is_manager_approver":True
    })
    assert r.status_code == 200
    mgr = r.json()

    # create employee (reports to manager)
    r = client.post("/admin/users", headers={"Authorization":"Bearer "+tok}, json={
        "email":"emp@example.com","full_name":"Emp One","password":"p@ss",
        "role":"employee","manager_id":mgr["id"],"is_manager_approver":False
    })
    assert r.status_code == 200

    # employee login
    r = client.post("/auth/login", json={"email":"emp@example.com","password":"p@ss"})
    emp_tok = r.json()["access_token"]

    # submit expense
    r = client.post("/expenses", headers={"Authorization":"Bearer "+emp_tok}, json={
        "amount": 100.0, "currency_code":"USD", "category":"Meals", "description":"Lunch", "date":"2024-01-10"
    })
    assert r.status_code == 200
    exp = r.json()
    assert exp["status"] == "pending"

    # manager pending
    r = client.get("/approvals/pending", headers={"Authorization":"Bearer "+tok})  # admin is also manager? (not required). We'll login manager.
    # login manager actually:
    r = client.post("/auth/login", json={"email":"manager@example.com","password":"p@ss"})
    mgr_tok = r.json()["access_token"]
    r = client.get("/approvals/pending", headers={"Authorization":"Bearer "+mgr_tok})
    assert r.status_code == 200
    lst = r.json()
    assert any(x["id"] == exp["id"] for x in lst)

    # approve
    r = client.post(f"/approvals/{exp['id']}/act", headers={"Authorization":"Bearer "+mgr_tok}, json={"approve": True, "comment":"ok"})
    assert r.status_code == 200
