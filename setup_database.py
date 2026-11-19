"""Creates the portal tables and loads sample data.

Run it ONCE with the Run button in VS Code.
WARNING: it deletes the old tables from setup_real_db.py
(students, courses, enrollments, rooms, professors, timetable)
and rebuilds them in the new format.
"""
from db import get_connection, hash_password

SCHEMA = """
DROP TABLE IF EXISTS timetable_entries, timetable_runs,
    professor_availability, timetable, enrollments, results,
    prerequisites, courses, rooms, professors, students,
    student_groups, admins, settings CASCADE;

CREATE TABLE admins (
    admin_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(64) NOT NULL
);

CREATE TABLE students (
    student_id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    year INT NOT NULL CHECK (year BETWEEN 1 AND 4),
    password_hash VARCHAR(64) NOT NULL
);

CREATE TABLE professors (
    professor_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE rooms (
    room_id SERIAL PRIMARY KEY,
    room_name VARCHAR(50) UNIQUE NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    is_lab BOOLEAN DEFAULT FALSE
);

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) UNIQUE NOT NULL,
    course_name VARCHAR(100) NOT NULL,
    year INT NOT NULL CHECK (year BETWEEN 1 AND 4),
    semester INT NOT NULL CHECK (semester IN (1, 2)),
    credit_hours INT NOT NULL DEFAULT 3,
    capacity INT NOT NULL DEFAULT 45,      -- max students in the course
    requires_lab BOOLEAN DEFAULT FALSE,     -- tutorials go to a lab
    lecture_sessions INT NOT NULL DEFAULT 1,  -- 90-min lectures per week
    tutorial_sessions INT NOT NULL DEFAULT 1, -- 90-min tutorials per week
    professor_id INT REFERENCES professors(professor_id) ON DELETE SET NULL
);

-- course_id needs prerequisite_id to be PASSED first
CREATE TABLE prerequisites (
    course_id INT REFERENCES courses(course_id) ON DELETE CASCADE,
    prerequisite_id INT REFERENCES courses(course_id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, prerequisite_id),
    CHECK (course_id <> prerequisite_id)
);

-- the transcript: one row per student per course already taken
CREATE TABLE results (
    student_id BIGINT REFERENCES students(student_id) ON DELETE CASCADE,
    course_id INT REFERENCES courses(course_id) ON DELETE CASCADE,
    status VARCHAR(10) NOT NULL CHECK (status IN ('Passed', 'Failed')),
    PRIMARY KEY (student_id, course_id)
);

-- current semester registration, with the group the student chose
CREATE TABLE enrollments (
    student_id BIGINT REFERENCES students(student_id) ON DELETE CASCADE,
    course_id INT REFERENCES courses(course_id) ON DELETE CASCADE,
    group_no INT NOT NULL CHECK (group_no >= 1),
    registered_by VARCHAR(10) NOT NULL DEFAULT 'student',
    PRIMARY KEY (student_id, course_id)
);

-- only the special periods are stored; anything not listed = available
CREATE TABLE professor_availability (
    professor_id INT REFERENCES professors(professor_id) ON DELETE CASCADE,
    day VARCHAR(10) NOT NULL,
    slot_id INT NOT NULL CHECK (slot_id BETWEEN 1 AND 6),
    status VARCHAR(12) NOT NULL CHECK (status IN ('unavailable', 'preferred')),
    PRIMARY KEY (professor_id, day, slot_id)
);

-- every press of "Generate" is saved as a run; one run is published
CREATE TABLE timetable_runs (
    run_id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    semester INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    score INT NOT NULL,
    not_preferred INT NOT NULL,
    single_class_days INT NOT NULL,
    solve_seconds NUMERIC(8, 2) NOT NULL,
    published BOOLEAN DEFAULT FALSE
);

CREATE TABLE timetable_entries (
    entry_id SERIAL PRIMARY KEY,
    run_id INT REFERENCES timetable_runs(run_id) ON DELETE CASCADE,
    course_id INT REFERENCES courses(course_id) ON DELETE CASCADE,
    group_no INT NOT NULL,
    session_type VARCHAR(10) NOT NULL,
    day VARCHAR(10) NOT NULL,
    slot_id INT NOT NULL,
    room_id INT REFERENCES rooms(room_id) ON DELETE CASCADE,
    professor_id INT REFERENCES professors(professor_id) ON DELETE CASCADE
);

CREATE TABLE settings (
    key VARCHAR(50) PRIMARY KEY,
    value VARCHAR(100) NOT NULL
);
"""


