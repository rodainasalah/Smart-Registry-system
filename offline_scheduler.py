from ortools.sat.python import cp_model

from data import (
    COURSES,
    DAYS,
    PROFESSORS,
    ROOMS,
    SESSIONS,
    SLOTS,
)


def validate_data():
    errors = []

    course_ids = {course["id"] for course in COURSES}
    professor_ids = {professor["id"] for professor in PROFESSORS}

    for course in COURSES:
        if course["professor_id"] not in professor_ids:
            errors.append(
                f"Course {course['code']} refers to an unknown professor."
            )

        suitable_rooms = [
            room
            for room in ROOMS
            if room["capacity"] >= course["students"]
        ]

        if not suitable_rooms:
            errors.append(
                f"No room is large enough for {course['code']}."
            )

    for session in SESSIONS:
        if session["course_id"] not in course_ids:
            errors.append(
                f"Session {session['id']} refers to an unknown course."
            )

    return errors


def generate_timetable():
    model = cp_model.CpModel()

    courses_by_id = {
        course["id"]: course
        for course in COURSES
    }

    professors_by_id = {
        professor["id"]: professor
        for professor in PROFESSORS
    }

    slot_ids = [slot["id"] for slot in SLOTS]
    maximum_slot = max(slot_ids)

    assignment = {}

    # Create only valid possible assignments.
    for session in SESSIONS:
        course = courses_by_id[session["course_id"]]

        for room in ROOMS:
            if room["capacity"] < course["students"]:
                continue

            if session["requires_lab"] and not room["is_lab"]:
                continue

            for day in DAYS:
                for start_slot in slot_ids:
                    end_slot = start_slot + session["duration"] - 1

                    if end_slot > maximum_slot:
                        continue

                    professor = professors_by_id[
                        course["professor_id"]
                    ]

                    occupied_slots = range(
                        start_slot,
                        end_slot + 1,
                    )

                    professor_unavailable = any(
                        (day, occupied_slot)
                        in professor["unavailable"]
                        for occupied_slot in occupied_slots
                    )

                    if professor_unavailable:
                        continue

                    key = (
                        session["id"],
                        room["id"],
                        day,
                        start_slot,
                    )

                    assignment[key] = model.new_bool_var(
                        f"session_{session['id']}_"
                        f"room_{room['id']}_"
                        f"{day}_slot_{start_slot}"
                    )

    # HC01: Every session must be scheduled exactly once.
    for session in SESSIONS:
        session_variables = [
            variable
            for key, variable in assignment.items()
            if key[0] == session["id"]
        ]

        if not session_variables:
            print(
                f"No valid assignment exists for "
                f"session {session['id']}."
            )
            return None

        model.add_exactly_one(session_variables)

    # HC02: A room cannot host overlapping sessions.
    for room in ROOMS:
        for day in DAYS:
            for occupied_slot in slot_ids:
                overlapping = []

                for key, variable in assignment.items():
                    session_id, room_id, key_day, start_slot = key

                    if room_id != room["id"] or key_day != day:
                        continue

                    session = next(
                        item
                        for item in SESSIONS
                        if item["id"] == session_id
                    )

                    end_slot = (
                        start_slot
                        + session["duration"]
                        - 1
                    )

                    if start_slot <= occupied_slot <= end_slot:
                        overlapping.append(variable)

                if overlapping:
                    model.add(sum(overlapping) <= 1)

    # HC03: A professor cannot teach overlapping sessions.
    for professor in PROFESSORS:
        for day in DAYS:
            for occupied_slot in slot_ids:
                overlapping = []

                for key, variable in assignment.items():
                    session_id, _, key_day, start_slot = key

                    if key_day != day:
                        continue

                    session = next(
                        item
                        for item in SESSIONS
                        if item["id"] == session_id
                    )

                    course = courses_by_id[
                        session["course_id"]
                    ]

                    if (
                        course["professor_id"]
                        != professor["id"]
                    ):
                        continue

                    end_slot = (
                        start_slot
                        + session["duration"]
                        - 1
                    )

                    if start_slot <= occupied_slot <= end_slot:
                        overlapping.append(variable)

                if overlapping:
                    model.add(sum(overlapping) <= 1)

    # HC04: A student group cannot attend overlapping sessions.
    student_groups = {
        course["student_group"]
        for course in COURSES
    }

    for group in student_groups:
        for day in DAYS:
            for occupied_slot in slot_ids:
                overlapping = []

                for key, variable in assignment.items():
                    session_id, _, key_day, start_slot = key

                    if key_day != day:
                        continue

                    session = next(
                        item
                        for item in SESSIONS
                        if item["id"] == session_id
                    )

                    course = courses_by_id[
                        session["course_id"]
                    ]

                    if course["student_group"] != group:
                        continue

                    end_slot = (
                        start_slot
                        + session["duration"]
                        - 1
                    )

                    if start_slot <= occupied_slot <= end_slot:
                        overlapping.append(variable)

                if overlapping:
                    model.add(sum(overlapping) <= 1)

    # Small first objective:
    # Prefer earlier slots, while still satisfying all hard constraints.
       # Soft constraint: prefer earlier times and avoid wasting labs
    objective_terms = []

    for key, variable in assignment.items():
        session_id, room_id, _, start_slot = key

        session = next(
            item
            for item in SESSIONS
            if item["id"] == session_id
        )

        room = next(
            item
            for item in ROOMS
            if item["id"] == room_id
        )

        # Small penalty for later starting times
        objective_terms.append(start_slot * variable)

        # Prefer normal rooms for sessions that do not require a lab
        if not session["requires_lab"] and room["is_lab"]:
            objective_terms.append(20 * variable)

    model.minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 8

    status = solver.solve(model)

    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ):
        print(f"Solver status: {solver.status_name(status)}")
        return None

    schedule = []

    for key, variable in assignment.items():
        if solver.value(variable) != 1:
            continue

        session_id, room_id, day, start_slot = key

        session = next(
            item
            for item in SESSIONS
            if item["id"] == session_id
        )

        course = courses_by_id[session["course_id"]]

        professor = professors_by_id[
            course["professor_id"]
        ]

        room = next(
            item
            for item in ROOMS
            if item["id"] == room_id
        )

        start_time = next(
            slot["start"]
            for slot in SLOTS
            if slot["id"] == start_slot
        )

        final_slot = (
            start_slot
            + session["duration"]
            - 1
        )

        end_time = next(
            slot["end"]
            for slot in SLOTS
            if slot["id"] == final_slot
        )

        schedule.append(
            {
                "day": day,
                "start_slot": start_slot,
                "start": start_time,
                "end": end_time,
                "course_code": course["code"],
                "course_name": course["name"],
                "session_type": session["type"],
                "professor": professor["name"],
                "student_group": course["student_group"],
                "room": room["name"],
            }
        )

    day_order = {
        day: position
        for position, day in enumerate(DAYS)
    }

    schedule.sort(
        key=lambda item: (
            day_order[item["day"]],
            item["start_slot"],
            item["room"],
        )
    )

    return {
        "status": solver.status_name(status),
        "solve_time": solver.wall_time,
        "schedule": schedule,
    }


def main():
    errors = validate_data()

    if errors:
        print("\nDATA ERRORS")

        for error in errors:
            print(f"- {error}")

        return

    result = generate_timetable()

    if result is None:
        print("\nNo valid timetable could be generated.")
        return

    print(f"\nSolver status: {result['status']}")
    print(
        f"Solve time: "
        f"{result['solve_time']:.3f} seconds"
    )

    print("\nGENERATED TIMETABLE")
    print("-" * 120)

    for item in result["schedule"]:
        print(
            f"{item['day']:<10} "
            f"{item['start']}-{item['end']} | "
            f"{item['course_code']:<7} | "
            f"{item['course_name']:<38} | "
            f"{item['session_type']:<9} | "
            f"{item['professor']:<24} | "
            f"{item['student_group']:<8} | "
            f"{item['room']}"
        )

    print("-" * 120)


if __name__ == "__main__":
    main()