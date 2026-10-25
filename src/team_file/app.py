"""Tandem: SJSU Career Mentorship Platform (TI track, SpartHill Hack 2026).

Roles: Mentee, Mentor, Staff, Admin. Run: streamlit run app.py
Storage: SQLite (tandem.db) with user accounts, messages, submissions, and program state.
"""
import base64
import hashlib
import io
import json
import os
import random
import secrets
import smtplib
import sqlite3
import threading
from email.message import EmailMessage
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import ui

from matching import (SJSU_LINKS, NOT_SURE, COLLEGES, GENERIC_COLLEGES, SCHOOLS,  REASON_FACTOR, INDUSTRIES, HELP_AREAS, FIELDS, MINORS, NO_MINOR, DAYS, TIMES,
                      MODES, YEARS, EXPERIENCE, WEIGHTS, run_matching, score_pair, explain, gaps,
                      supply_gap, learn_weights, rank_mentors, sentiment, safety_flags, train_model,
                      predict_success, MIN_TRAIN, industry_credit, confidence)
from seed_data import make

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tandem.db")
NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
DEMO_PASSWORD = "demo1234"
MAX_UPLOAD_MB = 5

CURRICULUM = [
    {"name": "Orientation", "week": 1,
     "prework": ["Read the program handbook", "Sign the mentee agreement", "Write 3 goals for the program"],
     "mentor_prep": ["Read your mentee's profile and goals", "Prepare a short intro about your career path"],
     "postwork": ["Share your goals doc with your mentor"]},
    {"name": "Lesson 1: Self-Assessment & Goal Setting", "week": 3,
     "prework": ["10 min reading: self-assessment and goal setting", "Complete the strengths self-assessment",
                 "List 5 roles or companies you're curious about"],
     "mentor_prep": ["Review mentee's self-assessment"],
     "postwork": ["Write a 1-paragraph career goal statement", "2 min survey"]},
    {"name": "Lesson 2: Resume & LinkedIn Building", "week": 5,
     "prework": ["10 min reading: resume and LinkedIn basics", "Update your resume",
                 "Update your LinkedIn headline and About section"],
     "mentor_prep": ["Review mentee's resume before the session"],
     "postwork": ["Apply mentor feedback and upload the new resume", "2 min survey"]},
    {"name": "Lesson 3: Networking & Informational Interviews", "week": 7,
     "prework": ["10 min reading: networking and informational interviews", "Find 2 people to reach out to on LinkedIn",
                 "Draft 3 questions for an informational interview"],
     "mentor_prep": ["Share how you approach informational interviews"],
     "postwork": ["Send 2 networking messages", "2 min survey"]},
    {"name": "Lesson 4: Interview Prep & Mock Interview", "week": 9,
     "prework": ["10 min reading: interview preparation", "Prepare 3 STAR stories"],
     "mentor_prep": ["Prepare 3 mock interview questions"],
     "postwork": ["Write down the feedback from your mock interview", "2 min survey"]},
    {"name": "Closing Session: Recap & Accomplishments (in person)", "week": 12,
     "prework": ["Reflect: what changed since orientation?", "List your accomplishments in the program",
                 "Fill the program survey"],
     "mentor_prep": ["Fill the mentor program survey"],
     "postwork": ["Thank your mentor and stay connected"]},
]

# ---------------- Role-based access: one place to change who can do what ----------------
PERMISSIONS = {
    "apply_and_edit_profile":   ["Mentee", "Mentor"],
    "view_own_match":           ["Mentee", "Mentor"],
    "submit_prework_postwork":  ["Mentee"],
    "view_mentee_submissions":  ["Mentor"],
    "session_confirm_feedback": ["Mentee", "Mentor"],
    "pair_messaging":           ["Mentee", "Mentor"],          # private: staff can't read
    "staff_dashboard":          ["Staff", "Admin"],
    "review_matches":           ["Staff", "Admin"],            # approve / deny / reassign
    "view_progress_insights":   ["Staff", "Admin"],
    "view_scorecards":          ["Admin"],                     # super-admin only (per team doc)
    "send_announcements":       ["Staff", "Admin"],
    "schedule_sessions":        ["Mentee", "Mentor"],
    "export_reports":           ["Staff", "Admin"],
    "open_close_applications":  ["Admin"],
    "run_matching":             ["Staff", "Admin"],
    "edit_matching_rules":      ["Staff", "Admin"],            # auto-approve toggle and score
    "release_matches":          ["Staff", "Admin"],            # only offered once every student has an approved match
    "edit_curriculum":          ["Staff", "Admin"],            # same prework for every mentee
    "edit_weights":             ["Staff", "Admin"],            # hand-edit the scoring weights
    "train_apply_model":        ["Admin"],
    "program_settings":         ["Admin"],                     # calendar, curriculum, demo tools
    "manage_staff_accounts":    ["Admin"],                     # add staff, change roles
    "manage_users":             ["Staff", "Admin"],            # search, edit, deactivate, reset password
    "edit_dropdown_options":    ["Admin"],
    "start_new_cycle":          ["Admin"],
}


def can(feature, role=None):
    role = role or (st.session_state.get("user") or {}).get("role")
    return role in PERMISSIONS.get(feature, [])


st.set_page_config(page_title="Tandem | SJSU Mentorship", page_icon=":material/directions_bike:", layout="wide",
                   initial_sidebar_state="expanded")
# Hide "Made with Streamlit" and give every page breathing room on the sides
st.markdown("""<style>
footer {visibility: hidden;}
[data-testid=stMainBlockContainer] {max-width: 1200px; margin: 0 auto; padding-left: 3rem; padding-right: 3rem;}
@media (max-width: 900px) {[data-testid=stMainBlockContainer] {padding-left: 2rem; padding-right: 2rem;}}
@media (max-width: 640px) {[data-testid=stMainBlockContainer] {padding-left: 1rem; padding-right: 1rem;}}
</style>""", unsafe_allow_html=True)
ui.inject()          # shared look + light/dark palette for every screen, including login


# ---------------- Database (SQLite) ----------------
def db():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.execute("""CREATE TABLE IF NOT EXISTS users(email TEXT PRIMARY KEY, name TEXT, role TEXT,
                   profile_id TEXT, salt TEXT, pw_hash TEXT, created TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY, doc TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS photos(email TEXT PRIMARY KEY, data BLOB)""")
    con.execute("""CREATE TABLE IF NOT EXISTS archives(id INTEGER PRIMARY KEY AUTOINCREMENT,
                   cycle TEXT, archived_at TEXT, doc TEXT)""")
    try:
        con.execute("ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    con.execute("""CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
                   pair TEXT, sender_role TEXT, sender_name TEXT, body TEXT, at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT,
                   pair TEXT, session INTEGER, kind TEXT, text TEXT, filename TEXT, data BLOB, at TEXT)""")
    return con


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 20000).hex()


def create_user(con, email, name, role, password, profile_id=None):
    salt = secrets.token_hex(16)
    con.execute("INSERT INTO users(email, name, role, profile_id, salt, pw_hash, created) VALUES (?,?,?,?,?,?,?)",
                (email.lower().strip(), name, role, profile_id, salt, hash_pw(password, salt), NOW()))
    con.commit()


def check_login(email, password):
    row = db().execute("SELECT email, name, role, profile_id, salt, pw_hash, active FROM users WHERE email=?",
                       (email.lower().strip(),)).fetchone()
    if row and row[6] != 0 and secrets.compare_digest(hash_pw(password, row[4]), row[5]):
        return {"email": row[0], "name": row[1], "role": row[2], "id": row[3]}
    return None


def fresh_state():
    students, mentors = make(n_mentors=50)
    for s in students:
        s["status"] = "Approved"
        s["agreement"] = NOW()
        s["about"] = f"Hoping to get better at {s['help_ranked'][0].lower()} and learn how people break into {s['industry']}."
    for m in mentors:
        m["status"] = "Rejected" if m["experience"] == "<1" else "Approved"
        m["agreement"] = NOW()
        m["about"] = f"{m['role']} at {m['company']}. Happy to help with {', '.join(m['can_help'][:2]).lower()}."
        m["linkedin"] = ""
    return {"students": students, "mentors": mentors, "matches": [], "decisions": [],
            "progress": {}, "emails": [], "reminders_sent": [], "weights": WEIGHTS,
            "cycle": {"apps_open": True, "released": False, "name": "Spring 2027",
                      "apps_deadline": "2027-01-15", "start": "2027-01-26", "today": None},
            "curriculum": CURRICULUM}


def reset_db():
    # Clear tables instead of deleting the file: Windows locks an open SQLite file.
    con = db()
    for t in ("users", "state", "photos", "messages", "submissions"):
        con.execute(f"DELETE FROM {t}")
    con.commit()
    d = fresh_state()
    for s in d["students"]:
        create_user(con, s["email"], s["name"], "Mentee", DEMO_PASSWORD, s["id"])
    for m in d["mentors"]:
        create_user(con, m["email"], m["name"], "Mentor", DEMO_PASSWORD, m["id"])
    create_user(con, "admin@sjsu.edu", "Career Center Lead", "Admin", "admin1234", "admin")
    create_user(con, "staff@sjsu.edu", "Career Center Coordinator", "Staff", "staff1234", "staff")
    con.execute("INSERT INTO state VALUES (1, ?)", (json.dumps(d),))
    con.commit()


def load():
    con = db()
    row = con.execute("SELECT doc FROM state WHERE id=1").fetchone()
    if not row:
        reset_db()
        row = db().execute("SELECT doc FROM state WHERE id=1").fetchone()
    return json.loads(row[0])


def save(d):
    con = db()
    con.execute("INSERT OR REPLACE INTO state VALUES (1, ?)", (json.dumps(d),))
    con.commit()


D = load()
for _p in D["students"] + D["mentors"]:  # no manual review step: applicants join the pool right away
    if _p.get("status") == "Pending":
        _p["status"] = "Approved"
OPTS = D.setdefault("options", {"industries": INDUSTRIES, "help_areas": HELP_AREAS,
                                "majors": FIELDS, "minors": MINORS})
INDUSTRIES, HELP_AREAS, FIELDS, MINORS = (OPTS["industries"], OPTS["help_areas"],
                                          OPTS["majors"], OPTS["minors"])


def abc(options):
    """Alphabetical dropdown order; 'None' / 'Not sure yet' stay first and 'Other...' stays last."""
    return sorted(options, key=lambda o: (0 if o in (NO_MINOR, NOT_SURE) else 2 if o.startswith("Other") else 1,
                                          o.lower()))


# Ordered scales (Year, experience, SJSU connection) keep their natural order instead.
(INDUSTRIES, HELP_AREAS, FIELDS, MINORS, COLLEGES, GENERIC_COLLEGES, SCHOOLS, MODES) = map(
    abc, (INDUSTRIES, HELP_AREAS, FIELDS, MINORS, COLLEGES, GENERIC_COLLEGES, SCHOOLS, MODES))
S_BY = {s["id"]: s for s in D["students"]}
M_BY = {m["id"]: m for m in D["mentors"]}


def commit(msg=None):
    save(D)
    if msg:
        st.session_state["toast"] = msg
    st.rerun()


def pair_key(m):
    return f"{m['student_id']}|{m['mentor_id']}"


def active_matches(status=("Approved",)):
    return [m for m in D["matches"] if m["status"] in status]


def match_for_student(sid):
    return next((m for m in D["matches"] if m["student_id"] == sid and m["status"] == "Approved"), None)


# ---------------- Program calendar + automated reminders ----------------
def today():
    t = D["cycle"].get("today")
    return date.fromisoformat(t) if t else date.today()


def apps_closed():
    """Applications are closed once an admin closes them or the deadline has passed (demo clock included)."""
    cyc = D["cycle"]
    return not cyc["apps_open"] or today() > date.fromisoformat(cyc["apps_deadline"])


TIME_RANGES = {"Morning": "8 AM-12 PM", "Afternoon": "12-5 PM", "Evening": "5-9 PM"}


def pair_session_date(pk, i):
    """Booked date for this pair's session, or the program default."""
    sch = D["progress"].get(pk, {}).get(str(i), {}).get("schedule")
    return date.fromisoformat(sch["date"]) if sch else session_date(i)


def week_dates(i):
    start = session_date(i)
    return [start + timedelta(days=k) for k in range(7)]


def mentor_booked(mentor_id, day, slot, skip_pk):
    for m in active_matches():
        pk = pair_key(m)
        if m["mentor_id"] != mentor_id or pk == skip_pk:
            continue
        for rec in D["progress"].get(pk, {}).values():
            sch = rec.get("schedule")
            if sch and sch["date"] == day.isoformat() and sch["slot"] == slot:
                return S_BY[m["student_id"]]["name"]
    return None


def session_date(i):
    return date.fromisoformat(D["cycle"]["start"]) + timedelta(weeks=D["curriculum"][i]["week"] - 1)


def smtp_creds():
    """Gmail address + app password from .streamlit/secrets.toml or env vars. Never stored in the DB."""
    try:
        u, p = st.secrets.get("SMTP_USER"), st.secrets.get("SMTP_PASSWORD")
    except Exception:
        u = p = None
    return (u or os.environ.get("TANDEM_SMTP_USER"), p or os.environ.get("TANDEM_SMTP_PASSWORD"))


def live_target(to):
    """Where a real email should go, or None. Only allowlisted addresses/domains get real mail,
    so the fake seeded accounts never do. 'Redirect' sends everything to one test inbox."""
    cfg = D.get("email_cfg", {})
    if not cfg.get("live"):
        return None
    if cfg.get("redirect"):
        return cfg["redirect"]
    allow = [a.strip().lower() for a in cfg.get("allow", "").split(",") if a.strip()]
    t = to.lower()
    return to if any(t == a or t.endswith("@" + a.lstrip("@")) for a in allow) else None


def smtp_send(to, subject, body):
    user, pw = smtp_creds()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = f"Tandem <{user}>", to, subject
    msg.set_content(body + "\n\n- Tandem, SJSU Career Mentorship")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.login(user, pw)
        s.send_message(msg)


def send(to, subject, body, kind="Reminder"):
    rec = {"to": to, "at": NOW(), "kind": kind, "subject": subject, "body": body, "delivery": "in-app"}
    D["emails"].append(rec)
    target = live_target(to)
    if target and all(smtp_creds()):
        subj = subject if target == to else f"[for {to}] {subject}"
        rec["delivery"] = f"emailed to {target}"
        threading.Thread(target=lambda: _safe_send(target, subj, body), daemon=True).start()


def _safe_send(to, subject, body):
    try:
        smtp_send(to, subject, body)
    except Exception as e:  # never break the app over email
        print("Email failed:", e)


def run_reminders():
    """Automated reminders tied to the program schedule. Idempotent: each fires once."""
    if not D["cycle"]["released"]:
        return 0
    sent, t, n = set(D["reminders_sent"]), today(), 0
    for m in active_matches():
        pk, s, mt = pair_key(m), S_BY[m["student_id"]], M_BY[m["mentor_id"]]
        for i, cur in enumerate(D["curriculum"]):
            d, rec = pair_session_date(pk, i), session_rec(pk, i)
            rules = [
                ("prework", d - timedelta(days=2) <= t < d and not all(rec["mentee_pre"]), [s],
                 f"Prework due before {cur['name']} on {d:%b %d}",
                 f"You've finished {sum(rec['mentee_pre'])}/{len(rec['mentee_pre'])} prework items."),
                ("session", d - timedelta(days=1) <= t <= d, [s, mt],
                 f"Tomorrow: {cur['name']}", f"Your Tandem session is on {d:%A %b %d}."),
                ("confirm", d - timedelta(days=2) <= t < d, [p for p, r in ((s, "mentee"), (mt, "mentor"))
                                                            if r not in rec.get("confirm", {})],
                 f"Please confirm you'll attend {cur['name']}", "Tap Confirm in your Sessions tab."),
                ("feedback", t >= d + timedelta(days=1), [p for p, r in ((s, "mentee"), (mt, "mentor"))
                                                         if r not in rec["checkin"]],
                 f"How did {cur['name']} go?", "Share quick feedback: did it happen and how useful was it?"),
                ("postwork", t >= d + timedelta(days=3) and not all(rec["post"]), [s],
                 f"Postwork for {cur['name']}", "Finish your postwork to unlock the next session."),
            ]
            for kind, due, people, subj, body in rules:
                for p in (people if due else []):
                    key = f"{pk}|{i}|{kind}|{p['id']}"
                    if key not in sent:
                        send(p["email"], subj, f"Hi {p['name'].split()[0]}, {body}")
                        sent.add(key)
                        n += 1
    D["reminders_sent"] = sorted(sent)
    return n


# ---------------- Session progress helpers ----------------
def session_rec(pk, i):
    p = D["progress"].setdefault(pk, {})
    cur = D["curriculum"][i]
    return p.setdefault(str(i), {
        "mentee_pre": [False] * len(cur["prework"]),
        "mentor_pre": [False] * len(cur["mentor_prep"]),
        "post": [False] * len(cur["postwork"]),
        "confirm": {}, "checkin": {}})


def session_status(rec):
    c = rec["checkin"]
    a, b = c.get("mentee"), c.get("mentor")
    if not a and not b:
        return "Upcoming"
    if not a or not b:
        return "Waiting on " + ("mentor" if a else "mentee")
    if a["happened"] == b["happened"] == "Yes":
        return "Attended"
    if a["happened"] == b["happened"]:
        return "Missed" if a["happened"] == "No" else "Rescheduled"
    return "Flagged"


def current_session(pk):
    for i in range(len(D["curriculum"])):
        if session_status(session_rec(pk, i)) not in ("Attended",):
            return i
    return len(D["curriculum"]) - 1


