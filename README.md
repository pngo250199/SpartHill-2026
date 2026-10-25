## Technical Contributions

### My Work

I developed the original object-oriented matching prototype.

- Created `Student` and `Instructor` data models using Python dataclasses.
- Built a `MatchingEngine` to compare:
  - Career interests
  - Goals
  - Development needs
- Implemented match scores from 0–100.
- Ranked instructors and selected the best match.
- Created the initial FastAPI routes and frontend connection.
- Built and tested a separate rematching prototype for accepting or denying matches.
- Debugged Python imports, package structure, Streamlit execution, and GitHub integration.

My original architecture was object-oriented:

Student and Instructor objects
            ↓
MatchingEngine
            ↓
MatchResult objects


#My Teammate's work
My teammate developed the advanced matching and dashboard system.
- Created realistic student and mentor seed data.
- Added eligibility filters for:
  - Experience
  - Availability
  - Meeting mode
  - Preferred student year
- Added weighted scoring based on:
  - Help areas
  - Industry
  - Academic background
  - SJSU connection
  - Availability
- Added mentor capacity management.
- Implemented the Hungarian algorithm for global one-to-one assignment.
- Added alternatives, match explanations, confidence levels, and gap analysis.
- Added staff approval and denial workflows.
- Added SQLite persistence.
- Built the Streamlit dashboard and reporting interface.
- Added optional machine-learning success prediction and learned weighting.

#The advanced architecture uses dictionary-based records:
Student and mentor dictionaries
            ↓
Eligibility filters
            ↓
score_pair()
            ↓
run_matching()
            ↓
Hungarian assignment
            ↓
Streamlit dashboard


#Differences
| Area               | My System                                    | Teammate System                                  |
|--------------------|----------------------------------------------|--------------------------------------------------|
| Data structure     | Python objects and dataclasses               | Dictionaries and generated records               |
| Matching           | Individual score ranking                     | Global assignment                                |
| Algorithm          | Weighted compatibility score                 | Weighted score plus Hungarian algorithm          |
| Capacity           | Basic availability                           | Multiple mentor capacity slots                   |
| Interface          | FastAPI and HTML                             | Streamlit dashboard                              |
| Run with           | PYTHONPATH=src uvicorn src.main:app --reload | PYTHONPATH=src streamlit run src/team_file/app.py|
| Storage            | Application-level objects                    | SQLite database                                  |
| Feedback           | Separate rematch prototype                   | Integrated staff approval and denial             |
| Explanations       | Match categories                             | Reasons, gaps, confidence, and alternatives      |




###How the Systems Were Combined
The systems were kept as separate components because they use different data models.

The teammate’s Streamlit application and advanced matching.py are used as the main demonstration system because they support database storage, staff review, mentor capacity, and global assignment.

My object-oriented implementation remains as the original matching prototype and demonstrates the core matching concepts using reusable Python classes.

The systems can be combined in the future using an adapter layer:

OOP Student/Instructor objects
            ↓
Adapter converts objects to dictionaries
            ↓
Advanced matching engine
            ↓
Ranked matches and assignments

Keeping the systems separated prevents duplicate matching logic and allows each implementation to be tested independently.

###The key point is:

My code = clean OOP foundation and API prototype
Teammate code = advanced production-style matching and dashboard


### Effectiveness Comparison

My original OOP system is effective for a simple matching scenario. It is easy to understand, maintain, and use for ranking instructors for one student. Its main strength is its clean class-based structure and straightforward scoring logic.

My teammate's system is more effective for the full mentorship program. It evaluates all students and mentors together, respects mentor capacity, checks availability, provides alternatives, and uses the Hungarian algorithm to create globally optimized assignments. It also includes staff review, SQLite storage, explanations, and a Streamlit dashboard.

The tradeoff is that my system is simpler and easier to extend for learning, while my teammate's system is more complex but better suited for real-world use. Therefore, the final application uses my OOP prototype as the conceptual foundation and my teammate's advanced engine as the main production-style matching system.
