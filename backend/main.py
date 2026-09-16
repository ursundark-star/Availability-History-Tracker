import os
import sqlite3
import shutil
import hashlib
import re
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, Request
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

def validate_password(password: str) -> bool:
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"\d", password) and
        re.search(r"[^A-Za-z0-9]", password)
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
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
                   description: str = Form(""), photo: UploadFile = File(None)):
    if not validate_password(password):
        return {"status": "error", "message": "Password must be at least 8 characters and include uppercase, lowercase, number, and special character"}

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        if cur.fetchone():
            return {"status": "error", "message": f"Username '{username}' already exists"}

        hashed_pw = hash_password(password)

        photo_path = None
        if photo:
            photo_path = f"/uploads/{photo.filename}"
            file_path = os.path.join(UPLOAD_DIR, photo.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)
            img = Image.open(file_path)
            img.thumbnail((300, 300))
            img.save(file_path, optimize=True, quality=85)

        conn.execute("INSERT INTO users (username, password_hash, photo, description) VALUES (?, ?, ?, ?)",
                     (username, hashed_pw, photo_path, description))
        conn.commit()

    except sqlite3.IntegrityError:
        return {"status": "error", "message": f"Username '{username}' already exists"}
    finally:
        conn.close()
    return {"status": "success", "message": "User registered successfully"}

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    if not user:
        return {"status": "error", "message": "Invalid username or password"}

    hashed_pw = hash_password(password)
    stored_hash = user["password_hash"]

    if hashed_pw != stored_hash:
        return {"status": "error", "message": "Invalid username or password"}

    return {"status": "success", "person_id": user["id"]}

# --- Username (for frontend) ---
@app.get("/username")
async def get_username():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users ORDER BY id DESC LIMIT 1")
    user = cur.fetchone()
    conn.close()
    if not user:
        return {"status": "error", "message": "No user found"}
    return {"username": user["username"], "id": user["id"]}

# --- User profile ---
@app.get("/user/{user_id}")
async def get_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, photo, description FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if not user:
        return {"status": "error", "message": "User not found"}

    user_data = {
        "id": user["id"],
        "username": user["username"],
        "photo": user["photo"],
        "description": user["description"],
    }
    return {"status": "success", "user": user_data, **user_data}

# --- Availability ---

def save_availability(user_id: int, city: str, day: str, date: str, start: str, end: str, contact: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO availability (user_id, city, day, date, start, end, contact) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, city, day, date, start, end, contact),
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Availability added"}


@app.post("/availability")
async def add_availability_json(request: Request):
    data = await request.json()
    person_id = data.get("person_id") or data.get("user_id")
    if person_id is None:
        return {"status": "error", "message": "person_id is required"}

    return save_availability(
        user_id=person_id,
        city=data.get("city", ""),
        day=data.get("day", ""),
        date=data.get("date", ""),
        start=data.get("start_time") or data.get("start", ""),
        end=data.get("end_time") or data.get("end", ""),
        contact=data.get("contact", ""),
    )


@app.post("/availability/add")
async def add_availability_form(user_id: int = Form(...), city: str = Form(...),
                           day: str = Form(...), date: str = Form(...),
                           start: str = Form(...), end: str = Form(...),
                           contact: str = Form(...)):
    return save_availability(user_id, city, day, date, start, end, contact)


@app.get("/availability/all")
async def get_availability():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, u.username as person, a.city, a.day, a.date, a.start, a.end, a.contact, u.photo, u.description, u.id as person_id
        FROM availability a
        JOIN users u ON a.user_id = u.id
    """)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"availability": rows}


@app.get("/availability/{user_id}")
async def get_availability_by_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, u.username as person, a.city, a.day, a.date, a.start, a.end, a.contact, u.photo, u.description, u.id as person_id
        FROM availability a
        JOIN users u ON a.user_id = u.id
        WHERE a.user_id=?
    """, (user_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"availability": rows}

# --- Documents ---


async def save_document(user_id: int, name: str, file: UploadFile):
    file_path = f"/uploads/{file.filename}"
    with open(os.path.join(UPLOAD_DIR, file.filename), "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO documents (user_id, name, file) VALUES (?, ?, ?)", (user_id, name, file_path))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Document added"}


@app.post("/documents/add")
async def add_document(user_id: int = Form(...), name: str = Form(...), file: UploadFile = File(...)):
    return await save_document(user_id, name, file)


@app.post("/documents")
async def add_document_alias(person_id: int = Form(...), name: str = Form(...), file: UploadFile = File(...)):
    return await save_document(person_id, name, file)


@app.get("/documents/all")
async def get_documents():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.user_id as person_id, u.username as person, d.name, d.file
        FROM documents d
        JOIN users u ON d.user_id = u.id
    """)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"documents": rows}


@app.get("/documents/{user_id}")
async def get_documents_by_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.user_id as person_id, u.username as person, d.name, d.file
        FROM documents d
        JOIN users u ON d.user_id = u.id
        WHERE d.user_id=?
    """, (user_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"documents": rows}

# --- History (placeholder) ---
@app.get("/history/{user_id}")
async def get_history(user_id: int):
    return {"history": []}

# --- Aliases for frontend ---
@app.get("/about/{user_id}")
async def get_about(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT description FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if not user:
        return {"status": "error", "message": "User not found"}
    return {"status": "success", "about_us": user["description"]}


@app.post("/upload_document")
async def upload_document_alias(person_id: int = Form(None), user_id: int = Form(None),
                               name: str = Form(...), file: UploadFile = File(...)):
    resolved_user_id = person_id if person_id is not None else user_id
    if resolved_user_id is None:
        return {"status": "error", "message": "person_id is required"}
    return await save_document(resolved_user_id, name, file)


@app.post("/add_availability")
async def add_availability_alias(person_id: int = Form(None), user_id: int = Form(None),
                                city: str = Form(...), day: str = Form(...), date: str = Form(...),
                                start: str = Form(...), end: str = Form(...), contact: str = Form(...)):
    resolved_user_id = person_id if person_id is not None else user_id
    if resolved_user_id is None:
        return {"status": "error", "message": "person_id is required"}
    return save_availability(resolved_user_id, city, day, date, start, end, contact)