def pair_stats(m):
    pk = pair_key(m)
    recs = [session_rec(pk, i) for i in range(len(D["curriculum"]))]
    statuses = [session_status(r) for r in recs]
    done = sum(s == "Attended" for s in statuses)
    due = sum(s != "Upcoming" for s in statuses)
    pre = [x for r in recs[:max(due, 1)] for x in r["mentee_pre"]]
    pre_pct = 100 * sum(pre) / len(pre) if pre else 0
    post = [x for r in recs[:max(done, 1)] for x in r["post"]]
    post_pct = 100 * sum(post) / len(post) if post else 0
    ratings = [r["checkin"][k]["rating"] for r in recs for k in ("mentee", "mentor") if k in r["checkin"]]
    rating = sum(ratings) / len(ratings) if ratings else None
    on_time = [r["checkin"][k]["on_time"] == "Yes" for r in recs for k in r["checkin"]]
    sents = [r["checkin"][k].get("sentiment", 0) for r in recs for k in r["checkin"]
             if r["checkin"][k].get("feedback")]
    sent = sum(sents) / len(sents) if sents else None
    safety = [f for r in recs for k in r["checkin"] for f in r["checkin"][k].get("safety", [])]
    # session score = 70% star rating + 30% sentiment of the written feedback
    # (no check-ins yet means no quality score, so a pair that hasn't met scores 0, not a default)
    # Written feedback only lowers the score when it is neutral or negative: none, or positive (VADER > 0.05), counts as full.
    sent_pts = 1.0 if sent is None or sent >= 0.05 else (sent + 1) / 1.05
    quality = (0.7 * ((rating or 4) / 5) + 0.3 * sent_pts) * 100 if ratings else 0
    engagement = round(0.5 * (100 * done / due if due else 0) + 0.3 * pre_pct + 0.2 * quality)
    risk = (any(s in ("Missed", "Flagged") for s in statuses) or bool(safety)
            or (due and pre_pct < 50) or (rating is not None and rating < 3)
            or (sent is not None and sent < -0.3))
    return {"attended": done, "due": due, "prework %": round(pre_pct), "postwork %": round(post_pct), "rating": rating,
            "on_time %": round(100 * sum(on_time) / len(on_time)) if on_time else None,
            "engagement": engagement, "at_risk": bool(risk), "statuses": statuses,
            "sentiment": sent, "safety": sorted(set(safety))}


# ---------------- UI helpers ----------------
# Display names for scoring factors (the internal keys stay the same in saved data)
FACTOR_LABELS = {"Help areas": "Goals"}


def score_bars(bd, w):
    caps = {"Help areas": sum(w["help"]), "Industry": w["industry"],
            "Background": w["field"], "Availability": w["availability"]}
    for k, v in bd.items():
        if k not in caps:       # factor from a newer/older saved match (e.g. "Interests"): nothing to scale it by
            continue
        st.progress(min(v / caps[k], 1.0) if caps[k] else 0,
                    text=f"{FACTOR_LABELS.get(k, k)}: {v:.0f}/{caps[k]:.0f}")


# Confidence badges: green / amber / red, using the shared chip colors from ui.py
CONF_TONE = {"High": "ok", "Medium": "amber", "Low": "warn"}
CONF_COLOR = {"High": "#2E9E78", "Medium": "#E0A800", "Low": "#D64534"}  # charts (theme-neutral)


GRID_CSS = """
.box { border: 1px solid rgba(128,128,128,.35); border-radius: 18px; overflow: hidden; background: rgba(255,255,255,.55); }
.row { display: grid; grid-template-columns: 120px repeat(7, 1fr); }
.row > div { border-top: 1px solid rgba(128,128,128,.22); border-left: 1px solid rgba(128,128,128,.22); }
.row > div:first-child { border-left: 0; }
.row.head > div { border-top: 0; }
.h { padding: 14px 8px; text-align: center; font-weight: 700; font-size: .95rem; background: rgba(128,128,128,.08); }
.t { padding: 14px 16px; display: flex; flex-direction: column; justify-content: center; font-weight: 600;
     background: rgba(128,128,128,.08); }
.t small { font-weight: 400; opacity: .65; font-size: .75rem; }
.c { height: 76px; cursor: pointer; display: flex; align-items: center; justify-content: center; user-select: none;
     transition: background .12s, transform .06s; font-size: 1.4rem; color: transparent; }
.c:hover { background: rgba(0,85,162,.12); }
.c.on { background: #0055A2; color: #fff; }
.c.on:hover { background: #0a64b8; }
.c:active { transform: scale(.97); }
.c:focus-visible { outline: 3px solid #0055A2; outline-offset: -3px; }
.hint { margin: 10px 4px 0; font-size: .85rem; opacity: .7; }
"""
GRID_JS = """
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement;
  if (root.querySelector('.box')) return;      // already mounted: the page keeps its own selection
  const sel = new Set(data.selected);
  const box = document.createElement('div'); box.className = 'box';
  const head = document.createElement('div'); head.className = 'row head';
  head.innerHTML = '<div class="h"></div>' + data.days.map(d => '<div class="h">' + d + '</div>').join('');
  box.append(head);
  const count = document.createElement('div'); count.className = 'hint';
  const update = () => { count.textContent = sel.size ? sel.size + ' time slot' + (sel.size > 1 ? 's' : '') + ' selected' : 'Click the times you are free.'; };
  data.times.forEach((t, ti) => {
    const row = document.createElement('div'); row.className = 'row';
    const lab = document.createElement('div'); lab.className = 't'; lab.innerHTML = t + '<small>' + data.ranges[ti] + '</small>'; row.append(lab);
    data.days.forEach(d => {
      const slot = d + ' ' + t;
      const c = document.createElement('div'); c.className = 'c' + (sel.has(slot) ? ' on' : ''); c.tabIndex = 0;
      c.setAttribute('role', 'checkbox'); c.setAttribute('aria-checked', sel.has(slot)); c.setAttribute('aria-label', slot);
      c.textContent = '\u2713';
      const toggle = () => { sel.has(slot) ? sel.delete(slot) : sel.add(slot); c.classList.toggle('on', sel.has(slot));
        c.setAttribute('aria-checked', sel.has(slot)); update(); setStateValue('sel', Array.from(sel)); };
      c.addEventListener('click', toggle);
      c.addEventListener('keydown', e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); } });
      row.append(c);
    });
    box.append(row);
  });
  update(); root.append(box, count);
}
"""
_availability_grid = st.components.v2.component("availability_grid", css=GRID_CSS, js=GRID_JS)
TIME_RANGES = {"Morning": "8am - 12pm", "Afternoon": "12pm - 5pm", "Evening": "5pm - 9pm"}


def availability_grid(prefix, selected=()):
    """One big box: days across, times down, each cell a large button. Free = blue. Returns e.g. ['Tue Evening']."""
    st.markdown("**When are you free?**" + REQ, help="Click every slot that works. Pacific time.")
    ss = f"{prefix}_av"
    if ss not in st.session_state:
        st.session_state[ss] = list(selected)
    res = _availability_grid(key=f"{prefix}_avgrid",
                             data={"days": DAYS, "times": TIMES, "ranges": [TIME_RANGES[x] for x in TIMES],
                                   "selected": st.session_state[ss]}, on_sel_change=lambda: None)
    if res.sel is not None:
        st.session_state[ss] = list(res.sel)
    return [f"{d} {tm}" for tm in TIMES for d in DAYS if f"{d} {tm}" in st.session_state[ss]]


def background(p):
    mn = p.get("minor", NO_MINOR)
    return p["field"] + (f" (minor {mn})" if mn != NO_MINOR else "")


def ranked_help_inputs(prefix, defaults=None):
    picks = []
    for i in range(3):
        picks.append(st.selectbox(f"Goal #{i+1}", HELP_AREAS, index=ix(HELP_AREAS, defaults[i] if defaults else None),
                                  key=f"{prefix}_h{i}"))
    return picks


STEPPER_CSS = """<style>
.tw-stepper{display:flex;align-items:flex-start;margin:4px 0 12px}
.tw-step{display:flex;flex-direction:column;align-items:center;width:92px;flex:0 0 auto}
.tw-dot{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:600;border:2px solid rgba(128,128,128,.45);color:rgba(128,128,128,.9);transition:all .2s}
.tw-step.done .tw-dot{background:var(--blue);border-color:var(--blue);color:#fff}
.tw-step.now .tw-dot{border-color:var(--blue);color:var(--blue);box-shadow:0 0 0 4px color-mix(in srgb, var(--blue) 22%, transparent)}
.tw-label{margin-top:6px;font-size:.8rem;text-align:center;opacity:.55}
.tw-step.done .tw-label,.tw-step.now .tw-label{opacity:1}
.tw-step.now .tw-label{font-weight:600}
.tw-line{flex:1;height:3px;margin:16px -29px 0;border-radius:2px;background:rgba(128,128,128,.3)}
.tw-line.done{background:var(--blue)}
</style>"""


def stepper(labels, current):
    """Numbered dots joined by lines; finished steps and the lines after them light up."""
    html = []
    for i, label in enumerate(labels):
        state = "done" if i < current else "now" if i == current else "todo"
        if i:
            html.append(f"<div class='tw-line {'done' if i <= current else ''}'></div>")
        html.append(f"<div class='tw-step {state}'><div class='tw-dot'>{'✓' if state == 'done' else i + 1}"
                    f"</div><div class='tw-label'>{label}</div></div>")
    st.markdown(STEPPER_CSS + "<div class='tw-stepper'>" + "".join(html) + "</div>", unsafe_allow_html=True)


def save_photo(email, f):
    if f is not None:
        con = db()
        con.execute("INSERT OR REPLACE INTO photos VALUES (?, ?)", (email, f.getvalue()))
        con.commit()


def show_photo(email, width=90):
    row = db().execute("SELECT data FROM photos WHERE email=?", (email,)).fetchone()
    if row:
        st.image(row[0], width=width)
    else:
        st.markdown(f"<div style='width:{width}px;height:{width}px;border-radius:50%;background:var(--hover)'></div>",
                    unsafe_allow_html=True)


TALKING_POINTS = {
    "Resume Review": "Go through their resume together and agree on 2 concrete edits.",
    "LinkedIn/Branding": "Look at their LinkedIn headline and About section; share what recruiters notice.",
    "Behavioral Interviews": "Run one STAR-format practice question and give feedback.",
    "Technical Interviews": "Walk through a typical technical question from your field and how you'd approach it.",
    "Networking": "Share how you'd reach out to someone at your company; offer one introduction if you can.",
    "Internship Search": "Talk about when and where internships in your field open, and how to stand out.",
    "Job Search Strategy": "Help them build a target list of 10 companies and a weekly plan.",
    "Career Exploration": "Describe a day in your role and 2 adjacent roles they could explore.",
    "Grad School Advice": "Discuss whether a master's/PhD helps in your field and how to decide.",
    "Industry Insights": "Share 2 trends in your industry and the skills they reward.",
}


def talking_points(student, i):
    """Platform guidance for mentors: session topic + the mentee's own ranked goals."""
    cur = D["curriculum"][i]
    pts = [f"Session focus: {cur['name']}. Check their prework: {', '.join(cur['prework']).lower()}."]
    pts += [f"#{k+1} goal, {h}: {TALKING_POINTS.get(h, 'Ask what they want to learn about ' + h + '.')}"
            for k, h in enumerate(student["help_ranked"])]
    pts.append("Close by agreeing on one action item before the next session.")
    return pts


def idx(options, value, default=0):
    return options.index(value) if value in options else default


def ix(options, value):
    """Selectbox index for the form questions: nothing is preselected until the person (or their saved answer) picks."""
    return options.index(value) if value in options else None


# ---------------- Login + account creation ----------------
AUTH_CSS = """<style>
[data-testid=stMainBlockContainer]{padding-top:3.5rem;padding-bottom:1rem;min-height:100vh;box-sizing:border-box;
  display:flex;flex-direction:column;justify-content:center}
[data-testid=stMainBlockContainer] > div{flex:0 0 auto !important;height:auto !important}
.st-key-auth_card{max-width:420px;width:100%;margin:0 auto;padding:1.5rem 1.75rem 1rem}
.st-key-auth_card h2{text-align:center;padding-bottom:0}
.st-key-auth_card [data-testid=stCaptionContainer]{text-align:center}
.st-key-auth_switch{align-items:center;justify-content:center;gap:.35rem}
.st-key-auth_switch > div{width:auto !important;flex:0 0 auto}
.st-key-auth_switch p{margin:0 !important;font-size:14px}
.st-key-auth_switch [data-testid=stCaptionContainer]{margin-bottom:0}
.st-key-auth_switch button{color:var(--blue);padding:0;min-height:0;font-size:14px}
.st-key-auth_switch button:hover{text-decoration:underline}
</style>"""


def login():
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    view = st.session_state.get("auth_view", "login")
    cyc = D["cycle"]
    with st.container(border=True, key="auth_card"):
        st.markdown("## Tandem")
        st.caption("SJSU Career Mentorship, matched with purpose")
        if view == "login":
            login_card()
        else:
            signup_card(cyc)
    st.caption(f"<div style='text-align:center'>{cyc['name']} applications are "
               f"{'closed' if apps_closed() else 'open'}"
               + ("" if apps_closed() else f" · apply by {date.fromisoformat(cyc['apps_deadline']):%B %d, %Y}")
               + "</div>", unsafe_allow_html=True)


def switch_auth(view, prompt, label):
    """Small 'Don't have an account? Create one' link under the card's main button."""
    with st.container(key="auth_switch", horizontal=True, horizontal_alignment="center", gap="small"):
        st.caption(prompt)
        if st.button(label, type="tertiary", key=f"to_{view}"):
            st.session_state["auth_view"] = view
            st.rerun()


def login_card():
    with st.form("login", border=False):
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary", use_container_width=True):
            u = check_login(email, pw)
            if u:
                st.session_state.user = u
                st.rerun()
            st.error("Wrong email or password.")
    switch_auth("signup", "Don't have an account?", "Create one")
    with st.expander("Demo accounts (for judges)"):
        st.markdown(f"- Admin: `admin@sjsu.edu` / `admin1234`\n- Staff: `staff@sjsu.edu` / `staff1234`\n"
                    f"- Any seeded student or mentor email / `{DEMO_PASSWORD}` "
                    f"(e.g. `student1@sjsu.edu`, `mentor1@example.com`)")
        role = st.radio("Quick log in as", ["Admin", "Staff", "Mentee", "Mentor"], horizontal=True)
        if role in ("Admin", "Staff"):
            acct = {"Admin": "admin@sjsu.edu", "Staff": "staff@sjsu.edu"}[role]
        else:
            rows = D["students"] if role == "Mentee" else D["mentors"]
            pick = st.selectbox("Account", rows, format_func=lambda r: f"{r['name']} ({r['email']})")
            acct = pick["email"]
        if st.button("Quick log in"):
            st.session_state.user = check_login(acct, {"Admin": "admin1234", "Staff": "staff1234"}
                                                .get(role, DEMO_PASSWORD))
            st.rerun()


