"""Timetable engine that works with the PostgreSQL database.

What it schedules
-----------------
Every course GROUP that has registered students gets its own sessions:
  - lecture_sessions  x 90-min lecture  (hall)
  - tutorial_sessions x 90-min tutorial (lab if the course needs a lab)

Hard constraints (never broken)
  HC01 every session is placed exactly once
  HC02 a room holds at most one session at a time
  HC03 a professor teaches at most one session at a time
  HC04 a student never has two sessions at the same time
  HC05 the room is big enough and of the right type
  HC06 professors are never placed in their unavailable periods

Soft constraints (minimised)
  SC01 +5  session outside the professor's preferred periods
  SC02 +10 a student has only one class on a day
  SC03 +20 a session that doesn't need a lab uses a lab (not in the score)

Quality score = max(0, 100 - 5 x SC01 - 10 x SC02)
"""
from ortools.sat.python import cp_model

from db import execute, get_connection, get_setting, query

DAYS = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]

SLOTS = [
    {"id": 1, "start": "09:00", "end": "10:30"},
    {"id": 2, "start": "10:30", "end": "12:00"},
    {"id": 3, "start": "12:00", "end": "13:30"},
    {"id": 4, "start": "13:30", "end": "15:00"},
    {"id": 5, "start": "15:00", "end": "16:30"},
    {"id": 6, "start": "16:30", "end": "18:00"},
]

NOT_PREFERRED_PENALTY = 5
SINGLE_CLASS_DAY_PENALTY = 10
LAB_MISUSE_PENALTY = 20


# =========================================================
# STEP 1 - LOAD DATA FROM THE DATABASE
# =========================================================

def load_professors():
    professors = {
        p["professor_id"]: {**p, "unavailable": set(), "preferred": set()}
        for p in query("SELECT professor_id, name FROM professors")
    }
    for row in query("SELECT * FROM professor_availability"):
        if row["professor_id"] in professors:
            professors[row["professor_id"]][row["status"]].add(
                (row["day"], row["slot_id"])
            )
    return professors


def build_sessions(semester):
    """One session per (course, group, lecture/tutorial number)."""
    sections = query(
        "SELECT c.*, e.group_no, COUNT(*) AS size "
        "FROM enrollments e JOIN courses c USING (course_id) "
        "WHERE c.semester = %s "
        "GROUP BY c.course_id, e.group_no ORDER BY c.course_code, e.group_no",
        (semester,),
    )

    sessions = []
    for sec in sections:
        for n in range(sec["lecture_sessions"]):
            sessions.append({**sec, "type": "lecture", "needs_lab": False, "n": n + 1})
        for n in range(sec["tutorial_sessions"]):
            sessions.append({
                **sec, "type": "tutorial",
                "needs_lab": sec["requires_lab"], "n": n + 1,
            })

    for i, s in enumerate(sessions):
        s["idx"] = i
        s["label"] = f"{s['course_code']} G{s['group_no']} {s['type']}"
    return sessions


def build_student_units(semester):
    """Students with exactly the same groups behave the same,
    so we keep one 'unit' per unique set of (course, group)."""
    timetable = {}
    for row in query(
        "SELECT e.student_id, e.course_id, e.group_no FROM enrollments e "
        "JOIN courses c USING (course_id) WHERE c.semester = %s",
        (semester,),
    ):
        timetable.setdefault(row["student_id"], set()).add(
            (row["course_id"], row["group_no"])
        )
    return list({frozenset(groups) for groups in timetable.values()})


# =========================================================
# STEP 2 - EXPLAIN PROBLEMS BEFORE SOLVING
# =========================================================

