from flask import Flask, render_template, request, redirect, url_for, session
import requests

app = Flask(__name__)
app.secret_key = "supersecretkey"
BACKEND_URL = "http://backend:8000"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        resp = requests.post(f"{BACKEND_URL}/login", data={"username": username, "password": password}).json()
        if resp["status"] == "success":
            session["person_id"] = resp["person_id"]
            return redirect(url_for("home"))
        else:
            return "Login failed. <a href='/login'>Try again</a>"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        description = request.form["description"]
        photo = request.files["photo"]
        files = {"photo": (photo.filename, photo.stream, photo.mimetype)}
        data = {"username": username, "password": password, "description": description}
        requests.post(f"{BACKEND_URL}/register", data=data, files=files)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/")
def home():
    all_availability = requests.get(f"{BACKEND_URL}/availability/all").json()
    if "person_id" in session:
        person_id = session["person_id"]
        user = requests.get(f"{BACKEND_URL}/user/{person_id}").json().get("user")
        availability = requests.get(f"{BACKEND_URL}/availability/{person_id}").json()
        history = requests.get(f"{BACKEND_URL}/history/{person_id}").json()
        return render_template("index.html", 
                               user=user, 
                               availability=availability["availability"], 
                               history=history["history"], 
                               all_availability=all_availability["availability"])
    else:
        return render_template("index.html", 
                               user=None, 
                               availability=[], 
                               history=[], 
                               all_availability=all_availability["availability"])

@app.route("/add_availability", methods=["POST"])
def add_availability():
    person_id = session["person_id"]
    data = {
        "person_id": person_id,
        "city": request.form["city"],
        "day": request.form["day"],
        "start_time": request.form["start"],
        "end_time": request.form["end"]
    }
    requests.post(f"{BACKEND_URL}/availability", json=data)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
