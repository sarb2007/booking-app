PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('customer', 'owner'))
);

CREATE TABLE services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    price        REAL NOT NULL,
    owner_id     INTEGER NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);
CREATE TABLE bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    service_id  INTEGER NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled')),
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (service_id)  REFERENCES services(id)
);
CREATE TABLE availability (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week  TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    owner_id     INTEGER NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);