def validate(sessions, rooms, professors, units):
    errors = []
    periods = len(DAYS) * len(SLOTS)

    for s in sessions:
        if s["professor_id"] is None:
            errors.append(f"{s['course_code']} has no professor assigned.")
            continue
        fitting = [r for r in rooms if r["is_lab"] == s["needs_lab"] or not s["needs_lab"]]
        if not fitting:
            errors.append(f"Cannot place {s['label']}: there is no lab room.")
        elif max(r["capacity"] for r in fitting) < s["size"]:
            errors.append(
                f"Cannot place {s['label']}: no room holds {s['size']} students "
                f"(largest = {max(r['capacity'] for r in fitting)})."
            )

    for pid, prof in professors.items():
        needed = sum(1 for s in sessions if s["professor_id"] == pid)
        free = periods - len(prof["unavailable"])
        if needed > free:
            errors.append(
                f"{prof['name']} must teach {needed} sessions "
                f"but is available for only {free} periods."
            )

    for unit in units:
        needed = sum(1 for s in sessions if (s["course_id"], s["group_no"]) in unit)
        if needed > periods:
            errors.append(
                f"Some students have {needed} sessions but the week has "
                f"only {periods} periods."
            )
            break

    return sorted(set(errors))


# =========================================================
# STEP 3 - BUILD AND SOLVE
# =========================================================

def generate(time_limit=30):
    semester = int(get_setting("current_semester", 1))
    rooms = query("SELECT * FROM rooms ORDER BY room_id")
    professors = load_professors()
    sessions = build_sessions(semester)
    units = build_student_units(semester)

    if not sessions:
        return {"status": "NO DATA", "errors": [
            "No students are registered in this semester's courses yet."
        ]}
    if not rooms:
        return {"status": "NO DATA", "errors": ["Add at least one room first."]}

    errors = validate(sessions, rooms, professors, units)
    if errors:
        return {"status": "INVALID DATA", "errors": errors}

    model = cp_model.CpModel()
    x = {}                       # (session idx, room_id, day, slot) -> bool var
    at_period = {}               # (day, slot) -> list of keys

    for s in sessions:
        prof = professors[s["professor_id"]]
        for room in rooms:
            if room["capacity"] < s["size"]:
                continue
            if s["needs_lab"] and not room["is_lab"]:
                continue
            for day in DAYS:
                for slot in SLOTS:
                    if (day, slot["id"]) in prof["unavailable"]:
                        continue
                    key = (s["idx"], room["room_id"], day, slot["id"])
                    x[key] = model.new_bool_var(str(key))
                    at_period.setdefault((day, slot["id"]), []).append(key)

    # HC01
    for s in sessions:
        options = [v for k, v in x.items() if k[0] == s["idx"]]
        if not options:
            return {"status": "INVALID DATA", "errors": [
                f"No free day, time and room for {s['label']}."
            ]}
        model.add_exactly_one(options)

    unit_of_session = {
        s["idx"]: [
            u for u, unit in enumerate(units)
            if (s["course_id"], s["group_no"]) in unit
        ]
        for s in sessions
    }

    for keys in at_period.values():
        # HC02 rooms
        by_room = {}
        for k in keys:
            by_room.setdefault(k[1], []).append(x[k])
        # HC03 professors
        by_prof = {}
        for k in keys:
            by_prof.setdefault(sessions[k[0]]["professor_id"], []).append(x[k])
        # HC04 students
        by_unit = {}
        for k in keys:
            for u in unit_of_session[k[0]]:
                by_unit.setdefault(u, []).append(x[k])

        for group in (by_room, by_prof, by_unit):
            for variables in group.values():
                if len(variables) > 1:
                    model.add_at_most_one(variables)

    # SC01 not preferred
    not_preferred = []
    for k, v in x.items():
        prof = professors[sessions[k[0]]["professor_id"]]
        if prof["preferred"] and (k[2], k[3]) not in prof["preferred"]:
            not_preferred.append(v)

    # SC02 single-class days
    single_days = []
    for u in range(len(units)):
        for day in DAYS:
            today = [
                v for k, v in x.items()
                if k[2] == day and u in unit_of_session[k[0]]
            ]
            if not today:
                continue
            only_one = model.new_bool_var(f"single_{u}_{day}")
            model.add(sum(today) == 1).only_enforce_if(only_one)
            model.add(sum(today) != 1).only_enforce_if(only_one.Not())
            single_days.append(only_one)

    # SC03 lab misuse
    lab_rooms = {r["room_id"] for r in rooms if r["is_lab"]}
    lab_misuse = [
        v for k, v in x.items()
        if k[1] in lab_rooms and not sessions[k[0]]["needs_lab"]
    ]

    model.minimize(
        NOT_PREFERRED_PENALTY * sum(not_preferred)
        + SINGLE_CLASS_DAY_PENALTY * sum(single_days)
        + LAB_MISUSE_PENALTY * sum(lab_misuse)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": solver.status_name(status), "errors": [
            "The hard rules cannot all be met together. "
            "Check professor availability, rooms and student registrations."
        ]}

    np_count = sum(solver.value(v) for v in not_preferred)
    sd_count = sum(solver.value(v) for v in single_days)
    score = max(0, 100 - NOT_PREFERRED_PENALTY * np_count
                - SINGLE_CLASS_DAY_PENALTY * sd_count)

    entries = [
        {
            "course_id": sessions[k[0]]["course_id"],
            "group_no": sessions[k[0]]["group_no"],
            "session_type": sessions[k[0]]["type"],
            "day": k[2],
            "slot_id": k[3],
            "room_id": k[1],
            "professor_id": sessions[k[0]]["professor_id"],
        }
        for k, v in x.items() if solver.value(v) == 1
    ]

    run_id = save_run(
        semester, solver.status_name(status), score, np_count,
        sd_count, solver.wall_time, entries,
    )

    return {
        "status": solver.status_name(status),
        "run_id": run_id,
        "score": score,
        "not_preferred": np_count,
        "single_class_days": sd_count,
        "solve_time": solver.wall_time,
        "sessions": len(entries),
        "errors": [],
    }


