from pathlib import Path
from unittest import TestCase, mock, main
from fastapi.testclient import TestClient
import hacconsumer.server as server
from hacconsumer.hac_report import HACStudent

client = TestClient(server.app)
TEST_STUDENT_PATH = Path("../test/students.json")


class TestStudentEndpoints(TestCase):
    def setUp(self) -> None:
        TEST_STUDENT_PATH.unlink()
        server.assignment_service.students_file = TEST_STUDENT_PATH
        server.assignment_service.load_students()

    @mock.patch("hacconsumer.hac_report.HacApiConsumer.post_cached")
    def test_create_student(self, mock_post_cached: mock.MagicMock):
        mock_post_cached.return_value = {"classwork": []}
        student_payload = {
            "name": "John Doe",
            "username": "john_doe",
            "password": "secure_password",
        }
        response = client.post("/api/students", json=student_payload)
        self.assertEqual(response.status_code, 200)
        created_student = response.json()
        self.assertEqual(created_student["name"], "John Doe")

    @mock.patch("hacconsumer.hac_report.AssignmentService.get_student")
    def test_update_student(self, mock_get_student: mock.MagicMock):
        mock_get_student.return_value = HACStudent(
            **{
                "name": "John Doe",
                "username": "john_doe",
                "password": "secure_password",
            }
        )
        student_name = "John Doe"
        updated_student_payload = {
            "name": "John Doe Updated",
            "username": "john_doe_updated",
            "password": "new_secure_password",
        }
        response = client.patch(
            f"/api/students/{student_name}", json=updated_student_payload
        )
        self.assertEqual(response.status_code, 200)
        updated_student = response.json()
        self.assertEqual(updated_student["name"], "John Doe Updated")

    def test_delete_student(self):
        student_name = "John Doe"
        response = client.delete(f"/api/students/{student_name}")
        self.assertEqual(response.status_code, 204)

    # Add more test cases as needed


if __name__ == "__main__":
    main()
