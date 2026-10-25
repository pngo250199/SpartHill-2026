from dataclasses import dataclass


@dataclass
class Student:
    student_id: int
    name: str
    career_interests: set[str]
    goals: set[str]
    development_needs: set[str]