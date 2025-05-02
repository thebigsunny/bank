"""Minimal Flask Bank App with Clean UI
====================================
Single file | Flask + SQLite | Wheel gauge turns green on deposit, red on withdraw.
"""
from flask import Flask, request, redirect, url_for, session, render_template_string, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "bank.db"
app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"  # replace for production

# --------------------------------------------------
# Database helpers
# --------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    if (db := g.pop("db", None)):
        db.close()


def init_db():
    get_db().execute(
        """CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                email    TEXT UNIQUE NOT NULL,
                password TEXT             NOT NULL,
                balance  REAL             NOT NULL DEFAULT 0
            );"""
    )
    get_db().commit()


with app.app_context():
    init_db()

# --------------------------------------------------
# Data access / domain logic
# --------------------------------------------------

def create_user(email, pw_hash):
    get_db().execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, pw_hash))
    get_db().commit()


def fetch_user_by_email(email):
    return get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def fetch_user(uid):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def change_balance(uid, delta):
    get_db().execute("UPDATE users SET balance = balance + ? WHERE id = ?", (delta, uid))
    get_db().commit()

# --------------------------------------------------
# Auth helper
# --------------------------------------------------

def current_user():
    uid = session.get("user_id")
    return fetch_user(uid) if uid else None

# --------------------------------------------------
# UI helpers (inline CSS + HTML)
# --------------------------------------------------

BASE_STYLE = """
<style>
/* ---- Layout ---- */
body {
  font-family: system-ui, Arial, sans-serif;
  margin: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f5f7fa;
}

/* ---- Card ---- */
.card {
  background: #fff;
  width: 340px;
  padding: 2rem 2.5rem;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.1);
}

/* ---- Wheel gauge ---- */
.wheel {
  width: 180px;
  height: 180px;
  margin: 0 auto 1.25rem;
  border: 8px solid var(--wheel-color, #333);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.4s;
}
.wheel span {
  font-size: 1.4rem;
  font-weight: 600;
  color: #333;
}

/* ---- Forms ---- */
input {
  width: 100%;
  padding: 0.55rem;
  margin: 0.35rem 0;
  border: 1px solid #ccc;
  border-radius: 6px;
}
button {
  width: 100%;
  padding: 0.65rem;
  margin-top: 0.6rem;
  border: none;
  border-radius: 6px;
  background: #0066ff;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
button:hover { background: #0051d4; }

/* ---- Misc ---- */
a {
  display: block;
  margin-top: 1rem;
  font-size: 0.9rem;
  color: #0066ff;
  text-decoration: none;
}
h2 { margin: 0 0 1rem; }
form { margin: 0; }
</style>
"""

def page(content: str, wheel_color: str | None = None) -> str:
    """Wrap *content* in card layout, optionally setting the wheel color."""
    style_attr = f" style='--wheel-color:{wheel_color}'" if wheel_color else ""
    return (
        f"<html><head>{BASE_STYLE}</head><body>"
        f"<div class='card'{style_attr}>{content}</div>"
        "</body></html>"
    )

# ---- View factories --------------------------------------------------

def view_signup():
    return page(
        """
        <h2>Create Account</h2>
        <form method='post'>
          <input name='email' type='email' placeholder='Email' required>
          <input name='password' type='password' placeholder='Password' required>
          <button type='submit'>Sign Up</button>
        </form>
        <a href='/login'>Already have an account? Log in</a>
        """
    )


def view_login():
    return page(
        """
        <h2>Log In</h2>
        <form method='post'>
          <input name='email' type='email' placeholder='Email' required>
          <input name='password' type='password' placeholder='Password' required>
          <button type='submit'>Log In</button>
        </form>
        <a href='/signup'>Create an account</a>
        """
    )


def view_dashboard(email: str, balance: float, action: str | None):
    wheel_color = {"deposit": "#0c0", "withdraw": "#e00"}.get(action, "#333")
    return page(
        f"""
        <h2>Hello, {email}</h2>
        <div class='wheel'><span>${balance:.2f}</span></div>
        <form action='/deposit' method='post'>
          <input name='amount' type='number' step='0.01' min='0' placeholder='Amount'>
          <button type='submit'>Deposit</button>
        </form>
        <form action='/withdraw' method='post'>
          <input name='amount' type='number' step='0.01' min='0' placeholder='Amount'>
          <button type='submit'>Withdraw</button>
        </form>
        <a href='/logout'>Log out</a>
        """,
        wheel_color=wheel_color,
    )

# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.route("/")
def home():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw_hash = generate_password_hash(request.form["password"])
        try:
            create_user(email, pw_hash)
        except sqlite3.IntegrityError:
            return "Email already registered. <a href='/signup'>Try again</a>."
        return redirect(url_for("login"))
    return render_template_string(view_signup())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        user = fetch_user_by_email(email)
        if user and check_password_hash(user["password"], pw):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        return "Invalid credentials. <a href='/login'>Try again</a>."
    return render_template_string(view_login())


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not (user := current_user()):
        return redirect(url_for("login"))
    action = request.args.get("action")
    return render_template_string(view_dashboard(user["email"], user["balance"], action))


@app.route("/deposit", methods=["POST"])
@app.route("/withdraw", methods=["POST"])
def make_transaction():
    if not (user := current_user()):
        return redirect(url_for("login"))
    try:
        amount = float(request.form["amount"] or 0)
    except ValueError:
        amount = 0

    if request.path == "/deposit":
        change_balance(user["id"], amount)
        action = "deposit"
    else:
        change_balance(user["id"], -amount)
        action = "withdraw"

    return redirect(url_for("dashboard", action=action))

# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
