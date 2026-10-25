"""Generate realistic fake mentors and mentees for the demo."""
import json
import random
from matching import (NO_MINOR, DAYS, TIMES, MODES, YEARS, COLLEGES, MAJOR_COLLEGE,
                      SCHOOLS, SJSU_LINKS, NOT_SURE)

# The demo people are drawn from these original lists (fixed RNG seed), so they stay the same even though the
# app's dropdowns now hold every SJSU major, more industries, goals and career paths.
GRAD_TERMS = ["Spring 2027", "Fall 2027", "Spring 2028", "Fall 2028", "Spring 2029", "Fall 2029",
              "2030 or later"]  # still drawn (RNG stream), no longer used
GRAD_PERIODS = ["2024 or later", "2020-2023", "2015-2019", "2010-2014", "Before 2010"]  # still drawn (RNG stream), no longer used
EXPERIENCE = ["<1", "1-2", "3-5", "6-10", "10+"]  # original list, keeps the seeded RNG stream unchanged
INDUSTRIES = ["Semiconductors/Hardware", "Embedded Systems", "Software", "AI/ML/Data", "Product Management",
              "Sales/Business", "Consulting", "Finance", "Healthcare/Biotech", "Design/UX"]
HELP_AREAS = ["Resume Review", "LinkedIn/Branding", "Behavioral Interviews", "Technical Interviews", "Networking",
              "Internship Search", "Job Search Strategy", "Career Exploration", "Grad School Advice", "Industry Insights"]
CAREER_PATHS = ["Engineering / technical", "Research", "Product / program management", "Sales / field applications",
                "Data / analytics", "Design", "Business / operations", "Consulting", "Entrepreneurship"]
FIELDS = ["Electrical Engineering", "Computer Engineering", "Computer Science", "Mechanical Engineering",
          "Business Administration", "Data Science", "Other Engineering", "Other"]
MINORS = [NO_MINOR, "Electrical Engineering", "Computer Engineering", "Computer Science", "Mechanical Engineering",
          "Business Administration", "Data Science", "Mathematics", "Psychology", "Communication Studies", "Other"]

FIRST = ["Aarav", "Priya", "Daniel", "Mei", "Carlos", "Fatima", "Jordan", "Ananya", "Kevin",
         "Sofia", "Rahul", "Linh", "Marcus", "Aisha", "Ethan", "Grace", "Omar", "Nina",
         "Tyler", "Divya", "Lucas", "Hana", "Isaac", "Riya", "Mateo", "Chloe", "Sam", "Zara"]
LAST = ["Patel", "Nguyen", "Garcia", "Kim", "Singh", "Lopez", "Chen", "Reddy", "Johnson",
        "Ali", "Martinez", "Shah", "Tran", "Brown", "Rao", "Wong", "Davis", "Iyer"]
COMPANIES = {"Semiconductors/Hardware": ["Texas Instruments", "Intel", "AMD", "Applied Materials"],
             "Embedded Systems": ["Texas Instruments", "Bosch", "Apple", "Tesla"],
             "Software": ["Google", "Adobe", "Salesforce", "Cisco"],
             "AI/ML/Data": ["NVIDIA", "Meta", "Databricks", "IBM"],
             "Product Management": ["Adobe", "PayPal", "Zoom", "LinkedIn"],
             "Sales/Business": ["Texas Instruments", "Oracle", "Cisco", "HP"],
             "Consulting": ["Deloitte", "Accenture", "PwC", "KPMG"],
             "Finance": ["Wells Fargo", "Visa", "Intuit", "Charles Schwab"],
             "Healthcare/Biotech": ["Genentech", "Stryker", "Medtronic", "Kaiser"],
             "Design/UX": ["Figma", "Adobe", "Airbnb", "Apple"]}
ROLES = ["Engineer", "Senior Engineer", "Manager", "Technical Sales", "Product Manager",
         "Data Scientist", "Director", "Analyst", "Designer"]

# Demand skews toward hardware/software (SJSU engineering-heavy)
IND_WEIGHTS = [16, 10, 18, 16, 8, 6, 6, 6, 7, 7]


def slots(rng, evening_bias):
    """Realistic availability: a few days, mostly one or two time blocks."""
    days = rng.sample(DAYS[:5], rng.randint(1, 3))
    if rng.random() < 0.5:
        days.append(rng.choice(DAYS[5:]))
    weights = [1, 2, 2 + evening_bias]
    out = []
    for d in days:
        for t in set(rng.choices(TIMES, weights, k=rng.randint(1, 2))):
            out.append(f"{d} {t}")
    return out


def minor(rng):
    return rng.choice(MINORS[1:]) if rng.random() < 0.35 else NO_MINOR


def name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def make(n_students=60, n_mentors=30, seed=7):
    rng = random.Random(seed)
    students = []
    for i in range(n_students):
        ind = rng.choices(INDUSTRIES, IND_WEIGHTS)[0]
        students.append({
            "id": f"S{i+1:03d}", "name": name(rng), "email": f"student{i+1}@sjsu.edu",
            "field": (f := rng.choice(FIELDS[:6])), "college": MAJOR_COLLEGE.get(f, COLLEGES[-1]),
            "minor": minor(rng), "year": rng.choice(YEARS), "grad_term": rng.choice(GRAD_TERMS),
            "industry": ind,
            "career_goal": rng.choice(CAREER_PATHS + [NOT_SURE] * 3),
            "help_ranked": rng.sample(HELP_AREAS, 3),
            "availability": slots(rng, 1),
            "mode": rng.choices(MODES, [2, 4, 5])[0],
        })
    mentors = []
    for i in range(n_mentors):
        ind = rng.choice(INDUSTRIES[:5]) if rng.random() < 0.6 else rng.choice(INDUSTRIES)
        mentors.append({
            "id": f"M{i+1:03d}", "name": name(rng), "email": f"mentor{i+1}@example.com",
            "company": rng.choice(COMPANIES[ind]), "role": rng.choice(ROLES),
            "experience": rng.choices(EXPERIENCE, [1, 4, 6, 5, 4])[0],
            "industry": ind, "field": (f := rng.choice(FIELDS[:6])),
            "college": MAJOR_COLLEGE.get(f, COLLEGES[-1]), "minor": minor(rng),
            "school": rng.choices(SCHOOLS, [5, 2, 2, 2, 1])[0], "career_path": rng.choice(CAREER_PATHS),
            "grad_period": rng.choice(GRAD_PERIODS),
            "sjsu_link": rng.choices(SJSU_LINKS, [4, 3, 2, 1])[0],
            "pref_years": rng.sample(YEARS, rng.randint(3, 5)) if rng.random() < 0.3 else [],
            "can_help": rng.sample(HELP_AREAS, rng.randint(3, 6)),
            "availability": slots(rng, 4),   # working professionals: evenings
            "mode": rng.choices(MODES, [2, 4, 5])[0],
            "capacity": rng.choices([1, 2, 3], [5, 3, 2])[0],
        })
    return students, mentors


if __name__ == "__main__":
    s, m = make()
    json.dump({"students": s, "mentors": m}, open("seed.json", "w"), indent=2)
    print(f"Wrote {len(s)} students, {len(m)} mentors to seed.json")