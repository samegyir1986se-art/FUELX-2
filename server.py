#!/usr/bin/env python3
"""FUELX ENERGY GHANA LIMITED - station management backend.
Pure Python 3.8+ (standard library only, nothing to pip install)."""
import hashlib, hmac, json, math, os, re, secrets, shutil, sys, tempfile, threading, time
from datetime import date as _d
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT") or 3000)
STN = ["Kasoa", "Asumura", "Tagina", "Hiayeya", "Nyamebekyere", "Kobro", "Appiankwanta"]
RN = {"ceo": "Chief Executive Officer", "ops": "Operations Head", "acc": "Accountant", "mgr": "Station Manager"}
MAP = {"staff": "staff", "st": "stations", "sales": "sales", "deliv": "deliveries", "dips": "dips",
       "exp": "expenses", "bank": "banking", "log": "audit", "cfg": "config"}
# who may add / delete in each collection (enforced here, on the server). sc = limited to one station for managers
RULE = {
    "sales": {"add": "mgr ops ceo", "del": "ceo", "sc": 1},
    "deliveries": {"add": "mgr ops ceo", "del": "ceo", "sc": 1},
    "dips": {"add": "mgr ops ceo", "del": "ceo", "sc": 1},
    "expenses": {"add": "mgr acc ceo", "del": "ceo acc", "sc": 1},
    "banking": {"add": "mgr acc ceo", "del": "ceo", "sc": 1},
    "stations": {"add": "ops ceo", "del": "", "sc": 1},
    "config": {"add": "ops ceo", "del": ""},
    "audit": {"add": "mgr ops acc ceo", "del": ""},
}
FIELDS = {"deliveries": "st date pr l sup inv cpl", "dips": "st pr date dip v", "expenses": "st date cat desc amt",
          "banking": "st date amt ref"}
NUMERIC = {"l", "cpl", "dip", "v", "amt"}
DATE = re.compile(r"^\d{4}-\d\d-\d\d$")
USER = re.compile(r"^[a-z0-9._-]{3,30}$")

# ---------------------------------------------------------------- storage
DIR = os.environ.get("DATA_DIR") or os.path.join(HERE, "data")
try:
    os.makedirs(DIR, exist_ok=True)
    if not os.access(DIR, os.W_OK):
        raise PermissionError("not writable")
except Exception as e:  # no disk attached etc: still start, but warn loudly
    alt = os.path.join(tempfile.gettempdir(), "fuelx-data")
    print("WARNING: cannot use data folder %s (%s). Using %s - data may be LOST on restart. "
          "Attach a persistent disk and set DATA_DIR." % (DIR, e, alt), file=sys.stderr)
    DIR = alt
    os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "db.json")
LOCK = threading.RLock()
DB = {"users": {}, "docs": {}, "sessions": {}, "fails": {}, "ver": 1}
try:
    with open(FILE, encoding="utf-8") as f:
        DB.update(json.load(f))
except Exception:
    pass
for _c in MAP.values():
    if _c != "staff":
        DB["docs"].setdefault(_c, {})
try:
    if os.path.exists(FILE):
        _b = os.path.join(DIR, "backup-%s.json" % _d.today().isoformat())
        if not os.path.exists(_b):
            shutil.copyfile(FILE, _b)
except Exception:
    pass


def _mt():
    try:
        return os.path.getmtime(FILE)
    except OSError:
        return 0


_seen = [_mt()]
try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


class FileLock:
    """Cross-process lock so several worker processes (shared hosting) never corrupt the data file."""
    def __enter__(self):
        self.f = open(os.path.join(DIR, "db.lock"), "a")
        if fcntl:
            fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        if fcntl:
            fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def reload_if_changed():
    m = _mt()
    if m and m != _seen[0]:
        try:
            with open(FILE, encoding="utf-8") as f:
                new = json.load(f)
            DB.clear()
            DB.update({"users": {}, "docs": {}, "sessions": {}, "fails": {}, "ver": 1})
            DB.update(new)
            for c in MAP.values():
                if c != "staff":
                    DB["docs"].setdefault(c, {})
            _seen[0] = m
        except Exception as e:
            print("reload failed:", e, file=sys.stderr)