def signup_card(cyc):
    if apps_closed():
        st.warning("Applications are closed for this cycle. Check back next semester.")
        switch_auth("login", "Already have an account?", "Log in")
        return
    role = st.radio("I want to join as", ["Student (mentee)", "Industry mentor"], horizontal=True)  # outside the form so the email label updates live
    with st.form("signup", border=False):
        name = st.text_input("Full name")
        email = st.text_input("Email (your @sjsu.edu email)" if role.startswith("Student") else "Email")
        c1, c2 = st.columns(2)
        pw = c1.text_input("Password (8+ chars)", type="password")
        pw2 = c2.text_input("Confirm password", type="password")
        if st.form_submit_button("Create account", type="primary", use_container_width=True):
            is_student = role.startswith("Student")
            exists = db().execute("SELECT 1 FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
            if not (name and email and pw):
                st.error("Please fill every field.")
            elif is_student and not email.lower().strip().endswith("@sjsu.edu"):
                st.error("Students must use their @sjsu.edu email.")
            elif len(pw) < 8 or pw != pw2:
                st.error("Passwords must match and be at least 8 characters.")
            elif exists:
                st.error("An account with this email already exists. Log in instead.")
            else:
                r = "Mentee" if is_student else "Mentor"
                create_user(db(), email, name, r, pw)
                st.session_state.user = check_login(email, pw)
                st.session_state["toast"] = "Account created! Now fill in your application."
                st.session_state.pop("auth_view", None)
                st.rerun()
    switch_auth("login", "Already have an account?", "Log in")


def link_profile(user, pid):
    con = db()
    con.execute("UPDATE users SET profile_id=? WHERE email=?", (pid, user["email"]))
    con.commit()
    user["id"] = pid


# ---------------- Application / profile forms (create + edit) ----------------
# ---- Mentee application: four sections, used by the step-by-step wizard and the profile page ----
STUDENT_STEPS = ["Academics", "Career goals", "Availability", "About you"]
AGREEMENT = ("I agree to the Tandem mentee agreement: attend all 6 sessions, "
             "complete prework, and communicate respectfully.")


REQ = " :red[*]"   # red asterisk after the label of every required question


def majors_for(college):
    """Majors offered by this college, plus any admin-added major that has no college (those show everywhere).
    `college` may be a named SJSU college or its generic name."""
    sjsu = next((c for c, g in GENERIC_COLLEGE.items() if g == college), college)
    return [f for f in FIELDS if MAJOR_COLLEGE.get(f) in (None, sjsu)] or FIELDS


def college_and_major(e, k, major_label="Major", generic=False, ready=True):
    """College first; the Major list below it only holds that college's majors. Picking a different college
    clears the major (each college gets its own Major widget, which starts empty).
    generic=True shows plain college names ("Engineering") for schools other than SJSU.
    ready=False greys both out until the question above them (the mentor's school) is answered."""
    colleges = GENERIC_COLLEGES if generic else COLLEGES
    kind = "gcollege" if generic else "college"
    saved = e.get("college")
    saved = GENERIC_COLLEGE.get(saved, saved) if generic else saved
    col = st.selectbox("College" + REQ, colleges, index=ix(colleges, saved), key=f"{k}_{kind}", disabled=not ready,
                       placeholder="Choose your school first" if not ready else "Choose an option")
    opts = majors_for(col) if col else []
    field = st.selectbox(major_label + REQ, opts, index=ix(opts, e.get("field")), disabled=not col,
                         placeholder="Choose your major" if col else "Choose your college first",
                         key=f"{k}_field_{kind}_{colleges.index(col) if col else 'none'}")
    return col, field


def student_academics(e, k):
    col, field = college_and_major(e, k)
    return {"college": col, "field": field,
            "minor": st.selectbox("Minor", MINORS, index=ix(MINORS, e.get("minor")), key=f"{k}_minor") or NO_MINOR,
            "year": st.selectbox("Year" + REQ, YEARS, index=ix(YEARS, e.get("year")), key=f"{k}_year")}


def student_career(e, k):
    data = {"industry": st.selectbox("Industry you're most interested in" + REQ, INDUSTRIES,
                                     index=ix(INDUSTRIES, e.get("industry")), key=f"{k}_industry")}
    st.markdown("**What are your top 3 goals?**" + REQ + "  \n#1 is the most important.")
    data["help_ranked"] = ranked_help_inputs(k, e.get("help_ranked"))
    return data


def student_availability(e, k):
    return {"availability": availability_grid(k, e.get("availability", ())),
            "mode": st.selectbox("Meeting preference" + REQ, MODES, index=ix(MODES, e.get("mode")), key=f"{k}_mode")}


def student_about(e, k):
    about = st.text_area("About me", e.get("about", ""), max_chars=400, key=f"{k}_about", height=90,
                         help="Shown only to your matched mentor. Not used for matching.",
                         placeholder="What you're hoping to get from the program, projects you're proud of...")
    photo = st.file_uploader("Profile picture", type=["png", "jpg", "jpeg"], key=f"{k}_photo")
    agree = st.checkbox(AGREEMENT + REQ, value=e.get("agree", False), key=f"{k}_agree")
    return {"about": about, "photo": photo, "agree": agree}


STUDENT_SECTIONS = [student_academics, student_career, student_availability, student_about]


def student_problem(data, step):
    """Validation message for one section, or None if it's fine."""
    if step == 0:
        for key, msg in (("college", "your college"), ("field", "your major"), ("year", "your year")):
            if not data[key]:
                return f"Please choose {msg}."
    if step == 1 and not data["industry"]:
        return "Please choose the industry you're most interested in."
    if step == 1 and (None in data["help_ranked"] or len(set(data["help_ranked"])) < 3):
        return "Pick 3 different goals for #1, #2 and #3."
    if step == 2 and not data["availability"]:
        return "Please tick at least one time slot."
    if step == 2 and not data["mode"]:
        return "Please choose a meeting preference."
    if step == 3 and not data["agree"]:
        return "Please accept the mentee agreement."
    return None


def save_student(user, e, data):
    save_photo(user["email"], data.pop("photo", None))
    data.pop("agree", None)
    if e:
        e.update(data, updated=NOW())
        commit("Profile updated")
    sid = f"S{len(D['students'])+1:03d}"
    D["students"].append({"id": sid, "name": user["name"], "email": user["email"], **data,
                          "status": "Approved", "agreement": NOW()})
    link_profile(user, sid)
    send(user["email"], "Tandem application received",
         "You're all set! We'll email you as soon as you have a match.", kind="Confirmation")
    commit("Application submitted!")


def student_form(user, existing=None):
    if existing:
        profile_form(user, existing, "student", STUDENT_STEPS, STUDENT_SECTIONS, student_problem, save_student)
    else:
        wizard(user, "sw", STUDENT_STEPS, STUDENT_SECTIONS, student_problem, save_student)


# ---- Mentor application: five sections, same wizard and profile page as mentees ----
MENTOR_STEPS = ["Work", "Background", "Mentoring", "Availability", "About you"]
MENTOR_AGREEMENT = "I agree to the Tandem mentor agreement: 6 sessions over 12 weeks and SJSU's code of conduct."


def mentor_work(e, k):
    return {"company": st.text_input("Company" + REQ, e.get("company", ""), key=f"{k}_company"),
            "role": st.text_input("Job title" + REQ, e.get("role", ""), key=f"{k}_role"),
            "experience": st.selectbox("Years of work experience" + REQ, EXPERIENCE,
                                       index=ix(EXPERIENCE, e.get("experience")), key=f"{k}_exp"),
            "industry": st.selectbox("Industry you work in" + REQ, INDUSTRIES,
                                     index=ix(INDUSTRIES, e.get("industry")), key=f"{k}_industry")}


SJSU_LINK_LABEL = {SJSU_LINKS[0]: "No connection to SJSU",
                   SJSU_LINKS[1]: "I also earned a degree at SJSU",
                   SJSU_LINKS[2]: "SJSU alum, and I'm still involved (clubs, events, hiring)",
                   SJSU_LINKS[3]: "I teach at SJSU (adjunct or lecturer)"}


def mentor_background(e, k):
    school = st.selectbox("Most recent school you graduated from" + REQ, SCHOOLS,
                          index=ix(SCHOOLS, e.get("school")), key=f"{k}_school",
                          help="If you earned more than one degree, choose the most recent one.")
    is_sjsu = school == "San Jose State University"
    col, field = college_and_major(e, k, "Degree major", generic=bool(school) and not is_sjsu, ready=bool(school))
    data = {"school": school, "college": col, "field": field,
            "minor": st.selectbox("Degree minor", MINORS, index=ix(MINORS, e.get("minor")), key=f"{k}_minor") or NO_MINOR}
    if not school:
        data["sjsu_link"] = None
    elif is_sjsu:   # an SJSU graduate is an alum already, so there is nothing to ask (keep a higher tier if they had one)
        data["sjsu_link"] = e["sjsu_link"] if e.get("sjsu_link") in SJSU_LINKS[1:] else SJSU_LINKS[1]
    else:
        data["sjsu_link"] = st.selectbox("Do you have another connection to SJSU?" + REQ, SJSU_LINKS,
                                         index=ix(SJSU_LINKS, e.get("sjsu_link")), key=f"{k}_sjsu",
                                         format_func=SJSU_LINK_LABEL.get,
                                         help="For example, an earlier degree from SJSU, or teaching or volunteering there.")
    return data


def mentor_mentoring(e, k):
    return {"can_help": st.multiselect("Student goals you can help with" + REQ, HELP_AREAS, default=e.get("can_help", []),
                                       key=f"{k}_help"),
            "pref_years": st.multiselect("Which students can you advise best?", YEARS,
                                         default=e.get("pref_years", []), key=f"{k}_years",
                                         help="Leave empty to take students from any year."),
            "capacity": st.selectbox("Max mentees you can take" + REQ, [1, 2, 3],
                                     index=ix([1, 2, 3], e.get("capacity")), key=f"{k}_cap")}


def mentor_about(e, k):
    about = st.text_area("Short bio", e.get("about", ""), max_chars=400, key=f"{k}_about", height=90,
                         help="Shown only to your matched mentees. Not used for matching.")
    linkedin = st.text_input("LinkedIn URL", e.get("linkedin", ""), key=f"{k}_linkedin")
    photo = st.file_uploader("Profile picture", type=["png", "jpg", "jpeg"], key=f"{k}_photo")
    agree = st.checkbox(MENTOR_AGREEMENT + REQ, value=e.get("agree", False), key=f"{k}_agree")
    return {"about": about, "linkedin": linkedin, "photo": photo, "agree": agree}


# Availability (grid + meeting preference) is the same question for both roles
MENTOR_SECTIONS = [mentor_work, mentor_background, mentor_mentoring, student_availability, mentor_about]


def mentor_problem(data, step):
    if step == 0:
        if not data["company"].strip():
            return "Please enter your company."
        if not data["role"].strip():
            return "Please enter your job title."
        if not data["experience"]:
            return "Please choose your years of work experience."
        if not data["industry"]:
            return "Please choose the industry you work in."
    if step == 1:
        for key, msg in (("school", "your most recent school"), ("college", "your college"),
                         ("field", "your degree major")):
            if not data[key]:
                return f"Please choose {msg}."
        if not data["sjsu_link"]:
            return "Please tell us if you have another connection to SJSU."
    if step == 2:
        if not data["capacity"]:
            return "Please choose how many mentees you can take."
        if not data["can_help"]:
            return "Pick at least one goal you can help with."
    if step == 3:
        if not data["availability"]:
            return "Please tick at least one time slot."
        if not data["mode"]:
            return "Please choose a meeting preference."
    if step == 4 and not data["agree"]:
        return "Please accept the mentor agreement."
    return None


def save_mentor(user, e, data):
    save_photo(user["email"], data.pop("photo", None))
    data.pop("agree", None)
    if e:
        e.update(data, updated=NOW())
        commit("Profile updated")
    mid = f"M{len(D['mentors'])+1:03d}"
    D["mentors"].append({"id": mid, "name": user["name"], "email": user["email"], **data,
                         "status": "Approved", "agreement": NOW()})
    link_profile(user, mid)
    send(user["email"], "Tandem mentor application received",
         "You're all set! We'll email you as soon as you're matched with a mentee.", kind="Confirmation")
    commit("Application submitted!")


def mentor_form(user, existing=None):
    if existing:
        profile_form(user, existing, "mentor", MENTOR_STEPS, MENTOR_SECTIONS, mentor_problem, save_mentor)
    else:
        wizard(user, "mw", MENTOR_STEPS, MENTOR_SECTIONS, mentor_problem, save_mentor)


# ---- Shared by both roles ----
def profile_form(user, e, kind, steps, sections, problem_for, save):
    """Profile page: same questions as the wizard, one per line, grouped under headings.
    No st.form here, so changing College updates the Major list right away."""
    st.markdown(WIZARD_CSS, unsafe_allow_html=True)
    with st.container(key="wizard"):
        st.caption("Fields marked :red[*] are required.")
        data = {}
        for step, (title, section) in enumerate(zip(steps, sections)):
            st.markdown(f"#### {title}")
            data.update(section({**e, "agree": True}, f"{kind}_p"))
            if step < len(steps) - 1:
                st.divider()
        if st.button("Save changes", type="primary", key=f"{kind}_save"):
            problem = next((p for p in (problem_for(data, s) for s in range(len(steps))) if p), None)
            if problem:
                st.error(problem)
                return
            save(user, e, data)


# Roomy spacing, sleek dropdowns, and a Back / Next bar fixed to the bottom of the screen on every step
WIZARD_CSS = """<style>
[data-testid=stMainBlockContainer]{padding-top:2.5rem;padding-bottom:8rem}
.st-key-wizard{gap:1.7rem}
.st-key-wizard [data-testid=stVerticalBlock]{gap:1.7rem}
.st-key-wizard [data-testid=stWidgetLabel]{min-height:0;margin-bottom:.45rem}
.st-key-wizard [data-testid=stWidgetLabel] p{font-weight:600;font-size:.95rem;letter-spacing:-.005em}
.st-key-wizard [data-testid=stMarkdownContainer] p{margin-bottom:.25rem}
.st-key-wizard [data-testid=stFileUploaderDropzone]{padding:1rem 1.1rem;border-radius:14px}
.st-key-wizard textarea{border-radius:14px !important;padding:.85rem 1rem !important}
/* sleek dropdowns */
.st-key-wizard [data-baseweb=select] > div{min-height:50px;border-radius:14px;border:1px solid rgba(128,128,128,.3);
  background:var(--panel,#fff);box-shadow:0 1px 2px rgba(16,24,40,.05);padding-left:.4rem;
  transition:border-color .15s, box-shadow .15s}
.st-key-wizard [data-baseweb=select] > div:hover{border-color:var(--blue,#0055A2)}
.st-key-wizard [data-baseweb=select] > div:focus-within{border-color:var(--blue,#0055A2);
  box-shadow:0 0 0 4px rgba(0,85,162,.14)}
.st-key-wizard [data-baseweb=select] svg{opacity:.55}
[data-baseweb=popover] ul[role=listbox]{border-radius:14px;padding:6px;box-shadow:0 12px 32px rgba(16,24,40,.16)}
[data-baseweb=popover] li[role=option]{border-radius:10px;margin:2px 0;padding:.55rem .75rem}
[data-baseweb=popover] li[role=option][aria-selected=true]{background:rgba(0,85,162,.1);color:var(--blue,#0055A2);font-weight:600}
/* Back / Next bar: same spot on every step */
.stApp{--sbw:0px}
.stApp:has([data-testid=stSidebar][data-collapsed=false]){--sbw:300px}
.st-key-wiznav{position:fixed !important;left:var(--sbw);right:0;bottom:0;z-index:1000;width:auto !important;
  padding:.9rem max(2rem, calc((100vw - var(--sbw) - 1200px) / 2 + 3rem));
  background:color-mix(in srgb, var(--canvas,#F6F7F9) 88%, transparent);backdrop-filter:blur(10px);
  border-top:1px solid rgba(128,128,128,.22);box-shadow:0 -6px 20px rgba(16,24,40,.06)}
.st-key-wiznav [data-testid=stHorizontalBlock]{align-items:center}
.st-key-wiznav [data-testid=stColumn]:last-child{display:flex;justify-content:flex-end}
.st-key-wiznav button{min-width:150px;min-height:46px;border-radius:12px;font-weight:600}
.st-key-wiznav button[kind=primary]{box-shadow:0 4px 14px rgba(0,85,162,.3)}
</style>"""


def wizard(user, k, steps, sections, problem_for, save):
    """New application step by step, with a progress stepper and Back / Next buttons."""
    key = f"wizard_{user['email']}"
    w = st.session_state.setdefault(key, {"step": 0, "data": {}})
    step, saved = w["step"], w["data"]
    if w.pop("scroll_top", False):  # after Back / Next, jump up so the stepper is in view
        with st.container(key="scroll_top"):
            st.html("<style>.st-key-scroll_top{display:none}</style>")
            st.iframe(f"<script>/* step {step} */ window.parent.document.querySelectorAll("
                      "'[data-testid=stMain], [data-testid=stAppViewContainer], section.main')"
                      ".forEach(el => el.scrollTo(0, 0));</script>", height=1)
    stepper(steps, step)
    st.markdown(WIZARD_CSS, unsafe_allow_html=True)
    with st.container(key="wizard"):
        st.caption("Fields marked :red[*] are required.")
        data = sections[step](saved, k)
        problem_box = st.empty()
    last = step == len(steps) - 1
    with st.container(key="wiznav"):                       # fixed to the bottom: Back left, Next / Submit right
        back_col, _, next_col = st.columns([1, 3, 1])
        went_back = bool(step) and back_col.button("\u2190 Back", key=f"{k}_back")
        went_next = next_col.button("Submit application" if last else "Next \u2192", type="primary", key=f"{k}_next")
    if went_back:
        saved.update({f: v for f, v in data.items() if f != "photo"})
        w["step"] -= 1
        w["scroll_top"] = True
        st.rerun()
    if went_next:
        problem = problem_for(data, step)
        if problem:
            problem_box.error(problem)
            return
        saved.update(data)
        if not last:
            w["step"] += 1
            w["scroll_top"] = True
            st.rerun()
        del st.session_state[key]
        save(user, None, dict(saved))


def profile_tab(user, rec, kind):
    if not apps_closed():
        st.caption(f"You can edit your profile any time until applications close on "
                   f"{date.fromisoformat(D['cycle']['apps_deadline']):%B %d}.")
        (student_form if kind == "Mentee" else mentor_form)(user, rec)
    else:
        st.info("Applications are closed, so your profile is locked for matching. "
                "Contact the Career Center if something needs to change.")
        show = {k: v for k, v in rec.items() if k not in ("id", "status", "agreement", "photo")}
        st.markdown("\n".join(f"- **{ {'field': 'major'}.get(k, k).replace('_', ' ').capitalize()}:** "
                               f"{', '.join(map(str, v)) if isinstance(v, (list, tuple)) else v}"
                               for k, v in show.items() if v not in ("", None, [])))


def inbox(user):
    mine = [e for e in D["emails"] if e["to"] == user["email"]][-5:][::-1]
    if mine:
        with st.expander(f"Notifications ({len(mine)})"):
            for e in mine:
                st.markdown(f"**{e['subject']}** · {e['at']}  \n{e['body']}")


# ---------------- Messaging ----------------
def messages_panel(m, role, me):
    pk = pair_key(m)
    con = db()
    rows = con.execute("SELECT sender_role, sender_name, body, at FROM messages WHERE pair=? ORDER BY id",
                       (pk,)).fetchall()
    box = st.container(height=320, border=True)
    with box:
        if not rows:
            st.caption("No messages yet. Say hi and agree on a time for your first session!")
        for r, name, body, at in rows:
            with st.chat_message("user" if r == role else "assistant",
                                 avatar=":material/school:" if r == "mentee" else ":material/work:"):
                st.markdown(f"**{name}** · {at}  \n{body}")
    with st.form(f"msg_{pk}_{role}", clear_on_submit=True):
        body = st.text_input("Message", placeholder="Type a message...")
        if st.form_submit_button("Send") and body.strip():
            con.execute("INSERT INTO messages(pair, sender_role, sender_name, body, at) VALUES (?,?,?,?,?)",
                        (pk, role, me, body.strip(), NOW()))
            con.commit()
            st.rerun()
    st.caption("Messages are private to you and your match.")


# ---------------- Submissions (prework/postwork) ----------------
def submissions_panel(m, i, role):
    pk = pair_key(m)
    con = db()
    rows = con.execute("SELECT id, kind, text, filename, at FROM submissions WHERE pair=? AND session=? "
                       "ORDER BY id", (pk, i)).fetchall()
    for sid, kind, text, fname, at in rows:
        with st.container(border=True):
            st.markdown(f"**{kind}** · {at}" + (f"  \n{text}" if text else ""))
            if fname:
                data = con.execute("SELECT data FROM submissions WHERE id=?", (sid,)).fetchone()[0]
                st.download_button(fname, data, fname, key=f"dl_{sid}_{role}")
    if can("submit_prework_postwork"):
        with st.form(f"sub_{pk}_{i}", clear_on_submit=True):
            kind = st.selectbox("Submission for", ["Prework", "Postwork"])
            text = st.text_area("Notes or a link (Google Doc, LinkedIn, etc.)", max_chars=1000)
            f = st.file_uploader(f"Attach a file (PDF, DOCX, PNG, JPG, TXT, up to {MAX_UPLOAD_MB} MB)",
                                 type=["pdf", "docx", "png", "jpg", "jpeg", "txt"])
            if st.form_submit_button("Submit"):
                if f and f.size > MAX_UPLOAD_MB * 1024 * 1024:
                    st.error(f"File is larger than {MAX_UPLOAD_MB} MB.")
                elif not (text.strip() or f):
                    st.error("Add a note, link, or file.")
                else:
                    con.execute("INSERT INTO submissions(pair, session, kind, text, filename, data, at) "
                                "VALUES (?,?,?,?,?,?,?)",
                                (pk, i, kind, text.strip(), f.name if f else None,
                                 f.getvalue() if f else None, NOW()))
                    con.commit()
                    st.session_state["toast"] = "Submitted! Your mentor can see it now."
                    st.rerun()
    elif not rows:
        st.caption("Your mentee hasn't submitted anything for this session yet.")


# ---------------- Session card (shared by mentee and mentor) ----------------
def session_panel(m, role):
    pk = pair_key(m)
    stats = pair_stats(m)
    st.progress(stats["attended"] / len(D["curriculum"]),
                text=f"Sessions completed: {stats['attended']} of {len(D['curriculum'])}")

    names = [f"{'Done' if s == 'Attended' else 'Needs follow-up' if s in ('Flagged', 'Missed') else 'Upcoming'}: {c['name']} "
             f"({pair_session_date(pk, k):%b %d})"
             for k, (c, s) in enumerate(zip(D["curriculum"], stats["statuses"]))]
    i = st.selectbox("Session", range(len(names)), index=current_session(pk), format_func=lambda k: names[k],
                     key=f"{role}_sess_{pk}")
    cur, rec = D["curriculum"][i], session_rec(pk, i)
    status = session_status(rec)
    st.caption(f"Week {cur['week']} · {pair_session_date(pk, i):%A %B %d} · Status: **{status}**")
    schedule_box(m, i, role)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Prework**")
        if role == "mentee":
            changed = False
            for j, item in enumerate(cur["prework"]):
                v = st.checkbox(item, rec["mentee_pre"][j], key=f"pre_{pk}_{i}_{j}")
                if v != rec["mentee_pre"][j]:
                    rec["mentee_pre"][j], changed = v, True
            if changed:
                if all(rec["mentee_pre"]):
                    mt_, s_ = M_BY[m["mentor_id"]], S_BY[m["student_id"]]
                    send(mt_["email"], f"{s_['name'].split()[0]} finished prework",
                         f"{s_['name']} completed all prework for {cur['name']}. You're ready to meet!",
                         kind="Prework done")
                commit()
            if all(rec["mentee_pre"]):
                st.success("You're ready to meet your mentor!")
            else:
                st.info(f"{sum(rec['mentee_pre'])}/{len(rec['mentee_pre'])} done. "
                        "Finish your prework before the session.")
        else:
            mentee = S_BY[m["student_id"]]["name"].split()[0]
            n, tot = sum(rec["mentee_pre"]), len(rec["mentee_pre"])
            if n == tot:
                st.success(f"{mentee} has finished prework ({n}/{tot})")
            else:
                st.warning(f"{mentee} has completed {n}/{tot} prework items")
            with st.expander(f"Talking points for {S_BY[m['student_id']]['name'].split()[0]}"):
                for t in talking_points(S_BY[m["student_id"]], i):
                    st.markdown(f"- {t}")
            st.markdown("**Your prep**")
            changed = False
            for j, item in enumerate(cur["mentor_prep"]):
                v = st.checkbox(item, rec["mentor_pre"][j], key=f"mp_{pk}_{i}_{j}")
                if v != rec["mentor_pre"][j]:
                    rec["mentor_pre"][j], changed = v, True
            if changed:
                commit()
        st.markdown("**Postwork**")
        changed = False
        for j, item in enumerate(cur["postwork"]):
            v = st.checkbox(item, rec["post"][j], key=f"post_{pk}_{i}_{j}_{role}",
                            disabled=role != "mentee")
            if v != rec["post"][j]:
                rec["post"][j], changed = v, True
        if changed:
            commit()

    with c2:
        partner = "mentor" if role == "mentee" else "mentee"
        st.markdown("**Before the session: confirm**")
        conf = rec["confirm"].get(role)
        if conf:
            st.success(f"You confirmed: {conf['answer']} ({conf['at']})")
        else:
            with st.form(f"cf_{pk}_{i}_{role}"):
                ans = st.radio("Will you attend?", ["Yes, I'll be there", "I need to reschedule"])
                note = st.text_input("Note for your match")
                if st.form_submit_button("Confirm"):
                    rec["confirm"][role] = {"answer": ans, "note": note, "at": NOW()}
                    commit("Thanks for confirming!")
        other = rec["confirm"].get(partner)
        st.caption(f"Your {partner}: " + (f"{other['answer']}" + (f' · "{other["note"]}"' if other.get("note") else "")
                                         if other else "hasn't confirmed yet"))

        st.markdown("**After the session: feedback**")
        mine = rec["checkin"].get(role)
        if mine:
            st.success(f"Thanks! You said the session {mine['happened'].lower()}, rated it {mine['rating']}/5.")
            if status == "Flagged":
                st.warning("Your answer differs from your partner's. Career Center staff will follow up.")
        else:
            with st.form(f"ci_{pk}_{i}_{role}"):
                happened = st.radio("Did the session happen?", ["Yes", "No", "Rescheduled"], horizontal=True)
                on_time = st.radio("Did it start on time?", ["Yes", "No"], horizontal=True)
                rating = st.slider("How useful was it?", 1, 5, 4)
                cont = st.radio("Want to continue with this match?", ["Yes", "No"], horizontal=True)
                goals = S_BY[m["student_id"]]["help_ranked"]
                covered = st.multiselect(f"Which of {S_BY[m['student_id']]['name'].split()[0]}'s goals did you "
                                         "help with?" if role == "mentor" else "Which of your goals did you work on?",
                                         goals)
                fb = st.text_area("What went well or could be better?", max_chars=500)
                if st.form_submit_button("Submit feedback", type="primary"):
                    rec["checkin"][role] = {"happened": happened, "on_time": on_time, "rating": rating,
                                            "continue": cont, "feedback": fb, "at": NOW(), "covered": covered,
                                            "sentiment": sentiment(fb), "safety": safety_flags(fb)}
                    commit("Feedback saved. Thank you!")

    st.markdown("**Submissions**")
    submissions_panel(m, i, role)


def schedule_box(m, i, role):
    """Book the session on a day + time slot that both people marked as free."""
    pk, rec = pair_key(m), session_rec(pair_key(m), i)
    s, mt = S_BY[m["student_id"]], M_BY[m["mentor_id"]]
    sch = rec.get("schedule")
    if sch:
        st.success(f"Booked: {date.fromisoformat(sch['date']):%A %b %d}, {sch['slot']} "
                   f"({TIME_RANGES[sch['slot']]} PT) · set by {sch['by']}")
    if not can("schedule_sessions"):
        return
    shared = [a for a in mt["availability"] if a in s["availability"]]
    options = [(d, a.split()[1]) for d in week_dates(i) for a in shared if a.split()[0] == f"{d:%a}"]
    with st.expander("Change booking" if sch else "Book this session"):
        if not options:
            st.warning("No shared time slots this week. Message your match to agree on a time.")
            return
        pick = st.selectbox("Pick a time you're both free", options, key=f"bk_{pk}_{i}_{role}",
                            format_func=lambda o: f"{o[0]:%a %b %d} · {o[1]} ({TIME_RANGES[o[1]]})")
        if st.button("Book", key=f"bkb_{pk}_{i}_{role}"):
            other = mentor_booked(mt["id"], pick[0], pick[1], pk)
            if other:
                st.error(f"The mentor already has a session with {other} then. Pick another time.")
            else:
                rec["schedule"] = {"date": pick[0].isoformat(), "slot": pick[1], "by": role, "at": NOW()}
                for p in (s, mt):
                    send(p["email"], f"Booked: {D['curriculum'][i]['name']}",
                         f"Your session is on {pick[0]:%A %b %d}, {pick[1]} ({TIME_RANGES[pick[1]]} PT).",
                         kind="Booking")
                commit("Session booked. Both of you got a confirmation.")


def person_scores(person_id, role):
    """Scorecard for one mentor or mentee across all their pairs (staff-only)."""
    partner = "mentor" if role == "mentee" else "mentee"
    key = "student_id" if role == "mentee" else "mentor_id"
    due = att = ontime = conf = fb = 0
    prep, ratings, sents, flags = [], [], [], []
    for m in active_matches():
        if m[key] != person_id:
            continue
        pk = pair_key(m)
        for i in range(len(D["curriculum"])):
            rec = session_rec(pk, i)
            if session_status(rec) == "Upcoming":
                continue
            due += 1
            mine, theirs = rec["checkin"].get(role), rec["checkin"].get(partner)
            conf += role in rec.get("confirm", {})
            fb += mine is not None
            if mine:
                att += mine["happened"] == "Yes"
                ontime += mine["on_time"] == "Yes"
            items = rec["mentee_pre"] if role == "mentee" else rec["mentor_pre"]
            if items:
                prep.append(sum(items) / len(items))
            if theirs:                                    # how the partner rated sessions with them
                ratings.append(theirs["rating"])
                if theirs.get("feedback"):
                    sents.append(theirs.get("sentiment", 0))
                flags += theirs.get("safety", [])
    if not due:
        return None
    r = sum(ratings) / len(ratings) if ratings else None
    snt = sum(sents) / len(sents) if sents else None
    received = ((0.8 * (r / 5) + 0.2 * ((snt if snt is not None else 0.5) + 1) / 2) if r else 0.7)
    score = round(100 * (0.30 * att / due + 0.20 * (sum(prep) / len(prep) if prep else 0)
                         + 0.15 * (conf + fb) / (2 * due) + 0.35 * received))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"
    return {"Sessions": due, "Attended %": round(100 * att / due), "On time %": round(100 * ontime / max(att, 1)),
            "Prepared %": round(100 * sum(prep) / len(prep)) if prep else 0,
            "Confirmed + feedback %": round(100 * (conf + fb) / (2 * due)),
            "Rating received": round(r, 1) if r else None,
            "Sentiment received": round(snt, 2) if snt is not None else None,
            "Score": score, "Grade": grade, "Flags": ", ".join(sorted(set(flags)))}


def all_set_card(kind):
    who = "mentor" if kind == "Mentee" else "mentee"
    st.success(f"### You're all set!\nYour application is in. We'll email you as soon as you have a {who}. "
               "You can edit your profile any time while applications are open.")


# ---------------- Staff / Admin ----------------
def overview():
    studs = [s for s in D["students"] if s["status"] == "Approved"]
    appr = active_matches()
    allm = active_matches(("Proposed", "Approved"))
    c = st.columns(5)
    c[0].metric("Approved students", len(studs))
    c[1].metric("Approved mentors", sum(m["status"] == "Approved" for m in D["mentors"]))
    c[2].metric("Matched", f"{100*len(allm)//max(len(studs),1)}%")
    c[3].metric("Avg match score", f"{sum(m['score'] for m in allm)/len(allm):.0f}" if allm else "-")
    c[4].metric("Mentor slots", sum(m["capacity"] for m in D["mentors"] if m["status"] == "Approved"))
    if allm:
        st.markdown("**Match confidence**")
        conf = pd.Series([m["confidence"] for m in allm]).value_counts().reindex(list(CONF_COLOR)).fillna(0)
        with st.container(border=True):
            st.vega_lite_chart(
                {"data": {"values": [{"Level": k, "Matches": int(conf[k])} for k in CONF_COLOR]},
                 "padding": {"left": 12, "right": 28, "top": 12, "bottom": 12},
                 "height": {"step": 34},
                 "background": None,
                 "view": {"stroke": None},
                 "mark": {"type": "bar", "cornerRadius": 7, "height": {"band": 0.72}},
                 "encoding": {
                     "y": {"field": "Level", "type": "nominal", "sort": list(CONF_COLOR), "title": None,
                           "axis": {"domain": False, "ticks": False, "labelPadding": 12}},
                     "x": {"field": "Matches", "type": "quantitative", "title": None,
                           "axis": {"domain": False, "ticks": False, "grid": False, "tickMinStep": 1}},
                     "color": {"field": "Level", "type": "nominal", "legend": None,
                               "scale": {"domain": list(CONF_COLOR), "range": list(CONF_COLOR.values())}},
                     "tooltip": [{"field": "Level"}, {"field": "Matches"}]}},
                width="stretch")

        if appr and D["cycle"]["released"]:
            stats = [pair_stats(m) for m in appr]
            ratings = [s["rating"] for s in stats if s["rating"]]
            due = sum(s["due"] for s in stats)
            c = st.columns(5)
            c[0].metric("Session completion", f"{100*sum(s['attended'] for s in stats)//max(due,1)}%")
            on = [s["on_time %"] for s in stats if s["on_time %"] is not None]
            c[1].metric("On time", f"{sum(on)//len(on)}%" if on else "-")
            c[2].metric("Avg rating", f"{sum(ratings)/len(ratings):.1f}/5" if ratings else "-")
            c[3].metric("Avg prework done", f"{sum(s['prework %'] for s in stats)//len(stats)}%")
            c[4].metric("Needs attention", sum(s["at_risk"] for s in stats))

        with st.expander("Fairness check: match rate and average score by group"):
            rows = []
            mby = {m["student_id"]: m for m in allm}
            for key in ("field", "year"):
                for val in sorted({s[key] for s in studs}):
                    grp = [s for s in studs if s[key] == val]
                    got = [mby[s["id"]]["score"] for s in grp if s["id"] in mby]
                    rows.append({"Group": key.title(), "Value": val, "Students": len(grp),
                                 "Matched %": round(100 * len(got) / len(grp)),
                                 "Avg score": round(sum(got) / len(got)) if got else None})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("No demographic data is collected or used in matching. "
                       "This table checks that no major or year is left behind.")


def run_matching_now(rerun=True):
    """The ONLY place matches are created, and only when an admin presses 'Match students to mentors'.
    Nothing matches on submit, so being first to apply gives no advantage: everyone is matched in one batch."""
    if not can("run_matching"):
        return
    cyc = D["cycle"]
    studs = [s for s in D["students"] if s["status"] == "Approved"]
    ments = [m for m in D["mentors"] if m["status"] == "Approved"]
    locked = [(m["student_id"], m["mentor_id"]) for m in active_matches()]
    excluded = [(m["student_id"], m["mentor_id"]) for m in D["matches"] if m["status"] == "Denied"]
    D["matches"] = [m for m in D["matches"] if m["status"] in ("Approved", "Denied")]
    thr = cyc.get("min_score", 50)
    new, unmatched = run_matching(studs, ments, locked=locked, weights=D["weights"], excluded=excluded)
    weak = [m for m in new if m["score"] < thr]           # below the strong-match bar: do not assign the pair
    new = [m for m in new if m["score"] >= thr]
    unmatched += [{"student_id": m["student_id"], "why": f"No strong match (best available {m['score']:.0f}%)"}
                  for m in weak]
    for m in new:
        m["below_threshold"] = False
    auto_on, auto_min = cyc.get("auto_approve", True), cyc.get("auto_approve_min", 50)
    for m in new:
        m["status"] = "Proposed"
        if auto_on and m["score"] >= auto_min:      # no staff click needed; kept out of the learning signal
            m["status"], m["auto_approved"] = "Approved", True
    D["matches"] += new
    D["unmatched"] = unmatched
    n_auto = sum(m.get("auto_approved", False) for m in new)
    done = (f"Matching done: {len(new)} matches ({n_auto} auto-approved), {len(unmatched)} unmatched")
    commit(done) if rerun else save(D)


def release_matches_now(rerun=True):
    D["cycle"]["released"] = True
    for m in active_matches():
        for p in (S_BY[m["student_id"]], M_BY[m["mentor_id"]]):
            send(p["email"], "Your Tandem match is ready",
                 f"Hi {p['name'].split()[0]}, your mentorship match is "
                 "ready. Log in to Tandem to meet them and start your prework.", kind="Match")
    commit("Matches released, emails sent") if rerun else save(D)


def load_midprogram_demo():
    """Reset, then play the cycle forward: match, approve strong matches, release, simulate weeks 1 to 5.
    Gives most student and mentor logins real lesson progress to look at."""
    global S_BY, M_BY
    reset_db()
    D.clear()
    D.update(load())
    S_BY = {s["id"]: s for s in D["students"]}
    M_BY = {m["id"]: m for m in D["mentors"]}
    D["cycle"]["apps_open"] = False
    run_matching_now(rerun=False)
    for m in D["matches"]:
        if m["status"] == "Proposed" and not m["below_threshold"]:
            approve(m)
    release_matches_now(rerun=False)
    simulate(rerun=False)


# Status filter symbols (Material icons, no emoji): o proposed, check approved, x denied
STATUS_ICON = {"Proposed": ":material/radio_button_unchecked:", "Approved": ":material/check:", "Denied": ":material/close:"}


def matching_tab(is_admin):
    cyc = D["cycle"]
    studs = [s for s in D["students"] if s["status"] == "Approved"]
    ments = [m for m in D["mentors"] if m["status"] == "Approved"]
    if can("edit_matching_rules"):
        ran = bool(D["matches"] or D["unmatched"])  # open until matching has run; the key resets it when that flips
        with st.expander("Matching rules", expanded=not ran, key=f"rules_box_{'after' if ran else 'before'}"):
            matching_rules_form()
            st.caption("Applies the next time matching runs. Matches already approved or denied are not changed. "
                       "Auto-approved matches are marked as such and don't count as staff decisions when the model learns.")
    if can("run_matching") and st.button("Match students to mentors", type="primary"):
        run_matching_now()
    if active_matches() and not cyc["released"] and can("release_matches"):
        to_review = len(active_matches(("Proposed",)))
        unplaced = sum(1 for s in studs if not match_for_student(s["id"]))
        if to_review or unplaced:   # release is offered only when nobody is left to review or place
            st.caption("Release appears once every student has an approved match. "
                       + ", ".join(p for p in (f"{to_review} still to review" if to_review else "",
                                               f"{unplaced} without a mentor" if unplaced else "") if p) + ".")
        elif st.button(f"Release {len(active_matches())} approved matches and email everyone"):
            release_matches_now()

    f1, f2 = st.columns([2, 1])
    with f1:
        flt = st.segmented_control("Show", list(STATUS_ICON), default="Proposed", selection_mode="single",
                                   format_func=lambda k: f"{STATUS_ICON[k]} {k}") or "Proposed"
    sort = f2.selectbox("Sort by", ["Highest score", "Lowest score"])
    rows = [m for m in D["matches"] if m["status"] == flt]
    shown = sorted(rows, key=lambda m: -m["score"] if sort == "Highest score" else m["score"])
    st.caption(("Strongest matches first." if sort == "Highest score" else "Weakest matches first.")
               + f" Showing {len(shown)}.")
    for m in shown:
        match_card(m)

    if D.get("unmatched"):
        with st.expander(f"Unmatched students ({len(D['unmatched'])})"):
            for u in D["unmatched"]:
                if u["student_id"] in S_BY:
                    st.markdown(f"- **{S_BY[u['student_id']]['name']}**: {u['why']}")


def approve(m):
    m["status"] = "Approved"
    D["decisions"].append({"student_id": m["student_id"], "mentor_id": m["mentor_id"],
                           "approved": True, "at": NOW()})


def match_card(m):
    s, mt = S_BY[m["student_id"]], M_BY[m["mentor_id"]]
    with st.container(border=True):
        c1, c2 = st.columns([3, 1.4], gap="large")
        with c1:
            left, mid, right = st.columns([5, 2.4, 5], gap="small", vertical_alignment="center")
            same_major = s["field"] == mt["field"]
            with left:
                profile_panel("Mentee", s["name"], f"{hit(background(s), same_major)} · {ui.esc(s['year'])}",
                              mentee_bullets(s, mt))
            with right:
                job = f"{mt['role']} at {mt['company']}" if mt.get("role") else mt["company"]
                profile_panel("Mentor", mt["name"], f"{ui.esc(job)} · {hit(background(mt), same_major)}",
                              mentor_bullets(s, mt))
            with mid:  # the score sits between the two people it describes
                p = predict_success(D.get("model"), s, mt)
                ui.html(f"<div style='text-align:center'><div style='font-size:2.2rem;font-weight:700;"
                        f"line-height:1.1;white-space:nowrap'>{m['score']:.0f}%</div>"
                        + ui.chip(f"{m['confidence']}", CONF_TONE[m["confidence"]])
                        + (f"<div style='font-size:.75rem;color:var(--muted)'>ML success {p:.0%}</div>"
                           if p is not None else "") + "</div>")
            if m.get("below_threshold"):
                st.warning(f"No strong match found (below {D['cycle'].get('min_score', 50)}%). This is the closest "
                           "available mentor. Approve if it still helps, or deny and recruit a better fit.")
            if m.get("note"):
                st.caption(f"Staff note: {m['note']}")
        with c2:
            score_bars(m["breakdown"], D["weights"])
            if m["status"] == "Proposed":
                st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)  # breathing room above buttons
                ok_col, no_col = st.columns(2, gap="medium")
                if ok_col.button("Approve", key=f"ok_{pair_key(m)}", type="primary", use_container_width=True):
                    approve(m)
                    commit("Match approved")
                if no_col.button("Deny", key=f"no_{pair_key(m)}", use_container_width=True):
                    m["status"] = "Denied"
                    D["decisions"].append({"student_id": m["student_id"], "mentor_id": m["mentor_id"],
                                           "approved": False, "reasons": [], "at": NOW()})
                    commit("Match denied. Run matching again to find a new mentor for this student.")
            elif m["status"] == "Approved":
                st.success("Auto-approved" if m.get("auto_approved") else "Approved")
        alternatives_box(m)


