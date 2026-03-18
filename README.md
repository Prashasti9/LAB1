# CheckMyGrade Application
**DATA 200 – Lab 1**

---

## Overview

CheckMyGrade is a console-based Python application that lets students check their grades and allows admins and professors to manage student records, courses, and professor information. All data is stored in CSV files so nothing is lost between runs.

---

## Project Structure

```
LAB1/
├── checkmygrade.py          # Main application
├── test_checkmygrade.py     # Unit tests (72 tests)
├── students.csv             # Student enrollment records
├── courses.csv              # Course information
├── professors.csv           # Professor information
├── login.csv                # User accounts (passwords encrypted)
└── README.md                # This file
```

---

## Features

- **Student Management** — Add, delete, modify, and display student records stored in a linked list
- **Course Management** — Add, delete, and modify courses
- **Professor Management** — Add, delete, and modify professor records
- **Grade Reports** — Generate reports filtered by course, professor, or student
- **Search with Timing** — Search student records and print the time taken
- **Sort with Timing** — Sort by marks (ascending/descending), email, or name with timing output
- **Statistics** — Calculate average and median marks per course
- **Password Encryption** — Passwords stored using a Caesar cipher so they are never plain text in the CSV
- **Role-based Access** — Three roles: admin, professor, student. Each role sees only what they are allowed to

---

## Classes

| Class | Description |
|---|---|
| `Student` | Manages student enrollment records using a linked list |
| `Course` | Manages course records stored in courses.csv |
| `Professor` | Manages professor records stored in professors.csv |
| `Grades` | Handles grade logic and marks-to-grade conversion |
| `LoginUser` | Handles login, logout, password change, and encryption |
| `Admin` | IS-A LoginUser — adds user management capabilities |
| `TextSecurity` | Caesar cipher encryption/decryption (professor's skeleton) |
| `LinkedList` + `Node` | Data structure used to store student records in memory |
| `Session` | Tracks the currently logged-in user and their role |
| `ReportGenerator` | Generates grade reports by course, professor, or student |

---

## Data Files (CSV)

| File | Contents |
|---|---|
| `students.csv` | Email, first name, last name, course ID, grade, marks |
| `courses.csv` | Course ID, course name, credits, description |
| `professors.csv` | Professor ID (email), name, rank, course ID |
| `login.csv` | User ID, encrypted password, role |

---

## Default Login Credentials

| User | Email | Password | Role |
|---|---|---|---|
| Admin | admin@mycsu.edu | Admin123! | admin |
| Prof. Saini | saini@sjsu.edu | Prof123! | professor |
| Prof. Masum | masum@sjsu.edu | Prof123! | professor |
| Sam Carpenter | sam@mycsu.edu | Student123! | student |

---

## How to Run

```bash
# Run the application
python checkmygrade.py

# Run all unit tests
python -m unittest test_checkmygrade -v
```

**Requirements:** Python 3.x — no external libraries needed (uses only `csv`, `os`, `time`)

---

## Unit Tests

72 unit tests covering:

- Student add / delete / modify / search / sort
- 1000-record bulk load with timed search
- Sort ascending/descending by marks and email with timing
- Course add / delete / modify
- Professor add / delete / modify
- Login, logout, password change, encryption/decryption
- Role-based access control
- Auto-sync of login accounts when students/professors are added or deleted

```bash
python -m unittest test_checkmygrade -v
# Ran 72 tests in ~0.15s — OK
```

---

## OOD Class Diagram

The class diagram showing IS-A and HAS-A relationships is included in the repository as `checkmygrade_class_diagram.svg`.

**IS-A relationship:** `Admin` inherits from `LoginUser`

**HAS-A relationships:**
- `Student` HAS-A `LinkedList` (stores records)
- `Student` HAS-A `Grades` (grade logic)
- `Student` HAS-A `Course` (via Course_id)
- `Professor` HAS-A `Course` (via Course_id)

---

## Author

Prashasti — DATA 200, San Jose State University
GitHub: https://github.com/Prashasti9
