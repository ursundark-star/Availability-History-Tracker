from flask import Flask, render_template, request, redirect, url_for, session
import requests, os
from urllib.parse import unquote
import mimetypes

app = Flask(__name__)
app.secret_key = "supersecretkey"

API_URL = os.environ.get("API_URL", "http://backend:8000")
PUBLIC_BACKEND_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")

@app.route("/")
def home():
    # fetch availability (includes person_id)
    resp = requests.get(f"{API_URL}/availability/all")
    all_availability = resp.json().get("availability", [])

    # fetch all documents once and map by person_id
    docs_resp = requests.get(f"{API_URL}/documents/all")
    docs_all = docs_resp.json().get("documents", [])
    docs_map = {}
    for pid, name, file in docs_all:
        docs_map.setdefault(pid, []).append((name, file))

    processed_all = []
    for row in all_availability:
        # row: (name, city, day, start_time, end_time, photo, desc, person_id)
        name, city, day, start_time, end_time, photo_path, desc, person_id = row
        photo_url = f"{PUBLIC_BACKEND_URL}{photo_path}" if photo_path and isinstance(photo_path, str) and photo_path.startswith("/") else None
        person_docs = docs_map.get(person_id, [])
        processed_all.append((name, city, day, start_time, end_time, photo_url, desc, person_id, person_docs))

    documents = []
    user = None
    availability = []
    history = []
    if "person_id" in session:
        person_id = session["person_id"]
        user_resp = requests.get(f"{API_URL}/user/{person_id}").json().get("user")
        if user_resp:
            u = list(user_resp)
            if u[1] and u[1].startswith("/"):
                u[1] = f"{PUBLIC_BACKEND_URL}{u[1]}"
            user = tuple(u)
        availability = requests.get(f"{API_URL}/availability/{person_id}").json().get("availability", [])
        history = requests.get(f"{API_URL}/history/{person_id}").json().get("history", [])
        docs_resp = requests.get(f"{API_URL}/documents/{person_id}").json()
        documents = docs_resp.get("documents", [])

    return render_template("index.html",
                           user=user,
                           availability=availability,
                           history=history,
                           all_availability=processed_all,
                           documents=documents,
                           PUBLIC_BACKEND_URL=PUBLIC_BACKEND_URL)

@app.route("/about/<int:person_id>")
def about(person_id):
    about_resp = requests.get(f"{API_URL}/about/{person_id}").json()
    user_resp = requests.get(f"{API_URL}/user/{person_id}").json().get("user")
    avatar_url = None
    if user_resp:
        u = list(user_resp)
        if u[1] and isinstance(u[1], str) and u[1].startswith("/"):
            avatar_url = f"{PUBLIC_BACKEND_URL}{u[1]}"
    return render_template("about.html", about=about_resp.get("about_us", ""), avatar_url=avatar_url)

@app.route("/upload_document", methods=["POST"])
def upload_document():
    if "person_id" not in session:
        return redirect(url_for("login"))
    person_id = session["person_id"]
    name = request.form["name"]
    file = request.files["file"]
    files = {"file": (file.filename, file.stream, file.mimetype)}
    data = {"person_id": person_id, "name": name}
    requests.post(f"{API_URL}/documents", data=data, files=files)
    return redirect(url_for("home"))

@app.route("/view_document")
def view_document():
    file_param = request.args.get("file", "")
    file_param = unquote(file_param)
    if not file_param or not isinstance(file_param, str) or not file_param.startswith("/uploads/"):
        return "Invalid file path.", 400
    file_url = f"{PUBLIC_BACKEND_URL}{file_param}"
    mime_type, _ = mimetypes.guess_type(file_param)
    if not mime_type:
        mime_type = "application/octet-stream"
    return render_template("viewer.html", file_url=file_url, mime_type=mime_type)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        resp = requests.post(f"{API_URL}/login", data={"username": username, "password": password}).json()
        if resp.get("status") == "success":
            session["person_id"] = resp["person_id"]
            session["username"] = username
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Login failed. Check credentials.")
    return render_template("login.html", error=None)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        description = request.form["description"]
        about_us = request.form.get("about_us", "")
        photo = request.files["photo"]
        files = {"photo": (photo.filename, photo.stream, photo.mimetype)}
        data = {"username": username, "password": password, "description": description, "about_us": about_us}
        requests.post(f"{API_URL}/register", data=data, files=files)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/add_availability", methods=["POST"])
def add_availability():
    if "person_id" not in session:
        return redirect(url_for("login"))
    person_id = session["person_id"]
    data = {
        "person_id": person_id,
        "city": request.form["city"],
        "day": request.form["day"],
        "start_time": request.form["start"],
        "end_time": request.form["end"]
    }
    requests.post(f"{API_URL}/availability", json=data)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
