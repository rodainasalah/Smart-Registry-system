DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Saturday",
]


SLOTS = [
    {
        "id": 1,
        "start": "09:00",
        "end": "10:00",
    },
    {
        "id": 2,
        "start": "10:00",
        "end": "11:00",
    },
    {
        "id": 3,
        "start": "11:00",
        "end": "12:00",
    },
    {
        "id": 4,
        "start": "12:00",
        "end": "13:00",
    },
    {
        "id": 5,
        "start": "13:00",
        "end": "14:00",
    },
    {
        "id": 6,
        "start": "14:00",
        "end": "15:00",
    },
    {
        "id": 7,
        "start": "15:00",
        "end": "16:00",
    },
    {
        "id": 8,
        "start": "16:00",
        "end": "17:00",
    },
    {
        "id": 9,
        "start": "17:00",
        "end": "18:00",
    },
]


PROFESSORS = [
    {
        "id": 1,
        "name": "Dr. Hesham Mansour",
        "unavailable": [
            ("Monday", 1),
            ("Monday", 2),
        ],
    },
    {
        "id": 2,
        "name": "Dr. Mohamed Tharwat",
        "unavailable": [
            ("Tuesday", 1),
        ],
    },
    {
        "id": 3,
        "name": "Dr. Walaa Hassan",
        "unavailable": [],
    },
]


ROOMS = [
    {
        "id": 1,
        "name": "Hall G1",
        "capacity": 45,
        "is_lab": False,
    },
    {
        "id": 2,
        "name": "Hall G2",
        "capacity": 45,
        "is_lab": False,
    },
    {
        "id": 3,
        "name": "Lab A",
        "capacity": 45,
        "is_lab": True,
    },
    {
        "id": 4,
        "name": "Lab B",
        "capacity": 45,
        "is_lab": True,
    },
]


COURSES = [
    {
        "id": 1,
        "code": "AI301",
        "name": "Unsupervised Machine Learning",
        "professor_id": 1,
        "student_group": "AI-Y3",
        "students": 40,
    },
    {
        "id": 2,
        "code": "AI302",
        "name": "Statistical ML and Inference",
        "professor_id": 1,
        "student_group": "AI-Y3",
        "students": 40,
    },
    {
        "id": 3,
        "code": "AI303",
        "name": "Deep Neural Networks",
        "professor_id": 2,
        "student_group": "AI-Y3",
        "students": 40,
    },
    {
        "id": 4,
        "code": "PRJ301",
        "name": "Graduation Project",
        "professor_id": 3,
        "student_group": "AI-Y3",
        "students": 40,
    },
]


SESSIONS = [
    {
        "id": 1,
        "course_id": 1,
        "type": "lecture",
        "duration": 2,
        "requires_lab": False,
    },
    {
        "id": 2,
        "course_id": 1,
        "type": "tutorial",
        "duration": 1,
        "requires_lab": True,
    },
    {
        "id": 3,
        "course_id": 2,
        "type": "lecture",
        "duration": 2,
        "requires_lab": False,
    },
    {
        "id": 4,
        "course_id": 2,
        "type": "tutorial",
        "duration": 1,
        "requires_lab": True,
    },
    {
        "id": 5,
        "course_id": 3,
        "type": "lecture",
        "duration": 2,
        "requires_lab": False,
    },
    {
        "id": 6,
        "course_id": 3,
        "type": "tutorial",
        "duration": 1,
        "requires_lab": True,
    },
    {
        "id": 7,
        "course_id": 4,
        "type": "project",
        "duration": 2,
        "requires_lab": False,
    },
]