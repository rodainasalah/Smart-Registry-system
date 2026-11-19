"""Smart University Registry - Login Portal (admin + student).

Run with the Run button in VS Code (or: streamlit run portal.py).
First run setup_database.py once to create the tables.
"""
import pandas as pd
import streamlit as st

import registration_rules as rules
import timetable_engine as T
from db import execute, get_setting, hash_password, query, set_setting

st.set_page_config(
    page_title="Smart University Registry",
    page_icon="🎓",
    layout="wide",
)

if "user" not in st.session_state:
    st.session_state.user = None


# =========================================================
# SMALL HELPERS
# =========================================================

def logout():
    st.session_state.user = None
    st.rerun()


def group_label(group):
    return f"Group {group['group_no']} ({group['free']} of {group['size']} seats left)"


def pick_group(course, key):
    """Dropdown of the course's groups. Full groups are hidden."""
    groups = rules.groups_for_course(course)
    current = course.get("registered_group")
    choices = [g for g in groups if g["free"] > 0 or g["group_no"] == current]

    if not choices:
        st.caption("All groups are full")
        return None

    index = 0
    for i, g in enumerate(choices):
        if g["group_no"] == current:
            index = i

    chosen = st.selectbox(
        "Group",
        choices,
        index=index,
        format_func=group_label,
        key=key,
        label_visibility="collapsed",
    )
    return chosen["group_no"]


def show_status_table(options):
    """Courses that cannot be registered, with the reason."""
    blocked = [c for c in options if not c["can_register"]]
    if not blocked:
        return
    with st.expander(f"🔒 Not available this semester ({len(blocked)})"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Code": c["course_code"],
                        "Course": c["course_name"],
                        "Year": c["year"],
                        "Reason": c["reason"],
                    }
                    for c in blocked
                ]
            ),
            hide_index=True,
            width="stretch",
        )


def show_registered(student_id, allow_drop=True, key_prefix="drop"):
    rows = query(
        "SELECT c.course_id, c.course_code, c.course_name, c.credit_hours, "
        "e.group_no, e.registered_by FROM enrollments e "
        "JOIN courses c USING (course_id) WHERE e.student_id = %s "
        "ORDER BY c.course_code",
        (student_id,),
    )
    total = sum(r["credit_hours"] for r in rows)
    max_credits = int(get_setting("max_credits", 21))

    st.subheader(f"Registered courses · {total} / {max_credits} credit hours")

    if not rows:
        st.info("No courses registered yet.")
        return

    for r in rows:
        col1, col2 = st.columns([6, 1])
        col1.write(
            f"**{r['course_code']}** {r['course_name']} · "
            f"Group {r['group_no']} · {r['credit_hours']} cr "
            f"· added by {r['registered_by']}"
        )
        if allow_drop and col2.button(
            "Drop", key=f"{key_prefix}_{student_id}_{r['course_id']}"
        ):
            rules.drop(student_id, r["course_id"])
            st.rerun()


def registration_form(student_id, registered_by, key_prefix):
    """List of courses the student may register, each with a group picker."""
    options = rules.course_options(student_id)
    allowed = [c for c in options if c["can_register"]]

    labels = {
        "retake": "🔁 Retake",
        "missing": "📌 Missing",
        "current": "🆕 This year",
    }

    st.subheader("Available courses")

    if not allowed:
        st.info("No courses available to register this semester.")

    for course in allowed:
        col1, col2, col3 = st.columns([4, 3, 1])
        col1.write(
            f"**{course['course_code']}** {course['course_name']}  \n"
            f"{labels[course['status']]} · {course['credit_hours']} cr"
            + (
                f" · ✅ Group {course['registered_group']}"
                if course["registered_group"]
                else ""
            )
        )
        with col2:
            group_no = pick_group(
                course, key=f"{key_prefix}_g_{student_id}_{course['course_id']}"
            )
        button_text = "Change" if course["registered_group"] else "Register"
        if group_no and col3.button(
            button_text,
            key=f"{key_prefix}_r_{student_id}_{course['course_id']}",
        ):
            ok, message = rules.register(
                student_id, course["course_id"], group_no, registered_by
            )
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    show_status_table(options)