def seed(cur):
    # ---------- admin (change the password after the first login) ----------
    cur.execute(
        "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
        ("admin", hash_password("admin123")),
    )

    # ---------- settings ----------
    cur.execute(
        "INSERT INTO settings (key, value) VALUES "
        "('current_semester', '1'), ('max_credits', '21')"
    )

    # ---------- students (default password = student ID) ----------
    students = [
        (242500079, "Rodaina El Goussi", 3),
        (242500080, "Mariam Mohammed Akmal", 3),
        (242500324, "Eyad Abdullah", 3),
        (242500999, "Mahmoud Hesham Gharib", 3),
    ]
    for sid, name, year in students:
        cur.execute(
            "INSERT INTO students VALUES (%s, %s, %s, %s)",
            (sid, name, year, hash_password(sid)),
        )

    # ---------- professors ----------
    for name in [
        "Dr. Hesham Mansour", "Dr. Mohamed Tharwat", "Dr. Walaa Hassan",
        "Dr. Raghda Essam", "Dr. Hazem Hussein", "Dr. Hoda",
    ]:
        cur.execute("INSERT INTO professors (name) VALUES (%s)", (name,))

    # ---------- sample availability (edit in Schedule Management) ----------
    # Dr. Hesham Mansour: cannot teach Monday mornings, prefers mornings
    for slot in (1, 2):
        cur.execute(
            "INSERT INTO professor_availability VALUES (1, 'Monday', %s, 'unavailable')",
            (slot,),
        )
    for day in ("Saturday", "Sunday", "Tuesday", "Wednesday", "Thursday"):
        for slot in (1, 2):
            cur.execute(
                "INSERT INTO professor_availability VALUES (1, %s, %s, 'preferred')",
                (day, slot),
            )

    # ---------- rooms ----------
    for name, cap, lab in [
        ("Hall G1", 45, False), ("Hall G2", 45, False),
        ("Lab A", 45, True), ("Lab B", 45, True),
    ]:
        cur.execute(
            "INSERT INTO rooms (room_name, capacity, is_lab) VALUES (%s, %s, %s)",
            (name, cap, lab),
        )

    # ---------- courses: (code, name, year, semester, credits, capacity, lab, prof) ----------
    courses = [
        # Year 2 (sample: MTH205 -> AML206 is the prerequisite example)
        ("MTH205", "Mathematics for Machine Learning", 2, 1, 3, 90, False, 1),
        ("AML206", "Applied Machine Learning", 2, 2, 3, 90, True, 1),
        ("MGT406", "Agile, Scrum & DevOps", 2, 1, 3, 90, False, 1),
        ("DAT404", "Big Data Analysis", 2, 1, 3, 90, True, 4),
        ("ENG201", "Year 2 English", 2, 1, 2, 90, False, 5),
        ("MGT305", "Supply Chain Management", 2, 1, 3, 90, False, 1),
        ("FRE201", "French 3", 2, 1, 2, 90, False, 6),
        ("VR402", "Augmented & Virtual Reality", 2, 1, 3, 90, True, 2),
        # Year 3 - AI track
        ("AI301", "Unsupervised Machine Learning", 3, 1, 3, 90, True, 1),
        ("AI302", "Statistical ML & Inference", 3, 1, 3, 90, True, 1),
        ("AI303", "Deep Neural Networks", 3, 1, 3, 90, True, 2),
        ("AI304", "NLP & Transformers", 3, 1, 3, 90, True, 2),
        ("PRJ301", "Graduation Project", 3, 1, 2, 90, False, 3),
        ("DAT301", "Data Wrangling & Visualization", 3, 1, 3, 90, True, 4),
        ("ENG301", "English Int. Career Prep", 3, 1, 2, 90, False, 5),
        ("FRE301", "French 5", 3, 1, 2, 90, False, 6),
    ]
    for row in courses:
        cur.execute(
            "INSERT INTO courses (course_code, course_name, year, semester, "
            "credit_hours, capacity, requires_lab, professor_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            row,
        )

    # ---------- prerequisites: (course, needs) ----------
    for course, needs in [
        ("AML206", "MTH205"),
        ("AI301", "MTH205"),
        ("ENG301", "ENG201"),
        ("FRE301", "FRE201"),
    ]:
        cur.execute(
            "INSERT INTO prerequisites "
            "SELECT c.course_id, p.course_id FROM courses c, courses p "
            "WHERE c.course_code = %s AND p.course_code = %s",
            (course, needs),
        )

    # ---------- results: everyone passed Year 2 except these ----------
    failed = {
        242500324: ["MGT406", "DAT404", "ENG201"],
        242500999: ["MGT406", "ENG201", "MGT305", "FRE201", "VR402", "MTH205"],
    }
    # Mahmoud failed MTH205, so he was never allowed to take AML206
    not_taken = {242500999: ["AML206"]}

    for sid, _, _ in students:
        cur.execute(
            "INSERT INTO results (student_id, course_id, status) "
            "SELECT %s, course_id, CASE WHEN course_code = ANY(%s) "
            "THEN 'Failed' ELSE 'Passed' END FROM courses "
            "WHERE year = 2 AND NOT (course_code = ANY(%s))",
            (sid, failed.get(sid, []), not_taken.get(sid, [])),
        )


def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SCHEMA)
    seed(cur)
    conn.commit()
    cur.close()
    conn.close()
    print("Database ready.")
    print("Admin login:   admin / admin123")
    print("Student login: student ID / student ID (e.g. 242500079 / 242500079)")


if __name__ == "__main__":
    main()