"""Run the full matching pipeline on fake data and print results."""
from collections import Counter

from team_file.seed_data import make
from team_file.matching import run_matching, supply_gap, learn_weights

students, mentors = make()
s_by = {s["id"]: s for s in students}
m_by = {m["id"]: m for m in mentors}

matches, unmatched = run_matching(students, mentors)

print(f"Students: {len(students)}  Mentors: {len(mentors)} "
      f"(eligible: {sum(m['experience'] != '<1' for m in mentors)})")
print(f"Matched: {len(matches)} ({100*len(matches)/len(students):.0f}%)  "
      f"Avg score: {sum(m['score'] for m in matches)/len(matches):.1f}")
print("Confidence:", dict(Counter(m["confidence"] for m in matches)))

print("\nSample matches:")
for mt in sorted(matches, key=lambda x: -x["score"])[:3] + matches[-2:]:
    s, m = s_by[mt["student_id"]], m_by[mt["mentor_id"]]
    print(f"  {s['name']} -> {m['name']} ({m['company']}) | {mt['score']}/100 "
          f"{mt['confidence']}\n     Why: {mt['reason']}"
          + (f"\n     Gaps: {'; '.join(mt['gaps'])}" if mt["gaps"] else ""))

print(f"\nUnmatched ({len(unmatched)}):")
for u in unmatched[:5]:
    print(f"  {s_by[u['student_id']]['name']}: {u['why']}")

print("\nLowest coverage (recruit here):")
for r in supply_gap(students, mentors)[:5]:
    print(f"  {r['Type']:15} {r['Tag']:25} students={r['Students']:3} "
          f"slots={r['Mentor slots']:3} coverage={r['Coverage %']:.0f}%")

# Extra credit: staff approves high scores, denies some industry mismatches
decisions = [{"student_id": m["student_id"], "mentor_id": m["mentor_id"],
              "approved": m["breakdown"]["Industry"] > 0} for m in matches]
print("\nLearned weights from staff decisions:", learn_weights(decisions, students, mentors))

# Lock first 10, re-run for the rest
locked = [(m["student_id"], m["mentor_id"]) for m in matches[:10]]
m2, u2 = run_matching(students, mentors, locked=locked)
print(f"\nRe-run with 10 locked: {len(m2)} new matches, {len(u2)} unmatched")