# =========================================================
# LOGIN PAGE
# =========================================================

def login_page():
    st.title("🎓 Smart University Registry")
    st.caption("Log in to continue")

    role = st.radio("I am a", ["Student", "Admin"], horizontal=True)

    with st.form("login"):
        if role == "Student":
            username = st.text_input("Student ID")
        else:
            username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if not submitted:
        if role == "Student":
            st.caption("First login: your password is your student ID.")
        return

    if role == "Admin":
        rows = query(
            "SELECT admin_id, username FROM admins "
            "WHERE username = %s AND password_hash = %s",
            (username.strip(), hash_password(password)),
        )
        if rows:
            st.session_state.user = {
                "role": "admin",
                "id": rows[0]["admin_id"],
                "name": rows[0]["username"],
            }
            st.rerun()
        st.error("Wrong username or password.")

    else:
        if not username.strip().isdigit():
            st.error("Student ID must be a number.")
            return
        rows = query(
            "SELECT student_id, name FROM students "
            "WHERE student_id = %s AND password_hash = %s",
            (int(username.strip()), hash_password(password)),
        )
        if rows:
            st.session_state.user = {
                "role": "student",
                "id": rows[0]["student_id"],
                "name": rows[0]["name"],
            }
            st.rerun()
        st.error("Wrong student ID or password.")


# =========================================================
# STUDENT PAGE  (login redirects here)
# =========================================================

def student_page(user):
    student_id = user["id"]
    student = rules.load_student(student_id)
    semester = get_setting("current_semester", "1")

    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"ID {student_id} · Year {student['year']}")
    if st.sidebar.button("Log out"):
        logout()

    st.title("📝 Course Registration")
    kind = "Irregular" if rules.is_irregular(student_id) else "Regular"
    st.caption(f"Semester {semester} · {kind} student")

    if kind == "Irregular":
        plan, total = rules.generate_plan(student_id)
        suggested = [p["course_code"] for p in plan if p["suggested"]]
        st.info(
            "Suggested plan for you (retakes first): "
            + (", ".join(suggested) if suggested else "none")
            + f" · {total} credit hours"
        )

    tab1, tab2 = st.tabs(["📝 Register", "📅 My Timetable"])

    with tab1:
        registration_form(student_id, "student", "stu")
        st.markdown("---")
        show_registered(student_id, key_prefix="stu_drop")

    with tab2:
        entries = T.student_entries(student_id)
        if entries is None:
            st.info("The timetable has not been published yet.")
        elif not entries:
            st.info("You have no classes in the published timetable yet.")
        else:
            st.dataframe(T.week_grid(entries), width="stretch")
            st.caption(
                "If you change your registration, the admin needs to "
                "generate and publish the timetable again."
            )

    with st.sidebar.expander("Change password"):
        new_password = st.text_input("New password", type="password")
        if st.button("Save password"):
            if len(new_password) < 6:
                st.error("At least 6 characters.")
            else:
                execute(
                    "UPDATE students SET password_hash = %s WHERE student_id = %s",
                    (hash_password(new_password), student_id),
                )
                st.success("Password changed.")


# =========================================================
# ADMIN PAGES
# =========================================================

def student_picker(key, only_irregular=False):
    students = query("SELECT student_id, name, year FROM students ORDER BY name")
    if only_irregular:
        students = [s for s in students if rules.is_irregular(s["student_id"])]
    if not students:
        st.info("No students found.")
        return None
    chosen = st.selectbox(
        "Student",
        students,
        format_func=lambda s: f"{s['student_id']} - {s['name']} (Year {s['year']})",
        key=key,
    )
    return chosen["student_id"]


