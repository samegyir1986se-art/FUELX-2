# FUELX ENERGY GHANA LIMITED - Station Management System

Own server + website. No npm packages to install. Needs Node.js 18 or newer.

## Run on your computer
    node server.js
Open http://localhost:3000. The FIRST person to register becomes the CEO (active). Everyone else registers
(username + PIN/password), then the CEO approves them under "Staff & Access".

## Put it online
1. Render.com / Railway / Fly.io / any VPS: upload this folder (or push to GitHub), start command `node server.js`.
2. IMPORTANT: attach a persistent disk/volume and set the environment variable DATA_DIR to its path (for example /data).
   Without a persistent disk, most hosts erase the data when the app restarts.
3. Use the HTTPS address the host gives you (never plain http) and point your own domain at it if you wish.
4. Docker: `docker build -t fuelx .` then `docker run -p 3000:3000 -v fuelx-data:/data fuelx`.

## Security built in
- Passwords/PINs are hashed (scrypt) with a unique salt per person; never stored in plain text.
- Login lockout after 5 wrong attempts (10 minutes); sessions expire after 12 hours; logout ends the session on the server.
- Every permission is enforced on the SERVER, not just on screen: managers only read/write their own station;
  prices and station setup are Operations Head/CEO only; expenses, banking and verification follow the role table;
  only the CEO can delete (the Accountant may delete own expenses) and manage staff. Sales totals are recalculated by the server.
- Data file: DATA_DIR/db.json, with a copy saved each day as backup-YYYY-MM-DD.json. The CEO can also download a full backup in the app.
