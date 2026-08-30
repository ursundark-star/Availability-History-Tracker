from flask import Flask, render_template, request, redirect, url_for, session
import requests, os

app = Flask(__name__)
app.secret_key = "supersecretkey"

API_URL = os.environ.get("API_URL", "http://backend:8000")
PUBLIC_BACKEND_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")

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
        photo = request.files["photo"]
        files = {"photo": (photo.filename, photo.stream, photo.mimetype)}
        data = {"username": username, "password": password, "description": description}
        requests.post(f"{API_URL}/register", data=data, files=files)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/")
def home():
    # fetch all availability (now includes photo and description per row)
    resp = requests.get(f"{API_URL}/availability/all")
    all_availability = resp.json().get("availability", [])

    # convert backend-relative photo paths in all_availability to PUBLIC_BACKEND_URL
    processed_all = []
    for row in all_availability:
        # row: (name, city, day, start_time, end_time, photo, description)
        name, city, day, start_time, end_time, photo_path, desc = row
        photo_url = None
        if photo_path and isinstance(photo_path, str) and photo_path.startswith("/"):
            photo_url = f"{PUBLIC_BACKEND_URL}{photo_path}"
        processed_all.append((name, city, day, start_time, end_time, photo_url, desc))

    if "person_id" in session:
        person_id = session["person_id"]
        user_resp = requests.get(f"{API_URL}/user/{person_id}").json().get("user")
        user = None
        if user_resp:
            u = list(user_resp)
            if u[1] and u[1].startswith("/"):
                u[1] = f"{PUBLIC_BACKEND_URL}{u[1]}"
            user = tuple(u)

        availability = requests.get(f"{API_URL}/availability/{person_id}").json()
        history = requests.get(f"{API_URL}/history/{person_id}").json()
        return render_template("index.html",
                               user=user,
                               availability=availability.get("availability", []),
                               history=history.get("history", []),
                               all_availability=processed_all)
    else:
        return render_template("index.html",
                               user=None,
                               availability=[],
                               history=[],
                               all_availability=processed_all)

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