def import_students(df):
    """Add or update students from an uploaded table.

    Returns (number added, list of skipped row numbers).
    """
    added, skipped = 0, []
    for i, row in df.iterrows():
        try:
            sid = int(row["student_id"])
            name = str(row["name"]).strip()
            year = int(row["year"])
            if not name or name.lower() == "nan" or year not in (1, 2, 3, 4):
                raise ValueError
            password = row.get("password")
            if password is None or pd.isna(password) or str(password).strip() == "":
                password = sid
            execute(
                "INSERT INTO students VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (student_id) DO UPDATE "
                "SET name = EXCLUDED.name, year = EXCLUDED.year",
                (sid, name, year, hash_password(password)),
            )
            added += 1
        except (ValueError, TypeError):
            skipped.append(i + 2)  # +2 = row number in the file
    return added, skipped


def admin_students():
    st.header("👥 Students")

    # ---------- upload CSV / Excel ----------
    st.subheader("Upload students (CSV or Excel)")
    st.caption(
        "Columns needed: student_id, name, year. Optional: password "
        "(if empty, the password is the student ID)."
    )
    file = st.file_uploader("Choose file", type=["csv", "xlsx", "xls"])

    if file is not None:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        st.dataframe(df.head(20), hide_index=True, width="stretch")

        missing = {"student_id", "name", "year"} - set(df.columns)
        if missing:
            st.error("Missing columns: " + ", ".join(sorted(missing)))
        elif st.button("Import students", type="primary"):
            added, skipped = import_students(df)
            st.success(f"{added} students imported or updated.")
            if skipped:
                st.warning(f"Skipped rows (bad data): {skipped}")

    # ---------- add one student ----------
    st.markdown("---")
    st.subheader("Add a student manually")
    with st.form("add_student", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 3, 1])
        sid = col1.text_input("Student ID")
        name = col2.text_input("Full name")
        year = col3.selectbox("Year", [1, 2, 3, 4])
        if st.form_submit_button("➕ Add student", type="primary"):
            if not sid.strip().isdigit() or not name.strip():
                st.error("Enter a numeric ID and a name.")
            elif query("SELECT 1 FROM students WHERE student_id = %s", (int(sid),)):
                st.warning("This student ID already exists.")
            else:
                execute(
                    "INSERT INTO students VALUES (%s, %s, %s, %s)",
                    (int(sid), name.strip(), year, hash_password(sid.strip())),
                )
                st.success(f"{name} added. Password = student ID.")

    # ---------- list ----------
    st.markdown("---")
    students = query("SELECT student_id, name, year FROM students ORDER BY year, name")
    st.subheader(f"All students ({len(students)})")
    if students:
        table = pd.DataFrame(students)
        table["type"] = [
            "Irregular" if rules.is_irregular(s["student_id"]) else "Regular"
            for s in students
        ]
        st.dataframe(table, hide_index=True, width="stretch")

        to_delete = student_picker("delete_student_pick")
        if st.button("🗑️ Delete selected student"):
            execute("DELETE FROM students WHERE student_id = %s", (to_delete,))
            st.rerun()


