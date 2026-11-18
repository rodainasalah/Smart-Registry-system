import psycopg2

# Connect to database
conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="123456",  # Replace with your actual password
    host="localhost"
)
cur = conn.cursor()

# 1. Rebuild Schema with Enrollments Table
cur.execute("""
DROP TABLE IF EXISTS timetable, enrollments, courses, rooms, professors, students, student_groups CASCADE;

CREATE TABLE students (
    student_id INT PRIMARY KEY, 
    name VARCHAR(100) NOT NULL, 
    type VARCHAR(20) NOT NULL
);

CREATE TABLE professors (
    professor_id SERIAL PRIMARY KEY, 
    name VARCHAR(100) NOT NULL
);

CREATE TABLE rooms (
    room_id SERIAL PRIMARY KEY, 
    room_name VARCHAR(50) NOT NULL, 
    capacity INT NOT NULL, 
    is_lab BOOLEAN DEFAULT FALSE
);

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY, 
    course_code VARCHAR(20) NOT NULL, 
    course_name VARCHAR(100) NOT NULL, 
    weekly_hours INT NOT NULL, 
    requires_lab BOOLEAN DEFAULT FALSE, 
    professor_id INT REFERENCES professors(professor_id)
);

CREATE TABLE enrollments (
    student_id INT REFERENCES students(student_id),
    course_id INT REFERENCES courses(course_id),
    PRIMARY KEY (student_id, course_id)
);

CREATE TABLE timetable (
    schedule_id SERIAL PRIMARY KEY, 
    course_id INT REFERENCES courses(course_id), 
    room_id INT REFERENCES rooms(room_id), 
    day_of_week VARCHAR(15) NOT NULL, 
    start_time TIME NOT NULL, 
    end_time TIME NOT NULL
);
""")

# 2. Insert Core Data
cur.execute("""
-- Insert Students
INSERT INTO students (student_id, name, type) VALUES 
(242500079, 'Rodaina El Goussi', 'Regular'),
(242500080, 'Mariam Mohammed Akmal', 'Regular'),
(242500324, 'Eyad Abdullah', 'Irregular'),
(242500999, 'Mahmoud Hesham Gharib', 'Irregular'); -- Placeholder ID

-- Insert Professors
INSERT INTO professors (name) VALUES 
('Dr. Hesham Mansour'), ('Dr. Mohamed Tharwat'), ('Dr. Walaa Hassan'), 
('Dr. Raghda Essam'), ('Dr. Hazem Hussein'), ('Dr. Hoda');

-- Insert Rooms (Max capacity 45)
INSERT INTO rooms (room_name, capacity, is_lab) VALUES 
('Hall G1', 45, FALSE), ('Hall G2', 45, FALSE), 
('Lab A', 45, TRUE), ('Lab B', 45, TRUE);

-- Insert Courses (Y3 AI Track + Y2 Retakes)
INSERT INTO courses (course_code, course_name, weekly_hours, requires_lab, professor_id) VALUES 
-- Y3 AI Track (IDs 1-8)
('AI301', 'Unsupervised Machine Learning', 3, TRUE, 1),
('AI302', 'Statistical ML & Inference', 3, TRUE, 1),
('AI303', 'Deep Neural Networks', 3, TRUE, 2),
('AI304', 'NLP & Transformers', 3, TRUE, 2),
('PRJ301', 'Graduation Project', 2, FALSE, 3),
('DAT301', 'Data Wrangling & Visualization', 3, TRUE, 4),
('ENG301', 'English Int. Career Prep', 2, FALSE, 5),
('FRE301', 'French 5', 2, FALSE, 6),
-- Y2 Retakes (IDs 9-13)
('MGT406', 'Agile, Scrum & DevOps', 3, FALSE, 1),
('DAT404', 'Big Data Analysis', 3, TRUE, 4),
('ENG201', 'Year 2 English', 2, FALSE, 5),
('MGT305', 'Supply Chain Management', 3, FALSE, 1),
('FRE201', 'French 3', 2, FALSE, 6),
('VR402', 'Augmented & Virtual Reality', 3, TRUE, 2);

-- Insert Enrollments
-- Regular Students (Rodaina & Mariam: Courses 1-8)
INSERT INTO enrollments (student_id, course_id)
SELECT s.student_id, c.course_id FROM students s, courses c 
WHERE s.type = 'Regular' AND c.course_id BETWEEN 1 AND 8;

-- Eyad (Courses 1-8 + Y2 English, Agile, Big Data)
INSERT INTO enrollments (student_id, course_id)
SELECT 242500324, course_id FROM courses WHERE course_id IN (1,2,3,4,5,6,7,8, 9,10,11);

-- Mahmoud (Courses 1-8 + Supply Chain, French 3, VR, Y2 English, Agile)
INSERT INTO enrollments (student_id, course_id)
SELECT 242500999, course_id FROM courses WHERE course_id IN (1,2,3,4,5,6,7,8, 9,11,12,13,14);
""")

conn.commit()
cur.close()
conn.close()
print("Real-world schema and enrollments successfully configured!")