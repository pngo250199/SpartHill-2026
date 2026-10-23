from dataclasses import dataclass


@dataclass
class Student:
    student_id: int
    name: str
    tags: set[str]


@dataclass
class Instructor:
    instructor_id: int
    name: str
    tags: set[str]


class MatchingSystem:
    def __init__(self):
        self.students = {}
        self.instructors = {}
        self.matches = {}  # student_id -> instructor_id

    def add_student(self, student):
        self.students[student.student_id] = student

    def add_instructor(self, instructor):
        self.instructors[instructor.instructor_id] = instructor

    def calculate_score(self, student, instructor):
        common_tags = student.tags & instructor.tags
        return len(common_tags)

    def find_best_match(self, student_id):
        student = self.students[student_id]

        available_instructors = [
            instructor
            for instructor in self.instructors.values()
            if instructor.instructor_id not in self.matches.values()
        ]

        if not available_instructors:
            return None

        best_instructor = max(
            available_instructors,
            key=lambda instructor: self.calculate_score(student, instructor)
        )

        if self.calculate_score(student, best_instructor) == 0:
            return None

        self.matches[student_id] = best_instructor.instructor_id
        return best_instructor

    def display_matches(self):
        for student_id, instructor_id in self.matches.items():
            student = self.students[student_id]
            instructor = self.instructors[instructor_id]

            score = self.calculate_score(student, instructor)
            common_tags = student.tags & instructor.tags

            print(
                f"{student.name} -> {instructor.name} | "
                f"Score: {score} | Shared tags: {common_tags}"
            )


system = MatchingSystem()

system.add_student(
    Student(1, "Henry", {"Python", "Embedded Systems", "C"})
)

system.add_student(
    Student(2, "Alice", {"AI", "Python", "Machine Learning"})
)

system.add_instructor(
    Instructor(101, "Dr. Smith", {"Python", "Embedded Systems", "C"})
)

system.add_instructor(
    Instructor(102, "Dr. Lee", {"AI", "Python", "Machine Learning"})
)

system.find_best_match(1)
system.find_best_match(2)

system.display_matches()