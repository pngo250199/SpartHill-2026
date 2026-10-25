from fastapi import APIRouter

from team_file.seed_data import make
from team_file.matching import run_matching, supply_gap


router = APIRouter()


@router.get("/team-demo")
def run_team_demo():
    students, mentors = make()

    matches, unmatched = run_matching(
        students,
        mentors
    )

    return {
        "students": len(students),
        "mentors": len(mentors),
        "matched": len(matches),
        "unmatched": len(unmatched),
        "match_rate": round(
            len(matches) / len(students) * 100,
            1
        ),
        "matches": matches[:5],
        "unmatched_students": unmatched[:5],
        "supply_gaps": supply_gap(students, mentors)[:5],
    }