import sqlite3
import bcrypt
import os
import jwt
import smtplib
from fastapi import FastAPI
from datetime import datetime, timedelta
from fastapi import HTTPException
from pydantic import BaseModel, Field, EmailStr
from typing import Literal
from datetime import timezone
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from email.message import EmailMessage
from fastapi import BackgroundTasks
from fastapi.staticfiles import StaticFiles

DB_PATH = "booking.db"

bearer = HTTPBearer()
app = FastAPI()
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

class LoginRequest(BaseModel):
    email: str
    password: str
class ServiceRequest(BaseModel):
    name: str
    duration_min: int = Field(gt=0)
    price: float = Field(ge=0)


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["customer", "owner"]

class BookingRequest(BaseModel):
    service_id: int
    start_time: str   # format: "2026-12-01 10:00"

class AvailabilityRequest(BaseModel):
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_time: str   # "09:00"
    end_time: str     # "17:00"


def get_db():
    conn = sqlite3.connect(DB_PATH)
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
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

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
def create_booking(b: BookingRequest, background: BackgroundTasks, user: dict = Depends(get_current_user)):
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
    row = conn.execute(
        "SELECT email FROM users WHERE id = ?", (user["id"],)
    ).fetchone()
    conn.close()
    background.add_task(
        send_email, row["email"], "Booking confirmed",
        f"Your booking is confirmed for {b.start_time}.",
    )
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

@app.get("/bookings")
def my_bookings(user: dict = Depends(get_current_user)):
    conn = get_db()
    if user["role"] == "customer":
        rows = conn.execute(
            "SELECT bookings.id, services.name AS service, "
            "bookings.start_time, bookings.end_time, bookings.status "
            "FROM bookings JOIN services ON bookings.service_id = services.id "
            "WHERE bookings.customer_id = ? ORDER BY bookings.start_time",
            (user["id"],),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT bookings.id, users.name AS customer, services.name AS service, "
            "bookings.start_time, bookings.end_time, bookings.status "
            "FROM bookings "
            "JOIN services ON bookings.service_id = services.id "
            "JOIN users ON bookings.customer_id = users.id "
            "WHERE services.owner_id = ? ORDER BY bookings.start_time",
            (user["id"],),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/services", status_code=201)
def create_service(s: ServiceRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only owners can add services")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO services (name, duration_min, price, owner_id) VALUES (?, ?, ?, ?)",
        (s.name, s.duration_min, s.price, user["id"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "name": s.name}

@app.patch("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    booking = conn.execute(
        "SELECT customer_id, status FROM bookings WHERE id = ?", (booking_id,)
    ).fetchone()
    if booking is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["customer_id"] != user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking["status"] == "cancelled":
        conn.close()
        raise HTTPException(status_code=409, detail="Already cancelled")

    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    return {"id": booking_id, "status": "cancelled"}

@app.post("/availability", status_code=201)
def set_availability(a: AvailabilityRequest, user: dict = Depends(get_current_user)):
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only owners can set availability")
    try:
        start = datetime.strptime(a.start_time, "%H:%M")
        end = datetime.strptime(a.end_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=422, detail="Use HH:MM format")
    if start >= end:
        raise HTTPException(status_code=422, detail="Start must be before end")

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO availability (day_of_week, start_time, end_time, owner_id) "
        "VALUES (?, ?, ?, ?)",
        (a.day_of_week, a.start_time, a.end_time, user["id"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}

@app.get("/services/{service_id}/slots")
def get_slots(service_id: int, date: str):
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="Use YYYY-MM-DD")
    day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day.weekday()]

    conn = get_db()
    service = conn.execute(
        "SELECT duration_min, owner_id FROM services WHERE id = ?", (service_id,)
    ).fetchone()
    if service is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Service not found")

    hours = conn.execute(
        "SELECT start_time, end_time FROM availability "
        "WHERE owner_id = ? AND day_of_week = ?",
        (service["owner_id"], day_name),
    ).fetchall()
    taken = conn.execute(
        "SELECT bookings.start_time, bookings.end_time FROM bookings "
        "JOIN services ON bookings.service_id = services.id "
        "WHERE services.owner_id = ? AND bookings.status = 'confirmed' "
        "AND bookings.start_time LIKE ?",
        (service["owner_id"], date + "%"),
    ).fetchall()
    conn.close()

    step = timedelta(minutes=service["duration_min"])
    fmt = "%Y-%m-%d %H:%M"
    slots = []
    for h in hours:
        cur = datetime.strptime(f"{date} {h['start_time']}", fmt)
        closing = datetime.strptime(f"{date} {h['end_time']}", fmt)
        while cur + step <= closing:
            s = cur.strftime(fmt)
            e = (cur + step).strftime(fmt)
            free = not any(s < t["end_time"] and e > t["start_time"] for t in taken)
            slots.append({"start_time": s, "end_time": e, "available": free})
            cur += step
    return slots

def send_email(to: str, subject: str, body: str):
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASSWORD")
    if not user or not password:
        print(f"[email not sent] To: {to} | {subject}\n{body}")
        return
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.send_message(msg)

app.mount("/app", StaticFiles(directory="static", html=True), name="static")