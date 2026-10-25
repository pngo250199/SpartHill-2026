"""Tandem matching engine.

Pipeline: hard filters -> weighted score (0-100) -> Hungarian assignment
(mentor capacity = slots) -> confidence + plain-language reason.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

# ---------- Shared dropdown options (same lists on both forms) ----------
INDUSTRIES = ["Semiconductors/Hardware", "Embedded Systems", "Software", "AI/ML/Data",
              "Product Management", "Sales/Business", "Consulting", "Finance",
              "Healthcare/Biotech", "Design/UX",
              "Aerospace/Defense", "Automotive/Transportation", "Cybersecurity", "Energy/Utilities",
              "Telecommunications", "Media/Entertainment", "Gaming", "Education/EdTech",
              "Government/Public Sector", "Nonprofit", "Retail/E-commerce", "Manufacturing",
              "Pharmaceuticals", "Real Estate/Construction", "Hospitality/Travel", "Law/Legal",
              "Marketing/Advertising"]
HELP_AREAS = ["Resume Review", "LinkedIn/Branding", "Behavioral Interviews",
              "Technical Interviews", "Networking", "Internship Search",
              "Job Search Strategy", "Career Exploration", "Grad School Advice",
              "Industry Insights",
              "Portfolio Building", "Public Speaking", "Leadership Skills",
              "Research Opportunities", "Starting a Company", "Work-Life Balance", "Building Confidence",
              "Time Management", "Professional Etiquette"]
# Every SJSU college and the majors (undergraduate and graduate programs) it offers. A major listed here shows up
# when its college is picked. Majors added later in Settings have no college, so they show under every college.
COLLEGE_MAJORS = {
    "Charles W. Davidson College of Engineering": [
        "Aerospace Engineering", "Aviation", "Biomedical Engineering", "Chemical Engineering", "Civil Engineering",
        "Computer Engineering", "Electrical Engineering", "Engineering Technology", "Environmental Engineering",
        "Human Factors and Ergonomics", "Industrial and Systems Engineering", "Materials Engineering",
        "Mechanical Engineering", "Software Engineering", "Cybersecurity Engineering", "Other Engineering"],
    "College of Health and Human Sciences": [
        "Health Science", "Hospitality Management", "Kinesiology", "Nursing", "Nutrition and Food Science",
        "Occupational Therapy", "Public Health", "Recreation", "Social Work", "Speech-Language Pathology",
        "Communicative Disorders and Sciences", "Environmental Health", "Athletic Training", "Gerontology"],
    "College of Humanities and the Arts": [
        "Advertising", "Animation and Illustration", "Art History", "Chinese", "Communication Studies",
        "Comparative World Literature", "Creative Writing", "Dance", "Digital Media Art", "English", "Film and Theatre",
        "French", "German", "Graphic Design", "History", "Humanities", "Industrial Design", "Interior Design",
        "Italian", "Japanese", "Journalism", "Linguistics", "Music", "Philosophy", "Photography", "Public Relations",
        "Radio, Television and Film", "Religious Studies", "Spanish", "Studio Art", "Theatre Arts", "TESOL"],
    "College of Science": [
        "Applied Mathematics", "Artificial Intelligence", "Astronomy", "Biochemistry", "Bioinformatics",
        "Biological Sciences", "Chemistry", "Computer Science", "Data Science", "Geology", "Marine Science",
        "Mathematics", "Meteorology and Climate Science", "Microbiology", "Molecular Biology", "Physics",
        "Statistics", "Software Systems"],
    "College of Social Sciences": [
        "African American Studies", "Anthropology", "Asian American Studies", "Behavioral Science",
        "Child and Adolescent Development", "Criminology", "Economics", "Environmental Studies", "Gender Studies",
        "Geography", "Global Studies", "Justice Studies", "Mexican American Studies", "Native American Studies",
        "Political Science", "Psychology", "Public Administration", "Social Science", "Sociology",
        "Urban and Regional Planning"],
    "Connie L. Lurie College of Education": [
        "Counselor Education", "Early Childhood Education", "Educational Leadership", "Elementary Education",
        "Instructional Technology", "Liberal Studies", "Secondary Education", "Special Education", "Teacher Education"],
    "Lucas College and Graduate School of Business": [
        "Accounting", "Business Administration", "Business Analytics", "Entrepreneurship", "Finance",
        "Global Business", "Human Resource Management", "Management Information Systems", "Marketing",
        "Real Estate", "Supply Chain and Operations Management", "Taxation", "Transportation Management"],
    "School of Information": [
        "Archives and Records Management", "Information Science", "Information and Data Science",
        "Library and Information Science", "Digital Assets and Information Management"],
    "College of Professional and Global Education": [
        "Leadership and Management", "Professional Studies", "Project Management", "Technology and Innovation Management"],
}
COLLEGES = list(COLLEGE_MAJORS) + ["Other"]

# Converts detailed SJSU college names into general categories
# so students and mentors can still match by college.
GENERIC_COLLEGE = {
    "Charles W. Davidson College of Engineering": "Engineering",
    "College of Health and Human Sciences": "Health",
    "College of Humanities and the Arts": "Humanities and Arts",
    "College of Science": "Science",
    "College of Social Sciences": "Social Sciences",
    "Connie L. Lurie College of Education": "Education",
    "Lucas College and Graduate School of Business": "Business",
    "School of Information": "Information",
    "College of Professional and Global Education": "Professional and Global Education",
    "Other": "Other",
}

GENERIC_COLLEGES = sorted(set(GENERIC_COLLEGE.values()))

MAJOR_COLLEGE = {
    major: college
    for college, majors in COLLEGE_MAJORS.items()
    for major in majors
}

FIELDS = sorted(MAJOR_COLLEGE) + ["Other"]
MAJOR_COLLEGE = {mj: col for col, mjs in COLLEGE_MAJORS.items() for mj in mjs}
FIELDS = sorted(MAJOR_COLLEGE) + ["Other"]
# Field points: major<->major = full; any match involving a minor = partial
MINOR_CREDIT = 0.6
COLLEGE_CREDIT = 0.3   # same college, different major (SJSU and generic college names compare equal)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIMES = ["Morning", "Afternoon", "Evening"]          # 8-12, 12-5, 5-9 PT
AVAILABILITY = [f"{d} {t}" for d in DAYS for t in TIMES]  # 21 time slots
NO_MINOR = "None"
MINORS = [NO_MINOR] + FIELDS
MODES = ["In person", "Virtual", "Either"]
YEARS = ["Freshman", "Sophomore", "Junior", "Senior", "Masters", "PhD"]
EXPERIENCE = ["1-2", "3-5", "6-10", "10+"]  # mentors need at least 1 year
SCHOOLS = ["San Jose State University", "Other CSU", "University of California", "Other US university",
           "International university"]
NOT_SURE = "Not sure yet"
SJSU_LINKS = ["No SJSU connection", "SJSU alum", "SJSU alum, still involved (clubs, events, hiring)",
              "Adjunct / lecturer at SJSU"]
SJSU_LINK_CREDIT = {SJSU_LINKS[0]: 0.0, SJSU_LINKS[1]: 0.5, SJSU_LINKS[2]: 0.75, SJSU_LINKS[3]: 1.0}

# Partial credit for related industries (explainable, no embeddings needed)
RELATED_INDUSTRIES = {
    frozenset(["Semiconductors/Hardware", "Embedded Systems"]): 0.6,
    frozenset(["Software", "AI/ML/Data"]): 0.6,
    frozenset(["Embedded Systems", "Software"]): 0.4,
    frozenset(["Product Management", "Software"]): 0.4,
    frozenset(["Sales/Business", "Consulting"]): 0.5,
    frozenset(["Finance", "Consulting"]): 0.4,
    frozenset(["Product Management", "Design/UX"]): 0.5,
    frozenset(["Cybersecurity", "Software"]): 0.5,
    frozenset(["Cybersecurity", "AI/ML/Data"]): 0.3,
    frozenset(["Automotive/Transportation", "Embedded Systems"]): 0.5,
    frozenset(["Aerospace/Defense", "Embedded Systems"]): 0.4,
    frozenset(["Energy/Utilities", "Manufacturing"]): 0.4,
    frozenset(["Media/Entertainment", "Gaming"]): 0.5,
    frozenset(["Gaming", "Software"]): 0.5,
    frozenset(["Media/Entertainment", "Design/UX"]): 0.4,
    frozenset(["Pharmaceuticals", "Healthcare/Biotech"]): 0.6,
    frozenset(["Marketing/Advertising", "Sales/Business"]): 0.5,
}

# Score weights (points). Help-area points are per student rank #1/#2/#3.
WEIGHTS = {"help": [25, 15, 10], "industry": 30, "field": 10, "availability": 10}


# ---------- Filters ----------
def eligible_mentor(m):
    return m["experience"] != "<1"


def passes_filters(s, m):
    """Return (ok, reason_if_not)."""
    if not eligible_mentor(m):
        return False, "mentor under 1 year experience"
    if not set(s["availability"]) & set(m["availability"]):
        return False, "no shared availability"
    if "Either" not in (s["mode"], m["mode"]) and s["mode"] != m["mode"]:
        return False, "meeting mode mismatch"
    if m.get("pref_years") and s.get("year") not in m["pref_years"]:
        return False, "mentor prefers other class years"
    return True, ""


# ---------- Scoring ----------
def industry_credit(a, b):
    if a == b:
        return 1.0
    return RELATED_INDUSTRIES.get(frozenset([a, b]), 0.0)


def college_of(p):
    """Generic college name, so a student's 'Charles W. Davidson College of Engineering' equals a mentor's 'Engineering'."""
    c = p.get("college")
    return GENERIC_COLLEGE.get(c, c)


def field_credit(s, m):
    """1.0 if majors match, 0.6 if a minor matches the other's major or minor, 0.3 if only the college matches."""
    if s["field"] == m["field"]:
        return 1.0, f"same major ({m['field']})"
    s_set = {s["field"], s.get("minor", NO_MINOR)} - {NO_MINOR, "Other"}
    m_set = {m["field"], m.get("minor", NO_MINOR)} - {NO_MINOR, "Other"}
    common = s_set & m_set
    if common:
        return MINOR_CREDIT, f"shared background via minor ({sorted(common)[0]})"
    college = college_of(s)
    if college and college == college_of(m) and college != "Other":
        return COLLEGE_CREDIT, f"same college ({college})"
    return 0.0, ""


