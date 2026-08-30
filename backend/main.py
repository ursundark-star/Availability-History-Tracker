from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import sqlite3, os, shutil, hashlib
from fastapi.staticfiles import StaticFiles

app = FastAPI()

DB_NAME = "data.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Serve uploaded images
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Initialize DB
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER, name TEXT, city TEXT, day TEXT, start_time TEXT, end_time TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS history (
        person_id INTEGER, action TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        person_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        photo TEXT,
        description TEXT)""")
    conn.commit()
    conn.close()

init_db()

class Availability(BaseModel):
    person_id: int
    city: str
    day: str
    start_time: str
    end_time: str

@app.post("/register")
def register(username: str = Form(...), password: str = Form(...),
             description: str = Form(...), photo: UploadFile = File(...)):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    filename = photo.filename
    safe_name = f"{username}_{filename}"
    photo_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(photo_path, "wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password, photo, description) VALUES (?, ?, ?, ?)",
                    (username, hashed_pw, f"/uploads/{safe_name}", description[:250]))
        conn.commit()
    return {"status": "registered"}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT person_id, photo, description FROM users WHERE username=? AND password=?",
                    (username, hashed_pw))
        row = cur.fetchone()
    if row:
        return {"status": "success", "person_id": row[0], "photo": row[1], "description": row[2]}
    return {"status": "failed"}

# <-- UPDATED: include photo and description for each availability row -->
@app.get("/availability/all")
def get_all_availability():
    """
    Returns list of availability rows with:
    (name, city, day, start_time, end_time, photo, description)
    photo and description come from users table (may be NULL)
    """
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.name, a.city, a.day, a.start_time, a.end_time,
                   u.photo, u.description
            FROM availability a
            LEFT JOIN users u ON a.person_id = u.person_id
            ORDER BY a.day
        """)
        rows = cur.fetchall()
    return {"availability": rows}

@app.post("/availability")
def add_availability(avail: Availability):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE person_id=?", (avail.person_id,))
        user_row = cur.fetchone()
        name = user_row[0] if user_row else "Unknown"
        cur.execute("INSERT INTO availability (person_id, name, city, day, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)", 
                    (avail.person_id, name, avail.city, avail.day, avail.start_time, avail.end_time))
        cur.execute("INSERT INTO history VALUES (?, ?)", (avail.person_id, f"{name} added {avail.day} availability"))
        conn.commit()
    return {"status": "saved"}

@app.get("/availability/{person_id}")
def get_availability(person_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT day, start_time, end_time FROM availability WHERE person_id=? ORDER BY day", (person_id,))
        rows = cur.fetchall()
    return {"availability": rows}

@app.get("/history/{person_id}")
def get_history(person_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT action FROM history WHERE person_id=? ORDER BY rowid DESC", (person_id,))
        rows = cur.fetchall()
    return {"history": rows}

@app.get("/user/{person_id}")
def get_user(person_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, photo, description FROM users WHERE person_id=?", (person_id,))
        row = cur.fetchone()
    return {"user": row}
