import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'my_society.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS societies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            total_flats INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL DEFAULT 'member',
            society_id INTEGER,
            flat_no TEXT,
            flat_status TEXT DEFAULT 'owned',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (society_id) REFERENCES societies(id)
        );

        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            monthly_cost REAL NOT NULL DEFAULT 0,
            society_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (society_id) REFERENCES societies(id)
        );

        CREATE TABLE IF NOT EXISTS flat_facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            facility_id INTEGER NOT NULL,
            availed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (facility_id) REFERENCES facilities(id),
            UNIQUE(user_id, facility_id)
        );

        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            facility_id INTEGER,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (facility_id) REFERENCES facilities(id)
        );

        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            base_amount REAL DEFAULT 500,
            facility_charges REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            paid_status TEXT DEFAULT 'Unpaid',
            paid_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')
    
    conn.commit()
    conn.close()
    print('Database initialized successfully!')

def seed_sample_data():
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if data already exists
    existing_society = cursor.execute('SELECT COUNT(*) FROM societies').fetchone()[0]
    if existing_society > 0:
        conn.close()
        return False

    # 1. Add Society
    cursor.execute('''
        INSERT INTO societies (name, address, city, total_flats)
        VALUES (?, ?, ?, ?)
    ''', ('Greenfield Heights CHS', 'Plot 42, Sector 18, Palm Beach Road', 'Mumbai', 48))
    society_id = cursor.lastrowid

    # 2. Add President
    cursor.execute('''
        INSERT INTO users (name, email, password, phone, role, society_id, flat_no, flat_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'Vikram Malhotra',
        'president@mysociety.com',
        generate_password_hash('admin123'),
        '+91 98201 12345',
        'president',
        society_id,
        'A-101',
        'owned'
    ))

    # 3. Add Members
    members = [
        ('Rahul Sharma', 'rahul@gmail.com', 'password123', '+91 98765 43210', 'member', society_id, 'A-202', 'owned'),
        ('Priya Patel', 'priya@gmail.com', 'password123', '+91 98111 22334', 'member', society_id, 'B-304', 'rented'),
        ('Amit Verma', 'amit@gmail.com', 'password123', '+91 97234 56789', 'member', society_id, 'C-105', 'owned'),
        ('Anjali Mehta', 'anjali@gmail.com', 'password123', '+91 99887 76655', 'member', society_id, 'C-402', 'rented'),
        ('Sunil Kumar (Unsold)', 'empty@mysociety.com', 'password123', '+91 91234 56780', 'member', society_id, 'D-501', 'empty')
    ]

    member_ids = []
    for m in members:
        cursor.execute('''
            INSERT INTO users (name, email, password, phone, role, society_id, flat_no, flat_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (m[0], m[1], generate_password_hash(m[2]), m[3], m[4], m[5], m[6], m[7]))
        member_ids.append(cursor.lastrowid)

    # 4. Add Facilities
    facilities = [
        ('Swimming Pool & Spa', 'Olympic size temperature-controlled pool with locker facility and shower rooms', 600.0, society_id),
        ('Modern Gymnasium', 'Fully equipped fitness center with cardio and strength training gear', 450.0, society_id),
        ('Reserved Covered Parking', 'Dedicated ground-floor covered parking space with 24/7 CCTV security', 300.0, society_id),
        ('Clubhouse & Badminton', 'Indoor sports facility including badminton courts, table tennis & lounge', 500.0, society_id)
    ]

    facility_ids = []
    for f in facilities:
        cursor.execute('''
            INSERT INTO facilities (name, description, monthly_cost, society_id)
            VALUES (?, ?, ?, ?)
        ''', (f[0], f[1], f[2], f[3]))
        facility_ids.append(cursor.lastrowid)

    # 5. Assign Flat Facilities (Who opted what)
    # Member 0 (Rahul): Pool + Gym
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[0], facility_ids[0]))
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[0], facility_ids[1]))

    # Member 1 (Priya): Parking + Gym
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[1], facility_ids[1]))
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[1], facility_ids[2]))

    # Member 2 (Amit): Pool + Parking + Clubhouse
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[2], facility_ids[0]))
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[2], facility_ids[2]))
    cursor.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (member_ids[2], facility_ids[3]))

    # 6. Add Complaints
    complaints = [
        (member_ids[0], facility_ids[0], 'Water filter issue in Swimming Pool', 'The filtration pump in the pool is making rattling noise and water looks cloudy.', 'Pending', None),
        (member_ids[1], facility_ids[2], 'Unauthorized vehicle in assigned parking spot', 'A black sedan is repeatedly parked in my designated B-304 parking bay.', 'In Progress', 'Security team has been notified. Towing warning issued to the vehicle owner.'),
        (member_ids[2], facility_ids[1], 'Treadmill #2 belt slipping', 'The motor belt of the center treadmill needs lubrication or tension tightening.', 'Resolved', 'Maintenance technician repaired the belt tensioner on 18th Oct.')
    ]

    for c in complaints:
        cursor.execute('''
            INSERT INTO complaints (user_id, facility_id, subject, description, status, response, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 'Resolved' THEN CURRENT_TIMESTAMP ELSE NULL END)
        ''', (c[0], c[1], c[2], c[3], c[4], c[5], c[4]))

    # 7. Add Maintenance Records
    # Month 10 (October 2024 / current)
    # Rahul: Base 500 + Pool 600 + Gym 450 = 1550 (Paid)
    cursor.execute('''
        INSERT INTO maintenance (user_id, month, year, base_amount, facility_charges, total_amount, paid_status, paid_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (member_ids[0], 10, 2024, 500, 1050, 1550, 'Paid'))

    # Priya: Base 500 + Gym 450 + Parking 300 = 1250 (Unpaid)
    cursor.execute('''
        INSERT INTO maintenance (user_id, month, year, base_amount, facility_charges, total_amount, paid_status, paid_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
    ''', (member_ids[1], 10, 2024, 500, 750, 1250, 'Unpaid'))

    # Amit: Base 500 + Pool 600 + Parking 300 + Clubhouse 500 = 1900 (Paid)
    cursor.execute('''
        INSERT INTO maintenance (user_id, month, year, base_amount, facility_charges, total_amount, paid_status, paid_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (member_ids[2], 10, 2024, 500, 1400, 1900, 'Paid'))

    # Anjali: Base 500 (No extra facilities) = 500 (Unpaid)
    cursor.execute('''
        INSERT INTO maintenance (user_id, month, year, base_amount, facility_charges, total_amount, paid_status, paid_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
    ''', (member_ids[3], 10, 2024, 500, 0, 500, 'Unpaid'))

    conn.commit()
    conn.close()
    print('Sample demo data seeded successfully!')
    return True

if __name__ == '__main__':
    init_db()
    seed_sample_data()
