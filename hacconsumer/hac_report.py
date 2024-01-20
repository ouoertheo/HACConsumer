from pathlib import Path
import requests
from datetime import datetime
from hashlib import md5
from loguru import logger
import json
import dotenv, os
import pydantic

dotenv.load_dotenv()

cwd = Path(__file__)
os.chdir(cwd.parent)

HAC_API_BASE = f"http://go-app:{os.getenv('SERVER_PORT')}/api/v1"
HAC_URL_BASE = os.getenv("HAC_URL_BASE")
CACHE_FOLDER = Path("cache")
CACHE_TTL = 24 * 60 * 60 * 1000


class Assignment(pydantic.BaseModel):
    name: str
    assignment_grade: float | str
    grading_period: int
    class_name: str
    class_avg: float | str


class HACStudent(pydantic.BaseModel):
    name: str
    username: str
    password: str
    assignments: list[Assignment] = pydantic.Field(default_factory=list)


class CacheEntry:
    def __init__(self, key, data, ttl):
        self.key = key
        self.data = data
        self.timestamp = datetime.now()
        self.ttl = ttl

    def is_valid(self):
        return (datetime.now() - self.timestamp).total_seconds() < self.ttl


class HacApiConsumer:
    def __init__(self) -> None:
        self.cache_folder = CACHE_FOLDER
        logger.info(
            f"HacApiConsumer initialized with cache location: {self.cache_folder.resolve()}"
        )
        self.cache: dict[str, CacheEntry] = {}
        self._create_cache_folder()
        self._load_existing_cache()

    def _create_cache_folder(self):
        if not self.cache_folder.exists():
            logger.info(
                f"Cache folder does not exist, creating at {self.cache_folder.resolve()}"
            )
            os.makedirs(self.cache_folder)

    def _get_cache_path(self, key):
        return self.cache_folder.joinpath(f"{key}.json")

    def _load_existing_cache(self):
        logger.info(
            f"Found cache files in {self.cache_folder.resolve()}: {[entry_file for entry_file in self.cache_folder.iterdir()]}"
        )

        for entry_file in self.cache_folder.iterdir():
            if entry_file.is_file():
                logger.info(f"Loading cache file {entry_file.resolve()}")
                with open(entry_file, "r") as file:
                    data = json.load(file)
                    if "err" in data and data["err"]:
                        logger.info(f"Error found in cached data, clearing cache.")
                        self.clear_cache()
                    cache_entry = CacheEntry(data["key"], data["data"], data["ttl"])
                    self.cache[data["key"]] = cache_entry

    def _save_cache(self, entry: CacheEntry):
        cache_path = self._get_cache_path(entry.key)
        with cache_path.open("w") as file:
            logger.info(f"Saving cache entry {cache_path.resolve()}")
            json.dump({"key": entry.key, "data": entry.data, "ttl": entry.ttl}, file)

    def post_cached(self, *args, **kwargs):
        key = md5(f"{args}{kwargs}".encode("utf-8")).hexdigest()
        if key in self.cache and self.cache[key].is_valid():
            data = self.cache[key].data
            logger.info(f"Retrieved cache entry {key}")
            if "err" in data and data["err"]:
                logger.info(
                    f"Error found in cached data, clearing cache and trying again..."
                )
                self.clear_cache()
                return self.post_cached(*args, **kwargs)
            return data
        else:
            logger.info(
                f"Key {key} not cached. Making fresh call. Params: {args, kwargs}"
            )
            data = requests.post(*args, **kwargs).json()
            if "err" in data and data["err"]:
                raise Exception(data["msg"])
            cache_entry = CacheEntry(key, data, CACHE_TTL)
            self.cache[key] = cache_entry
            self._save_cache(cache_entry)
            return data

    def clear_cache(self):
        logger.warning(f"Clearing cache at {self.cache_folder.resolve()}")
        self.cache = {}
        for entry_file in self.cache_folder.iterdir():
            if entry_file.is_file():
                entry_file.unlink()

    def get_student_base_payload(self, student: HACStudent):
        payload = {
            "base": HAC_URL_BASE,
            "username": student.username,
            "password": student.password,
        }
        logger.info(f"Returning base {payload}")
        return payload

    def get_assignments_raw(self, student: HACStudent):
        payload = self.get_student_base_payload(student) | {
            "markingPeriods": [1, 2, 3, 4]
        }
        try:
            data = self.post_cached(HAC_API_BASE + "/classwork", json=payload)
        except Exception as e:
            logger.exception(e)
        return data