def admin_courses():
    st.header("📚 Courses & Prerequisites")

    professors = query("SELECT professor_id, name FROM professors ORDER BY name")
    courses = query("SELECT * FROM courses ORDER BY year, semester, course_code")

    # ---------- add course ----------
    with st.form("add_course", clear_on_submit=True):
        st.subheader("Add a course")
        col1, col2 = st.columns([1, 3])
        code = col1.text_input("Code", placeholder="AML206")
        name = col2.text_input("Name", placeholder="Applied Machine Learning")

        col1, col2, col3, col4 = st.columns(4)
        year = col1.selectbox("Year", [1, 2, 3, 4])
        semester = col2.selectbox("Semester", [1, 2])
        credits = col3.number_input("Credit hours", 1, 6, 3)
        capacity = col4.number_input("Capacity (max students)", 1, 1000, 45)

        col1, col2, col3 = st.columns(3)
        lecture_sessions = col1.number_input("Lectures per week (90 min)", 0, 6, 1)
        tutorial_sessions = col2.number_input("Tutorials per week (90 min)", 0, 6, 1)
        requires_lab = col3.checkbox("Tutorials need a lab")
        professor = st.selectbox(
            "Professor",
            [None] + professors,
            format_func=lambda p: "- none -" if p is None else p["name"],
        )

        prereq_choices = st.multiselect(
            "Prerequisites (must be PASSED first)",
            courses,
            format_func=lambda c: f"{c['course_code']} - {c['course_name']}",
        )

        if st.form_submit_button("➕ Add course", type="primary"):
            code = code.strip().upper()
            if not code or not name.strip():
                st.error("Code and name are required.")
            elif query("SELECT 1 FROM courses WHERE course_code = %s", (code,)):
                st.warning("A course with this code already exists.")
            else:
                execute(
                    "INSERT INTO courses (course_code, course_name, year, semester, "
                    "credit_hours, capacity, requires_lab, lecture_sessions, "
                    "tutorial_sessions, professor_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        code, name.strip(), year, semester, int(credits),
                        int(capacity), requires_lab, int(lecture_sessions),
                        int(tutorial_sessions),
                        professor["professor_id"] if professor else None,
                    ),
                )
                new_id = query(
                    "SELECT course_id FROM courses WHERE course_code = %s", (code,)
                )[0]["course_id"]
                for p in prereq_choices:
                    execute(
                        "INSERT INTO prerequisites VALUES (%s, %s)",
                        (new_id, p["course_id"]),
                    )
                st.success(f"{code} added.")
                st.rerun()

    # ---------- edit prerequisites ----------
    st.markdown("---")
    st.subheader("Edit prerequisites")
    if courses:
        course = st.selectbox(
            "Course",
            courses,
            format_func=lambda c: f"{c['course_code']} - {c['course_name']}",
            key="edit_prereq_course",
        )
        current_ids = {
            r["prerequisite_id"]
            for r in query(
                "SELECT prerequisite_id FROM prerequisites WHERE course_id = %s",
                (course["course_id"],),
            )
        }
        others = [c for c in courses if c["course_id"] != course["course_id"]]
        new_prereqs = st.multiselect(
            "Must pass first",
            others,
            default=[c for c in others if c["course_id"] in current_ids],
            format_func=lambda c: f"{c['course_code']} - {c['course_name']}",
            key=f"prereq_edit_{course['course_id']}",
        )
        col1, col2 = st.columns(2)
        if col1.button("💾 Save prerequisites"):
            execute(
                "DELETE FROM prerequisites WHERE course_id = %s",
                (course["course_id"],),
            )
            for p in new_prereqs:
                execute(
                    "INSERT INTO prerequisites VALUES (%s, %s)",
                    (course["course_id"], p["course_id"]),
                )
            st.success("Prerequisites saved.")
            st.rerun()
        if col2.button("🗑️ Delete this course"):
            execute("DELETE FROM courses WHERE course_id = %s", (course["course_id"],))
            st.rerun()

    # ---------- list ----------
    st.markdown("---")
    st.subheader(f"All courses ({len(courses)})")
    prof_names = {p["professor_id"]: p["name"] for p in professors}
    prereq_text = {}
    for r in query(
        "SELECT p.course_id, c.course_code FROM prerequisites p "
        "JOIN courses c ON c.course_id = p.prerequisite_id"
    ):
        prereq_text.setdefault(r["course_id"], []).append(r["course_code"])

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Code": c["course_code"],
                    "Course": c["course_name"],
                    "Year": c["year"],
                    "Semester": c["semester"],
                    "Credits": c["credit_hours"],
                    "Capacity": c["capacity"],
                    "Lectures/wk": c["lecture_sessions"],
                    "Tutorials/wk": c["tutorial_sessions"],
                    "Lab": "Yes" if c["requires_lab"] else "No",
                    "Professor": prof_names.get(c["professor_id"], "-"),
                    "Groups": len(rules.groups_for_course(c)),
                    "Prerequisites": ", ".join(prereq_text.get(c["course_id"], [])),
                }
                for c in courses
            ]
        ),
        hide_index=True,
        width="stretch",
    )


