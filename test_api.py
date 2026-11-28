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