# =========================================================
# STEP 4 - SAVE, PUBLISH, READ
# =========================================================

def save_run(semester, status, score, np_count, sd_count, seconds, entries):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO timetable_runs (semester, status, score, not_preferred, "
        "single_class_days, solve_seconds) VALUES (%s, %s, %s, %s, %s, %s) "
        "RETURNING run_id",
        (semester, status, score, np_count, sd_count, round(seconds, 2)),
    )
    run_id = cur.fetchone()[0]
    for e in entries:
        cur.execute(
            "INSERT INTO timetable_entries (run_id, course_id, group_no, "
            "session_type, day, slot_id, room_id, professor_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (run_id, e["course_id"], e["group_no"], e["session_type"],
             e["day"], e["slot_id"], e["room_id"], e["professor_id"]),
        )
    conn.commit()
    cur.close()
    conn.close()
    return run_id


def publish(run_id):
    execute("UPDATE timetable_runs SET published = FALSE")
    execute("UPDATE timetable_runs SET published = TRUE WHERE run_id = %s", (run_id,))


def list_runs():
    return query("SELECT * FROM timetable_runs ORDER BY run_id DESC")


def published_run():
    rows = query("SELECT * FROM timetable_runs WHERE published = TRUE")
    return rows[0] if rows else None


ENTRY_SQL = """
    SELECT t.day, t.slot_id, c.course_code, c.course_name, t.group_no,
           t.session_type, r.room_name, p.name AS professor
    FROM timetable_entries t
    JOIN courses c ON c.course_id = t.course_id
    JOIN rooms r ON r.room_id = t.room_id
    JOIN professors p ON p.professor_id = t.professor_id
"""


def run_entries(run_id):
    return query(ENTRY_SQL + " WHERE t.run_id = %s", (run_id,))


def student_entries(student_id):
    """The published timetable, only the groups this student registered."""
    run = published_run()
    if run is None:
        return None
    return query(
        ENTRY_SQL + " JOIN enrollments e ON e.course_id = t.course_id "
        "AND e.group_no = t.group_no "
        "WHERE t.run_id = %s AND e.student_id = %s",
        (run["run_id"], student_id),
    )


def week_grid(entries):
    """Rows = time slots, columns = days."""
    import pandas as pd

    grid = pd.DataFrame(
        "",
        index=[f"{s['start']}-{s['end']}" for s in SLOTS],
        columns=DAYS,
    )
    slot_names = {s["id"]: f"{s['start']}-{s['end']}" for s in SLOTS}
    for e in entries:
        text = (
            f"{e['course_code']} G{e['group_no']} {e['session_type']} "
            f"· {e['room_name']}"
        )
        cell = grid.loc[slot_names[e["slot_id"]], e["day"]]
        grid.loc[slot_names[e["slot_id"]], e["day"]] = (
            cell + " | " + text if cell else text
        )
    return grid