def sjsu_credit(s, m):
    """How connected the mentor is to SJSU today (adjunct > involved alum > alum)."""
    return SJSU_LINK_CREDIT.get(m.get("sjsu_link", SJSU_LINKS[0]), 0.0)


# Inside each factor's points: Industry factor = industry alone (same = full, related = partial);
# Background factor = 60% major/minor + 40% SJSU connection. Totals stay at 100.
def score_pair(s, m, weights=WEIGHTS):
    """Return (total 0-100, breakdown dict of factor -> points)."""
    help_pts = sum(w for area, w in zip(s["help_ranked"], weights["help"])
                   if area in m["can_help"])
    ind_pts = weights["industry"] * industry_credit(s["industry"], m["industry"])
    field_pts = weights["field"] * (0.6 * field_credit(s, m)[0] + 0.4 * sjsu_credit(s, m))
    shared = len(set(s["availability"]) & set(m["availability"]))
    avail_pts = weights["availability"] * min(shared, 3) / 3   # 3+ shared slots = full
    breakdown = {"Help areas": help_pts, "Industry": ind_pts,
                 "Background": field_pts, "Availability": avail_pts}
    return round(sum(breakdown.values()), 1), breakdown


def explain(s, m, breakdown):
    parts = []
    covered = [f"#{i+1} {a}" for i, a in enumerate(s["help_ranked"]) if a in m["can_help"]]
    if covered:
        parts.append("covers " + ", ".join(covered))
    if s["industry"] == m["industry"]:
        parts.append(f"same industry ({m['industry']})")
    elif breakdown["Industry"] > 0:
        parts.append(f"related industry ({m['industry']})")
    if field_credit(s, m)[1]:
        parts.append(field_credit(s, m)[1])
    if SJSU_LINK_CREDIT.get(m.get("sjsu_link"), 0) >= 0.75:
        parts.append(f"{m['sjsu_link'].split(' (')[0].lower()}")
    shared = [a for a in AVAILABILITY if a in s["availability"] and a in m["availability"]]
    more = f" +{len(shared) - 3} more" if len(shared) > 3 else ""
    parts.append("both free " + ", ".join(shared[:3]) + more)
    return "; ".join(parts)


