import sqlite3
import pytest
from fastapi.testclient import TestClient
import main

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_file)
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.close()
    monkeypatch.setattr(main, "DB_PATH", db_file)
    return TestClient(main.app)

def test_register_and_login(client):
    r = client.post("/register", json={
        "name": "Lee", "email": "lee@mail.com",
        "password": "password123", "role": "customer"})
    assert r.status_code == 201

    r = client.post("/login", json={
        "email": "lee@mail.com", "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_wrong_password_rejected(client):
    client.post("/register", json={
        "name": "Lee", "email": "lee@mail.com",
        "password": "password123", "role": "customer"})
    r = client.post("/login", json={
        "email": "lee@mail.com", "password": "wrongpass1"})
    assert r.status_code == 401


def make_user(client, name, email, role):
    client.post("/register", json={
        "name": name, "email": email,
        "password": "password123", "role": role})
    r = client.post("/login", json={
        "email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def test_overlap_rules(client):
    owner = make_user(client, "Amy", "amy@mail.com", "owner")
    customer = make_user(client, "Sam", "sam@mail.com", "customer")
    s = client.post("/services", headers=owner, json={
        "name": "Haircut", "duration_min": 30, "price": 15})
    sid = s.json()["id"]

    first = client.post("/bookings", headers=customer, json={
        "service_id": sid, "start_time": "2026-12-02 11:00"})
    assert first.status_code == 201

    overlap = client.post("/bookings", headers=customer, json={
        "service_id": sid, "start_time": "2026-12-02 11:15"})
    assert overlap.status_code == 409

    back_to_back = client.post("/bookings", headers=customer, json={
        "service_id": sid, "start_time": "2026-12-02 11:30"})
    assert back_to_back.status_code == 201

def test_booking_requires_login(client):
    r = client.post("/bookings", json={
        "service_id": 1, "start_time": "2026-12-02 11:00"})
    assert r.status_code in (401, 403)

def test_cannot_cancel_someone_elses_booking(client):
    owner = make_user(client, "Amy", "amy@mail.com", "owner")
    sam = make_user(client, "Sam", "sam@mail.com", "customer")
    lee = make_user(client, "Lee", "lee@mail.com", "customer")
    sid = client.post("/services", headers=owner, json={
        "name": "Haircut", "duration_min": 30, "price": 15}).json()["id"]
    bid = client.post("/bookings", headers=sam, json={
        "service_id": sid, "start_time": "2026-12-02 11:00"}).json()["id"]

    stolen = client.patch(f"/bookings/{bid}/cancel", headers=lee)
    assert stolen.status_code == 403

    own = client.patch(f"/bookings/{bid}/cancel", headers=sam)
    assert own.status_code == 200

def test_invalid_email_rejected(client):
    r = client.post("/register", json={
        "name": "Bad", "email": "preet",
        "password": "password123", "role": "customer"})
    assert r.status_code == 422