def admin_rooms():
    st.subheader("🏫 Rooms")
    st.caption(
        "Group size = the biggest room of the right type "
        "(labs for lab courses, halls for the rest)."
    )

    with st.form("add_room", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        name = col1.text_input("Room name")
        capacity = col2.number_input("Capacity", 1, 500, 45)
        is_lab = col3.checkbox("Lab")
        if st.form_submit_button("➕ Add room", type="primary"):
            if not name.strip():
                st.error("Room name is required.")
            elif query("SELECT 1 FROM rooms WHERE room_name = %s", (name.strip(),)):
                st.warning("Room already exists.")
            else:
                execute(
                    "INSERT INTO rooms (room_name, capacity, is_lab) VALUES (%s, %s, %s)",
                    (name.strip(), int(capacity), is_lab),
                )
                st.rerun()

    for room in query("SELECT * FROM rooms ORDER BY room_name"):
        col1, col2 = st.columns([5, 1])
        col1.write(
            f"**{room['room_name']}** · {'Lab' if room['is_lab'] else 'Hall'} "
            f"· {room['capacity']} seats"
        )
        if col2.button("Delete", key=f"room_del_{room['room_id']}"):
            execute("DELETE FROM rooms WHERE room_id = %s", (room["room_id"],))
            st.rerun()


def admin_results():
    st.header("📊 Results (Passed / Failed)")
    st.caption(
        "Prerequisites and the irregular plan are based on these results."
    )
    student_id = student_picker("results_student")
    if student_id is None:
        return

    student = rules.load_student(student_id)
    courses = query(
        "SELECT * FROM courses WHERE year <= %s ORDER BY year, semester, course_code",
        (student["year"],),
    )
    results = {
        r["course_id"]: r["status"]
        for r in query(
            "SELECT course_id, status FROM results WHERE student_id = %s",
            (student_id,),
        )
    }

    choices = ["Not taken", "Passed", "Failed"]
    new_values = {}

    for c in courses:
        col1, col2 = st.columns([4, 2])
        col1.write(f"**{c['course_code']}** {c['course_name']} · Y{c['year']} S{c['semester']}")
        current = results.get(c["course_id"], "Not taken")
        new_values[c["course_id"]] = col2.selectbox(
            "Result",
            choices,
            index=choices.index(current),
            key=f"res_{student_id}_{c['course_id']}",
            label_visibility="collapsed",
        )

    if st.button("💾 Save results", type="primary"):
        for course_id, value in new_values.items():
            if value == "Not taken":
                execute(
                    "DELETE FROM results WHERE student_id = %s AND course_id = %s",
                    (student_id, course_id),
                )
            else:
                execute(
                    "INSERT INTO results VALUES (%s, %s, %s) "
                    "ON CONFLICT (student_id, course_id) "
                    "DO UPDATE SET status = EXCLUDED.status",
                    (student_id, course_id, value),
                )
        st.success("Results saved.")


def admin_register():
    st.header("🧾 Register a student manually")
    st.caption("Prerequisites are still checked; locked courses cannot be added.")
    student_id = student_picker("register_student")
    if student_id is None:
        return
    registration_form(student_id, "admin", "adm")
    st.markdown("---")
    show_registered(student_id, key_prefix="adm_drop")


def admin_irregular():
    st.header("🔁 Irregular student plans")
    st.caption(
        "The system suggests courses: retakes first, then missing courses, "
        "then this year's courses. Locked courses (prerequisite not passed) "
        "are never suggested. You can change anything before saving."
    )

    student_id = student_picker("irregular_student", only_irregular=True)
    if student_id is None:
        return

    default_max = int(get_setting("max_credits", 21))
    max_credits = st.number_input(
        "Max credit hours for this student",
        min_value=1,
        max_value=30,
        value=default_max,
        key=f"irr_max_{student_id}",
    )

    plan, total = rules.generate_plan(student_id, max_credits)
    st.write(f"Suggested load: **{total} credit hours**")

    labels = {"retake": "🔁 Retake", "missing": "📌 Missing", "current": "🆕 This year"}
    selected = []

    for course in plan:
        col1, col2, col3 = st.columns([1, 5, 3])
        take = col1.checkbox(
            "Take",
            value=course["suggested"] or bool(course["registered_group"]),
            key=f"irr_take_{student_id}_{course['course_id']}_{max_credits}",
            label_visibility="collapsed",
        )
        col2.write(
            f"**{course['course_code']}** {course['course_name']} · "
            f"{labels[course['status']]} · {course['credit_hours']} cr"
        )
        with col3:
            group_no = pick_group(course, key=f"irr_g_{student_id}_{course['course_id']}")
        if take and group_no:
            selected.append((course, group_no))

    chosen_credits = sum(c["credit_hours"] for c, _ in selected)
    st.write(f"Selected: **{chosen_credits} / {max_credits} credit hours**")

    if st.button("💾 Register selected courses", type="primary"):
        if chosen_credits > max_credits:
            st.error("Selected courses are above the credit limit.")
        else:
            # remove courses that were un-ticked, then register the ticked ones
            keep = {c["course_id"] for c, _ in selected}
            for course in plan:
                if course["registered_group"] and course["course_id"] not in keep:
                    rules.drop(student_id, course["course_id"])
            for course, group_no in selected:
                ok, message = rules.register(
                    student_id, course["course_id"], group_no, "admin", max_credits
                )
                (st.success if ok else st.error)(message)

    show_status_table(rules.course_options(student_id))
    st.markdown("---")
    show_registered(student_id, key_prefix="irr_drop")


def admin_professors():
    st.subheader("👨‍🏫 Professors")

    professor_name = st.text_input(
        "Professor Name",
        placeholder="Example: Dr. Ahmed Hassan",
    )

    if st.button("➕ Add Professor", type="primary"):
        cleaned_name = professor_name.strip()

        if not cleaned_name:
            st.error("Please enter a professor name.")
        elif query(
            "SELECT 1 FROM professors WHERE LOWER(name) = LOWER(%s)",
            (cleaned_name,),
        ):
            st.warning("This professor already exists.")
        else:
            execute("INSERT INTO professors (name) VALUES (%s)", (cleaned_name,))
            st.success(f"{cleaned_name} added successfully.")
            st.rerun()

    st.markdown("---")
    professors = query(
        "SELECT p.professor_id, p.name, COUNT(c.course_id) AS courses "
        "FROM professors p LEFT JOIN courses c USING (professor_id) "
        "GROUP BY p.professor_id ORDER BY p.name"
    )

    if not professors:
        st.info("No professors have been added yet.")

    for professor in professors:
        col1, col2 = st.columns([5, 1])
        col1.write(
            f"**{professor['name']}** · teaches {professor['courses']} course(s)"
        )
        if col2.button("Delete", key=f"del_prof_{professor['professor_id']}"):
            execute(
                "DELETE FROM professors WHERE professor_id = %s",
                (professor["professor_id"],),
            )
            st.rerun()


def admin_availability():
    st.subheader("🕐 Professor Availability & Preferences")

    professors = query("SELECT professor_id, name FROM professors ORDER BY name")
    if not professors:
        st.warning("Add at least one professor first.")
        return

    professor = st.selectbox(
        "Select Professor",
        professors,
        format_func=lambda p: p["name"],
    )
    pid = professor["professor_id"]

    saved = {
        (r["day"], r["slot_id"]): r["status"]
        for r in query(
            "SELECT day, slot_id, status FROM professor_availability "
            "WHERE professor_id = %s",
            (pid,),
        )
    }

    st.info(
        "**Available**: unticked = the professor CANNOT teach then (hard rule).  \n"
        "**Preferred**: ticked = the optimizer tries to use it (soft rule)."
    )

    availability, preferences = [], []

    for day in T.DAYS:
        st.markdown(f"#### {day}")
        columns = st.columns(len(T.SLOTS))
        for index, slot in enumerate(T.SLOTS):
            pair = (day, slot["id"])
            with columns[index]:
                st.caption(f"{slot['start']}-{slot['end']}")
                available = st.checkbox(
                    "Available",
                    value=saved.get(pair) != "unavailable",
                    key=f"avail_{pid}_{day}_{slot['id']}",
                )
                preferred = st.checkbox(
                    "Preferred",
                    value=saved.get(pair) == "preferred",
                    key=f"pref_{pid}_{day}_{slot['id']}",
                )
            if available:
                availability.append(pair)
            if preferred:
                preferences.append(pair)

    if st.button("💾 Save Professor Availability", type="primary"):
        if any(pair not in availability for pair in preferences):
            st.error("A preferred period must also be marked as available.")
        else:
            execute(
                "DELETE FROM professor_availability WHERE professor_id = %s",
                (pid,),
            )
            for day in T.DAYS:
                for slot in T.SLOTS:
                    pair = (day, slot["id"])
                    status = None
                    if pair not in availability:
                        status = "unavailable"
                    elif pair in preferences:
                        status = "preferred"
                    if status:
                        execute(
                            "INSERT INTO professor_availability "
                            "VALUES (%s, %s, %s, %s)",
                            (pid, day, slot["id"], status),
                        )
            st.success(f"Availability saved for {professor['name']}.")


def admin_generate():
    st.subheader("⚙️ Generate & Publish Timetable")

    semester = get_setting("current_semester", "1")
    counts = query(
        "SELECT "
        "(SELECT COUNT(*) FROM professors) AS professors, "
        "(SELECT COUNT(*) FROM rooms) AS rooms, "
        "(SELECT COUNT(DISTINCT (e.course_id, e.group_no)) FROM enrollments e "
        " JOIN courses c USING (course_id) WHERE c.semester = %s) AS groups, "
        "(SELECT COUNT(DISTINCT e.student_id) FROM enrollments e "
        " JOIN courses c USING (course_id) WHERE c.semester = %s) AS students",
        (semester, semester),
    )[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Semester", semester)
    col2.metric("Registered students", counts["students"])
    col3.metric("Course groups", counts["groups"])
    col4.metric("Rooms", counts["rooms"])

    st.caption(
        "Each course group with registered students gets its lectures and "
        "tutorials. Students never get two classes at the same time."
    )

    if st.button("🚀 Generate Optimized Timetable", type="primary"):
        with st.spinner("Running OR-Tools CP-SAT..."):
            result = T.generate()

        if result["errors"]:
            st.error("A timetable could not be generated:")
            for error in result["errors"]:
                st.write(f"- {error}")
        else:
            st.success(
                f"Run #{result['run_id']} saved · {result['status']} · "
                f"score {result['score']}/100 · {result['sessions']} sessions · "
                f"{result['solve_time']:.1f} s"
            )

    runs = T.list_runs()
    if not runs:
        st.info("No timetable generated yet.")
        return

    st.markdown("---")
    st.subheader("Saved runs")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Run": r["run_id"],
                    "Created": r["created_at"].strftime("%Y-%m-%d %H:%M"),
                    "Semester": r["semester"],
                    "Status": r["status"],
                    "Score": f"{r['score']}/100",
                    "Not preferred": r["not_preferred"],
                    "Single-class days": r["single_class_days"],
                    "Published": "✅" if r["published"] else "",
                }
                for r in runs
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    col1, col2 = st.columns([3, 1])
    run = col1.selectbox(
        "Run",
        runs,
        format_func=lambda r: f"Run #{r['run_id']} · score {r['score']}/100",
        label_visibility="collapsed",
        key="publish_run",
    )
    if col2.button("📢 Publish this run"):
        T.publish(run["run_id"])
        st.success(f"Run #{run['run_id']} is now visible to students.")
        st.rerun()


def admin_view_timetable():
    st.subheader("📅 View Timetable")

    runs = T.list_runs()
    if not runs:
        st.info("No timetable generated yet.")
        return

    published_index = next(
        (i for i, r in enumerate(runs) if r["published"]), 0
    )
    run = st.selectbox(
        "Run",
        runs,
        index=published_index,
        format_func=lambda r: (
            f"Run #{r['run_id']} · score {r['score']}/100"
            + (" · published" if r["published"] else "")
        ),
        key="view_run",
    )
    entries = T.run_entries(run["run_id"])

    view = st.radio(
        "Show timetable for",
        ["Course group", "Professor", "Room"],
        horizontal=True,
    )

    if view == "Course group":
        names = sorted({f"{e['course_code']} G{e['group_no']}" for e in entries})
        chosen = st.selectbox("Course group", names)
        shown = [e for e in entries if f"{e['course_code']} G{e['group_no']}" == chosen]
    elif view == "Professor":
        chosen = st.selectbox("Professor", sorted({e["professor"] for e in entries}))
        shown = [e for e in entries if e["professor"] == chosen]
    else:
        chosen = st.selectbox("Room", sorted({e["room_name"] for e in entries}))
        shown = [e for e in entries if e["room_name"] == chosen]

    st.dataframe(T.week_grid(shown), width="stretch")


def admin_schedule():
    st.header("🗓️ Schedule Management")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "👨‍🏫 Professors",
            "🕐 Availability",
            "🏫 Rooms",
            "⚙️ Generate & Publish",
            "📅 View Timetable",
        ]
    )
    with tab1:
        admin_professors()
    with tab2:
        admin_availability()
    with tab3:
        admin_rooms()
    with tab4:
        admin_generate()
    with tab5:
        admin_view_timetable()


