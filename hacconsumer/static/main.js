// main.ts
$(document).ready(function () {
    let assignmentsTable;
    let students;
    // Initialize DataTable with bootstrap styling
    assignmentsTable = $('#assignmentsTable').DataTable({
        "dom": '<"top"Bf><"clear">lrt<"bottom"ip>',
        "language": {
            "search": "_INPUT_",
            "searchPlaceholder": "Search..."
        }
    });
    // Function to update table with selected student's assignments
    function updateTable(selected_student) {
        // Make API call to get assignments for the selected student
        $.ajax({
            url: `/api/students`,
            method: 'GET',
            success: function (students_response) {
                // Update the cached students
                students = students_response;
                // Select proper student from cached data
                const student = students.find(s => s.name === selected_student);
                if (student) {
                    let assignments = student.assignments;
                    // Get selected filters
                    const showFailing = $('#failingFilter').prop('checked');
                    const showMissing = $('#missingFilter').prop('checked');
                    const selectedGradingPeriod = $('#gradingPeriodFilter').val();
                    // Apply filters
                    let filtered_assignments = assignments.filter(assignment => {
                        // Check if there's a specific grading period set to filter by, otherwise accept all.
                        const matchesGradingPeriod = !selectedGradingPeriod || assignment.grading_period === parseInt(selectedGradingPeriod, 10);
                        // Determine if an assignment is missing or has a failing grade.
                        const isMissing = assignment.assignment_grade === 'M';
                        const gradeNumber = Number(assignment.assignment_grade);
                        const isFailingGrade = !isNaN(gradeNumber) && gradeNumber < 70;
                        // Determine visibility based on filter combinations:
                        if (showFailing && showMissing) {
                            // Show failing OR missing assignments in specified grading period.
                            return (isFailingGrade || isMissing) && matchesGradingPeriod;
                        }
                        else if (showFailing) {
                            // Show only failing assignments in specified grading period.
                            return !isMissing && isFailingGrade && matchesGradingPeriod;
                        }
                        else if (showMissing) {
                            // Show only missing assignments in specified grading period.
                            return isMissing && matchesGradingPeriod;
                        }
                        else {
                            return matchesGradingPeriod;
                        }
                    });
                    // Clear existing rows
                    assignmentsTable.clear().draw();
                    // Populate table with filtered data
                    filtered_assignments.forEach(function (assignment) {
                        assignmentsTable.row.add([
                            assignment.grading_period,
                            assignment.class_name,
                            assignment.class_avg,
                            assignment.name,
                            assignment.assignment_grade
                        ]).draw();
                    });
                }
                else {
                    throw new Error("Internal error: Student selection was not found in backend response");
                }
            },
            error: function (error) {
                console.error('Error fetching assignments:', error);
            }
        });
    }
    // Dropdown change event
    $('#studentSelect').on('change', function () {
        const selectedStudent = $(this).val();
        updateTable(selectedStudent);
    });
    // Refresh assignments button click event
    $('#refreshAssignments').on('click', function () {
        // Make API call to refresh assignments for all students
        $.ajax({
            url: '/api/refresh_students',
            method: 'GET',
            success: function (students_response) {
                // Update the cached students
                students = students_response;
                // After refreshing, update the table for the selected student
                const selectedStudent = $('#studentSelect').val();
                updateTable(selectedStudent);
            },
            error: function (error) {
                console.error('Error refreshing assignments:', error);
            }
        });
    });
    // Event handler for failing filter change
    $('#failingFilter').on('change', function () {
        const selectedStudent = $('#studentSelect').val();
        updateTable(selectedStudent);
    });
    // Event handler for missing filter change
    $('#missingFilter').on('change', function () {
        const selectedStudent = $('#studentSelect').val();
        updateTable(selectedStudent);
    });
    // Event handler for grading period filter change
    $('#gradingPeriodFilter').on('change', function () {
        const selectedStudent = $('#studentSelect').val();
        updateTable(selectedStudent);
    });
    // Function to populate student list in the modal
    const populateStudentList = () => {
        $.get("/api/students", (students) => {
            const studentListHtml = students.map((student) => `
                <div class="expandableRow">
                    <div>Name: ${student.name}</div>
                    <div>Username: ${student.username}</div>
                    <div>Password: *********</div>
                    <button class="updateStudentBtn" data-name="${student.name}">Update</button>
                </div>
            `).join('');
            $('#studentList').html(studentListHtml);
        });
    };
    // Open modal on button click
    $('#manageStudentsBtn').click(() => {
        populateStudentList();
        const modalElement = document.getElementById('manageStudentsModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        }
    });
    // Close modal on button click
    $('#closeModalBtn').click(() => {
        const modalElement = document.getElementById('manageStudentsModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.hide();
        }
    });
    // Add new student
    $('#addStudentBtn').click(() => {
        const newName = $('#newName').val();
        const newUsername = $('#newUsername').val();
        const newPassword = $('#newPassword').val();
        const newStudent = {
            name: newName,
            username: newUsername,
            password: newPassword,
            assignments: []
        };
        $.ajax({
            url: "/api/students",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(newStudent),
            success: () => {
                // Clear fields
                $('#newName').val('');
                $('#newUsername').val('');
                $('#newPassword').val('');
                // Refresh student list
                populateStudentList();
            },
            error: (xhr, status, error) => {
                console.error(error);
            }
        });
    });
    // Update student
    $('#studentList').on('click', '.updateStudentBtn', function () {
        const studentName = $(this).data('name');
        // Fetch current student data
        $.get(`/api/students/${studentName}`, (student) => {
            // Open a modal or form to update student details
            // You can implement this based on your UI requirements
        });
    });
    // Initial update of the table
    updateTable($('#studentSelect').val());
});