def gaps(s, m):
    """What this mentor does NOT cover for the student (shown to staff)."""
    out = [f"does not cover #{i+1} {a}" for i, a in enumerate(s["help_ranked"])
           if a not in m["can_help"]]
    if industry_credit(s["industry"], m["industry"]) == 0:
        out.append(f"different industry ({m['industry']})")
    return out


def confidence(score, margin):
    if score >= 75 and margin >= 10:
        return "High"
    if score < 55:
        return "Low"
    return "Medium"


# ---------- Ranking for one student ----------
def rank_mentors(s, mentors, top_k=3, weights=WEIGHTS):
    ranked = []
    for m in mentors:
        ok, _ = passes_filters(s, m)
        if not ok:
            continue
        total, bd = score_pair(s, m, weights)
        ranked.append({"mentor_id": m["id"], "score": total, "breakdown": bd,
                       "reason": explain(s, m, bd), "gaps": gaps(s, m)})
    ranked.sort(key=lambda r: -r["score"])
    return ranked[:top_k]


# ---------- Global assignment ----------
def run_matching(students, mentors, locked=None, weights=WEIGHTS, min_score=1, excluded=None):
    """Assign students to mentors 1:1 (or up to mentor capacity).

    locked: list of (student_id, mentor_id) already approved by staff; kept as is
            and they consume mentor capacity.
    excluded: set of (student_id, mentor_id) pairs staff denied; never re-proposed.
    Returns (matches, unmatched).
    """
    locked = locked or []
    excluded = set(excluded or [])
    locked_students = {s for s, _ in locked}
    used = {}
    for _, m_id in locked:
        used[m_id] = used.get(m_id, 0) + 1

    pool_s = [s for s in students if s["id"] not in locked_students]
    m_by_id = {m["id"]: m for m in mentors}

    # Expand each mentor into capacity slots
    slots = []
    for m in mentors:
        if not eligible_mentor(m):
            continue
        free = m.get("capacity", 1) - used.get(m["id"], 0)
        slots += [m["id"]] * max(free, 0)

    matches, unmatched = [], []
    if pool_s and slots:
        BIG = 1e6
        cost = np.full((len(pool_s), len(slots)), BIG)
        cache = {}
        for i, s in enumerate(pool_s):
            for j, m_id in enumerate(slots):
                key = (s["id"], m_id)
                if key not in cache:
                    ok, _ = passes_filters(s, m_by_id[m_id])
                    ok = ok and key not in excluded
                    cache[key] = score_pair(s, m_by_id[m_id], weights) if ok else None
                if cache[key] and cache[key][0] >= min_score:
                    cost[i, j] = -cache[key][0]
        rows, cols = linear_sum_assignment(cost)
        assigned = set()
        for i, j in zip(rows, cols):
            if cost[i, j] >= BIG:
                continue
            s, m = pool_s[i], m_by_id[slots[j]]
            total, bd = cache[(s["id"], m["id"])]
            alts = [a for a in rank_mentors(s, mentors, top_k=6, weights=weights)
                    if (s["id"], a["mentor_id"]) not in excluded]
            runner_up = next((a["score"] for a in alts if a["mentor_id"] != m["id"]), 0)
            matches.append({
                "student_id": s["id"], "mentor_id": m["id"], "score": total,
                "breakdown": bd, "confidence": confidence(total, total - runner_up),
                "reason": explain(s, m, bd), "gaps": gaps(s, m),
                "alternatives": [a for a in alts if a["mentor_id"] != m["id"]][:3],
            })
            assigned.add(s["id"])
        pool_left = [s for s in pool_s if s["id"] not in assigned]
    else:
        pool_left = pool_s

    for s in pool_left:
        unmatched.append({"student_id": s["id"], "why": why_unmatched(s, mentors)})
    return matches, unmatched