def hit(text, on, partial=False):
    """Green and bold when this answer lines up with the other person's; amber for a partial match."""
    t = ui.esc(str(text))
    if on or partial:
        return f"<span style='color:var(--{'ok' if on else 'amber'});font-weight:600'>{t}</span>"
    return t


def industry_hit(mine, theirs):
    return hit(mine, mine == theirs, partial=industry_credit(mine, theirs) > 0)


def profile_panel(role, name, subtitle, bullets):
    """Big name, a one-line subtitle, then a few short bullets so staff can judge the fit at a glance."""
    items = "".join(f"<li><span style='color:var(--muted)'>{label}:</span> {value}</li>" for label, value in bullets)
    ui.html(f"<div style='font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)'>"
            f"{role}</div><div style='font-size:1.35rem;font-weight:700;line-height:1.25;margin-top:.1rem'>"
            f"{ui.esc(name)}</div><div style='font-size:.85rem;color:var(--muted);margin-bottom:.4rem'>{subtitle}</div>"
            f"<ul style='margin:0;padding-left:1.1rem;font-size:.9rem;line-height:1.5'>{items}</ul>")


def hits_first(items, is_hit):
    """Matching items in green; everything else collapses into '+N more'."""
    shown = [hit(x, True) for x in items if is_hit(x)]
    rest = sum(not is_hit(x) for x in items)
    more = f"<span style='color:var(--muted)'>+{rest} more</span>" if rest else ""
    return ", ".join(shown + ([more] if more else [])) or "<span style='color:var(--muted)'>none</span>"


