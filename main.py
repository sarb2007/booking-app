import sqlite3
from fastapi import FastAPI

app = FastAPI()

def get_db():
    conn = sqlite3.connect("booking.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@app.get("/services")
def list_services():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, duration_min, price FROM services"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
