PRAGMA foreign_keys = ON;

INSERT INTO users (name, email, password_hash, role)
VALUES ('Amy', 'amy@mail.com', 'hash1', 'owner');

INSERT INTO users (name, email, password_hash, role)
VALUES ('Sam', 'sam@mail.com', 'hash2', 'customer');

INSERT INTO services (name, duration_min, price, owner_id)
VALUES ('Haircut', 30, 15.00, 1);

INSERT INTO bookings (customer_id, service_id, start_time, end_time, status)
VALUES (2, 1, '2026-12-01 10:00', '2026-12-01 10:30', 'confirmed');