def mentee_bullets(s, mt):
    return [("Industry", industry_hit(s["industry"], mt["industry"])),
            ("Goals", ", ".join(hit(f"#{i+1} {g}", g in mt["can_help"]) for i, g in enumerate(s["help_ranked"]))),
            ("Free", hits_first(s["availability"], lambda t: t in mt["availability"]))]


def mentor_bullets(s, mt):
    return [("Industry", industry_hit(mt["industry"], s["industry"])),
            ("Helps with", hits_first(mt["can_help"], lambda g: g in s["help_ranked"])),
            ("Free", hits_first(mt["availability"], lambda t: t in s["availability"]))]


def alternatives_box(m):
    """Show the recommender's other top mentors for this student, so staff see the full picture,
    not just the one pick. Explains when a higher-scoring mentor went to someone else."""
    alts = [a for a in m.get("alternatives", []) if has_capacity(a["mentor_id"])][:2]   # full mentors are not offered
    if not alts:
        return
    with st.expander(f"Other top mentors the recommender found ({len(alts)})"):
        st.caption("Each student is ranked against every mentor. The final pick comes from the "
                   "assignment step, which maximizes match quality across ALL students, so the "
                   "#1 scorer for one student may go to someone they fit even better.")
        for a in alts:
            mt = M_BY[a["mentor_id"]]
            free = has_capacity(a["mentor_id"])
            taken = [S_BY[x["student_id"]]["name"] for x in active_matches(("Proposed", "Approved"))
                     if x["mentor_id"] == a["mentor_id"]]
            c1, c2 = st.columns([4, 1])
            diff = a["score"] - m["score"]
            c1.markdown(f"**{mt['name']}** ({mt['role']}, {mt['company']}) · **{a['score']:.0f}%** "
                        f"({'+' if diff >= 0 else ''}{diff:.0f} vs current pick)")
            c1.caption("Why: " + a["reason"])
            if a["gaps"]:
                c1.caption("Gaps: " + "; ".join(a["gaps"]))
            if free:
                c1.caption(f"Has open capacity ({len(taken)}/{mt['capacity']} used)")
            else:
                c1.caption(f"Full ({len(taken)}/{mt['capacity']}): matched with {', '.join(taken) or 'others'}")
            if m["status"] == "Proposed" and can("review_matches"):
                if c2.button("Use this mentor", key=f"rb_{pair_key(m)}_{a['mentor_id']}", disabled=not free):
                    reassign(m, a["mentor_id"])


def has_capacity(mid):
    mt = M_BY[mid]
    used = sum(1 for m in active_matches(("Proposed", "Approved")) if m["mentor_id"] == mid)
    return mt["status"] == "Approved" and used < mt["capacity"]


def reassign(m, mid):
    s, mt = S_BY[m["student_id"]], M_BY[mid]
    D["decisions"].append({"student_id": m["student_id"], "mentor_id": m["mentor_id"],
                           "approved": False, "reasons": ["Better option available"], "at": NOW()})
    total, bd = score_pair(s, mt, D["weights"])
    m.update({"mentor_id": mid, "score": total, "breakdown": bd, "reason": explain(s, mt, bd),
              "gaps": gaps(s, mt), "note": "Manually reassigned by staff"})
    approve(m)
    commit(f"Reassigned {s['name']} to {mt['name']}")


def progress_card(m, ps, total):
    """One pair as a single clickable <details> box: names up top, every stat in the dropdown."""
    s, mt = S_BY[m["student_id"]], M_BY[m["mentor_id"]]
    lab = "font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)"
    sub = "font-size:.85rem;color:var(--muted)"

    def person(role, name, line, align):
        return (f"<div style='flex:1;text-align:{align}'><div style='{lab}'>{role}</div>"
                f"<div style='font-size:1.35rem;font-weight:700;line-height:1.25'>{ui.esc(name)}</div>"
                f"<div style='{sub}'>{line}</div></div>")

    def stat(label, value):
        return (f"<div style='flex:1;min-width:110px'><div style='{sub}'>{label}</div>"
                f"<div style='font-size:1.4rem;font-weight:600'>{value}</div></div>")

    def bar(label, val):
        v = min(max(val, 0), 100)
        return (f"<div style='margin:.5rem 0'><div style='{sub};display:flex;justify-content:space-between'>"
                f"<span>{label}</span><span>{val:.0f}%</span></div>"
                f"<div style='height:8px;border-radius:99px;background:var(--hover)'>"
                f"<div style='height:8px;border-radius:99px;width:{v}%;background:hsl({v * 1.25:.0f},68%,42%)'></div></div></div>")

    job = f"{mt['role']} at {mt['company']}" if mt.get("role") else mt["company"]
    chip = (ui.chip("At risk", "warn") if ps["at_risk"] else ui.chip("On track", "ok") if ps["due"]
            else ui.chip("Not started", "plain"))
    mid = (f"<div style='text-align:center;min-width:110px'><div style='font-size:2rem;font-weight:700;"
           f"line-height:1.1'>{ps['engagement']:.0f}%</div><div style='{sub}'>engagement</div>{chip}</div>")
    stats = (stat("Match score", f"{m['score']:.1f}") + stat("Sessions", f"{ps['attended']}/{total}")
             + stat("Avg rating", f"{ps['rating']:.1f}" if ps["rating"] else "-")
             + stat("Feedback sentiment", f"{ps['sentiment']:.2f}" if ps["sentiment"] is not None else "-")
             + stat("On time", f"{ps['on_time %']}%" if ps.get("on_time %") is not None else "-"))
    safety = (f"<div style='color:var(--warn);margin-top:.5rem'>Safety words in feedback: "
              f"{ui.esc(', '.join(ps['safety']))}</div>" if ps.get("safety") else "")
    return (f"<details style='border:1px solid var(--line, rgba(128,128,128,.3));border-radius:12px;"
            f"padding:1rem 1.25rem;margin-bottom:.75rem'><summary style='cursor:pointer;list-style:none'>"
            f"<div style='display:flex;align-items:center;gap:1.5rem'>"
            f"{person('Mentee', s['name'], f'{ui.esc(s['year'])} · {ui.esc(s['field'])}', 'left')}{mid}"
            f"{person('Mentor', mt['name'], ui.esc(job), 'right')}</div></summary>"
            f"<div style='margin-top:1rem;padding-top:1rem;border-top:1px solid rgba(128,128,128,.25)'>"
            f"<div style='display:flex;flex-wrap:wrap;gap:1rem'>{stats}</div>"
            f"{bar('Prework', ps['prework %'])}"
            f"{bar('Postwork', ps['postwork %'])}{safety}</div></details>")


def progress_tab():
    appr = active_matches()
    if not (appr and D["cycle"]["released"]):
        st.info("Progress tracking starts once matches are released.")
        return
    t1, t2 = st.columns([3, 1], vertical_alignment="bottom")
    only = t1.toggle("Show at-risk pairs only")
    order = t2.selectbox("Sort by", ["Lowest scoring", "Highest scoring"])
    pairs = sorted(((m, pair_stats(m)) for m in appr), key=lambda x: x[1]["engagement"],
                   reverse=order == "Highest scoring")
    if only:
        pairs = [(m, ps) for m, ps in pairs if ps["at_risk"]]
    total = len(D["curriculum"])
    for m, ps in pairs:
        ui.html(progress_card(m, ps, total))
    st.caption("Engagement = 50% attendance + 30% prework + 20% session quality (70% star rating + 30% "
               "written feedback, which only lowers the score if it is neutral or negative). At risk = missed or disputed session, safety words in "
               "feedback, prework under 50%, rating under 3, or negative written feedback.")



def needs_mentor():
    """Students staff must place by hand: their match was denied, or matching found no strong match for them.
    Only after matching has run, and never someone who already has a live match."""
    live = {m["student_id"] for m in active_matches(("Proposed", "Approved"))}
    why = {u["student_id"]: u["why"] for u in D.get("unmatched", [])}
    for m in D["matches"]:
        if m["status"] == "Denied":
            why.setdefault(m["student_id"], "Match denied")
    return [(S_BY[sid], w) for sid, w in why.items()
            if sid in S_BY and sid not in live and S_BY[sid].get("status") == "Approved"]


def mentor_choices(s):
    """Mentors who still fit this student (open capacity, never one staff already denied), best score first."""
    denied = {x["mentor_id"] for x in D["matches"] if x["student_id"] == s["id"] and x["status"] == "Denied"}
    pool = [mt for mt in D["mentors"] if mt["id"] not in denied and has_capacity(mt["id"])]
    return rank_mentors(s, pool, top_k=8, weights=D["weights"])


def needs_mentor_section():
    todo = needs_mentor()
    if not todo:
        return 0
    st.markdown(f"**Students who need a mentor ({len(todo)})**")
    st.caption("No pair is assigned for these students. Pick a mentor who fits, or hold them for the next cycle.")
    for s, why in todo:
        cands = mentor_choices(s)
        with st.expander(f"{s['name']}  ·  {why}"):
            if not cands:
                st.info("No available mentor fits this student right now.")
            else:
                by_id = {c["mentor_id"]: c for c in cands}
                pick = st.selectbox("Mentor", list(by_id), key=f"pm_{s['id']}",
                                    format_func=lambda i: f"{M_BY[i]['name']}  ·  {by_id[i]['score']:.0f}%  "
                                                          f"({M_BY[i]['role']}, {M_BY[i]['company']})")
                c = by_id[pick]
                mt = M_BY[pick]
                score_bars(c["breakdown"], D["weights"])
                st.caption(c["reason"])
                preview = {"student_id": s["id"], "mentor_id": pick, "score": c["score"], "breakdown": c["breakdown"],
                           "confidence": confidence(c["score"], 0), "reason": c["reason"], "gaps": c["gaps"],
                           "alternatives": [], "status": "Preview"}
                b1, b2, _ = st.columns([1.2, 1.2, 4], vertical_alignment="center")
                with b1.popover("Full stats", icon=":material/info:"):
                    match_card(preview)
                if b2.button("Assign", key=f"as_{s['id']}", type="primary"):
                    preview.pop("status")
                    preview["note"] = "Chosen by staff from the flags list"
                    D["matches"].append(preview)
                    D["unmatched"] = [u for u in D.get("unmatched", []) if u["student_id"] != s["id"]]
                    approve(preview)
                    commit(f"{s['name']} matched with {mt['name']}")
            if st.button("Match next cycle", key=f"nc_{s['id']}", icon=":material/event_repeat:"):
                s["status"], s["next_cycle"] = "Deferred", True      # back in the database, first in line next cycle
                D["unmatched"] = [u for u in D.get("unmatched", []) if u["student_id"] != s["id"]]
                commit(f"{s['name']} will be matched with a new mentor next cycle")
    return len(todo)