def admin_settings(user):
    st.header("⚙️ Settings")
    col1, col2 = st.columns(2)
    semester = col1.selectbox(
        "Current semester",
        [1, 2],
        index=int(get_setting("current_semester", 1)) - 1,
    )
    max_credits = col2.number_input(
        "Default max credit hours per student",
        1, 30, int(get_setting("max_credits", 21)),
    )
    if st.button("💾 Save settings", type="primary"):
        set_setting("current_semester", semester)
        set_setting("max_credits", int(max_credits))
        st.success("Settings saved.")

    st.markdown("---")
    st.subheader("Change admin password")
    new_password = st.text_input("New password", type="password")
    if st.button("Save password"):
        if len(new_password) < 6:
            st.error("At least 6 characters.")
        else:
            execute(
                "UPDATE admins SET password_hash = %s WHERE admin_id = %s",
                (hash_password(new_password), user["id"]),
            )
            st.success("Password changed.")


def admin_page(user):
    st.sidebar.write(f"🛠️ Admin: **{user['name']}**")
    page = st.sidebar.radio(
        "Menu",
        [
            "Schedule Management",
            "Students",
            "Courses & Prerequisites",
            "Results",
            "Register Student",
            "Irregular Plans",
            "Settings",
        ],
    )
    if st.sidebar.button("Log out"):
        logout()

    if page == "Schedule Management":
        admin_schedule()
    elif page == "Students":
        admin_students()
    elif page == "Courses & Prerequisites":
        admin_courses()
    elif page == "Results":
        admin_results()
    elif page == "Register Student":
        admin_register()
    elif page == "Irregular Plans":
        admin_irregular()
    else:
        admin_settings(user)


# =========================================================
# MAIN
# =========================================================

user = st.session_state.user

try:
    if user is None:
        login_page()
    elif user["role"] == "admin":
        admin_page(user)
    else:
        student_page(user)
except Exception as error:
    st.error(f"Database error: {error}")
    st.caption("Check your .env file and that setup_database.py has been run.")