def save():
    DB["ver"] += 1
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(DB, f)
    os.replace(tmp, FILE)
    _seen[0] = _mt()


# ---------------------------------------------------------------- helpers
def now():
    return int(time.time() * 1000)


def rid():
    return secrets.token_hex(8)


def hash_pw(pw, salt):
    return hashlib.scrypt(pw.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32).hex()


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0
    if math.isnan(v) or math.isinf(v):
        return 0
    return int(v) if v.is_integer() else v


def s_(x):
    return "" if x is None else str(x)[:200]


def pub(u):
    return {k: u.get(k) for k in ("id", "username", "name", "phone", "role", "station", "status", "created")}


def okrole(lst, U):
    return U["role"] in lst.split()


def kill(uid):
    for k in [k for k, v in DB["sessions"].items() if v["uid"] == uid]:
        del DB["sessions"][k]


def tok_of(headers):
    return (headers.get("X-Auth-Token") or (headers.get("Authorization") or "")[7:] or "").strip()


def auth(headers):
    t = tok_of(headers)
    if not t:
        return None
    s = DB["sessions"].get(sha(t))
    if not s or s["exp"] < now():
        return None
    u = DB["users"].get(s["uid"])
    return u if u and u["status"] == "active" else None


def calc_sale(o, id_):
    """Server recalculates every figure so clients cannot fake totals."""
    if o.get("st") not in STN or not DATE.match(s_(o.get("date"))) or id_ != "%s_%s" % (o["st"], o["date"]):
        return "Invalid station or date"
    pr = DB["docs"]["config"].get("prices")
    if not pr or not pr.get("Petrol", {}).get("sell") or not pr.get("Diesel", {}).get("sell"):
        return "Fuel prices are not set"
    lines_in = o.get("lines")
    if not isinstance(lines_in, list) or len(lines_in) != 4 or {x.get("p") for x in lines_in if isinstance(x, dict)} != {"P1", "P2", "P3", "P4"}:
        return "Four pump readings are required"
    L = {"Petrol": 0, "Diesel": 0}
    v = cg = 0
    lines = []
    for x in lines_in:
        p = x["p"]
        r = "Petrol" if p in ("P1", "P2") else "Diesel"
        op, c = num(x.get("o")), num(x.get("c"))
        if c < op:
            return "Bad meter reading for " + p
        l = c - op
        lines.append({"p": p, "pr": r, "o": op, "c": c, "l": l})
        L[r] += l
        v += l * pr[r]["sell"]
        cg += l * pr[r]["cost"]
    pin = o.get("pay") if isinstance(o.get("pay"), dict) else {}
    pay = {k: max(0, num(pin.get(k))) for k in ("cash", "momo", "card", "credit")}
    col = sum(pay.values())
    return {"st": o["st"], "date": o["date"], "lines": lines, "L": L, "sales": v, "cogs": cg, "pay": pay,
            "collected": col, "diff": col - v, "verified": False}


