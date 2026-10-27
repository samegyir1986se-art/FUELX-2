# FUELX ENERGY GHANA LIMITED - Station Management System (Python 3)

Own server + website written in Python 3.8+ using ONLY the standard library. Nothing to install with pip.

**Easiest way online: read DEPLOY.md (PythonAnywhere, cPanel hosting, Render, Docker).**

## Run on your computer
    python3 server.py        (Windows: python server.py)
Open http://localhost:3000. The FIRST person to register becomes the CEO (active). Everyone else registers
(username + PIN/password), then the CEO approves them under "Staff & Access".

## Put it online (Render, Railway, Fly.io, any VPS)
1. Upload this folder so that server.py, requirements.txt and the public folder are at the TOP LEVEL.
2. Build command: pip install -r requirements.txt   Start command: python server.py   (Python 3.8 or newer)
3. IMPORTANT: attach a persistent disk and set DATA_DIR to its path (e.g. /data), otherwise data is erased on restart.
4. Do not set PORT yourself; the host provides it. Health check path: /healthz. Use the https address.
5. Docker: docker build -t fuelx .  then  docker run -p 3000:3000 -v fuelx-data:/data fuelx
Using Netlify for the website? See DEPLOY-NETLIFY.md.

## Security built in
- PINs/passwords hashed with scrypt and a unique salt per person; never stored in plain text.
- 5 wrong attempts locks that username for 10 minutes; sessions last 12 hours; logout ends the session on the server.
- Every permission is enforced on the SERVER: managers only see/write their own station; prices and station setup are
  Operations Head/CEO only; expenses, banking and verification follow the role table; only the CEO can delete
  (Accountant may delete own expenses) and manage staff. Sales totals are recalculated by the server.
- Data file: DATA_DIR/db.json, with a copy saved each day as backup-YYYY-MM-DD.json. The CEO can download a full backup in the app.

## If deployment fails
- server.py and the public folder must be at the top level of the upload (not inside another folder).
- If the page says public/index.html is missing, the public folder was not uploaded.
