import psycopg2
from ortools.sat.python.cp_model import CpModel, CpSolver, OPTIMAL, FEASIBLE

# Connect to database
conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="123456",  # Replace with your actual password
    host="localhost"
)
cur = conn.cursor()

# 1. Fetch only courses that have active student enrollments
cur.execute("""
    SELECT DISTINCT c.course_id, c.course_name, c.weekly_hours, c.requires_lab, c.professor_id 
    FROM courses c
    JOIN enrollments e ON c.course_id = e.course_id;
""")
courses = cur.fetchall()

cur.execute("SELECT room_id, room_name, is_lab FROM rooms;")
rooms = cur.fetchall()

cur.execute("SELECT student_id, course_id FROM enrollments;")
enrollments = cur.fetchall()

# Map student conflicts
student_courses = {}
for sid, cid in enrollments:
    if sid not in student_courses:
        student_courses[sid] = []
    student_courses[sid].append(cid)

# 2. Setup Constraint Model
model = CpModel()
DAYS = range(1, 6)   # Mon - Thu, Sat
SLOTS = range(1, 9)  # 9 AM to 5 PM

X = {}
for c in courses:
    c_id, c_name, hours, req_lab, prof_id = c
    for r in rooms:
        r_id, r_name, is_lab = r
        if req_lab and not is_lab:
            continue
        for d in DAYS:
            for s in SLOTS:
                if s + hours - 1 <= max(SLOTS):
                    X[(c_id, r_id, d, s)] = model.NewBoolVar(f"x_{c_id}_{r_id}_{d}_{s}")

# Hard Constraint 1: Schedule each active course once
for c in courses:
    c_id = c[0]
    model.Add(sum(X[k] for k in X if k[0] == c_id) == 1)

# Hard Constraint 2: Room capacity / double-booking
for r in rooms:
    r_id = r[0]
    for d in DAYS:
        for s in SLOTS:
            model.Add(
                sum(
                    X[(c[0], r_id, d, s_prime)]
                    for c in courses
                    for s_prime in range(max(1, s - c[2] + 1), s + 1)
                    if (c[0], r_id, d, s_prime) in X
                ) <= 1
            )

# Hard Constraint 3: Professor double-booking
for prof_id in set(c[4] for c in courses):
    prof_courses = [c for c in courses if c[4] == prof_id]
    for d in DAYS:
        for s in SLOTS:
            model.Add(
                sum(
                    X[(c[0], r[0], d, s_prime)]
                    for c in prof_courses
                    for r in rooms
                    for s_prime in range(max(1, s - c[2] + 1), s + 1)
                    if (c[0], r[0], d, s_prime) in X
                ) <= 1
            )

# Hard Constraint 4: Student double-booking
for sid, c_ids in student_courses.items():
    student_course_details = [c for c in courses if c[0] in c_ids]
    for d in DAYS:
        for s in SLOTS:
            model.Add(
                sum(
                    X[(c[0], r[0], d, s_prime)]
                    for c in student_course_details
                    for r in rooms
                    for s_prime in range(max(1, s - c[2] + 1), s + 1)
                    if (c[0], r[0], d, s_prime) in X
                ) <= 1
            )

# 3. Solve Model
solver = CpSolver()
status = solver.Solve(model)

day_names = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Saturday'}

if status in (OPTIMAL, FEASIBLE):
    print("\nSUCCESS: Active Timetable Generated!")
    print("-" * 50)
    cur.execute("TRUNCATE TABLE timetable;")
    
    for (c_id, r_id, d, s), var in X.items():
        if solver.Value(var) == 1:
            course = next(c for c in courses if c[0] == c_id)
            room = next(r for r in rooms if r[0] == r_id)
            
            start_hour = 8 + s
            end_hour = start_hour + course[2]
            
            start_time = f"{start_hour:02d}:00"
            end_time = f"{end_hour:02d}:00"
            day_str = day_names[d]
            
            print(f"[{day_str.ljust(9)}] {start_time} - {end_time} | {room[1].ljust(7)} | {course[1]}")
            
            cur.execute(
                "INSERT INTO timetable (course_id, room_id, day_of_week, start_time, end_time) VALUES (%s, %s, %s, %s, %s);",
                (c_id, r_id, day_str, f"{start_time}:00", f"{end_time}:00")
            )
    conn.commit()
    print("-" * 50)
    print("Saved to PostgreSQL 'timetable' table.")
else:
    print("No feasible schedule found. Check if student course selections overlap too heavily.")

cur.close()
conn.close()