def flags_tab():
    """Everything a human should look at, in one list."""
    if needs_mentor_section():
        st.divider()
    rows = []
    for m in active_matches(("Proposed",)):
        if m["confidence"] == "Low":
            rows.append({"Type": "Low-confidence match", "Pair": f"{S_BY[m['student_id']]['name']} / "
                         f"{M_BY[m['mentor_id']]['name']}", "Detail": f"Score {m['score']:.0f}. Review in Matching."})
    if D["cycle"]["released"]:
        for m in active_matches():
            pair = f"{S_BY[m['student_id']]['name']} / {M_BY[m['mentor_id']]['name']}"
            ps = pair_stats(m)
            for i, stt in enumerate(ps["statuses"]):
                if stt in ("Flagged", "Missed"):
                    rows.append({"Type": "Disputed check-in" if stt == "Flagged" else "Missed session",
                                 "Pair": pair, "Detail": D["curriculum"][i]["name"]})
            if ps["safety"]:
                rows.append({"Type": "Safety words in feedback", "Pair": pair,
                             "Detail": ", ".join(ps["safety"]) + ". Read the feedback and contact the pair."})
            if ps["rating"] is not None and ps["rating"] < 3:
                rows.append({"Type": "Low rating", "Pair": pair, "Detail": f"Avg {ps['rating']:.1f}/5"})
            if ps["sentiment"] is not None and ps["sentiment"] < -0.3:
                rows.append({"Type": "Negative written feedback", "Pair": pair,
                             "Detail": f"Sentiment {ps['sentiment']:+.2f}"})
    if not rows:
        st.success("No flags")
        return
    df = pd.DataFrame(rows)
    pick = st.multiselect("Show", sorted(df["Type"].unique()), default=sorted(df["Type"].unique()))
    st.dataframe(df[df["Type"].isin(pick)], hide_index=True, width="stretch")
    st.caption("Flags only alert humans. Nothing here changes a match automatically.")


def scorecards_tab():
    if not (D["cycle"]["released"] and active_matches()):
        st.info("Scorecards appear once matches are released and sessions start.")
        return
    st.caption("Score = 30% attendance + 20% preparation (prework or mentor prep) + 15% confirming and "
               "giving feedback + 35% how their partner rated sessions (80% stars, 20% written-feedback "
               "sentiment). Grades: A 85+, B 70+, C 55+, D below. Visible to Career Center staff only, "
               "for coaching and recognition, never shared with participants.")
    who = st.radio("Show", ["Mentors", "Mentees"], horizontal=True, key="sc_who")
    role = "mentor" if who == "Mentors" else "mentee"
    people = D["mentors"] if role == "mentor" else D["students"]
    rows = []
    for p in people:
        sc = person_scores(p["id"], role)
        if sc:
            extra = {"Company": p["company"]} if role == "mentor" else {"Major": background(p)}
            rows.append({"Name": p["name"], **extra, **sc})
    if not rows:
        st.info("No completed sessions yet.")
        return
    df = pd.DataFrame(rows).sort_values("Score", ascending=False)
    grades = st.multiselect("Grade", ["A", "B", "C", "D"], default=["A", "B", "C", "D"], key="sc_g")
    df = df[df["Grade"].isin(grades)]
    c = st.columns(4)
    for col, g in zip(c, "ABCD"):
        col.metric(f"Grade {g}", int((pd.DataFrame(rows)["Grade"] == g).sum()))
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100)})
    st.download_button("Export scorecards (CSV)", df.to_csv(index=False), f"tandem_{who.lower()}_scorecards.csv")
    if role == "mentor" and len(df):
        st.success(f"Top mentor: **{df.iloc[0]['Name']}** (score {df.iloc[0]['Score']}). "
                   "Consider a thank-you or recognition at the closing session.")


def announcements_tab():
    st.markdown("**Send an announcement** (e.g. orientation details)")
    with st.form("announce", clear_on_submit=True):
        aud = st.selectbox("To", ["Everyone", "All mentees", "All mentors", "Matched pairs only"])
        subj = st.text_input("Subject", placeholder="Orientation: Thursday Feb 4, 5 PM, Engineering 189")
        body = st.text_area("Message")
        if st.form_submit_button("Send", type="primary"):
            if not (subj and body):
                st.error("Add a subject and message.")
            else:
                studs = [s for s in D["students"] if s["status"] == "Approved"]
                ments = [m for m in D["mentors"] if m["status"] == "Approved"]
                if aud == "Matched pairs only":
                    ids = {x for m in active_matches() for x in (m["student_id"], m["mentor_id"])}
                    people = [p for p in studs + ments if p["id"] in ids]
                else:
                    people = (studs if aud != "All mentors" else []) + (ments if aud != "All mentees" else [])
                for p in people:
                    send(p["email"], subj, f"Hi {p['name'].split()[0]}, {body}", kind="Announcement")
                D.setdefault("announcements", []).append({"to": aud, "subject": subj, "count": len(people),
                                                          "by": st.session_state.user["email"], "at": NOW()})
                commit(f"Sent to {len(people)} people")
    if D.get("announcements"):
        st.dataframe(pd.DataFrame(D["announcements"][::-1]), hide_index=True, width="stretch")


def users_tab():
    con = db()
    users = pd.DataFrame(con.execute("SELECT email, name, role, active, created FROM users").fetchall(),
                         columns=["Email", "Name", "Role", "Active", "Created"])
    c1, c2 = st.columns([2, 1])
    q = c1.text_input("Search users", key="user_q").lower()
    roles = c2.multiselect("Role", ["Mentee", "Mentor", "Staff", "Admin"])
    view = users[(users["Email"].str.contains(q) | users["Name"].str.lower().str.contains(q))
                 & (users["Role"].isin(roles) if roles else True)]
    st.dataframe(view.assign(Active=view["Active"].map({1: "Yes", 0: "No"})), hide_index=True, width="stretch")
    st.download_button("Export users (CSV)", view.to_csv(index=False), "tandem_users.csv")
    if view.empty:
        return
    email = st.selectbox("Manage account", view["Email"].tolist())
    row = users[users["Email"] == email].iloc[0]
    with st.form("manage_user"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name", row["Name"])
        role_opts = ["Mentee", "Mentor", "Staff", "Admin"]
        role = c2.selectbox("Role", role_opts, index=role_opts.index(row["Role"]),
                            disabled=not can("manage_staff_accounts"),
                            help="Only Admin can change roles.")
        active = c3.checkbox("Active", bool(row["Active"]))
        new_pw = st.text_input("Reset password (leave blank to keep)", type="password")
        if st.form_submit_button("Save account"):
            if email == st.session_state.user["email"] and (not active or role != row["Role"]):
                st.error("You can't deactivate or change the role of your own account.")
            elif new_pw and len(new_pw) < 8:
                st.error("New password must be at least 8 characters.")
            else:
                con.execute("UPDATE users SET name=?, role=?, active=? WHERE email=?",
                            (name, role, int(active), email))
                if new_pw:
                    salt = secrets.token_hex(16)
                    con.execute("UPDATE users SET salt=?, pw_hash=? WHERE email=?",
                                (salt, hash_pw(new_pw, salt), email))
                con.commit()
                for p in D["students"] + D["mentors"]:
                    if p["email"] == email:
                        p["name"] = name
                commit(f"Saved {email}")


WEIGHT_SLIDER_CSS = """
.wrap { padding: 28px 10px 6px; user-select: none; }
.bar { position: relative; height: 46px; }
.seg { height: 100%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700;
       font-size: 0.95rem; overflow: hidden; white-space: nowrap; transition: width .06s linear; }
.track { position: absolute; inset: 0; display: flex; border-radius: 12px; overflow: hidden; }
.node { position: absolute; top: -7px; width: 18px; height: 60px; margin-left: -9px; cursor: ew-resize; touch-action: none;
        display: flex; justify-content: center; outline: none; z-index: 2; }
.node::before { content: ""; width: 4px; height: 100%; border-radius: 4px; background: #fff; box-shadow: 0 0 0 1px rgba(0,0,0,.25); }
.node::after { content: ""; position: absolute; top: 50%; width: 16px; height: 16px; margin-top: -8px; border-radius: 50%;
        background: #fff; border: 2px solid #334155; box-shadow: 0 1px 4px rgba(0,0,0,.35); }
.node:focus-visible::after, .node:hover::after { border-color: #0055A2; transform: scale(1.12); }
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 18px; font-size: .85rem; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 11px; height: 11px; border-radius: 4px; display: inline-block; }
.legend b { font-weight: 700; }
"""
WEIGHT_SLIDER_JS = """
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement;
  let wrap = root.querySelector('.wrap');
  if (wrap) wrap.remove();
  wrap = document.createElement('div'); wrap.className = 'wrap';
  const bar = document.createElement('div'); bar.className = 'bar';
  const legend = document.createElement('div'); legend.className = 'legend';
  wrap.append(bar, legend); root.append(wrap);
  const n = data.values.length;
  const cum = []; let s = 0;
  data.values.forEach((v, i) => { s += v; if (i < n - 1) cum.push(s); });
  const track = document.createElement('div'); track.className = 'track'; bar.append(track);
  const segs = [], nodes = [], items = [];
  for (let i = 0; i < n; i++) {
    const g = document.createElement('div'); g.className = 'seg'; g.style.background = data.colors[i]; track.append(g); segs.push(g);
    const it = document.createElement('span'); it.innerHTML = '<i style="background:' + data.colors[i] + '"></i>' + data.labels[i] + ' <b></b>';
    legend.append(it); items.push(it.querySelector('b'));
  }
  const vals = () => cum.map((c, i) => c - (i ? cum[i - 1] : 0)).concat([100 - cum[n - 2]]);
  function paint() {
    const v = vals();
    segs.forEach((g, i) => { g.style.width = v[i] + '%'; g.textContent = v[i] >= 6 ? v[i] : ''; });
    items.forEach((b, i) => { b.textContent = v[i]; });
    nodes.forEach((nd, i) => { nd.style.left = cum[i] + '%'; nd.setAttribute('aria-valuenow', cum[i]); });
  }
  function commit() { setStateValue('w', vals()); }
  for (let i = 0; i < n - 1; i++) {
    const nd = document.createElement('div'); nd.className = 'node'; nd.tabIndex = 0; nd.setAttribute('role', 'slider');
    nd.setAttribute('aria-label', 'Boundary between ' + data.labels[i] + ' and ' + data.labels[i + 1]);
    const lo = () => (i ? cum[i - 1] : 0), hi = () => (i < n - 2 ? cum[i + 1] : 100);
    nd.addEventListener('pointerdown', e => { nd.setPointerCapture(e.pointerId); nd.dragging = true; e.preventDefault(); });
    nd.addEventListener('pointermove', e => {
      if (!nd.dragging) return;
      const r = bar.getBoundingClientRect();
      const p = Math.round(((e.clientX - r.left) / r.width) * 100);
      cum[i] = Math.min(Math.max(p, lo()), hi()); paint();
    });
    const end = () => { if (nd.dragging) { nd.dragging = false; commit(); } };
    nd.addEventListener('pointerup', end); nd.addEventListener('pointercancel', end);
    nd.addEventListener('keydown', e => {
      const d = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0;
      if (!d) return; e.preventDefault();
      cum[i] = Math.min(Math.max(cum[i] + d, lo()), hi()); paint(); commit();
    });
    bar.append(nd); nodes.push(nd);
  }
  paint();
}
"""
_weight_slider = st.components.v2.component("weight_slider", css=WEIGHT_SLIDER_CSS, js=WEIGHT_SLIDER_JS)
WEIGHT_COLORS = ["#0055A2", "#2E7DBF", "#6FA8DC", "#E0A800", "#2E9E78", "#7C5CBF"]


def weights_editor():
    """Hand-edit the scoring weights on one bar: each factor is a slice of the 100 points; drag the nodes
    between slices to resize them. The slices always add up to 100. The next matching run uses the saved weights."""
    w = D["weights"]
    labels = ["Goal #1", "Goal #2", "Goal #3", "Industry", "Background", "Availability"]
    saved = [w["help"][0], w["help"][1], w["help"][2], w["industry"], w["field"], w["availability"]]
    scaled = [round(100 * v / sum(saved)) for v in saved]       # whole points that add up to exactly 100
    scaled[3] += 100 - sum(scaled)
    st.markdown("**Scoring weights**")
    st.caption("Each factor is a slice of the 100 points. Drag the nodes (or focus one and use the arrow keys) to "
               "resize the slices. Changes apply the next time matching runs; existing matches keep their scores.")
    res = _weight_slider(key="wslider_" + "_".join(map(str, scaled)),
                         data={"labels": labels, "values": scaled, "colors": WEIGHT_COLORS}, on_w_change=lambda: None)
    vals = [int(x) for x in res.w] if res.w else scaled
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("Save weights", type="primary", disabled=vals == scaled):
        D["weights"] = {"help": vals[:3], "industry": vals[3], "field": vals[4], "availability": vals[5]}
        commit("Weights saved. The next matching run will use them.")
    if b2.button("Reset to defaults"):
        D["weights"] = dict(WEIGHTS)
        commit("Weights reset to defaults")


def insights_tab():
    if can("edit_weights"):
        weights_editor()
        st.divider()
    st.markdown("**Mentor supply gap:** where to recruit next")
    studs = [s for s in D["students"] if s["status"] == "Approved"]
    ments = [m for m in D["mentors"] if m["status"] == "Approved"]
    gap = pd.DataFrame(supply_gap(studs, ments, INDUSTRIES, HELP_AREAS))
    if gap.empty:
        st.info("No approved students yet. Insights appear once applications come in.")
        return
    st.dataframe(gap, hide_index=True, width="stretch",
                 column_config={"Coverage %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%")})
    low = gap[gap["Coverage %"] < 60]
    for _, r in low.head(3).iterrows():
        st.warning(f"{r['Students']} students want **{r['Tag']}**, only {r['Mentor slots']} mentor slot(s). "
                   f"Recruit more {r['Tag']} mentors.")

    if not can("train_apply_model"):
        st.info("Learning from feedback is visible to super-admins (Admin) only.")
        return
    st.markdown("**Learning from feedback** (extra credit)")
    st.caption("Signals: staff approvals, checked deny reasons, and session outcomes "
               "(pairs averaging under 3/5 or saying 'don't continue' count as unsuccessful).")
    signals = [d for d in D["decisions"] if d["student_id"] in S_BY and d["mentor_id"] in M_BY]
    if D["cycle"]["released"]:
        for m in active_matches():
            ps = pair_stats(m)
            recs = [session_rec(pair_key(m), i)["checkin"] for i in range(len(D["curriculum"]))]
            stop = any(c.get(k, {}).get("continue") == "No" for c in recs for k in c)
            if ps["rating"] is not None:
                ok = ps["rating"] >= 3 and not stop and (ps["sentiment"] is None or ps["sentiment"] >= -0.2)
                signals.append({"student_id": m["student_id"], "mentor_id": m["mentor_id"],
                                "approved": ok, "reasons": []})
    n_ok = sum(d["approved"] for d in signals)
    reason_tally = pd.Series([r for d in D["decisions"] for r in d.get("reasons", [])]).value_counts()
    c1, c2 = st.columns(2)
    c1.metric("Positive signals", n_ok)
    c2.metric("Negative signals", len(signals) - n_ok)
    if len(reason_tally):
        st.markdown("Deny reasons so far")
        st.bar_chart(reason_tally, color="#0055A2", horizontal=True)
    n_no = len(signals) - n_ok
    learned = learn_weights(signals, D["students"], D["mentors"], base=D["weights"])
    model = train_model(signals, D["students"], D["mentors"])
    cur, new = D["weights"], learned
    rows = {"Factor": ["Goal #1", "Goal #2", "Goal #3", "Industry",
                       "Background (major/minor + SJSU connection)", "Availability"],
            "Current": cur["help"] + [cur["industry"], cur["field"], cur["availability"]],
            "Rule-based suggestion": new["help"] + [new["industry"], new["field"], new["availability"]]}
    if model:
        w = model["weights"]
        rows["ML model suggestion"] = w["help"] + [w["industry"], w["field"], w["availability"]]
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption("Rule-based: compares approved vs denied pairs and boosts factors named in deny reasons "
               "and staff notes. ML model: logistic regression trained on every labeled pair to predict "
               "P(match succeeds); its coefficients become the suggested weights.")
    if model:
        acc = f"{model['cv_accuracy']:.0%}" if model["cv_accuracy"] is not None else "n/a"
        st.success(f"ML model trained on {model['n']} labeled pairs ({model['positives']} successful). "
                   f"Cross-validated accuracy: {acc}.")
    else:
        st.info(f"Cold start: the ML model needs at least {MIN_TRAIN} labeled pairs with both outcomes "
                f"(have {len(signals)}). Until then the rule-based suggestion is used.")
    if n_no == 0:
        st.info("Deny or reassign a few matches to see how the algorithm adapts.")
    elif can("train_apply_model"):
        c1, c2 = st.columns(2)
        if c1.button("Apply rule-based weights"):
            D["weights"] = new
            commit("Weights updated. The next matching run will use them.")
        if model and c2.button("Apply ML model weights", type="primary"):
            D["weights"], D["model"] = model["weights"], {k: model[k] for k in ("coef", "intercept", "n", "cv_accuracy")}
            commit("ML weights applied. Match cards now show predicted success.")


