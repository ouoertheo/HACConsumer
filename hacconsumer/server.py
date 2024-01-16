from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from loguru import logger
from pathlib import Path
from hacconsumer.hac_report import AssignmentService, HACStudent, HacApiConsumer
import os
import dotenv


dotenv.load_dotenv()
try:
    FRONTEND_PORT = int(os.getenv("FRONTEND_PORT"))
except:
    FRONTEND_PORT = 3001

app = FastAPI()
cwd = Path(__file__)
os.chdir(cwd.parent)
template_path = cwd.parent.joinpath("templates")
templates = Jinja2Templates(directory=template_path)

api_consumer = HacApiConsumer()
assignment_service = AssignmentService(api_consumer)


@app.get("/static/{filename}")
def static(filename: str) -> FileResponse:
    if filename.endswith(".js"):
        return FileResponse(
            f"static/{filename}", headers={"content-type": "application/javascript"}
        )
    if filename.endswith(".css"):
        return FileResponse(f"static/{filename}", headers={"content-type": "text/css"})


@app.get("/")
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": assignment_service.students,
        },
    )


@app.get("/api/students")
def get_students() -> list[HACStudent]:
    try:
        need_assignments = False
        for student in assignment_service.students:
            if not student.assignments:
                need_assignments = True

        if need_assignments:
            logger.info(f"Students do now have assignments. Getting assignments.")
            assignment_service.parse_all()
            for student in assignment_service.students:
                logger.info(f" n")

        return assignment_service.students
    except Exception as e:
        logger.exception(e)
        return HTTPException(status_code=500, detail=f"error: {str(e)}")


@app.get("/api/refresh_students")
def refresh_students() -> list[HACStudent]:
    try:
        assignment_service.parse_all(clear_cache=True)
        return assignment_service.students
    except Exception as e:
        logger.exception(e)
        return HTTPException(status_code=500, detail=f"error: {str(e)}")


@app.post("/api/students", status_code=200)
def create_student(student_payload: HACStudent) -> HACStudent:
    try:
        student = assignment_service.create_student(student_payload)
        return student
    except ValueError as e:
        logger.error(str(e))
        return HTTPException(409, e)
    except Exception as e:
        logger.error(str(e))
        return HTTPException(400, e)


@app.patch("/api/students/{student_name}", status_code=200)
def update_student(student_name: str, student_payload: HACStudent) -> HACStudent:
    try:
        student = assignment_service.update_student(
            student_name=student_name, student_new=student_payload
        )
        return student
    except ValueError as e:
        logger.error(str(e))
        return HTTPException(404, e)
    except Exception as e:
        logger.error(str(e))
        return HTTPException(400, e)


@app.delete("/api/students/{student_name}", status_code=204)
def delete_student(student_name: str) -> None:
    try:
        assignment_service.delete_student(student_name=student_name)
    except ValueError as e:
        logger.error(str(e))
        return HTTPException(404, e)
    except Exception as e:
        logger.error(str(e))
        return HTTPException(400, e)


def run():
    # Get all assignments at the start
    assignment_service.load_students()
    assignment_service.parse_all()
    uvicorn.run(app, host="0.0.0.0", port=FRONTEND_PORT)
