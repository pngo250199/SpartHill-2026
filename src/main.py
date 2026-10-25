from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import HTMLResponse
from Routes.matching import router as matching_router
from Routes.team_demo import router as team_demo_router

app = FastAPI(title="Tandem Mentorship API")

app.include_router(matching_router)
app.include_router(team_demo_router)

@app.get("/")
def home():
    return {"message": "Tandem API is running"}


@app.get("/students", response_class=HTMLResponse)
def students_page():
    file_path = Path(__file__).parent.parent / "frontend" / "students.html"

    return file_path.read_text(encoding="utf-8")

@app.get("/dashboard")
def dashboard_page():
    file_path = Path(__file__).parent.parent / "frontend" / "dashboard.html"
    return HTMLResponse(file_path.read_text(encoding="utf-8"))