def reports_tab():
    appr = active_matches()
    rows = []
    for m in D["matches"]:
        ps = pair_stats(m) if m["status"] == "Approved" else {}
        rows.append({"student": S_BY[m["student_id"]]["name"], "mentor": M_BY[m["mentor_id"]]["name"],
                     "status": m["status"], "score": m["score"], "confidence": m["confidence"],
                     "sessions_attended": ps.get("attended"), "prework_pct": ps.get("prework %"),
                     "avg_rating": ps.get("rating"), "engagement": ps.get("engagement")})
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Matches", index=False)
        pd.DataFrame(D["students"]).astype(str).to_excel(xw, sheet_name="Students", index=False)
        pd.DataFrame(D["mentors"]).astype(str).to_excel(xw, sheet_name="Mentors", index=False)
        if D["emails"]:
            pd.DataFrame(D["emails"]).to_excel(xw, sheet_name="Emails", index=False)
    st.download_button("Full report (Excel)", buf.getvalue(), f"tandem_{D['cycle']['name']}.xlsx", type="primary")
    st.download_button("Matches + engagement (CSV)", df.to_csv(index=False), "tandem_matches.csv")
    st.download_button("Students (CSV)", pd.DataFrame(D["students"]).to_csv(index=False), "tandem_students.csv")
    st.download_button("Mentors (CSV)", pd.DataFrame(D["mentors"]).to_csv(index=False), "tandem_mentors.csv")
    if appr and D["cycle"]["released"]:
        st.markdown("**Satisfaction by session**")
        avg = []
        for i, c in enumerate(D["curriculum"]):
            r = [session_rec(pair_key(m), i)["checkin"][k]["rating"] for m in appr
                 for k in ("mentee", "mentor") if k in session_rec(pair_key(m), i)["checkin"]]
            avg.append(sum(r) / len(r) if r else 0)
        st.bar_chart(pd.Series(avg, index=[c["name"].split(":")[0] for c in D["curriculum"]]), color="#E5A823")
    if D["emails"]:
        with st.expander(f"Email log ({len(D['emails'])} sent, simulated)"):
            st.dataframe(pd.DataFrame(D["emails"]), hide_index=True)


def curriculum_tab():
    cyc = D["cycle"]
    st.caption("Prework, mentor prep and postwork are the same for every pair. Edit a lesson below or upload a CSV.")
    tmpl = pd.DataFrame([{"session": c["name"], "week": c["week"], "type": t, "item": it}
                         for c in D["curriculum"] for t in ("prework", "mentor_prep", "postwork") for it in c[t]])
    c1, c2 = st.columns(2)
    c1.download_button("Download curriculum (CSV template)", tmpl.to_csv(index=False), "tandem_curriculum.csv")
    up = c2.file_uploader("Import lesson plans (CSV: session, week, type, item)", type=["csv"], key="cur_up")
    if up is not None and st.button("Import curriculum", disabled=cyc["released"]):
        try:
            df = pd.read_csv(up)
            new = []
            for (name, week), g in df.groupby(["session", "week"], sort=False):
                new.append({"name": str(name), "week": int(week),
                            **{t: g[g["type"] == t]["item"].astype(str).tolist()
                               for t in ("prework", "mentor_prep", "postwork")}})
            new.sort(key=lambda c: c["week"])
            D["curriculum"], D["progress"] = new, {}
            commit(f"Imported {len(new)} sessions")
        except Exception as ex:
            st.error(f"Couldn't read that file: {ex}. Use the template columns.")
    if cyc["released"]:
        st.caption("Import is disabled after matches are released, so in-progress checklists aren't lost.")
    for i, c in enumerate(D["curriculum"]):
        with st.expander(f"Week {c['week']}: {c['name']}"):
            for key, label in (("prework", "Mentee prework"), ("mentor_prep", "Mentor prep"),
                               ("postwork", "Postwork")):
                txt = st.text_area(label + " (one per line)", "\n".join(c[key]), key=f"cur_{i}_{key}")
                items = [x.strip() for x in txt.splitlines() if x.strip()]
                if items != c[key] and st.button("Save", key=f"save_{i}_{key}"):
                    c[key] = items
                    for pk in D["progress"]:
                        rec = D["progress"][pk].get(str(i))
                        if rec:
                            field = {"prework": "mentee_pre", "mentor_prep": "mentor_pre", "postwork": "post"}[key]
                            rec[field] = (rec[field] + [False] * len(items))[:len(items)]
                    commit("Curriculum saved")



def matching_rules_form():
    cyc = D["cycle"]
    editable = can("edit_matching_rules")
    with st.form("matching_rules"):
        auto = st.toggle("Auto-approve strong matches", cyc.get("auto_approve", True), disabled=not editable,
                         help="When matching runs, any match at or above the score below is approved "
                              "automatically. Everything else stays Proposed for staff to review.")
        amin = st.slider("Auto-approve at or above this score", 0, 100, cyc.get("auto_approve_min", 50), step=5,
                         disabled=not auto or not editable)
        if st.form_submit_button("Save matching rules", disabled=not editable):
            cyc.update(auto_approve=auto, auto_approve_min=amin)
            commit("Matching rules saved" + (f": auto-approve at {amin}%+" if auto else ": auto-approve off"))


def admin_settings():
    cyc = D["cycle"]
    st.markdown("**Matching rules**")
    matching_rules_form()
    r1, r2 = st.columns(2)
    if today() > date.fromisoformat(cyc["apps_deadline"]):
        r1.caption(f"Applications closed on {cyc['apps_deadline']} (the deadline passed). "
                   "Move the deadline below to a later date to accept applications again.")
    elif cyc["apps_open"]:
        if r1.button("Close applications", disabled=not can("open_close_applications")):
            cyc["apps_open"] = False
            commit("Applications closed")
    elif r1.button("Reopen applications", disabled=not can("open_close_applications")):
        cyc["apps_open"] = True
        commit("Applications reopened")
    if r2.button("Match students to mentors", type="primary", disabled=not can("run_matching")):
        run_matching_now()
    st.caption("Matching happens only when an admin presses Match students to mentors. It matches everyone in one "
               "batch, so applying earlier gives no priority. Applies the next time matching runs. Matches already approved or denied are not changed. "
               "Auto-approved matches are marked as such and don't count as staff decisions when the model learns.")
    st.markdown("**Program calendar** (drives session dates and automated reminders)")
    c1, c2, c3 = st.columns(3)
    dl = c1.date_input("Application deadline", date.fromisoformat(cyc["apps_deadline"]))
    start = c2.date_input("Program start (orientation)", date.fromisoformat(cyc["start"]))
    clock = c3.date_input("Demo clock: pretend today is", today())
    if st.button("Save calendar"):
        cyc.update(apps_deadline=dl.isoformat(), start=start.isoformat(),
                   today=None if clock == date.today() else clock.isoformat())
        n = run_reminders()
        commit(f"Calendar saved. {n} reminder(s) sent.")
    st.caption("Reminders run automatically on every page load: prework due (2 days before), "
               "session tomorrow (1 day before), check-in missing (day after), postwork (3 days after). "
               "Each fires once. Emails show in Inboxes and Reports, and go out for real if enabled below.")
    sched = pd.DataFrame([{"Session": c["name"], "Week": c["week"], "Date": session_date(i)}
                          for i, c in enumerate(D["curriculum"])])
    st.dataframe(sched, hide_index=True)

    st.markdown("**Real email (Gmail SMTP)**")
    cfg = D.setdefault("email_cfg", {"live": False, "allow": "yopmail.com", "redirect": ""})
    user, pw = smtp_creds()
    if not (user and pw):
        st.info("Emails show in each user's Inbox. To also send real email, add SMTP_USER (your Gmail) and "
                "SMTP_PASSWORD (a Gmail app password) to .streamlit/secrets.toml, then restart.")
    else:
        st.caption(f"Sending from {user}. Only allowlisted addresses get real mail; seeded demo accounts never do.")
        live = st.toggle("Send real emails", cfg.get("live", False))
        allow = st.text_input("Allowlist (comma-separated addresses or domains)", cfg.get("allow", ""))
        redirect = st.text_input("Or redirect ALL emails to one test inbox", cfg.get("redirect", ""))
        c1, c2 = st.columns(2)
        if c1.button("Save email settings"):
            cfg.update(live=live, allow=allow, redirect=redirect.strip())
            commit("Email settings saved")
        test_to = c2.text_input("Send a test email to", redirect or "tandem-demo@yopmail.com")
        if c2.button("Send test email"):
            try:
                smtp_send(test_to, "Tandem test email", "Hi! This is a test from Tandem. Real email is working.")
                st.success(f"Sent to {test_to}")
            except Exception as e:
                st.error(f"Could not send: {e}")

    st.markdown("**Strong-match threshold**")
    thr = st.slider("Matches below this score are flagged 'no strong match found' for staff", 0, 90,
                    cyc.get("min_score", 50), step=5)
    if thr != cyc.get("min_score", 50) and st.button("Save threshold"):
        cyc["min_score"] = thr
        commit(f"Threshold set to {thr}%")

    st.markdown("**Dropdown options** (one per line; both forms and matching use these lists)")
    with st.form("options"):
        cols = st.columns(4)
        labels = {"industries": "Industries", "help_areas": "Goals", "majors": "Majors", "minors": "Minors"}
        new = {k: [x.strip() for x in c.text_area(labels[k], "\n".join(OPTS[k]), height=260).splitlines()
                   if x.strip()] for c, k in zip(cols, labels)}
        if st.form_submit_button("Save options"):
            if NO_MINOR not in new["minors"]:
                new["minors"].insert(0, NO_MINOR)
            if len(new["help_areas"]) < 3:
                st.error("Keep at least 3 goals.")
            else:
                D["options"] = new
                commit("Dropdown options saved")
    st.caption("Removing an option doesn't change existing profiles; people keep what they chose.")

    st.markdown("**Program cycle**")
    with st.form("new_cycle"):
        c1, c2 = st.columns(2)
        name = c1.text_input("New cycle name", "Fall 2027")
        sure = c2.checkbox("I understand: current cycle is archived, students must re-apply, "
                           "mentors stay in the pool")
        if st.form_submit_button("Archive and start new cycle") and sure:
            con = db()
            con.execute("INSERT INTO archives(cycle, archived_at, doc) VALUES (?,?,?)",
                        (D["cycle"]["name"], NOW(), json.dumps(D)))
            con.commit()
            carry = [dict(s, status="Approved", next_cycle=False, carried_over=True)
                     for s in D["students"] if s.get("next_cycle")]       # held back last cycle: first in line
            D.update(students=carry, matches=[], decisions=[], progress={}, unmatched=[], reminders_sent=[])
            D["cycle"].update(name=name, apps_open=True, released=False, today=None)
            commit(f"{name} started. Previous cycle archived.")
    arch = db().execute("SELECT cycle, archived_at FROM archives ORDER BY id DESC").fetchall()
    if arch:
        st.caption("Archived cycles: " + ", ".join(f"{c} ({a})" for c, a in arch))

    st.markdown("**Who can do what** (from the `PERMISSIONS` table in app.py)")
    roles = ["Mentee", "Mentor", "Staff", "Admin"]
    st.dataframe(pd.DataFrame([{"Feature": f.replace("_", " "), **{r: "✓" if r in rs else "" for r in roles}}
                               for f, rs in PERMISSIONS.items()]), hide_index=True)

    st.markdown("**Users and roles**")
    con = db()
    staff = con.execute("SELECT email, name, role FROM users WHERE role IN ('Admin','Staff')").fetchall()
    st.dataframe(pd.DataFrame(staff, columns=["Email", "Name", "Role"]), hide_index=True)
    with st.form("add_staff", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        em = c1.text_input("Email")
        nm = c2.text_input("Name")
        rl = c3.selectbox("Role", ["Staff", "Admin"])
        pw = c4.text_input("Temp password", type="password")
        if st.form_submit_button("Add staff account"):
            if em and nm and len(pw) >= 8 and not con.execute("SELECT 1 FROM users WHERE email=?",
                                                               (em.lower().strip(),)).fetchone():
                create_user(con, em, nm, rl, pw, rl.lower())
                st.session_state["toast"] = f"Added {nm} as {rl}"
                st.rerun()
            st.error("Need a new email, a name, and a password of 8+ characters.")

    st.markdown("**Demo tools**")
    c1, c2, c3 = st.columns(3)
    if c1.button("Simulate weeks 1 to 5 of activity", disabled=not active_matches() or not cyc["released"]):
        simulate()
    if c2.button("Load mid-program demo", help="Resets everything, then matches, approves strong matches, "
                 "releases and simulates weeks 1 to 5, so most logins show lesson progress."):
        load_midprogram_demo()
        st.session_state.clear()
        st.rerun()
    if c3.button("Reset demo data"):
        reset_db()
        st.session_state.clear()
        st.rerun()


GOOD_FB = ["Really helpful, great advice on my resume!", "Loved the session, very encouraging.",
           "Super useful tips on networking.", "Great mentor, clear and friendly."]
OK_FB = ["It was okay, a bit short.", "Decent session but we ran out of time.", "Fine, nothing special."]
BAD_FB = ["Not very useful, felt rushed.", "Mentor seemed distracted and unprepared.",
          "Mentor never showed up on time, frustrating."]


def simulate(rerun=True):
    rng = random.Random(42)
    con = db()
    for m in active_matches():
        pk = pair_key(m)
        engaged = 0.4 + 0.6 * rng.random()
        mt_ = M_BY[m["mentor_id"]]
        shared = [a for a in mt_["availability"] if a in S_BY[m["student_id"]]["availability"]]
        for i in range(3):
            rec = session_rec(pk, i)
            opts = [(d, a.split()[1]) for d in week_dates(i) for a in shared if a.split()[0] == f"{d:%a}"]
            if opts:
                d_, slot = rng.choice(opts)
                if not mentor_booked(mt_["id"], d_, slot, pk):
                    rec["schedule"] = {"date": d_.isoformat(), "slot": slot, "by": "mentee", "at": NOW()}
            rec["mentee_pre"] = [rng.random() < 0.3 + engaged * 0.7 for _ in rec["mentee_pre"]]
            rec["mentor_pre"] = [rng.random() < 0.8 for _ in rec["mentor_pre"]]
            rec["post"] = [rng.random() < engaged for _ in rec["post"]]
            if i == 2 and rng.random() < 0.4:
                break
            for role in ("mentee", "mentor"):
                rec["confirm"][role] = {"answer": "Yes, I'll be there" if rng.random() < 0.9 else
                                        "I need to reschedule", "note": "", "at": NOW()}
            happened = "Yes" if rng.random() < 0.6 + engaged * 0.4 else "No"
            for role in ("mentee", "mentor"):
                h = happened if rng.random() > 0.03 else ("No" if happened == "Yes" else "Yes")
                rating = max(1, min(5, round(2.5 + engaged * 2.5 + rng.uniform(-1, 1))))
                fb = rng.choice(GOOD_FB if rating >= 4 else OK_FB if rating == 3 else BAD_FB) \
                    if rng.random() < 0.6 else ""
                rec["checkin"][role] = {"happened": h, "on_time": "Yes" if rng.random() < 0.85 else "No",
                                        "rating": rating, "continue": "Yes" if rating >= 2 else "No",
                                        "feedback": fb, "at": NOW(),
                                        "sentiment": sentiment(fb), "safety": safety_flags(fb)}
        s, mt = S_BY[m["student_id"]], M_BY[m["mentor_id"]]
        con.executemany("INSERT INTO messages(pair, sender_role, sender_name, body, at) VALUES (?,?,?,?,?)",
                        [(pk, "mentee", s["name"], f"Hi {mt['name'].split()[0]}! Excited to work with you.", NOW()),
                         (pk, "mentor", mt["name"], "Likewise! Does our first shared slot work for orientation?", NOW())])
    con.commit()
    D["cycle"]["today"] = (session_date(2) + timedelta(days=2)).isoformat()
    run_reminders()
    msg = "Simulated the first 3 sessions, messages, and reminders (demo clock moved to week 5)"
    commit(msg) if rerun else save(D)


# ---------------- Unified dashboard ----------------
# One page for every role. Widgets and tool tabs are declared once, each with the permission it
# needs (see PERMISSIONS); the dashboard shows only what the signed-in role may use.
def my_pairs(user):
    """Approved matches this user can see (mentee: their one; mentor: all of theirs)."""
    if not D["cycle"]["released"]:
        return []
    if user["role"] == "Mentee":
        m = match_for_student(user.get("id"))
        return [m] if m else []
    if user["role"] == "Mentor":
        return [m for m in active_matches() if m["mentor_id"] == user.get("id")]
    return []


def my_profile_rec(user):
    if user["role"] not in ("Mentee", "Mentor"):
        return None
    return (S_BY if user["role"] == "Mentee" else M_BY).get(user.get("id"))


def pair_picker(user, key):
    pairs = my_pairs(user)
    if len(pairs) == 1:
        return pairs[0]
    labels = [S_BY[m["student_id"]]["name"] for m in pairs]
    return pairs[st.selectbox("Mentee", range(len(pairs)), format_func=lambda k: labels[k], key=key)]


def mentee_card(m):
    s = S_BY[m["student_id"]]
    with st.container(border=True):
        show_photo(s["email"])
        st.markdown(f"**{s['name']}** · {background(s)} · {s['year']} · "
                    f"interested in {s['industry']}")
        st.markdown("Goals: " + ", ".join(f"#{i+1} {h}" for i, h in enumerate(s["help_ranked"])))
        if s.get("about"):
            st.markdown(f"> {s['about']}")
        st.markdown(f"**Why you were matched:** {m['reason']}")


def stat_cards(user):
    pairs, rec = my_pairs(user), my_profile_rec(user)
    if pairs:
        stats = [pair_stats(m) for m in pairs]
        done, total = sum(s["attended"] for s in stats), len(D["curriculum"]) * len(pairs)
        items = [("Sessions completed", f"{done}/{total}"),
                 ("Prework done", f"{sum(s['prework %'] for s in stats) // len(stats)}%")]
        if user["role"] == "Mentor":
            return [("Mentees", f"{len(pairs)}/{rec['capacity']}")] + items
        pk = pair_key(pairs[0])
        nxt = current_session(pk)
        return items + [("Next session", f"{pair_session_date(pk, nxt):%b %d}")]
    if rec:
        return [("Application", rec["status"]), ("Matches", "Released" if D["cycle"]["released"] else "Not yet")]
    if can("view_progress_insights"):
        studs = [s for s in D["students"] if s["status"] == "Approved"]
        allm = active_matches(("Proposed", "Approved"))
        return [("Approved students", len(studs)),
                ("Approved mentors", sum(m["status"] == "Approved" for m in D["mentors"])),
                ("Matched", f"{100 * len(allm) // max(len(studs), 1)}%"),
                ("Mentor slots", sum(m["capacity"] for m in D["mentors"] if m["status"] == "Approved"))]
    return []


# ---- Dashboard data helpers ----
def photo_uri(email):
    row = db().execute("SELECT data FROM photos WHERE email=?", (email,)).fetchone()
    if not row:
        return None
    mime = "image/png" if row[0][:4] == b"\x89PNG" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(row[0]).decode()}"


