import os
import time
import hashlib
import sqlite3
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = os.path.join(os.path.dirname(__file__), "database.db")
ROUND_DURATION = 30  # 30-second round cycle
LOCK_SECONDS = 5     # betting locks 5 seconds before round ends

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                referral_code TEXT UNIQUE NOT NULL,
                referred_by TEXT,
                virtual_coins INTEGER DEFAULT 1000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_code TEXT UNIQUE NOT NULL,
                winning_number INTEGER NOT NULL,
                winning_color TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                round_code TEXT NOT NULL,
                bet_type TEXT NOT NULL,       -- 'color' or 'number'
                bet_choice TEXT NOT NULL,     -- 'Red', 'Green', 'Violet', or '0'-'9'
                amount INTEGER NOT NULL,
                payout INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- 'won', 'lost', 'pending'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def get_round_info():
    """Calculates synchronized time and resolves previous round if needed."""
    now = int(time.time())
    round_idx = now // ROUND_DURATION
    time_left = ROUND_DURATION - (now % ROUND_DURATION)
    current_round_code = f"RD{round_idx}"
    previous_round_code = f"RD{round_idx - 1}"

    # Ensure previous round is resolved in DB
    resolve_round(previous_round_code, round_idx - 1)

    return {
        "current_round_code": current_round_code,
        "time_left": time_left,
        "is_locked": time_left <= LOCK_SECONDS
    }

def resolve_round(round_code, round_idx):
    """Deterministically resolves round and settles pending bets."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rounds WHERE round_code = ?", (round_code,))
        existing = cursor.fetchone()
        if existing:
            return

        # Deterministic outcome from round index
        hash_seed = hashlib.sha256(f"virtual_color_seed_{round_idx}".encode()).hexdigest()
        winning_number = int(hash_seed[:8], 16) % 10

        # Colors logic:
        # 0 = Red + Violet
        # 5 = Green + Violet
        # 1,3,7,9 = Green
        # 2,4,6,8 = Red
        if winning_number == 0:
            winning_color = "Red,Violet"
        elif winning_number == 5:
            winning_color = "Green,Violet"
        elif winning_number % 2 == 0:
            winning_color = "Red"
        else:
            winning_color = "Green"

        cursor.execute("""
            INSERT OR IGNORE INTO rounds (round_code, winning_number, winning_color)
            VALUES (?, ?, ?)
        """, (round_code, winning_number, winning_color))

        # Settle pending bets for this round
        cursor.execute("SELECT * FROM bets WHERE round_code = ? AND status = 'pending'", (round_code,))
        pending_bets = cursor.fetchall()

        winning_colors_list = winning_color.split(",")

        for bet in pending_bets:
            bet_id = bet["id"]
            user_id = bet["user_id"]
            bet_type = bet["bet_type"]
            choice = bet["bet_choice"]
            amount = bet["amount"]

            payout = 0
            if bet_type == "number":
                if int(choice) == winning_number:
                    payout = amount * 9
            elif bet_type == "color":
                if choice in winning_colors_list:
                    if choice == "Violet":
                        payout = int(amount * 4.5)
                    else:
                        payout = amount * 2

            if payout > 0:
                cursor.execute("UPDATE bets SET payout = ?, status = 'won' WHERE id = ?", (payout, bet_id))
                cursor.execute("UPDATE users SET virtual_coins = virtual_coins + ? WHERE id = ?", (payout, user_id))
            else:
                cursor.execute("UPDATE bets SET payout = 0, status = 'lost' WHERE id = ?", (bet_id,))

        conn.commit()

# --- WEB ROUTES ---

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("game"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    invitation_code = request.args.get("invitationCode", "")
    
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        ref_code_input = request.form.get("invitation_code", "").strip()

        if not phone or not password:
            flash("Phone number and password are required.", "error")
            return render_template("register.html", invitation_code=ref_code_input)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", invitation_code=ref_code_input)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html", invitation_code=ref_code_input)

        # Generate unique referral code for user
        user_ref_code = hashlib.md5(f"{phone}_{time.time()}".encode()).hexdigest()[:8].upper()
        pwd_hash = generate_password_hash(password)

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Check referrer
                referrer_id = None
                if ref_code_input:
                    cursor.execute("SELECT id FROM users WHERE referral_code = ?", (ref_code_input,))
                    ref_row = cursor.fetchone()
                    if ref_row:
                        referrer_id = ref_row["id"]

                # New user starts with 1000 Virtual Coins
                cursor.execute("""
                    INSERT INTO users (phone, password_hash, referral_code, referred_by, virtual_coins)
                    VALUES (?, ?, ?, ?, 1000)
                """, (phone, pwd_hash, user_ref_code, ref_code_input if referrer_id else None))
                new_user_id = cursor.lastrowid

                # Reward referrer with 200 Virtual Bonus Coins
                if referrer_id:
                    cursor.execute("UPDATE users SET virtual_coins = virtual_coins + 200 WHERE id = ?", (referrer_id,))

                conn.commit()

            session["user_id"] = new_user_id
            session["phone"] = phone
            flash("Registration successful! Welcome bonus of 1,000 Virtual Coins credited.", "success")
            return redirect(url_for("game"))

        except sqlite3.IntegrityError:
            flash("This phone number is already registered.", "error")
            return render_template("register.html", invitation_code=ref_code_input)

    return render_template("register.html", invitation_code=invitation_code)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
            user = cursor.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["phone"] = user["phone"]
            return redirect(url_for("game"))
        else:
            flash("Invalid phone number or password.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/game")
@login_required
def game():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
        user = cursor.fetchone()
    return render_template("game.html", user=user)

@app.route("/invite")
@login_required
def invite():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
        user = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE referred_by = ?", (user["referral_code"],))
        referred_count = cursor.fetchone()["count"]

    invite_url = request.host_url.rstrip("/") + url_for("register") + f"?invitationCode={user['referral_code']}"
    return render_template("invite.html", user=user, referred_count=referred_count, invite_url=invite_url)

@app.route("/faucet", methods=["POST"])
@login_required
def faucet():
    """Adds 500 free virtual demo coins whenever user wants to reload."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET virtual_coins = virtual_coins + 500 WHERE id = ?", (session["user_id"],))
        conn.commit()
    flash("+500 Free Virtual Coins added to your wallet!", "success")
    return redirect(url_for("game"))