def why_unmatched(s, mentors):
    """Responsible AI framing: the gap is in our mentor pool, not the student."""
    reasons, compatible = {}, 0
    for m in mentors:
        ok, r = passes_filters(s, m)
        if ok:
            compatible += 1
        else:
            reasons[r] = reasons.get(r, 0) + 1
    if compatible:
        return (f"{compatible} compatible mentor(s), all at capacity. "
                f"Recruit more mentors in {s['industry']}")
    top = max(reasons, key=reasons.get)
    return f"Mentor pool gap: most mentors excluded for '{top}'"


# ---------- Supply gap analysis ----------
def supply_gap(students, mentors, industries=None, help_areas=None):
    elig = [m for m in mentors if eligible_mentor(m)]
    rows = []
    for ind in industries or INDUSTRIES:
        demand = sum(s["industry"] == ind for s in students)
        supply = sum(m.get("capacity", 1) for m in elig if m["industry"] == ind)
        if demand:
            rows.append({"Type": "Industry", "Tag": ind, "Students": demand,
                         "Mentor slots": supply,
                         "Coverage %": round(100 * min(supply / demand, 1), 0)})
    for area in help_areas or HELP_AREAS:
        demand = sum(s["help_ranked"][0] == area for s in students)  # #1 priority
        supply = sum(area in m["can_help"] for m in elig)
        if demand:
            rows.append({"Type": "Goal (#1)", "Tag": area, "Students": demand,
                         "Mentor slots": supply,
                         "Coverage %": round(100 * min(supply / demand, 1), 0)})
    return sorted(rows, key=lambda r: r["Coverage %"])


