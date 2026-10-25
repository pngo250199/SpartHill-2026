from dataclasses import dataclass


@dataclass
class Instructor:
    instructor_id: int
    name: str
    expertise: set[str]
    career_interests: set[str]
    available: bool = True