import psycopg2

# Connect to database (Replace YOUR_DB_PASSWORD with your actual password)
conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="123456", 
    host="localhost"
)
cur = conn.cursor()

# Safely create tables and insert data
cur.execute("""
DROP TABLE IF EXISTS timetable, courses, rooms, professors, students, student_groups CASCADE;

CREATE TABLE student_groups (group_id SERIAL PRIMARY KEY, group_name VARCHAR(50) NOT NULL);
CREATE TABLE students (student_id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, group_id INT REFERENCES student_groups(group_id));
CREATE TABLE professors (professor_id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL);
CREATE TABLE rooms (room_id SERIAL PRIMARY KEY, room_name VARCHAR(50) NOT NULL, capacity INT NOT NULL, is_lab BOOLEAN DEFAULT FALSE);
CREATE TABLE courses (course_id SERIAL PRIMARY KEY, course_code VARCHAR(20) NOT NULL, course_name VARCHAR(100) NOT NULL, weekly_hours INT NOT NULL, requires_lab BOOLEAN DEFAULT FALSE, professor_id INT REFERENCES professors(professor_id), group_id INT REFERENCES student_groups(group_id));
CREATE TABLE timetable (schedule_id SERIAL PRIMARY KEY, course_id INT REFERENCES courses(course_id), room_id INT REFERENCES rooms(room_id), day_of_week VARCHAR(15) NOT NULL, start_time TIME NOT NULL, end_time TIME NOT NULL);

INSERT INTO student_groups (group_id, group_name) VALUES (1, 'Computer Science - Year 1');
INSERT INTO students (name, group_id) VALUES ('Student A', 1), ('Student B', 1), ('Student C', 1), ('Student D', 1);
INSERT INTO professors (professor_id, name) VALUES (1, 'Dr. Ahmed'), (2, 'Dr. Sarah');
INSERT INTO rooms (room_id, room_name, capacity, is_lab) VALUES (101, 'Lab 1', 30, TRUE), (102, 'Hall A', 50, FALSE);
INSERT INTO courses (course_id, course_code, course_name, weekly_hours, requires_lab, professor_id, group_id) VALUES (1, 'CS101', 'Intro to Programming', 2, TRUE, 1, 1), (2, 'CS102', 'Data Structures', 2, FALSE, 1, 1), (3, 'MATH101', 'Calculus I', 2, FALSE, 2, 1);
""")

conn.commit()
cur.close()
conn.close()

print("Database clean and setup is 100% complete!")