# ---------- Extra credit: learn weights from staff decisions ----------
# Deny-reason checklist -> the scoring factor that reason points at
REASON_FACTOR = {
    "Industry mismatch": "Industry",
    "Goals not covered": "Help areas",
    "Help areas not covered": "Help areas",   # older saved decisions
    "Major/minor background mismatch": "Background",
    "Schedule doesn't really work": "Availability",
}


def learn_weights(decisions, students, mentors, base=WEIGHTS, lr=0.5, reason_boost=0.1):
    """Suggest new weights from staff decisions and session outcomes.

    decisions: list of {student_id, mentor_id, approved: bool, reasons: [..]}.
    Two signals, both explainable:
      1. Factors that score higher in approved/successful pairs than in denied/
         unsuccessful ones get more weight.
      2. Each checked deny reason (e.g. "Industry mismatch") adds a direct boost
         to its factor, so staff can tell the algorithm what it got wrong.
    Total always stays at 100.
    """
    s_by = {s["id"]: s for s in students}
    m_by = {m["id"]: m for m in mentors}
    keys = ["Help areas", "Industry", "Background", "Availability"]
    caps = {"Help areas": sum(base["help"]), "Industry": base["industry"],
            "Background": base["field"], "Availability": base["availability"]}
    app, den = {k: [] for k in keys}, {k: [] for k in keys}
    reason_counts = {k: 0 for k in keys}
    for d in decisions:
        _, bd = score_pair(s_by[d["student_id"]], m_by[d["mentor_id"]], base)
        for k in keys:
            (app if d["approved"] else den)[k].append(bd[k] / caps[k])
        for r in d.get("reasons", []):
            if r in REASON_FACTOR:
                reason_counts[REASON_FACTOR[r]] += 1
        if not d["approved"]:
            for f in note_factors(d.get("note", "")):   # free-text staff notes count too
                reason_counts[f] += 1
    n_den = sum(not d["approved"] for d in decisions)
    if not n_den or not any(app.values()):
        return base
    new = {}
    for k in keys:
        diff = float((np.mean(app[k]) if app[k] else 0) - (np.mean(den[k]) if den[k] else 0))
        boost = reason_boost * reason_counts[k] / n_den * 10
        new[k] = max(caps[k] * (1 + lr * diff + boost), 1)
    scale = 100 / sum(new.values())
    h = new["Help areas"] * scale / sum(base["help"])
    return {"help": [round(w * h, 1) for w in base["help"]],
            "industry": round(new["Industry"] * scale, 1),
            "field": round(new["Background"] * scale, 1),
            "availability": round(new["Availability"] * scale, 1)}


