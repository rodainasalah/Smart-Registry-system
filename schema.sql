-- 1. Student Groups & Students
CREATE TABLE IF NOT EXISTS student_groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    group_id INT REFERENCES student_groups(group_id)
);

-- 2. Professors
CREATE TABLE IF NOT EXISTS professors (
    professor_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- 3. Rooms
CREATE TABLE IF NOT EXISTS rooms (
    room_id SERIAL PRIMARY KEY,
    room_name VARCHAR(50) NOT NULL,
    capacity INT NOT NULL,
    is_lab BOOLEAN DEFAULT FALSE
);

-- 4. Courses
CREATE TABLE IF NOT EXISTS courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL,
    course_name VARCHAR(100) NOT NULL,
    weekly_hours INT NOT NULL,
    requires_lab BOOLEAN DEFAULT FALSE,
    professor_id INT REFERENCES professors(professor_id),
    group_id INT REFERENCES student_groups(group_id)
);

-- 5. Timetable Output
CREATE TABLE IF NOT EXISTS timetable (
    schedule_id SERIAL PRIMARY KEY,
    course_id INT REFERENCES courses(course_id),
    room_id INT REFERENCES rooms(room_id),
    day_of_week VARCHAR(15) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL
);

-- Insert 1 trial student group
INSERT INTO student_groups (group_id, group_name) VALUES (1, 'Computer Science - Year 1') ON CONFLICT DO NOTHING;

-- Insert 4 trial students
INSERT INTO students (name, group_id) VALUES 
('Student A', 1), ('Student B', 1), ('Student C', 1), ('Student D', 1);

-- Insert 2 trial professors
INSERT INTO professors (professor_id, name) VALUES 
(1, 'Dr. Ahmed'), (2, 'Dr. Sarah') ON CONFLICT DO NOTHING;

-- Insert 2 trial rooms
INSERT INTO rooms (room_id, room_name, capacity, is_lab) VALUES 
(101, 'Lab 1', 30, TRUE), (102, 'Hall A', 50, FALSE) ON CONFLICT DO NOTHING;

-- Insert 3 trial courses
INSERT INTO courses (course_id, course_code, course_name, weekly_hours, requires_lab, professor_id, group_id) VALUES 
(1, 'CS101', 'Intro to Programming', 2, TRUE, 1, 1),
(2, 'CS102', 'Data Structures', 2, FALSE, 1, 1),
(3, 'MATH101', 'Calculus I', 2, FALSE, 2, 1) ON CONFLICT DO NOTHING;