# Deploying FUELX with Netlify (simple 2-part method)

WHY TWO PARTS: Netlify can only host web pages. It cannot run the FUELX server or keep a permanent data file.
So: the SERVER (data, logins, roles) runs on Render, and the WEBSITE is on Netlify and talks to it.

## PART 1 - Server on Render (about 5 minutes)
1. Put these project files in a new GitHub repository (server.py, requirements.txt, public, etc. at the top level).
2. render.com > New > Web Service > connect the repository.
   - Runtime: Python 3.   Build command: pip install -r requirements.txt   Start command: python server.py
   - Add a Disk: mount path /data, size 1 GB.   Add environment variable: DATA_DIR = /data
3. Click Deploy. When finished, copy your address, e.g. https://fuelx-abc1.onrender.com
   Open it once: you should see the FUELX sign-in page.  Register FIRST yourself: you become the CEO.

## PART 2 - Website on Netlify (about 3 minutes)
1. Open netlify.toml in this project and replace  YOUR-APP-NAME.onrender.com  with your Render address
   (keep the /api/:splat at the end). Save and upload the change to GitHub.
2. app.netlify.com > Add new site > Import from Git > choose the same repository.
   Build command: (empty). Publish directory: public   (netlify.toml sets this automatically).
3. Deploy. Your staff use the Netlify address (or your own domain added under Domain settings).

## Checks
- Staff register and sign in on the Netlify address. If you see "Unexpected token" or sign-in errors,
  the address in netlify.toml is wrong or the Render server is asleep (free plans sleep; use a paid plan for always-on).
- Data is stored on the Render disk, not on Netlify.