# --- JSON API ENDPOINTS ---

@app.route("/api/status")
@login_required
def api_status():
    round_info = get_round_info()
    user_id = session["user_id"]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT virtual_coins FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        balance = user["virtual_coins"] if user else 0

        # Recent 10 rounds
        cursor.execute("SELECT round_code, winning_number, winning_color FROM rounds ORDER BY id DESC LIMIT 10")
        recent_rounds = [dict(row) for row in cursor.fetchall()]

        # Active bets for current round
        cursor.execute("""
            SELECT bet_type, bet_choice, amount, status, payout
            FROM bets WHERE user_id = ? AND round_code = ?
        """, (user_id, round_info["current_round_code"]))
        active_bets = [dict(row) for row in cursor.fetchall()]

        # Latest completed bet result (to notify win/loss)
        cursor.execute("""
            SELECT b.*, r.winning_color, r.winning_number 
            FROM bets b
            JOIN rounds r ON b.round_code = r.round_code
            WHERE b.user_id = ? AND b.status IN ('won', 'lost')
            ORDER BY b.id DESC LIMIT 1
        """, (user_id,))
        last_result_row = cursor.fetchone()
        last_result = dict(last_result_row) if last_result_row else None

    return jsonify({
        "round_code": round_info["current_round_code"],
        "time_left": round_info["time_left"],
        "is_locked": round_info["is_locked"],
        "balance": balance,
        "recent_rounds": recent_rounds,
        "active_bets": active_bets,
        "last_result": last_result
    })

@app.route("/api/bet", methods=["POST"])
@login_required
def api_bet():
    round_info = get_round_info()
    if round_info["is_locked"]:
        return jsonify({"success": False, "message": "Betting is locked for this round. Please wait for the next round."}), 400

    data = request.get_json() or {}
    bet_type = data.get("bet_type")       # 'color' or 'number'
    bet_choice = str(data.get("choice"))  # 'Red', 'Green', 'Violet' or '0'-'9'
    amount = int(data.get("amount", 0))

    if amount <= 0:
        return jsonify({"success": False, "message": "Please enter a valid bet amount."}), 400

    user_id = session["user_id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT virtual_coins FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        if not user or user["virtual_coins"] < amount:
            return jsonify({"success": False, "message": "Insufficient Virtual Coins in your wallet."}), 400

        # Deduct coins and insert bet
        cursor.execute("UPDATE users SET virtual_coins = virtual_coins - ? WHERE id = ?", (amount, user_id))
        cursor.execute("""
            INSERT INTO bets (user_id, round_code, bet_type, bet_choice, amount)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, round_info["current_round_code"], bet_type, bet_choice, amount))
        conn.commit()

        cursor.execute("SELECT virtual_coins FROM users WHERE id = ?", (user_id,))
        new_balance = cursor.fetchone()["virtual_coins"]

    return jsonify({
        "success": True,
        "message": f"Bet placed: {amount} Coins on {bet_choice}",
        "new_balance": new_balance
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
