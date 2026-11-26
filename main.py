import sqlite3
import bcrypt
import os
import jwt
from fastapi import FastAPI
from datetime import datetime, timedelta
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Literal
from pydantic import Field
from datetime import timezone
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer = HTTPBearer()
app = FastAPI()
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8)
    role: Literal["customer", "owner"]

class BookingRequest(BaseModel):
    service_id: int
    start_time: str   # format: "2026-12-01 10:00"


def get_db():
    conn = sqlite3.connect("booking.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



@app.post("/login")
def login(creds: LoginRequest):
    conn = get_db()
    user = conn.execute(
        "SELECT id, password_hash, role FROM users WHERE email = ?",
        (creds.email,),
    ).fetchone()
    conn.close()

    if user is None or not bcrypt.checkpw(
        creds.password.encode(), user["password_hash"].encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"id": int(payload["sub"]), "role": payload["role"]}


@app.get("/services")
def list_services():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, duration_min, price FROM services"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/bookings", status_code=201)
def create_booking(b: BookingRequest, user: dict = Depends(get_current_user)):
    conn = get_db()
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can book")
    
    service = conn.execute(
        "SELECT duration_min, owner_id FROM services WHERE id = ?", (b.service_id,)
    ).fetchone()
    if service is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Service not found")

    start = datetime.strptime(b.start_time, "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=service["duration_min"])
    end_text = end.strftime("%Y-%m-%d %H:%M")

    conflict = conn.execute(
        "SELECT bookings.id FROM bookings "
        "JOIN services ON bookings.service_id = services.id "
        "WHERE services.owner_id = ? "
        "AND bookings.status = 'confirmed' "
        "AND ? < bookings.end_time "
        "AND ? > bookings.start_time",
        (service["owner_id"], b.start_time, end_text),
    ).fetchone()
    if conflict:
        conn.close()
        raise HTTPException(status_code=409, detail="Time slot already booked")

    cur = conn.execute(
        "INSERT INTO bookings (customer_id, service_id, start_time, end_time, status) "
        "VALUES (?, ?, ?, ?, 'confirmed')",
        (user["id"], b.service_id, b.start_time, end_text),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "end_time": end_text}

@app.post("/register", status_code=201)
def register(u: RegisterRequest):
    hashed = bcrypt.hashpw(u.password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (u.name, u.email, hashed, u.role),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Email already registered")
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "name": u.name, "email": u.email, "role": u.role}