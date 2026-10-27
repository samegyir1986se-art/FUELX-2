# How to put FUELX online - pick ONE option

All options give you a secure https address you share with staff. The FIRST person to register becomes the CEO,
so open the site and register yourself first. Then staff register and you approve them under "Staff & Access".

## OPTION A - PythonAnywhere (EASIEST: no Git, no command line knowledge, free to start)
1. Create an account at pythonanywhere.com. Your site will be https://YOURUSERNAME.pythonanywhere.com
2. Files tab > Upload a file > upload fuelx-backend.zip. Then open Consoles > Bash and run:
       mkdir fuelx && cd fuelx && unzip ../fuelx-backend.zip
   (check with `ls` that server.py and the public folder are directly inside /home/YOURUSERNAME/fuelx)
3. Web tab > Add a new web app > Next > "Manual configuration" > choose Python 3.10 (or newer) > Next.
4. On the Web tab, click the WSGI configuration file link, delete everything in it, and paste:
       import sys
       sys.path.insert(0, '/home/YOURUSERNAME/fuelx')
       from server import application
   (replace YOURUSERNAME) Save.
5. Back on the Web tab click the green Reload button, then open your address. Done.
   Data is kept permanently in /home/YOURUSERNAME/fuelx/data (back it up from the Files tab).
   Free accounts: click "Run until 3 months from today" on the Web tab every so often so the site stays active.

## OPTION B - cPanel shared hosting (many Ghanaian hosts) with "Setup Python App"
1. cPanel > Setup Python App > Create Application: Python 3.8+, Application root = fuelx,
   Application URL = your domain or subdomain (use the ROOT of a domain/subdomain, not a sub-folder).
   Startup file: passenger_wsgi.py     Entry point: application
2. File Manager: upload and extract fuelx-backend.zip INTO the application root so server.py,
   passenger_wsgi.py and the public folder sit directly inside it. Back in Setup Python App click Restart.
3. Open your domain. Data is stored in the data folder inside the application root.

## OPTION C - Render.com (needs a GitHub account; paid plan needed for a persistent disk)
1. Upload the project files to a GitHub repository (server.py, requirements.txt, public etc. at the top level).
2. render.com > New > Blueprint (uses render.yaml) or New > Web Service:
   Build: pip install -r requirements.txt   Start: python server.py   Disk: mount /data   Env var DATA_DIR=/data
3. Open the address Render gives you. (Using Netlify for the site address? see DEPLOY-NETLIFY.md)

## Also works anywhere Python runs (VPS, Docker, gunicorn)
    python3 server.py                      (built-in server, port from PORT variable, default 3000)
    gunicorn server:application            (production WSGI)
    docker build -t fuelx . && docker run -p 3000:3000 -v fuelx-data:/data fuelx

## Important notes
- Keep your data safe: it lives in the "data" folder (db.json plus a daily backup-DATE.json copy).
  The CEO can also download a full backup inside the app (Staff & Access).
- Always use the https address. Never share the CEO PIN. Use "Reset PIN" for staff who forget theirs.
- If the page shows "public/index.html is missing", the public folder was not uploaded next to server.py.