class AssignmentService:
    def __init__(self, api_consumer: HacApiConsumer) -> None:
        self.api_consumer = api_consumer
        self.students_file = Path("config/students.json")

    def load_students(self):
        # Load students
        try:
            with self.students_file.open("r") as fh:
                data = json.load(fh)
        except:
            with self.students_file.open("x") as fh:
                json.dump([], fh)
                data = []

        self.students = [HACStudent(**student) for student in data]
        logger.info(f"Loaded {len(self.students)} students")

    def get_student(self, name) -> HACStudent | None:
        for student in self.students:
            if student.name == name:
                return student
        logger.info(f"Returned student {student.name}")
        return None

    def create_student(self, student: HACStudent):
        if [s.name for s in self.students if s.name == student.name]:
            raise ValueError(f"Student with name {student.name} already exists")
        with self.students_file.open("w") as fh:
            self.students.append(student)
            json.dump([s.model_dump() for s in self.students], fh)
        logger.info(f"Created student {student.name}. Getting assignments...")
        self.parse_assignments(student=student)
        return student

    def update_student(self, student_name: str, student_new: HACStudent):
        student = self.get_student(student_name)
        if student:
            student.name = student_new.name
            student.username = student_new.username
            student.password = student_new.password
            logger.info(f"Student {student_name} updated.")
        else:
            raise ValueError(f"Student {student_name} not found.")
        return student

    def delete_student(self, student_name: str):
        student = self.get_student(student_name)
        if student:
            self.students.remove(student)
            logger.info(f"Student {student.name} removed.")
        else:
            raise ValueError(f"Student {student_name} not found.")

    def parse_all(self, clear_cache=False):
        for student in self.students:
            self.parse_assignments(student, clear_cache)

    def parse_assignments(self, student: HACStudent, clear_cache=False):
        if clear_cache:
            self.api_consumer.clear_cache()

        # Clear out previous assignments
        student.assignments = []

        # Grab assignments from HAC
        logger.info(
            f"Fetching student assignments {student.name}. Parsing assignments now..."
        )
        assignments = self.api_consumer.get_assignments_raw(student)
        if "err" in assignments and assignments["err"]:
            raise Exception(assignments["msg"])
        logger.info(
            f"Fetched student assignments {student.name}. Parsing assignments now..."
        )

        # String together data about class, assignments and grade to populate rows
        for grading_period in assignments["classwork"]:
            period = grading_period["sixWeeks"]
            for class_entry in grading_period["entries"]:
                class_name = class_entry["class"]["name"]
                if not class_entry["average"]:
                    class_avg = "No grade"
                else:
                    try:
                        class_avg = float(class_entry["average"])
                    except:
                        class_avg = class_entry["average"]
                for assignment in class_entry["assignments"]:
                    assignment_name = assignment["name"]
                    if isinstance(assignment["grade"], int):
                        grade = float(assignment["grade"]) / float(
                            assignment["totalPoints"]
                        )
                        grade = int(grade * 100)
                    elif isinstance(assignment["grade"], str) and assignment["grade"]:
                        grade = assignment["grade"]
                    elif not assignment["grade"]:
                        grade = "Not Graded"

                    student.assignments.append(
                        Assignment(
                            name=assignment_name,
                            assignment_grade=grade,
                            grading_period=period,
                            class_name=class_name,
                            class_avg=class_avg,
                        )
                    )
        logger.info(
            f"Loaded {len(student.assignments)} assignments for student {student.name}"
        )
