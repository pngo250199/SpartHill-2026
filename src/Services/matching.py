from dataclasses import dataclass

from Models.student import Student
from Models.instructor import Instructor


@dataclass
class MatchResult:
    instructor: Instructor
    score: float
    interest_matches: set[str]
    goal_matches: set[str]
    development_matches: set[str]


class MatchingEngine:
    def calculate_match(self, student: Student, instructor: Instructor):
        interest_matches = (
            student.career_interests & instructor.career_interests
        )

        goal_matches = (
            student.goals & instructor.expertise
        )

        development_matches = (
            student.development_needs & instructor.expertise
        )

        interest_score = (
            len(interest_matches)
            / max(len(student.career_interests), 1)
        )

        goal_score = (
            len(goal_matches)
            / max(len(student.goals), 1)
        )

        development_score = (
            len(development_matches)
            / max(len(student.development_needs), 1)
        )

        availability_score = 1 if instructor.available else 0

        total_score = (
            interest_score * 40
            + goal_score * 30
            + development_score * 20
            + availability_score * 10
        )

        return MatchResult(
            instructor=instructor,
            score=round(total_score, 2),
            interest_matches=interest_matches,
            goal_matches=goal_matches,
            development_matches=development_matches,
        )

    def find_matches(
        self,
        student: Student,
        instructors: list[Instructor],
        top_n: int = 5
    ):
        results = []

        for instructor in instructors:
            if instructor.available:
                result = self.calculate_match(student, instructor)
                results.append(result)

        results.sort(
            key=lambda result: result.score,
            reverse=True
        )

        return results[:top_n]

    def find_best_match(self, student, instructors):
        matches = self.find_matches(student, instructors, top_n=1)

        if not matches:
            return None

        return matches[0]