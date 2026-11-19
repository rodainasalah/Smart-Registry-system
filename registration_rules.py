"""Registration rules: prerequisites, groups and irregular-student plans.

Rules
-----
1. A course can be taken only if ALL its prerequisites are Passed.
   Example: MTH205 (Mathematics for ML) failed -> AML206 (Applied ML) locked.
2. Only courses of the current semester can be registered.
3. A student cannot take courses from a year above their own year.
4. Number of groups = course capacity / largest suitable room (rounded up).
   Lab courses use lab rooms, others use halls.
5. Total credit hours cannot go above the max_credits setting.
"""
import math

from db import execute, get_setting, query

PRIORITY = {"retake": 1, "missing": 2, "current": 3}


# =========================================================
# GROUPS
# =========================================================

def group_size(course):
    """Seats in one group = biggest room of the right type."""
    rooms = query(
        "SELECT capacity FROM rooms WHERE is_lab = %s",
        (course["requires_lab"],),
    )
    if not rooms:
        return 0
    return min(course["capacity"], max(r["capacity"] for r in rooms))


def groups_for_course(course):
    """List the groups of a course with free seats."""
    size = group_size(course)
    if size == 0:
        return []

    count = math.ceil(course["capacity"] / size)

    taken = {
        row["group_no"]: row["n"]
        for row in query(
            "SELECT group_no, COUNT(*) AS n FROM enrollments "
            "WHERE course_id = %s GROUP BY group_no",
            (course["course_id"],),
        )
    }

    return [
        {
            "group_no": g,
            "size": size,
            "taken": taken.get(g, 0),
            "free": size - taken.get(g, 0),
        }
        for g in range(1, count + 1)
    ]


# =========================================================
# COURSE STATUS FOR ONE STUDENT
# =========================================================

def load_student(student_id):
    rows = query("SELECT * FROM students WHERE student_id = %s", (student_id,))
    return rows[0] if rows else None


def course_options(student_id):
    """Every course of the current semester with its status for this student.

    status: retake | missing | current  -> can register
            passed | locked | future     -> cannot register
    """
    student = load_student(student_id)
    semester = int(get_setting("current_semester", 1))

    results = {
        r["course_id"]: r["status"]
        for r in query(
            "SELECT course_id, status FROM results WHERE student_id = %s",
            (student_id,),
        )
    }

    prereqs = {}
    for row in query(
        "SELECT p.course_id, c.course_id AS pre_id, c.course_code "
        "FROM prerequisites p JOIN courses c ON c.course_id = p.prerequisite_id"
    ):
        prereqs.setdefault(row["course_id"], []).append(row)

    registered = {
        r["course_id"]: r["group_no"]
        for r in query(
            "SELECT course_id, group_no FROM enrollments WHERE student_id = %s",
            (student_id,),
        )
    }

    options = []
    courses = query(
        "SELECT * FROM courses WHERE semester = %s ORDER BY year, course_code",
        (semester,),
    )

    for course in courses:
        cid = course["course_id"]
        not_passed = [
            p["course_code"]
            for p in prereqs.get(cid, [])
            if results.get(p["pre_id"]) != "Passed"
        ]

        if results.get(cid) == "Passed":
            status, reason = "passed", "Already passed"
        elif course["year"] > student["year"]:
            status, reason = "future", f"Year {course['year']} course"
        elif not_passed:
            status = "locked"
            reason = "Must pass " + ", ".join(not_passed) + " first"
        elif results.get(cid) == "Failed":
            status, reason = "retake", "Failed before - retake"
        elif course["year"] < student["year"]:
            status, reason = "missing", f"Not taken from Year {course['year']}"
        else:
            status, reason = "current", f"Year {course['year']} course"

        options.append({
            **course,
            "status": status,
            "reason": reason,
            "can_register": status in PRIORITY,
            "registered_group": registered.get(cid),
        })

    return options


def is_irregular(student_id):
    """Irregular = has a failed course or a missing course from an earlier year."""
    student = load_student(student_id)
    failed = query(
        "SELECT 1 FROM results WHERE student_id = %s AND status = 'Failed'",
        (student_id,),
    )
    missing = query(
        "SELECT 1 FROM courses c WHERE c.year < %s AND NOT EXISTS ("
        "SELECT 1 FROM results r WHERE r.student_id = %s "
        "AND r.course_id = c.course_id AND r.status = 'Passed')",
        (student["year"], student_id),
    )
    return bool(failed or missing)


# =========================================================
# PLAN GENERATOR (irregular students)
# =========================================================

def generate_plan(student_id, max_credits=None):
    """Suggest courses for this semester.

    Order: retakes first, then missing earlier-year courses,
    then current-year courses, until max_credits is reached.
    Locked courses (prerequisite not passed) are never suggested.
    """
    if max_credits is None:
        max_credits = int(get_setting("max_credits", 21))

    eligible = [c for c in course_options(student_id) if c["can_register"]]
    eligible.sort(key=lambda c: (PRIORITY[c["status"]], c["year"], c["course_code"]))

    plan, total = [], 0
    for course in eligible:
        fits = total + course["credit_hours"] <= max_credits
        plan.append({**course, "suggested": fits})
        if fits:
            total += course["credit_hours"]

    return plan, total


# =========================================================
# REGISTER
# =========================================================

def registered_credits(student_id, ignore_course=None):
    rows = query(
        "SELECT COALESCE(SUM(c.credit_hours), 0) AS total "
        "FROM enrollments e JOIN courses c USING (course_id) "
        "WHERE e.student_id = %s AND e.course_id <> COALESCE(%s, -1)",
        (student_id, ignore_course),
    )
    return int(rows[0]["total"])


def register(student_id, course_id, group_no, registered_by="student",
             max_credits=None):
    """Register one course. Returns (True, message) or (False, reason).

    The admin may pass a different max_credits (customised plan).
    Prerequisites are always enforced.
    """
    option = next(
        (c for c in course_options(student_id) if c["course_id"] == course_id),
        None,
    )
    if option is None:
        return False, "This course is not offered this semester."
    if not option["can_register"]:
        return False, f"{option['course_code']}: {option['reason']}."

    if max_credits is None:
        max_credits = int(get_setting("max_credits", 21))
    if registered_credits(student_id, course_id) + option["credit_hours"] > max_credits:
        return False, f"Credit limit reached ({max_credits} credit hours)."

    group = next(
        (g for g in groups_for_course(option) if g["group_no"] == group_no),
        None,
    )
    if group is None:
        return False, "This group does not exist."

    same_group = option["registered_group"] == group_no
    if group["free"] <= 0 and not same_group:
        return False, f"Group {group_no} of {option['course_code']} is full."

    execute(
        "INSERT INTO enrollments (student_id, course_id, group_no, registered_by) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (student_id, course_id) "
        "DO UPDATE SET group_no = EXCLUDED.group_no, "
        "registered_by = EXCLUDED.registered_by",
        (student_id, course_id, group_no, registered_by),
    )
    return True, f"Registered in {option['course_code']} - Group {group_no}."


def drop(student_id, course_id):
    execute(
        "DELETE FROM enrollments WHERE student_id = %s AND course_id = %s",
        (student_id, course_id),
    )