class Err(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg


# ---------------------------------------------------------------- request handling
def handle(method, path, query, headers, b):
    """Returns (status, python-object). Raises Err for errors."""
    if path == "/api/status" and method == "GET":
        return 200, {"first": not DB["users"]}
    if path == "/api/register" and method == "POST":
        un = s_(b.get("username")).lower().strip()
        pw = str(b.get("password") or "")
        if not USER.match(un):
            raise Err(400, "Username: 3-30 letters, numbers, . _ -")
        if not 4 <= len(pw) <= 64:
            raise Err(400, "PIN / password must be 4-64 characters")
        if not s_(b.get("name")).strip():
            raise Err(400, "Enter your full name")
        if any(x["username"] == un for x in DB["users"].values()):
            raise Err(409, "That username is taken")
        first = not DB["users"]
        role = "ceo" if first else b.get("role")
        if role not in RN or (role == "ceo" and not first):
            raise Err(400, "Choose a valid role")
        if role == "mgr" and b.get("station") not in STN:
            raise Err(400, "Choose your station")
        salt, id_ = rid(), rid()
        DB["users"][id_] = {"id": id_, "username": un, "name": s_(b.get("name")).strip(), "phone": s_(b.get("phone")),
                            "role": role, "station": b["station"] if role == "mgr" else "",
                            "status": "active" if first else "pending", "salt": salt, "hash": hash_pw(pw, salt),
                            "created": now()}
        save()
        return 200, {"ok": 1, "status": DB["users"][id_]["status"]}
    if path == "/api/login" and method == "POST":
        un = s_(b.get("username")).lower().strip()
        f = DB["fails"].get(un, {"n": 0, "t": 0})
        user = next((x for x in DB["users"].values() if x["username"] == un), None)
        if f["t"] > now():
            raise Err(429, "Too many wrong attempts. Try again in a few minutes.")
        if not user or not hmac.compare_digest(user["hash"], hash_pw(str(b.get("password") or ""), user["salt"])):
            n = f["n"] + 1
            DB["fails"][un] = {"n": 0 if n >= 5 else n, "t": now() + 600000 if n >= 5 else 0}
            raise Err(401, "Wrong username or PIN / password")
        if user["status"] != "active":
            raise Err(403, "Your account is waiting for CEO approval" if user["status"] == "pending"
                      else "Your account is suspended. Contact the CEO.")
        DB["fails"].pop(un, None)
        for k in [k for k, v in DB["sessions"].items() if v["exp"] < now()]:
            del DB["sessions"][k]
        tok = secrets.token_hex(32)
        DB["sessions"][sha(tok)] = {"uid": user["id"], "exp": now() + 12 * 3600000}
        save()
        return 200, {"token": tok, "user": pub(user)}

    U = auth(headers)
    if not U:
        raise Err(401, "Please log in")
    if path == "/api/logout" and method == "POST":
        DB["sessions"].pop(sha(tok_of(headers)), None)
        save()
        return 200, {"ok": 1}
    if path == "/api/me" and method == "GET":
        return 200, {"user": pub(U)}
    if path == "/api/password" and method == "POST":
        if not hmac.compare_digest(U["hash"], hash_pw(str(b.get("old") or ""), U["salt"])):
            raise Err(403, "Current PIN is wrong")
        n = str(b.get("pw") or "")
        if not 4 <= len(n) <= 64:
            raise Err(400, "New PIN must be 4-64 characters")
        U["salt"] = rid()
        U["hash"] = hash_pw(n, U["salt"])
        save()
        return 200, {"ok": 1}
    if path == "/api/data" and method == "GET":
        try:
            v = int((query.get("v") or ["0"])[0])
        except ValueError:
            v = 0
        if v == DB["ver"]:
            return 200, {"same": 1, "v": v}
        o = {"v": DB["ver"]}
        for k, c in MAP.items():
            if c == "staff":
                a = [pub(x) for x in DB["users"].values()] if U["role"] == "ceo" else [pub(U)]
            elif c == "audit" and U["role"] not in ("ceo", "ops"):
                a = []
            else:
                a = [dict(d, id=i) for i, d in DB["docs"][c].items()]
            if U["role"] == "mgr" and RULE.get(c, {}).get("sc"):
                a = [d for d in a if (d["id"] if c == "stations" else d.get("st")) == U["station"]]
            o[k] = a
        return 200, o
    if path == "/api/backup" and method == "GET":
        if U["role"] != "ceo":
            raise Err(403, "CEO only")
        return 200, {"docs": DB["docs"], "users": [pub(x) for x in DB["users"].values()]}

    parts = path.split("/") + [None] * 5
    coll, id_, act = parts[2], parts[3], parts[4]
    if coll == "staff":
        if U["role"] != "ceo":
            raise Err(403, "CEO only")
        T = DB["users"].get(id_)
        if not T:
            raise Err(404, "No such user")
        if method == "POST" and act == "reset":
            n = str(b.get("password") or "")
            if not 4 <= len(n) <= 64:
                raise Err(400, "PIN must be 4-64 characters")
            T["salt"] = rid()
            T["hash"] = hash_pw(n, T["salt"])
            kill(T["id"])
            save()
            return 200, {"ok": 1}
        if method == "PATCH":
            if id_ == U["id"]:
                raise Err(400, "You cannot change your own role or status")
            if "role" in b:
                if b["role"] not in RN:
                    raise Err(400, "Bad role")
                T["role"] = b["role"]
            if "station" in b:
                if b["station"] and b["station"] not in STN:
                    raise Err(400, "Bad station")
                T["station"] = b["station"] or ""
            if "status" in b:
                if b["status"] not in ("active", "suspended", "pending"):
                    raise Err(400, "Bad status")
                T["status"] = b["status"]
                if b["status"] != "active":
                    kill(T["id"])
            if T["role"] == "mgr" and not T["station"]:
                T["status"] = "pending"
            save()
            return 200, {"ok": 1}
        raise Err(405, "Not allowed")

    R = RULE.get(coll)
    if not R:
        raise Err(404, "Unknown")
    D = DB["docs"][coll]

    def stamp(o):
        o["by"], o["byName"], o["ts"] = U["id"], "%s (%s)" % (U["name"], RN[U["role"]]), now()
        return o

    if method in ("POST", "PUT"):
        if not okrole(R["add"], U):
            raise Err(403, "Your role cannot add this")
        nid = id_ or rid()
        if coll == "audit":
            D[nid] = {"ts": now(), "u": "%s (%s)" % (U["name"], RN[U["role"]]), "a": s_(b.get("a"))}
            save()
            return 200, {"ok": 1}
        if method == "PUT" and coll not in ("sales", "stations", "config"):
            raise Err(405, "Not allowed")
        if R.get("sc"):
            st = id_ if coll == "stations" else b.get("st")
            if st not in STN:
                raise Err(400, "Invalid station")
            if U["role"] == "mgr" and st != U["station"]:
                raise Err(403, "You can only enter data for your own station")
        if coll == "sales":
            if id_ in D:
                raise Err(409, "A record for this station and date already exists")
            o = calc_sale(b, id_)
            if isinstance(o, str):
                raise Err(400, o)
        elif coll == "config":
            if id_ != "prices":
                raise Err(400, "Bad id")
            o = {k: {"sell": max(0, num((b.get(k) or {}).get("sell"))), "cost": max(0, num((b.get(k) or {}).get("cost")))}
                 for k in ("Petrol", "Diesel")}
        elif coll == "stations":
            tk, mt = b.get("tanks") or {}, b.get("meters") or {}
            o = {"tanks": {k: {"cap": max(0, num((tk.get(k) or {}).get("cap"))), "open": max(0, num((tk.get(k) or {}).get("open")))}
                           for k in ("Petrol", "Diesel")},
                 "meters": {k: max(0, num(mt.get(k))) for k in ("P1", "P2", "P3", "P4")}}
        else:
            o = {k: (num(b.get(k)) if k in NUMERIC else s_(b.get(k))) for k in FIELDS[coll].split()}
            if not DATE.match(o["date"]):
                raise Err(400, "Invalid date")
            if any(k in o and o[k] <= 0 for k in ("l", "amt")):
                raise Err(400, "Amount must be above zero")
            if o.get("pr") and o["pr"] not in ("Petrol", "Diesel"):
                raise Err(400, "Bad product")
        D[nid] = stamp(o)
        save()
        return 200, {"ok": 1, "id": nid}
    if method == "PATCH" and coll == "sales" and id_:
        if not okrole("acc ops ceo", U) or id_ not in D:
            raise Err(403, "Not allowed")
        D[id_].update(verified=True, vname=U["name"], vts=now())
        save()
        return 200, {"ok": 1}
    if method == "DELETE" and id_:
        if not okrole(R["del"], U) or id_ not in D:
            raise Err(403, "Not allowed")
        if U["role"] == "acc" and D[id_].get("by") != U["id"]:
            raise Err(403, "You can only delete your own entries")
        del D[id_]
        save()
        return 200, {"ok": 1}
    raise Err(405, "Not allowed")


def find_index():
    for f in (os.path.join(HERE, "public", "index.html"), os.path.join(HERE, "index.html"),
              os.path.join(os.getcwd(), "public", "index.html")):
        if os.path.exists(f):
            return f
    return None


JSON = "application/json"


def dispatch(method, target, headers, raw):
    """Shared by the built-in server and by WSGI hosts. Returns (status, payload, content-type)."""
    try:
        u = urlparse(target)
        p = u.path
        if p == "/healthz":
            return 200, "ok", "text/plain"
        if not p.startswith("/api/"):
            if p in ("/", "/index.html"):
                f = find_index()
                if not f:
                    return 500, ("FUELX: public/index.html is missing from the deployed files. "
                                 "Upload the whole project including the public folder."), "text/plain"
                with open(f, "rb") as fh:
                    return 200, fh.read(), "text/html; charset=utf-8"
            return 404, "Not found", "text/plain"
        b = {}
        if method != "GET":
            if len(raw) > 200000:
                return 413, {"error": "Request too large"}, JSON
            try:
                b = json.loads(raw or b"{}")
                if not isinstance(b, dict):
                    b = {}
            except ValueError:
                b = {}
        with LOCK, FileLock():
            reload_if_changed()
            code, obj = handle(method, p, parse_qs(u.query), headers, b)
        return code, obj, JSON
    except Err as e:
        return e.code, {"error": e.msg}, JSON
    except Exception as e:  # never crash, never reply twice
        print("Error:", repr(e), file=sys.stderr)
        return 500, {"error": "Server error"}, JSON


# ---- WSGI entry point (PythonAnywhere, cPanel/Passenger, gunicorn, mod_wsgi ...)
def application(environ, start_response):
    try:
        n = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        n = 0
    raw = environ["wsgi.input"].read(min(n, 200001)) if n > 0 else b""
    target = (environ.get("PATH_INFO") or "/") + ("?" + environ["QUERY_STRING"] if environ.get("QUERY_STRING") else "")
    hdr = {"Authorization": environ.get("HTTP_AUTHORIZATION", ""), "X-Auth-Token": environ.get("HTTP_X_AUTH_TOKEN", "")}
    code, data, ctype = dispatch(environ.get("REQUEST_METHOD", "GET"), target, hdr, raw)
    body = data if isinstance(data, bytes) else (data if isinstance(data, str) else json.dumps(data)).encode()
    start_response("%d %s" % (code, {200: "OK", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found"}.get(code, "Status")), [
        ("Content-Type", ctype), ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store" if ctype == JSON else "no-cache"),
        ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY")])
    return [] if environ.get("REQUEST_METHOD") == "HEAD" else [body]


class H(BaseHTTPRequestHandler):
    server_version = "FUELX"

    def log_message(self, fmt, *a):
        pass

    def route(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if 0 < n <= 200000 else (b"x" * 200001 if n > 200000 else b"")
            hdr = {"Authorization": self.headers.get("Authorization", ""), "X-Auth-Token": self.headers.get("X-Auth-Token", "")}
            code, data, ctype = dispatch(self.command, self.path, hdr, raw)
            body = data if isinstance(data, bytes) else (data if isinstance(data, str) else json.dumps(data)).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if ctype == JSON else "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except Exception as e:
            print("Error:", repr(e), file=sys.stderr)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = route


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    srv.daemon_threads = True
    print("FUELX server (Python) running on port %d" % PORT, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
