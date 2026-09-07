import os
import sqlite3
import shutil
import hashlib
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

DB_DIR = "/app/db"
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "simpleapp.db")

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        photo TEXT,
        description TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        city TEXT,
        day TEXT,
        date TEXT,
        start TEXT,
        end TEXT,
        contact TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        file TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Auth ---
@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...),
                   description: str = Form(""), about_us: str = Form(""),
                   photo: UploadFile = File(None)):
    conn = get_db()
    try:
        hashed_pw = hash_password(password)
        photo_path = None
        if photo:
            photo_path = f"/uploads/{photo.filename}"
            file_path = os.path.join(UPLOAD_DIR, photo.filename)
            # Save original upload
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)
            # Resize and overwrite
            img = Image.open(file_path)
            img.thumbnail((300, 300))  # max size
            img.save(file_path, optimize=True, quality=85)
        conn.execute("INSERT INTO users (username, password, photo, description) VALUES (?, ?, ?, ?)",
                     (username, hashed_pw, photo_path, description))
        conn.commit()
    except sqlite3.IntegrityError:
        return {"status": "error", "message": "Username already exists"}
    finally:
        conn.close()
    return {"status": "success"}

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    if not user or user["password"] != hash_password(password):
        return {"status": "error"}
    return {"status": "success", "person_id": user["id"]}

# --- Availability ---
@app.get("/all_availability")
async def all_availability():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    SELECT u.username, a.city, a.day, a.date, a.start, a.end, a.contact, u.photo, u.description, u.id
    FROM availability a
    JOIN users u ON a.user_id = u.id
    """)
    rows = cur.fetchall()
    conn.close()
    return {"availability": [tuple(row) for row in rows]}

@app.get("/availability/all")
async def availability_all_alias():
    return await all_availability()

@app.get("/availability/{person_id}")
async def availability_by_user(person_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT city, day, date, start, end, contact FROM availability WHERE user_id=?", (person_id,))
    rows = cur.fetchall()
    conn.close()
    return {"availability": [tuple(row) for row in rows]}

@app.post("/availability")
async def add_availability_api(payload: dict = Body(...)):
    person_id = payload.get("person_id")
    city = payload.get("city")
    day = payload.get("day")
    date = payload.get("date")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    contact = payload.get("contact")

    conn = get_db()
    conn.execute(
        "INSERT INTO availability (user_id, city, day, date, start, end, contact) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (person_id, city, day, date, start_time, end_time, contact)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

# --- Documents ---
@app.post("/documents")
async def upload_document(person_id: int = Form(...), name: str = Form(...), file: UploadFile = File(...)):
    filename = file.filename
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # Store with /uploads/ prefix so viewer works
    conn = get_db()
    conn.execute("INSERT INTO documents (user_id, name, file) VALUES (?, ?, ?)",
                 (person_id, name, f"/uploads/{filename}"))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/documents/all")
async def documents_all():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, file FROM documents")
    rows = cur.fetchall()
    conn.close()
    return {"documents": [(row["user_id"], row["name"], row["file"]) for row in rows]}

@app.get("/documents/{person_id}")
async def documents_by_user(person_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, file FROM documents WHERE user_id=?", (person_id,))
    rows = cur.fetchall()
    conn.close()
    return {"documents": [(row["name"], row["file"]) for row in rows]}

# --- User & About ---
@app.get("/user/{person_id}")
async def get_user(person_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, photo, description FROM users WHERE id=?", (person_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"user": None}
    return {"user": (row["username"], row["photo"], row["description"], person_id)}

@app.get("/about/{person_id}")
async def about_user(person_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT description FROM users WHERE id=?", (person_id,))
    row = cur.fetchone()
    conn.close()
    return {"about_us": row["description"] if row else ""}