# ---------- Text feedback -> signals ----------
# Free-text notes are turned into numbers the algorithm can use:
#   1) sentiment (-1 very negative .. +1 very positive) via VADER
#   2) which scoring factor a staff note talks about (keyword map)
#   3) safety flags that a human must review (never auto-actioned)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
except Exception:          # library missing: fall back to neutral
    _VADER = None

FACTOR_KEYWORDS = {
    "Industry": ["industry", "company", "field of work", "sector"],
    "Help areas": ["resume", "linkedin", "interview", "networking", "help with", "goal", "topic"],
    "Background": ["major", "minor", "degree", "background", "coursework"],
    "Availability": ["schedule", "time", "availability", "timezone", "busy", "reschedul", "conflict"],
}
SAFETY_KEYWORDS = ["rude", "harass", "uncomfortable", "inappropriate", "unsafe", "disrespect",
                   "never showed", "no show", "no-show", "ghost", "offensive"]


def sentiment(text):
    if not text or not text.strip() or _VADER is None:
        return 0.0
    return round(_VADER.polarity_scores(text)["compound"], 3)


def note_factors(text):
    t = (text or "").lower()
    return [f for f, kws in FACTOR_KEYWORDS.items() if any(k in t for k in kws)]


def safety_flags(text):
    t = (text or "").lower()
    return [k for k in SAFETY_KEYWORDS if k in t]


# ---------- ML: logistic regression on match outcomes ----------
FEATURES = ["Help areas", "Industry", "Background", "Availability"]
MIN_TRAIN = 30   # cold start: below this many labeled pairs, keep hand-set weights


def feature_vector(s, m, base=WEIGHTS):
    _, bd = score_pair(s, m, base)
    caps = {"Help areas": sum(base["help"]), "Industry": base["industry"],
            "Background": base["field"], "Availability": base["availability"]}
    return [bd[k] / caps[k] for k in FEATURES]


def train_model(examples, students, mentors):
    """examples: [{student_id, mentor_id, approved: bool}] (staff decisions + session outcomes).

    Trains logistic regression: P(pair succeeds | factor scores). Returns None during
    cold start (too little data or only one class). The positive coefficients become
    suggested weights (rescaled to 100 points), so the model stays explainable.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    s_by = {s["id"]: s for s in students}
    m_by = {m["id"]: m for m in mentors}
    X, y = [], []
    for e in examples:
        if e["student_id"] in s_by and e["mentor_id"] in m_by:
            X.append(feature_vector(s_by[e["student_id"]], m_by[e["mentor_id"]]))
            y.append(int(e["approved"]))
    if len(y) < MIN_TRAIN or len(set(y)) < 2:
        return None
    clf = LogisticRegression(class_weight="balanced", max_iter=1000).fit(X, y)
    folds = min(5, min(y.count(0), y.count(1)))
    acc = float(np.mean(cross_val_score(LogisticRegression(class_weight="balanced", max_iter=1000),
                                        X, y, cv=folds))) if folds >= 2 else None
    coef = dict(zip(FEATURES, clf.coef_[0].tolist()))
    pos = {k: max(v, 0.05) for k, v in coef.items()}      # keep every factor at least a little
    scale = 100 / sum(pos.values())
    h = pos["Help areas"] * scale / sum(WEIGHTS["help"])
    weights = {"help": [round(w * h, 1) for w in WEIGHTS["help"]],
               "industry": round(pos["Industry"] * scale, 1),
               "field": round(pos["Background"] * scale, 1),
               "availability": round(pos["Availability"] * scale, 1)}
    return {"coef": coef, "intercept": float(clf.intercept_[0]), "n": len(y),
            "positives": sum(y), "cv_accuracy": acc, "weights": weights}


def predict_success(model, s, m):
    if not model:
        return None
    x = feature_vector(s, m)
    z = model["intercept"] + sum(model["coef"][k] * v for k, v in zip(FEATURES, x))
    return 1 / (1 + np.exp(-z))