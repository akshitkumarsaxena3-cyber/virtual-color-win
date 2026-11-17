# Virtual Color Win (Full-Stack Simulation App)

A modern, responsive, mobile-first web application featuring a real-time round-based color game with **100% internal virtual coins** (play money only).

---

## 🚀 Key Features

1. **User Authentication & Registration:**
   - Registration with mobile phone and password.
   - Referral / Invitation code tracking via URL query parameter (`/register?invitationCode=XYZ`).
   - 1,000 Welcome Bonus Virtual Coins for newly registered accounts.

2. **Referral Reward System:**
   - Unique referral code generated for every user.
   - Referrers earn +200 Virtual Bonus Coins whenever an invited friend signs up.

3. **Synchronized 30-Second Round Arena:**
   - Live synchronized timer across all clients.
   - Color selection: **Green (2x)**, **Violet (4.5x)**, **Red (2x)**.
   - Number selection: **0 to 9 (9x payout)**.
   - Betting auto-locks in the last 5 seconds of each round.
   - Live round settlement with real-time balance updates and toast notifications.

4. **Internal Virtual Coins Only (Safe Simulation):**
   - No payment gateways, no deposits, and no real-money withdrawals.
   - Built-in **Free Coins Faucet** (`+500 Coins`) anytime you want to reload virtual points.

5. **Past Rounds History:**
   - Live table displaying period codes, winning numbers, and color badges.

---

## 🛠️ Tech Stack

- **Backend:** Python 3 (Flask, SQLite3, Werkzeug)
- **Frontend:** HTML5, Modern CSS3, Tailwind CSS (CDN), Vanilla JavaScript
- **API:** RESTful JSON endpoints (`/api/status`, `/api/bet`, `/faucet`)

---

## 💻 How to Run Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
Run with Python:
```bash
python app.py
```
Or double-click `run.bat` on Windows.

### 3. Open in Browser
Visit:
`http://localhost:5000`

To test registration with an invitation code:
`http://localhost:5000/register?invitationCode=4785616395140`

---

## 📦 How to Push this Project to GitHub

1. Open your terminal or PowerShell in this project folder:
   ```bash
   cd c:\Users\HP\Desktop\virtual-color-win
   ```

2. (Optional) Check git status:
   ```bash
   git status
   ```

3. Create a new repository on [GitHub](https://github.com/new).

4. Link your local project to GitHub and push:
   ```bash
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git
   git branch -M main
   git push -u origin main
   ```

---

## ⚠️ Disclaimer
This project is built strictly for **educational and research purposes** to demonstrate full-stack web development, real-time client-server synchronization, and referral tracking architectures. It does not use, support, or process real money, cryptocurrency, or actual gambling transactions.
