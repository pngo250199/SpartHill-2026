from fastapi import APIRouter
from pydantic import BaseModel

from Models.student import Student
from Models.instructor import Instructor
from Services.matching import MatchingEngine


router = APIRouter()


class StudentRequest(BaseModel):
    student_id: int
    name: str
    career_interests: list[str]
    goals: list[str]
    development_needs: list[str]


class InstructorRequest(BaseModel):
    instructor_id: int
    name: str
    expertise: list[str]
    career_interests: list[str]
    available: bool = True


class MatchingRequest(BaseModel):
    student: StudentRequest
    instructors: list[InstructorRequest]


@router.post("/matches")
def find_matches(request: MatchingRequest):
    student = Student(
        student_id=request.student.student_id,
        name=request.student.name,
        career_interests=set(request.student.career_interests),
        goals=set(request.student.goals),
        development_needs=set(request.student.development_needs),
    )

    instructors = [
        Instructor(
            instructor_id=instructor.instructor_id,
            name=instructor.name,
            expertise=set(instructor.expertise),
            career_interests=set(instructor.career_interests),
            available=instructor.available,
        )
        for instructor in request.instructors
    ]

    engine = MatchingEngine()
    matches = engine.find_matches(student, instructors)

    return [
        {
            "instructor_id": match.instructor.instructor_id,
            "instructor_name": match.instructor.name,
            "score": match.score,
            "interest_matches": list(match.interest_matches),
            "goal_matches": list(match.goal_matches),
            "development_matches": list(match.development_matches),
        }
        for match in matches
    ]