def route_stops(user, pair=None):
    """The route map: six sessions for a pair, or the cycle pipeline for staff and admin."""
    if pair:
        pk = pair_key(pair)
        statuses, cur = pair_stats(pair)["statuses"], current_session(pk)
        return [{"name": c["name"], "when": f"Week {c['week']} · {pair_session_date(pk, i):%b %d}",
                 "state": "done" if s == "Attended" else "flag" if s in ("Missed", "Flagged")
                 else "current" if i == cur else "todo"}
                for i, (c, s) in enumerate(zip(D["curriculum"], statuses))]
    cyc, approved = D["cycle"], active_matches()
    proposed = len(active_matches(("Proposed",)))
    stats = [pair_stats(m) for m in approved] if cyc["released"] else []
    due = sum(s["due"] for s in stats)
    return [
        {"name": "Applications", "state": "done" if apps_closed() else "current",
         "when": "Closed" if apps_closed() else f"Open until {cyc['apps_deadline']}"},
        {"name": "Matching", "state": "done" if cyc["released"] or (approved and not proposed)
         else "current" if proposed or apps_closed() else "todo",
         "when": f"{proposed} to review" if proposed else f"{len(approved)} approved" if approved else "Not run yet"},
        {"name": "Release", "state": "done" if cyc["released"] else "current" if approved else "todo",
         "when": "Emails sent" if cyc["released"] else "Waiting on you" if approved else "After matching"},
        {"name": "Sessions", "state": "current" if cyc["released"] else "todo",
         "when": f"{100 * sum(s['attended'] for s in stats) // max(due, 1)}% completed" if cyc["released"]
         else "Starts after release"},
    ]


def hero_text(user):
    first, pairs, rec = user["name"].split()[0], my_pairs(user), my_profile_rec(user)
    if user["role"] == "Mentee" and pairs:
        return f"Hi {first}", f"You're paired with {M_BY[pairs[0]['mentor_id']]['name']}."
    if user["role"] == "Mentor" and pairs:
        return f"Hi {first}", f"You're mentoring {len(pairs)} of {rec['capacity']} possible mentees."
    if rec:
        return f"Hi {first}", "Your application is in. We'll email you when you have a match."
    cyc = D["cycle"]
    return "Program overview", (f"{cyc['name']} · Today {today():%b %d, %Y} · Signed in as {user['name']}")


# ---- Dashboard widgets (each takes the signed-in user) ----
def w_status(user):
    rec = my_profile_rec(user)
    if rec["status"] == "Deferred":
        st.info("We couldn't find the right mentor for you this cycle. You're first in line for the next recruitment cycle.")
        return
    if rec["status"] == "Rejected":
        st.info("Thank you for applying. We can't offer a spot this cycle.")
        return
    who = "mentor" if user["role"] == "Mentee" else "mentee"
    ui.html(f"<p style='margin:0 0 .6rem'>Your application is in. We'll email you as soon as you have a {who}. "
            "You can edit your profile any time while applications are open.</p>"
            + ui.chip(f"Status: {rec['status']}", "ok" if rec["status"] == "Approved" else "gold"))


def w_my_match(user):
    pairs = my_pairs(user)
    if user["role"] == "Mentee":
        m = pairs[0]
        s, mt = S_BY[m["student_id"]], M_BY[m["mentor_id"]]
        shared = [a for a in mt["availability"] if a in s["availability"]]
        ui.person(mt["name"], f"{mt['role']} at {mt['company']} · studied {background(mt)}",
                  [mt["industry"]],
                  why=m["reason"], photo_uri=photo_uri(mt["email"]),
                  extra=(f"<div style='margin-top:.4rem'>{ui.chips(shared[:4], 'ok')}</div>"
                         f"<div style='font-size:.85rem;color:var(--ink-2)'>You're both free at these times</div>")
                  + (f"<p style='margin:.6rem 0 0;font-style:italic'>“{ui.esc(mt['about'])}”</p>" if mt.get("about") else ""))
        return
    for m in pairs:
        s, ps = S_BY[m["student_id"]], pair_stats(m)
        with st.container(key=f"card_row_{m['student_id']}") if len(pairs) > 1 else st.container():
            ui.person(s["name"], f"{background(s)} · {s['year']}",
                      [f"#{i + 1} {h}" for i, h in enumerate(s["help_ranked"])], why=m["reason"],
                      photo_uri=photo_uri(s["email"]),
                      extra=ui.progress_line(f"Prework {ps['prework %']}% · {ps['attended']}/"
                                             f"{len(D['curriculum'])} sessions", ps["prework %"]))


def w_todo(user):
    m = my_pairs(user)[0]
    pk, total = pair_key(m), len(D["curriculum"])
    if pair_stats(m)["attended"] == total:
        ui.html("<p style='margin:0 0 .6rem'>You've completed all six sessions. Thank your mentor, finish the "
                "program survey, and stay in touch.</p>" + ui.chip("Program complete", "ok"))
        return
    i = current_session(pk)
    cur, rec = D["curriculum"][i], session_rec(pk, i)
    ui.html(f"<div style='margin-bottom:.7rem'><b>{ui.esc(cur['name'])}</b> · {pair_session_date(pk, i):%A, %b %d}</div>")
    pre = list(zip(cur["prework"], rec["mentee_pre"]))
    if all(done for _, done in pre):
        ui.html(ui.chip("Prework done. You're ready to meet your mentor.", "ok"))
    else:
        ui.checklist(pre)
    if session_status(rec) == "Attended":
        ui.html("<div style='margin:.8rem 0 .3rem;font-weight:600'>After the session</div>")
        ui.checklist(list(zip(cur["postwork"], rec["post"])))
    if st.button("Open this session", key="todo_open"):
        st.session_state["nav"] = "Sessions"
        st.rerun()


def w_lessons(user):
    m = my_pairs(user)[0]
    pk, cur_i = pair_key(m), current_session(pair_key(m))
    rows = []
    for i, (c, s) in enumerate(zip(D["curriculum"], pair_stats(m)["statuses"])):
        rec = session_rec(pk, i)
        label, tone = {"Attended": ("Completed", "ok"), "Missed": ("Missed", "warn"), "Flagged": ("Needs follow-up", "warn"),
                       "Rescheduled": ("Rescheduled", "amber")}.get(s, ("Up next", "") if i == cur_i else ("Upcoming", "plain"))
        if s.startswith("Waiting"):
            label, tone = "Waiting on " + s.split()[-1], "amber"
        rows.append({"name": c["name"], "when": f"Week {c['week']} · {pair_session_date(pk, i):%b %d}",
                     "status": label, "tone": tone, "future": s == "Upcoming" and i != cur_i,
                     "pre": (sum(rec["mentee_pre"]), len(rec["mentee_pre"])), "post": (sum(rec["post"]), len(rec["post"]))})
    ui.lesson_rows(rows)


def w_next_session(user):
    for m in my_pairs(user):
        pk = pair_key(m)
        nxt = current_session(pk)
        pre = session_rec(pk, nxt)["mentee_pre"]
        d = pair_session_date(pk, nxt)
        who = S_BY[m["student_id"]]["name"] if user["role"] == "Mentor" else M_BY[m["mentor_id"]]["name"]
        ui.next_session(f"{d:%b}", f"{d:%d}", D["curriculum"][nxt]["name"],
                        f"with {ui.esc(who)}<br>Prework {sum(pre)}/{len(pre)} done")


def w_attention(user):
    risk = sum(pair_stats(m)["at_risk"] for m in active_matches()) if D["cycle"]["released"] else 0
    ui.attention([(len(active_matches(("Proposed",))), "Proposed matches to approve or deny"),
                  (risk, "At-risk pairs to follow up with")])
    if can("run_matching"):
        cyc = D["cycle"]
        if not apps_closed():
            st.caption(f"Applications are open until {cyc['apps_deadline']}. Close them, then run matching.")
        elif not D["matches"]:
            st.warning("Applications are closed and matching hasn't been run yet.")
        elif not cyc["released"] and active_matches():
            st.warning("Approved matches are ready to release.")


def w_health(user):
    overview()


WIDGETS = [  # id, title, column, permission, show-when (optional), renderer
    ("status", "Your application",  "main", "apply_and_edit_profile",   lambda u: my_profile_rec(u) and not my_pairs(u), w_status),
    ("todo",   "This week",         "main", "submit_prework_postwork",  lambda u: u["role"] == "Mentee" and bool(my_pairs(u)), w_todo),
    ("match",  "Your match" ,       "main", "view_own_match",           lambda u: bool(my_pairs(u)),                    w_my_match),
    ("lessons", "Lesson progress",  "main", "submit_prework_postwork",  lambda u: u["role"] == "Mentee" and bool(my_pairs(u)), w_lessons),
    ("next",   "Next session",      "side", "session_confirm_feedback", lambda u: bool(my_pairs(u)),                    w_next_session),
    ("attn",   "Needs attention",   "main", "review_matches",           None,                                           w_attention),
    ("health", "Program health",    "main", "view_progress_insights",   None,                                           w_health),
]


def goals_card(user):
    rec, role = my_profile_rec(user), user["role"]
    if role == "Mentee" and rec:
        with st.container(key="card_goals"):
            ui.card_title("Your goals")
            ui.numbered([(i + 1, h) for i, h in enumerate(rec["help_ranked"])])
    elif role == "Mentor" and rec:
        with st.container(key="card_goals"):
            ui.card_title("Goals you can help with")
            ui.html(ui.chips(rec.get("can_help", [])))


# ---- Pages (one per sidebar entry) ----
def tool_sessions(user):
    m = pair_picker(user, "pick_sess")
    if user["role"] == "Mentor":
        mentee_card(m)
    session_panel(m, user["role"].lower())


def tool_messages(user):
    m = pair_picker(user, "pick_msg")
    messages_panel(m, user["role"].lower(), my_profile_rec(user)["name"])


def tool_profile(user):
    profile_tab(user, my_profile_rec(user), user["role"])


def page_home(user):
    ui.kpis(stat_cards(user))
    shown = [w for w in WIDGETS if can(w[3]) and (w[4] is None or w[4](user))]
    pairs = my_pairs(user)
    if pairs or can("view_progress_insights"):
        with st.container(key="card_route"):
            ui.card_title("Your 12-week route" if pairs else "Where the cycle is")
            pair = pair_picker(user, "pick_home") if pairs else None
            ui.route(route_stops(user, pair))
    main, side = st.columns([2.1, 1], gap="large")
    with main:
        for wid, wtitle, zone, _, _, render in shown:
            if zone == "main":
                with st.container(key=f"card_{wid}"):
                    ui.card_title(wtitle)
                    render(user)
    with side:
        for wid, wtitle, zone, _, _, render in shown:
            if zone == "side":
                with st.container(key=f"card_{wid}"):
                    ui.card_title(wtitle)
                    render(user)
        goals_card(user)
        mine = [e for e in D["emails"] if e["to"] == user["email"]][-5:][::-1]
        with st.container(key="card_updates"):
            ui.card_title("Updates")
            ui.updates([(e["subject"], e["at"]) for e in mine])


has_pairs = lambda u: bool(my_pairs(u))
PAGES = [  # label, icon, group, permission, show-when, renderer, one-line description
    ("Dashboard",     "dashboard",       "Workspace",      None, None, page_home, None),
    ("Sessions",      "event",           "Workspace",      "session_confirm_feedback", has_pairs, tool_sessions,
     "Prework, check-ins and notes for each session."),
    ("Messages",      "chat_bubble",     "Workspace",      "pair_messaging", has_pairs, tool_messages,
     "A private thread with your match. Staff can't read it."),
    ("My profile",    "person",          "Workspace",      "apply_and_edit_profile", None, tool_profile,
     "What your match sees about you."),
    ("Matching",      "group",           "Program",        "review_matches", None,
     lambda u: matching_tab(can("program_settings")), "Review proposed matches. Approve, deny or reassign."),
    ("Progress",      "trending_up",     "Program",        "view_progress_insights", None, lambda u: progress_tab(),
     "Engagement for every pair."),
    ("Flags",         "flag",            "Program",        "view_progress_insights", None, lambda u: flags_tab(),
     "Sessions and feedback that need a human."),
    ("Insights",      "insights",        "Program",        "view_progress_insights", None, lambda u: insights_tab(),
     "Mentor supply and what the model has learned."),
    ("Curriculum",    "menu_book",       "Program",        "edit_curriculum", None, lambda u: curriculum_tab(),
     "Lessons, prework and postwork. The same for every mentee."),
    ("Announcements", "campaign",        "Program",        "send_announcements", None, lambda u: announcements_tab(),
     "Send a message to everyone, or to a group."),
    ("Scorecards",    "grade",           "Administration", "view_scorecards", None, lambda u: scorecards_tab(),
     "Participation grades. Visible to admins only."),
    ("Users",         "manage_accounts", "Administration", "manage_users", None, lambda u: users_tab(),
     "Find people, edit names, reset passwords."),
    ("Reports",       "summarize",       "Administration", "export_reports", None, lambda u: reports_tab(),
     "Download matches, engagement and email logs."),
    ("Settings",      "settings",        "Administration", "program_settings", None, lambda u: admin_settings(),
     "Calendar, email, dropdown options and cycles."),
]


def sidebar(user, pages, current):
    """Navigation lives in the sidebar. The small panel button switches it between full and icon-only."""
    rail = st.session_state.get("rail", False)
    if rail:
        ui.rail_css([p[0] for p in pages])
    with st.sidebar:
        if rail:
            toggle = st.button("", key="railtoggle", icon=":material/left_panel_open:", type="tertiary",
                               width="stretch")
        else:
            ui.brand()
            toggle = st.button("", key="railtoggle", icon=":material/left_panel_close:", type="tertiary",
                               help="Collapse sidebar")
        if toggle:
            st.session_state["rail"] = not rail
            st.rerun()
        group = None
        for n, (label, icon, grp, *_) in enumerate(pages):
            if grp != group and len(pages) > 1:
                if rail:
                    ui.separator()
                else:
                    ui.nav_heading(grp)
                group = grp
            on = label == current
            if st.button(label, key=f"{'navon' if on else 'nav'}_{n}", icon=f":material/{icon}:",
                         type="tertiary", width="stretch") and not on:
                st.session_state["nav"] = label
                st.rerun()
        ui.me_block(user["name"], user["role"], photo_uri(user["email"]), rail)
        if st.button("" if rail else "Log out", key="logout", icon=":material/logout:", type="tertiary",
                     width="stretch"):
            st.session_state.clear()
            st.rerun()
        if not rail:
            st.caption("Responsible AI: matches use only career tags you chose. "
                       "Every match is explained and approved by a human.")


def dashboard(user):
    cyc = D["cycle"]
    first = user["name"].split()[0]
    if user["role"] in ("Mentee", "Mentor") and not my_profile_rec(user):
        sidebar(user, [], None)
        ui.page_header(f"Hi {first}", f"Start your {user['role'].lower()} application.")
        if apps_closed():
            st.warning("Applications are closed for this cycle.")
            return
        st.caption("Everything is a dropdown or checkbox. Takes about 3 minutes." if user["role"] == "Mentee"
                   else "Mentors need at least 1 year of work experience.")
        (student_form if user["role"] == "Mentee" else mentor_form)(user)
        return
    pages = [p for p in PAGES if (p[3] is None or can(p[3])) and (p[4] is None or p[4](user))]
    current = st.session_state.get("nav")
    if current not in [p[0] for p in pages]:
        current = "Dashboard"
    sidebar(user, pages, current)
    label, _, _, _, _, render, blurb = next(p for p in pages if p[0] == current)
    status = (ui.chip("Applications closed" if apps_closed() else "Applications open", "plain" if apps_closed() else "ok")
              + ui.chip("Matches released" if cyc["released"] else "Matches not released", "ok" if cyc["released"] else "plain"))
    if current == "Dashboard":
        title, sub = hero_text(user)
        ui.page_header(title, sub, status)
    else:
        ui.page_header(label, blurb, "" if current == "Matching" else status)
    render(user)


# ---------------- Main ----------------
if run_reminders():          # automated reminders: fire anything newly due
    save(D)
if "toast" in st.session_state:
    st.toast(st.session_state.pop("toast"))

user = st.session_state.get("user")
if not user:
    login()
else:
    dashboard(user)