"""
CheckMyGrade Application

This application lets students check their grades, and lets admins/professors
manage student records, courses, and professor information. All data is stored
in CSV files so nothing gets lost between runs.
"""

import csv
import os
import time

# These are the four CSV files the application reads from and writes to.
# Keeping them as constants at the top makes it easy to change the filenames
# if needed, and the test file overrides these to use temp files instead.
STUDENTS_FILE   = "students.csv"
COURSES_FILE    = "courses.csv"
PROFESSORS_FILE = "professors.csv"
LOGIN_FILE      = "login.csv"

# The three valid roles a user can have in the system.
ROLES = ("admin", "professor", "student")


# ── CSV helpers ───────────────────────────────────────────────────────────────

def read_csv(filepath):
    """
    Read a CSV file and return its contents as a list of dictionaries.
    Each row becomes a dict where the keys are the column headers.
    Returns an empty list if the file doesn't exist yet, which is fine
    on a fresh install before any data has been added.
    """
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, newline="") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return []


def write_csv(filepath, rows, fieldnames):
    """
    Write a list of dictionaries back to a CSV file.
    The fieldnames list controls the column order in the output file.
    We always rewrite the whole file since our datasets are small enough
    that partial updates would just add complexity for no real benefit.
    """
    try:
        with open(filepath, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    except Exception as e:
        print(f"  Error writing {filepath}: {e}")


# ── Password encryption (Caesar cipher) ──────────────────────────────────────
# Based on the TextSecurity skeleton provided by Professor Saini.
# We use a Caesar cipher so that passwords stored in login.csv look like
# scrambled text instead of the actual password.

class TextSecurity:
    """
    Encrypts and decrypts text using a Caesar cipher shift.
    The shift value determines how many positions each letter is moved.
    Non-letter characters like digits and symbols are left unchanged so
    that passwords like "Welcome12#_" can round-trip correctly.
    """

    def __init__(self, shift=13):
        self.shifter = shift
        # We mod by 26 so a shift of 27 behaves the same as a shift of 1, etc.
        self.s = self.shifter % 26

    def _convert(self, text, s):
        """
        Core logic that shifts every letter in the text by s positions.
        Upper and lower case are handled separately so the case is preserved.
        """
        result = ""
        for ch in text:
            if ch.isalpha():
                if ch.isupper():
                    result += chr((ord(ch) + s - 65) % 26 + 65)
                else:
                    result += chr((ord(ch) + s - 97) % 26 + 97)
            else:
                # Leave digits, spaces, and symbols exactly as they are
                result += ch
        return result

    def encrypt(self, text):
        """Shift each letter forward by the configured amount."""
        return self._convert(text, self.shifter)

    def decrypt(self, text):
        """Shift each letter backward to reverse the encryption."""
        return self._convert(text, 26 - self.s)


# We use a shift of 13 (ROT13) which is convenient because encrypting twice
# gives you back the original — encrypt and decrypt are the same operation.
_cipher = TextSecurity(shift=13)


def encrypt_password(plain):
    """Encrypt a plain-text password before saving it to login.csv."""
    try:
        return _cipher.encrypt(plain)
    except Exception as e:
        print(f"  Encrypt error: {e}")
        return ""


def decrypt_password(enc):
    """Decrypt a password that was read from login.csv back to plain text."""
    try:
        return _cipher.decrypt(enc)
    except Exception as e:
        print(f"  Decrypt error: {e}")
        return ""


# ── Session ───────────────────────────────────────────────────────────────────

class Session:
    """
    Keeps track of who is currently logged in and what role they have.
    Most operations check the session before doing anything so that
    students can't accidentally (or intentionally) modify other records.
    """

    def __init__(self):
        self.user_id = None
        self.role    = None

    def is_logged_in(self): return self.role is not None
    def is_admin(self):     return self.role == "admin"
    # Admins can do everything professors can, so this returns True for both
    def is_professor(self): return self.role in ("admin", "professor")
    def is_student(self):   return self.role == "student"

    def login(self, user_id, role):
        """Set the current logged-in user after a successful login."""
        self.user_id = user_id
        self.role    = role

    def logout(self):
        """Clear the session so the next user starts fresh."""
        print(f"  {self.user_id} logged out.")
        self.user_id = None
        self.role    = None

    def require(self, *allowed):
        """
        Check whether the current user's role is in the allowed list.
        Returns True if access is granted, False and prints a message otherwise.
        Used at the top of most methods that shouldn't be open to everyone.
        """
        if self.role in allowed:
            return True
        print(f"  Access denied. Required: {', '.join(allowed)}. "
              f"Your role: {self.role or 'not logged in'}.")
        return False


# One global session object that the whole application shares
session = Session()


# ── Linked List ───────────────────────────────────────────────────────────────
# Student records are stored in a linked list as required by the assignment.
# Each node holds one student-enrollment dictionary (one row from students.csv).

class Node:
    """A single node in the linked list, holding one student record."""
    def __init__(self, data):
        self.data = data   # the student record dict
        self.next = None   # pointer to the next node


class LinkedList:
    """
    A singly-linked list that holds all student enrollment records in memory.
    We load the whole CSV into this list at startup and flush it back to disk
    whenever a record is added, deleted, or modified.
    """

    def __init__(self):
        self.head = None

    def append(self, data):
        """Add a new record to the end of the list."""
        node = Node(data)
        if not self.head:
            self.head = node
            return
        # Walk to the last node and attach the new one
        cur = self.head
        while cur.next:
            cur = cur.next
        cur.next = node

    def to_list(self):
        """Convert the linked list to a plain Python list for easier processing."""
        result, cur = [], self.head
        while cur:
            result.append(cur.data)
            cur = cur.next
        return result

    def find(self, email, course_id=None):
        """
        Search for a student record by email. If a course_id is also given,
        the match must be for that specific enrollment. Returns the first
        matching record dict, or None if nothing was found.
        """
        cur = self.head
        while cur:
            em = cur.data.get("Email_address", "").lower() == email.lower()
            if course_id:
                if em and cur.data.get("Course_id","").upper() == course_id.upper():
                    return cur.data
            elif em:
                return cur.data
            cur = cur.next
        return None

    def find_all(self, email):
        """
        Return all enrollment records for a given student email.
        A student can be enrolled in multiple courses, so this may return
        more than one record.
        """
        result, cur = [], self.head
        while cur:
            if cur.data.get("Email_address","").lower() == email.lower():
                result.append(cur.data)
            cur = cur.next
        return result

    def delete(self, email, course_id=None):
        """
        Remove a record from the list. If course_id is specified, only that
        particular enrollment is removed. Returns True if something was deleted,
        False if the record wasn't found.
        """
        def match(d):
            em = d.get("Email_address","").lower() == email.lower()
            return em and (not course_id or
                           d.get("Course_id","").upper() == course_id.upper())

        if not self.head:
            return False
        # Special case: the record to remove is the very first node
        if match(self.head.data):
            self.head = self.head.next
            return True
        # General case: walk the list until we find the node before the one to remove
        cur = self.head
        while cur.next:
            if match(cur.next.data):
                cur.next = cur.next.next
                return True
            cur = cur.next
        return False


# ── Grades ────────────────────────────────────────────────────────────────────

class Grades:
    """
    Handles grade-related logic. Grades are stored directly in students.csv
    as a Grade letter and a Marks value, so this class is mainly a utility
    for converting marks to grade letters and for managing grade records.
    """

    # Maps each letter grade to the marks range it covers
    GRADE_MAP = {"A": (90, 100), "B": (80, 89), "C": (70, 79),
                 "D": (60, 69),  "F": (0,  59)}

    def __init__(self, grade_id, grade, marks_range):
        self.grade_id    = grade_id
        self.grade       = grade
        self.marks_range = marks_range

    @staticmethod
    def marks_to_grade(marks):
        """
        Convert a numeric marks value to the corresponding letter grade.
        Returns 'F' for anything below 60 or if the input isn't a valid number.
        """
        try:
            m = float(marks)
            for g, (lo, hi) in Grades.GRADE_MAP.items():
                if lo <= m <= hi:
                    return g
            return "F"
        except ValueError:
            print(f"  Invalid marks '{marks}'.")
            return "F"

    def display_grade_report(self):
        """Print this grade record's details."""
        print(f"  {self.grade_id}  Grade: {self.grade}  Range: {self.marks_range}")

    @staticmethod
    def add_grade(grade_id, grade, marks_range):
        """Create and return a new Grades object."""
        return Grades(grade_id, grade, marks_range)

    @staticmethod
    def delete_grade(grade_list, grade_id):
        """Return a new list with the specified grade_id removed."""
        return [g for g in grade_list if g.grade_id != grade_id]

    @staticmethod
    def modify_grade(grade_list, grade_id, new_grade, new_range):
        """Update the grade and marks range for the given grade_id in place."""
        for g in grade_list:
            if g.grade_id == grade_id:
                g.grade = new_grade
                g.marks_range = new_range
        return grade_list


# ── Student ───────────────────────────────────────────────────────────────────

class Student:
    """
    Manages all student enrollment records. Records are kept in a linked list
    in memory and flushed to students.csv whenever something changes.

    A student can be enrolled in multiple courses, so the same email address
    can appear more than once — once per course they're taking.
    """

    # Column order for students.csv
    FIELDS = ["Email_address", "First_name", "Last_name",
              "Course_id", "Grade", "Marks"]

    def __init__(self):
        self._ll = LinkedList()
        self._load()

    def _load(self):
        """Read all rows from students.csv into the linked list."""
        self._ll.head = None
        for row in read_csv(STUDENTS_FILE):
            self._ll.append(row)

    def _save(self):
        """Write the current state of the linked list back to students.csv."""
        write_csv(STUDENTS_FILE, self._ll.to_list(), self.FIELDS)

    def _sync_login_add(self, email):
        """
        When a new student is added, make sure they also have a login account.
        If one already exists we leave it alone; we only create it if it's missing.
        """
        rows = read_csv(LOGIN_FILE)
        if not any(r["User_id"].lower() == email.lower() for r in rows):
            rows.append({"User_id": email,
                         "Password": encrypt_password("Student123!"),
                         "Role": "student"})
            write_csv(LOGIN_FILE, rows, ["User_id","Password","Role"])
            print(f"  Login created for {email} (password: Student123!)")

    def _sync_login_remove(self, email):
        """
        When a student enrollment is deleted, check if they still have any
        other enrollments. If they don't, remove their login account too.
        """
        if not self._ll.find(email):
            rows = read_csv(LOGIN_FILE)
            updated = [r for r in rows if r["User_id"].lower() != email.lower()]
            if len(updated) < len(rows):
                write_csv(LOGIN_FILE, updated, ["User_id","Password","Role"])
                print(f"  Login removed for {email}.")

    def _sync_course_add(self, course_id):
        """
        If a student is enrolled in a course that doesn't exist in courses.csv yet,
        create a placeholder entry so the foreign key reference isn't broken.
        The admin can fill in the proper details later via Course Management.
        """
        rows = read_csv(COURSES_FILE)
        if not any(r["Course_id"].upper() == course_id.upper() for r in rows):
            rows.append({"Course_id": course_id, "Course_name": course_id,
                         "Credits": "3",
                         "Description": "Auto-created. Update via Course Management."})
            write_csv(COURSES_FILE, rows,
                      ["Course_id","Course_name","Credits","Description"])
            print(f"  Course {course_id} auto-created in courses.csv.")

    def display_records(self):
        """
        Show all student records. Professors only see students enrolled in
        their own courses; admins see everyone.
        """
        try:
            if not session.require("admin", "professor"):
                return
            rows = self._ll.to_list()
            # Filter down to only the logged-in professor's courses
            if session.is_professor() and not session.is_admin():
                my_courses = [r["Course_id"] for r in read_csv(PROFESSORS_FILE)
                              if r["Professor_id"].lower() == session.user_id.lower()]
                rows = [r for r in rows if r.get("Course_id","") in my_courses]
            if not rows:
                print("  No records found.")
                return
            print(f"  {'Email':<28} {'Name':<20} {'Course':<10} {'Grade':<6} Marks")
            print("  " + "-" * 70)
            for r in rows:
                name = r.get("First_name","") + " " + r.get("Last_name","")
                print(f"  {r.get('Email_address',''):<28} {name:<20} "
                      f"{r.get('Course_id',''):<10} {r.get('Grade',''):<6} "
                      f"{r.get('Marks','')}")
        except Exception as e:
            print(f"  Error: {e}")

    def add_new_student(self, email, first, last, course_id, grade, marks):
        """
        Enroll a new student in a course. The email+course combination must be
        unique — the same student can take multiple courses, but can't be enrolled
        in the same course twice. All fields are required and marks must be numeric.
        """
        try:
            if not session.require("admin"):
                return False
            if not email or not first or not last or not course_id:
                print("  Error: All fields required.")
                return False
            # Prevent duplicate enrollments for the same student + course pair
            if self._ll.find(email, course_id):
                print(f"  {email} already enrolled in {course_id}.")
                return False
            float(marks)  # will raise ValueError if marks isn't a valid number
            self._ll.append({"Email_address": email, "First_name": first,
                              "Last_name": last, "Course_id": course_id,
                              "Grade": grade, "Marks": marks})
            self._save()
            print(f"  Student {email} enrolled in {course_id}.")
            # Keep courses.csv and login.csv in sync with the new enrollment
            self._sync_course_add(course_id)
            self._sync_login_add(email)
            return True
        except ValueError:
            print("  Error: Marks must be numeric.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def delete_new_student(self, email, course_id=None):
        """
        Remove a student's enrollment. If a course_id is given, only that one
        enrollment is removed. If no course_id is given, all of that student's
        enrollments are deleted. The login account is removed only if the student
        has no remaining enrollments after the deletion.
        """
        try:
            if not session.require("admin"):
                return False
            if not email:
                print("  Error: Email required.")
                return False
            if course_id:
                # Delete just one specific enrollment
                if self._ll.delete(email, course_id):
                    self._save()
                    print(f"  Removed {email} from {course_id}.")
                    self._sync_login_remove(email)
                    return True
                print(f"  Enrollment not found.")
                return False
            else:
                # Delete every enrollment for this student
                rows = self._ll.to_list()
                kept = [r for r in rows
                        if r.get("Email_address","").lower() != email.lower()]
                if len(kept) < len(rows):
                    self._ll.head = None
                    for r in kept:
                        self._ll.append(r)
                    self._save()
                    print(f"  All enrollments for {email} deleted.")
                    self._sync_login_remove(email)
                    return True
                print(f"  Student {email} not found.")
                return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def update_student_record(self, email, field, value):
        """
        Update a single field on a student record. If the Marks field is updated,
        the Grade is automatically recalculated so they always stay in sync.
        """
        try:
            if not session.require("admin"):
                return False
            rec = self._ll.find(email)
            if not rec:
                print(f"  Student {email} not found.")
                return False
            if field == "Marks":
                float(value)  # validate before changing anything
                rec["Grade"] = Grades.marks_to_grade(value)
            rec[field] = value
            self._save()
            print(f"  Updated {field} for {email}.")
            return True
        except ValueError:
            print("  Error: Marks must be numeric.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def check_my_grades(self, email):
        """
        Show the grade letter for each course a student is enrolled in.
        Students can only view their own grades; admins and professors can
        look up any student.
        """
        try:
            if session.is_student() and session.user_id.lower() != email.lower():
                print("  Access denied.")
                return
            if not session.require("admin", "professor", "student"):
                return
            recs = self._ll.find_all(email)
            if recs:
                print(f"  Grades for {email}:")
                for r in recs:
                    print(f"    {r.get('Course_id',''):<12} "
                          f"Grade: {r.get('Grade','')}  Marks: {r.get('Marks','')}")
            else:
                print("  Student not found.")
        except Exception as e:
            print(f"  Error: {e}")

    def check_my_marks(self, email):
        """
        Show the numeric marks for each course a student is enrolled in.
        Same access rules as check_my_grades — students can only see their own.
        """
        try:
            if session.is_student() and session.user_id.lower() != email.lower():
                print("  Access denied.")
                return
            if not session.require("admin", "professor", "student"):
                return
            recs = self._ll.find_all(email)
            if recs:
                print(f"  Marks for {email}:")
                for r in recs:
                    print(f"    {r.get('Course_id',''):<12} Marks: {r.get('Marks','')}")
            else:
                print("  Student not found.")
        except Exception as e:
            print(f"  Error: {e}")

    def search_student(self, email):
        """
        Search for a student by email and print how long the search took.
        Timing is printed as required by the assignment so we can see the
        performance of the linked list search.
        """
        try:
            if not session.require("admin", "professor"):
                return None
            start = time.perf_counter()
            rec   = self._ll.find(email)
            elapsed = (time.perf_counter() - start) * 1000
            print(f"  Search time: {elapsed:.4f} ms")
            if rec:
                print(f"  Found: {rec}")
            else:
                print("  Not found.")
            return rec
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def sort_records(self, key="marks", descending=False):
        """
        Sort all student records by the given key (marks, email, or name)
        and return the sorted list. The caller is responsible for printing
        the timing — see the student_menu function for how that's done.
        """
        try:
            if not session.require("admin", "professor"):
                return []
            rows = self._ll.to_list()
            if key == "marks":
                rows.sort(key=lambda r: float(r.get("Marks", 0)),
                          reverse=descending)
            elif key == "email":
                rows.sort(key=lambda r: r.get("Email_address","").lower(),
                          reverse=descending)
            elif key == "name":
                # Sort by first name, then last name as a tiebreaker
                rows.sort(key=lambda r: (r.get("First_name","").lower(),
                                         r.get("Last_name","").lower()),
                          reverse=descending)
            return rows
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def course_stats(self, course_id):
        """
        Calculate and print the average and median marks for a given course.
        Only considers students who are actually enrolled in that course.
        """
        try:
            if not session.require("admin", "professor"):
                return
            rows = [r for r in self._ll.to_list()
                    if r.get("Course_id","").upper() == course_id.upper()]
            if not rows:
                print(f"  No records for {course_id}.")
                return
            marks  = sorted([float(r["Marks"]) for r in rows])
            avg    = sum(marks) / len(marks)
            n      = len(marks)
            # Standard median: middle value if odd count, average of two middle values if even
            median = (marks[n//2] if n % 2
                      else (marks[n//2-1] + marks[n//2]) / 2)
            print(f"  {course_id} | Students: {n} | "
                  f"Avg: {avg:.2f} | Median: {median:.2f}")
        except Exception as e:
            print(f"  Error: {e}")

    def get_all(self):
        """Return all student records as a plain list. Used by ReportGenerator."""
        return self._ll.to_list()


# ── Course ────────────────────────────────────────────────────────────────────

class Course:
    """
    Manages course records stored in courses.csv.
    Only admins can add, delete, or modify courses.
    Deleting a course also cleans up related student enrollments and
    unassigns any professor who was teaching it.
    """

    FIELDS = ["Course_id", "Course_name", "Credits", "Description"]

    def __init__(self):
        self._rows = read_csv(COURSES_FILE)

    def _save(self):
        """Write the current course list back to courses.csv."""
        write_csv(COURSES_FILE, self._rows, self.FIELDS)

    def display_courses(self):
        """
        List all courses. Professors only see their assigned courses;
        everyone else sees the full list.
        """
        try:
            if not session.require("admin", "professor", "student"):
                return
            rows = self._rows
            if session.is_professor() and not session.is_admin():
                my_courses = [r["Course_id"] for r in read_csv(PROFESSORS_FILE)
                              if r["Professor_id"].lower() == session.user_id.lower()]
                rows = [r for r in rows if r.get("Course_id","") in my_courses]
            if not rows:
                print("  No courses found.")
                return
            print(f"  {'ID':<12} {'Name':<25} {'Credits':<8} Description")
            print("  " + "-" * 65)
            for r in rows:
                print(f"  {r.get('Course_id',''):<12} {r.get('Course_name',''):<25} "
                      f"{r.get('Credits',''):<8} {r.get('Description','')}")
        except Exception as e:
            print(f"  Error: {e}")

    def add_new_course(self, course_id, name, credits, description):
        """
        Add a new course. The course_id must be unique and not empty.
        Course IDs are compared case-insensitively to avoid duplicates like
        'data200' and 'DATA200' coexisting.
        """
        try:
            if not session.require("admin"):
                return False
            if not course_id or not name:
                print("  Error: ID and name required.")
                return False
            if any(r["Course_id"].upper() == course_id.upper()
                   for r in self._rows):
                print(f"  Course {course_id} already exists.")
                return False
            self._rows.append({"Course_id": course_id, "Course_name": name,
                                "Credits": credits, "Description": description})
            self._save()
            print(f"  Course {course_id} added.")
            return True
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def delete_new_course(self, course_id):
        """
        Delete a course and cascade the changes to related records:
        - Students enrolled in this course are removed from students.csv
        - Students with no remaining enrollments lose their login account
        - Professors assigned to this course have their Course_id cleared
        """
        try:
            if not session.require("admin"):
                return False
            before = len(self._rows)
            self._rows = [r for r in self._rows
                          if r["Course_id"].upper() != course_id.upper()]
            if len(self._rows) < before:
                self._save()
                print(f"  Course {course_id} deleted.")

                # Remove all student enrollments for this course
                s_rows = read_csv(STUDENTS_FILE)
                affected = {r["Email_address"] for r in s_rows
                            if r.get("Course_id","").upper() == course_id.upper()}
                kept_s = [r for r in s_rows
                          if r.get("Course_id","").upper() != course_id.upper()]
                write_csv(STUDENTS_FILE, kept_s, Student.FIELDS)

                # Remove login accounts for students who are now fully unenrolled
                remaining = {r["Email_address"].lower() for r in kept_s}
                l_rows = read_csv(LOGIN_FILE)
                l_rows = [r for r in l_rows
                          if not (r.get("Role") == "student" and
                                  r["User_id"].lower() in
                                  {e.lower() for e in affected} and
                                  r["User_id"].lower() not in remaining)]
                write_csv(LOGIN_FILE, l_rows, ["User_id","Password","Role"])

                # Clear the Course_id for any professor who was assigned to this course
                p_rows = read_csv(PROFESSORS_FILE)
                for p in p_rows:
                    if p.get("Course_id","").upper() == course_id.upper():
                        p["Course_id"] = ""
                write_csv(PROFESSORS_FILE, p_rows, Professor.FIELDS)
                print(f"  All related records synced.")
                return True
            print(f"  Course {course_id} not found.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def modify_course(self, course_id, field, value):
        """Update a single field on an existing course record."""
        try:
            if not session.require("admin"):
                return False
            for r in self._rows:
                if r["Course_id"].upper() == course_id.upper():
                    r[field] = value
                    self._save()
                    print(f"  Updated {field} for {course_id}.")
                    return True
            print(f"  Course {course_id} not found.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False


# ── Professor ─────────────────────────────────────────────────────────────────

class Professor:
    """
    Manages professor records stored in professors.csv.
    Each professor is identified by their email address (Professor_id),
    has a name, a rank (e.g. Senior Professor), and is assigned one course.
    """

    FIELDS = ["Professor_id", "Professor_name", "Rank", "Course_id"]

    def __init__(self):
        self._rows = read_csv(PROFESSORS_FILE)

    def _save(self):
        """Write the current professor list back to professors.csv."""
        write_csv(PROFESSORS_FILE, self._rows, self.FIELDS)

    def professors_details(self):
        """
        Display professor records. A professor can only see their own record;
        admins can see everyone.
        """
        try:
            if not session.require("admin", "professor"):
                return
            rows = self._rows
            if session.is_professor() and not session.is_admin():
                rows = [r for r in rows
                        if r.get("Professor_id","").lower() == session.user_id.lower()]
            if not rows:
                print("  No professors found.")
                return
            for r in rows:
                print(f"  {r.get('Professor_id',''):<28} "
                      f"{r.get('Professor_name',''):<22} "
                      f"{r.get('Rank',''):<18} {r.get('Course_id','')}")
        except Exception as e:
            print(f"  Error: {e}")

    def add_new_professor(self, prof_id, name, rank, course_id):
        """
        Add a new professor. The professor's email (prof_id) must be unique.
        A login account is automatically created for them so they can log in
        right away using the default password Prof123!
        """
        try:
            if not session.require("admin"):
                return False
            if not prof_id or not name:
                print("  Error: ID and name required.")
                return False
            if any(r["Professor_id"].lower() == prof_id.lower()
                   for r in self._rows):
                print(f"  Professor {prof_id} already exists.")
                return False
            self._rows.append({"Professor_id": prof_id, "Professor_name": name,
                                "Rank": rank, "Course_id": course_id})
            self._save()
            print(f"  Professor {prof_id} added.")
            # Create a login account for the new professor if one doesn't exist yet
            l_rows = read_csv(LOGIN_FILE)
            if not any(r["User_id"].lower() == prof_id.lower() for r in l_rows):
                l_rows.append({"User_id": prof_id,
                                "Password": encrypt_password("Prof123!"),
                                "Role": "professor"})
                write_csv(LOGIN_FILE, l_rows, ["User_id","Password","Role"])
                print(f"  Login created for {prof_id} (password: Prof123!)")
            return True
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def delete_professore(self, prof_id):
        """
        Delete a professor record and remove their login account.
        Note: the method name 'delete_professore' matches the assignment spec exactly.
        """
        try:
            if not session.require("admin"):
                return False
            before = len(self._rows)
            self._rows = [r for r in self._rows
                          if r["Professor_id"].lower() != prof_id.lower()]
            if len(self._rows) < before:
                self._save()
                print(f"  Professor {prof_id} deleted.")
                # Also remove their login so they can't still log in after being deleted
                l_rows = read_csv(LOGIN_FILE)
                l_rows = [r for r in l_rows
                          if r["User_id"].lower() != prof_id.lower()]
                write_csv(LOGIN_FILE, l_rows, ["User_id","Password","Role"])
                print(f"  Login for {prof_id} removed.")
                return True
            print(f"  Professor {prof_id} not found.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def modify_professor_details(self, prof_id, field, value):
        """Update a single field on an existing professor record."""
        try:
            if not session.require("admin"):
                return False
            for r in self._rows:
                if r["Professor_id"].lower() == prof_id.lower():
                    r[field] = value
                    self._save()
                    print(f"  Updated {field} for {prof_id}.")
                    return True
            print(f"  Professor {prof_id} not found.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def show_course_details_by_professor(self, prof_id):
        """Show which course a particular professor is assigned to teach."""
        try:
            if not session.require("admin", "professor"):
                return
            for r in self._rows:
                if r["Professor_id"].lower() == prof_id.lower():
                    print(f"  {r.get('Professor_name','')} "
                          f"teaches {r.get('Course_id','')}")
                    return
            print(f"  Professor {prof_id} not found.")
        except Exception as e:
            print(f"  Error: {e}")


# ── LoginUser ─────────────────────────────────────────────────────────────────

class LoginUser:
    """
    Handles login, logout, password changes, and user registration.
    Passwords are always encrypted before being saved to login.csv, and
    decrypted when read back for comparison during login.
    """

    FIELDS = ["User_id", "Password", "Role"]

    def __init__(self):
        self._rows = read_csv(LOGIN_FILE)

    def _save(self):
        """Write the current login records back to login.csv."""
        write_csv(LOGIN_FILE, self._rows, self.FIELDS)

    def _find(self, user_id):
        """Look up a user by their ID (case-insensitive). Returns None if not found."""
        for r in self._rows:
            if r["User_id"].lower() == user_id.lower():
                return r
        return None

    def Login(self, user_id, password):
        """
        Attempt to log in with the given credentials. The password is compared
        against the decrypted value stored in login.csv. On success, the global
        session is updated with the user's ID and role.
        """
        try:
            if not user_id or not password:
                print("  Error: Fields required.")
                return None
            rec = self._find(user_id)
            if rec and decrypt_password(rec["Password"]) == password:
                session.login(user_id, rec["Role"])
                print(f"  Login successful. Welcome {user_id}! Role: {rec['Role']}")
                return rec["Role"]
            print("  Invalid credentials.")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def Logout(self):
        """Log out the current user by clearing the session."""
        try:
            if not session.is_logged_in():
                print("  No user logged in.")
                return
            session.logout()
        except Exception as e:
            print(f"  Error: {e}")

    def Change_password(self, user_id, old_pw, new_pw):
        """
        Change a user's password after verifying the old one.
        Users can only change their own password unless they're an admin.
        """
        try:
            if not session.is_admin() and session.user_id.lower() != user_id.lower():
                print("  Access denied.")
                return False
            rec = self._find(user_id)
            if rec and decrypt_password(rec["Password"]) == old_pw:
                rec["Password"] = encrypt_password(new_pw)
                self._save()
                print("  Password changed.")
                return True
            print("  Old password incorrect.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def Encrypt_password(self, plain):
        """Public wrapper for encrypt_password, as required by the class spec."""
        return encrypt_password(plain)

    def decrypt_password(self, enc):
        """Public wrapper for decrypt_password, as required by the class spec."""
        return decrypt_password(enc)

    def register(self, user_id, password, role):
        """
        Register a new user account. Only admins can create admin or professor
        accounts — students can self-register but only as the 'student' role.
        """
        try:
            if role not in ROLES:
                print(f"  Invalid role.")
                return False
            if role in ("admin","professor") and not session.is_admin():
                print("  Only admin can create admin/professor accounts.")
                return False
            if self._find(user_id):
                print(f"  User {user_id} already exists.")
                return False
            self._rows.append({"User_id": user_id,
                                "Password": encrypt_password(password),
                                "Role": role})
            self._save()
            print(f"  User {user_id} registered as {role}.")
            return True
        except Exception as e:
            print(f"  Error: {e}")
            return False


# ── Admin ─────────────────────────────────────────────────────────────────────

class Admin(LoginUser):
    """
    Admin IS-A LoginUser — it inherits all login functionality and adds
    extra management capabilities like listing all users, adding/removing
    accounts, and resetting passwords for any user.
    """

    def __init__(self):
        super().__init__()

    def list_users(self):
        """Print all user accounts and their roles."""
        try:
            if not session.require("admin"):
                return
            print(f"  {'User ID':<30} Role")
            print("  " + "-" * 45)
            for r in self._rows:
                print(f"  {r.get('User_id',''):<30} {r.get('Role','')}")
        except Exception as e:
            print(f"  Error: {e}")

    def add_user(self, user_id, password, role):
        """Add a new user account (delegates to the register method)."""
        return self.register(user_id, password, role)

    def remove_user(self, user_id):
        """
        Delete a user account. Admins cannot delete their own account
        to prevent accidentally locking everyone out of the system.
        """
        try:
            if not session.require("admin"):
                return False
            if session.user_id.lower() == user_id.lower():
                print("  Cannot delete your own account.")
                return False
            before = len(self._rows)
            self._rows = [r for r in self._rows
                          if r["User_id"].lower() != user_id.lower()]
            if len(self._rows) < before:
                self._save()
                print(f"  User {user_id} deleted.")
                return True
            print(f"  User {user_id} not found.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def reset_password(self, user_id, new_pw):
        """
        Set a new password for any user without needing to know the old one.
        This is an admin-only action for when users get locked out.
        """
        try:
            if not session.require("admin"):
                return False
            rec = self._find(user_id)
            if rec:
                rec["Password"] = encrypt_password(new_pw)
                self._save()
                print(f"  Password reset for {user_id}.")
                return True
            print(f"  User {user_id} not found.")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False


# ── ReportGenerator ───────────────────────────────────────────────────────────

class ReportGenerator:
    """
    Generates grade reports filtered by course, professor, or student.
    Average and median stats are also printed when a course report is shown.
    Students can only see their own reports; professors can only see reports
    for their assigned courses.
    """

    def __init__(self, student):
        # We keep a reference to the Student instance so we can access its data
        self.student = student

    def display_grade_report(self, by, value):
        """
        Print a formatted grade report. The 'by' parameter controls the filter:
          'course'    — show all students in a given course
          'professor' — show all students in the courses a professor teaches
          'student'   — show all courses and grades for one student
        """
        try:
            if not session.require("admin", "professor", "student"):
                return
            rows = self.student.get_all()

            if by == "course":
                # Professors can only run reports for their own courses
                if session.is_professor() and not session.is_admin():
                    my = [r["Course_id"] for r in read_csv(PROFESSORS_FILE)
                          if r["Professor_id"].lower() == session.user_id.lower()]
                    if value.upper() not in [c.upper() for c in my]:
                        print("  Access denied. Not your course.")
                        return
                rows = [r for r in rows
                        if r.get("Course_id","").upper() == value.upper()]
                title = f"Course {value}"

            elif by == "professor":
                # Look up which course the professor teaches, then filter by that
                p_rows = read_csv(PROFESSORS_FILE)
                p = next((r for r in p_rows
                          if r["Professor_id"].lower() == value.lower()), None)
                if not p:
                    print("  Professor not found.")
                    return
                rows = [r for r in rows
                        if r.get("Course_id","").upper() == p["Course_id"].upper()]
                title = f"Professor {p.get('Professor_name','')}"

            elif by == "student":
                # Students can only pull their own report
                if session.is_student() and session.user_id.lower() != value.lower():
                    print("  Access denied.")
                    return
                rows = self.student._ll.find_all(value)
                title = f"Student {value}"

            if not rows:
                print("  No records found.")
                return
            print(f"\n  === Grade Report: {title} ===")
            for r in rows:
                name = r.get("First_name","") + " " + r.get("Last_name","")
                print(f"  {r.get('Email_address',''):<28} {name:<20} "
                      f"{r.get('Course_id',''):<10} "
                      f"Grade: {r.get('Grade','')}  Marks: {r.get('Marks','')}")
            # Show stats at the bottom of course and professor reports
            if by in ("course", "professor"):
                cid = value if by == "course" else p["Course_id"]
                self.student.course_stats(cid)
        except Exception as e:
            print(f"  Error: {e}")


# ── Startup sync ──────────────────────────────────────────────────────────────

def startup_sync():
    """
    On every startup, go through professors.csv and students.csv and create
    login accounts for anyone who doesn't have one yet. This handles the case
    where records were added directly to the CSV files (e.g. during seeding)
    without going through the application, so they still get a usable login.
    """
    login_rows = read_csv(LOGIN_FILE)
    existing   = {r["User_id"].lower() for r in login_rows}
    added      = 0

    # Check all professors first
    for p in read_csv(PROFESSORS_FILE):
        uid = p.get("Professor_id","")
        if uid and uid.lower() not in existing:
            login_rows.append({"User_id": uid,
                                "Password": encrypt_password("Prof123!"),
                                "Role": "professor"})
            existing.add(uid.lower())
            added += 1

    # Then check all students
    for s in read_csv(STUDENTS_FILE):
        uid = s.get("Email_address","")
        if uid and uid.lower() not in existing:
            login_rows.append({"User_id": uid,
                                "Password": encrypt_password("Student123!"),
                                "Role": "student"})
            existing.add(uid.lower())
            added += 1

    if added > 0:
        write_csv(LOGIN_FILE, login_rows, ["User_id","Password","Role"])
        print(f"  Startup sync: {added} missing login account(s) auto-created.")


# ── Console menus ─────────────────────────────────────────────────────────────

def main_menu():
    """
    The main entry point for the console UI. Loads all data objects once,
    then loops showing the appropriate menu based on whether someone is
    logged in and what role they have.
    """
    startup_sync()
    student   = Student()
    course    = Course()
    professor = Professor()
    lu        = LoginUser()
    admin     = Admin()
    report    = ReportGenerator(student)

    while True:
        print("\n" + "=" * 45)
        print("   CheckMyGrade  |  DATA 200  |  SJSU")
        if session.is_logged_in():
            print(f"   {session.user_id}  [{session.role}]")
        else:
            print("   Not logged in")
        print("=" * 45)

        if not session.is_logged_in():
            print("  1. Login\n  2. Register as student\n  0. Exit")
            c = input("\n  Select: ").strip()
            if c == "1":
                uid = input("  User ID: ").strip()
                pw  = input("  Password: ").strip()
                lu.Login(uid, pw)
            elif c == "2":
                uid = input("  Email: ").strip()
                pw  = input("  Password: ").strip()
                if uid and pw:
                    lu.register(uid, pw, "student")
            elif c == "0":
                print("  Goodbye!")
                break
        else:
            print("  1. Student Records\n  2. Course Management")
            print("  3. Professor Management\n  4. Reports")
            if session.is_admin():
                print("  5. User Management  [admin]")
            print("  6. Change Password\n  7. Logout\n  0. Exit")
            c = input("\n  Select: ").strip()
            if   c == "1": student_menu(student)
            elif c == "2": course_menu(course)
            elif c == "3": professor_menu(professor)
            elif c == "4": report_menu(report)
            elif c == "5" and session.is_admin(): user_menu(admin)
            elif c == "6":
                old = input("  Old password: ").strip()
                new = input("  New password: ").strip()
                lu.Change_password(session.user_id, old, new)
            elif c == "7": lu.Logout()
            elif c == "0": print("  Goodbye!"); break


def student_menu(student):
    """Sub-menu for student record operations. Options shown depend on role."""
    while True:
        print("\n  -- Student Records --")
        if session.is_admin():
            print("  1. Display  2. Add  3. Delete  4. Update")
        elif session.is_professor():
            print("  1. Display")
        if session.is_student():
            print("  9. My Grades & Marks")
        if not session.is_student():
            print("  5. Search  6. Sort  8. Course Stats")
        print("  0. Back")
        c = input("  Select: ").strip()

        if c == "1":
            student.display_records()
        elif c == "2":
            e   = input("  Email: ").strip()
            f   = input("  First name: ").strip()
            l   = input("  Last name: ").strip()
            cid = input("  Course ID: ").strip()
            m   = input("  Marks (0-100): ").strip()
            student.add_new_student(e, f, l, cid, Grades.marks_to_grade(m), m)
        elif c == "3":
            e   = input("  Email: ").strip()
            cid = input("  Course ID (blank = delete all): ").strip()
            student.delete_new_student(e, cid if cid else None)
        elif c == "4":
            e     = input("  Email: ").strip()
            field = input("  Field (First_name/Last_name/Course_id/Marks): ").strip()
            val   = input("  New value: ").strip()
            student.update_student_record(e, field, val)
        elif c == "5":
            student.search_student(input("  Email: ").strip())
        elif c == "6":
            print("  Sort by: 1.Marks  2.Email  3.Name")
            s = input("  Select: ").strip()
            d = input("  Descending? (y/n): ").strip().lower() == "y"
            key = {"1":"marks","2":"email","3":"name"}.get(s,"marks")
            # Time the sort and print it as required by the assignment
            start = time.perf_counter()
            rows = student.sort_records(key, d)
            elapsed = (time.perf_counter() - start) * 1000
            print(f"  Sort time: {elapsed:.4f} ms")
            for r in rows:
                print(f"  {r.get('Email_address',''):<28} "
                      f"{r.get('Course_id',''):<10} Marks: {r.get('Marks','')}")
        elif c == "8":
            student.course_stats(input("  Course ID: ").strip())
        elif c == "9":
            student.check_my_grades(session.user_id)
            student.check_my_marks(session.user_id)
        elif c == "0":
            break


def course_menu(course):
    """Sub-menu for course management. Add/delete/modify are admin-only."""
    while True:
        print("\n  -- Courses --")
        print("  1. Display")
        if session.is_admin():
            print("  2. Add  3. Delete  4. Modify")
        print("  0. Back")
        c = input("  Select: ").strip()
        if c == "1":
            course.display_courses()
        elif c == "2":
            course.add_new_course(
                input("  Course ID: ").strip(),
                input("  Name: ").strip(),
                input("  Credits: ").strip(),
                input("  Description: ").strip())
        elif c == "3":
            course.delete_new_course(input("  Course ID: ").strip())
        elif c == "4":
            course.modify_course(
                input("  Course ID: ").strip(),
                input("  Field (Course_name/Credits/Description): ").strip(),
                input("  New value: ").strip())
        elif c == "0":
            break


def professor_menu(professor):
    """Sub-menu for professor management. Add/delete/modify are admin-only."""
    while True:
        print("\n  -- Professors --")
        print("  1. Display")
        if session.is_admin():
            print("  2. Add  3. Delete  4. Modify  5. Course by Professor")
        print("  0. Back")
        c = input("  Select: ").strip()
        if c == "1":
            professor.professors_details()
        elif c == "2":
            professor.add_new_professor(
                input("  Professor ID (email): ").strip(),
                input("  Name: ").strip(),
                input("  Rank: ").strip(),
                input("  Course ID: ").strip())
        elif c == "3":
            professor.delete_professore(input("  Professor ID: ").strip())
        elif c == "4":
            professor.modify_professor_details(
                input("  Professor ID: ").strip(),
                input("  Field (Professor_name/Rank/Course_id): ").strip(),
                input("  New value: ").strip())
        elif c == "5":
            professor.show_course_details_by_professor(
                input("  Professor ID: ").strip())
        elif c == "0":
            break


def report_menu(report):
    """Sub-menu for grade reports. Students only see option 3 (their own report)."""
    while True:
        print("\n  -- Reports --")
        if session.is_student():
            print("  3. My Grade Report")
        else:
            print("  1. By Course  2. By Professor  3. By Student")
        print("  0. Back")
        c = input("  Select: ").strip()
        if c == "1":
            report.display_grade_report("course", input("  Course ID: ").strip())
        elif c == "2":
            report.display_grade_report("professor", input("  Professor ID: ").strip())
        elif c == "3":
            email = (session.user_id if session.is_student()
                     else input("  Student email: ").strip())
            report.display_grade_report("student", email)
        elif c == "0":
            break


def user_menu(admin):
    """Sub-menu for user account management. Admin only."""
    while True:
        print("\n  -- User Management [admin] --")
        print("  1. List users  2. Add user  3. Delete user  4. Reset password")
        print("  0. Back")
        c = input("  Select: ").strip()
        if c == "1":
            admin.list_users()
        elif c == "2":
            admin.add_user(
                input("  User ID: ").strip(),
                input("  Password: ").strip(),
                input(f"  Role ({'/'.join(ROLES)}): ").strip().lower())
        elif c == "3":
            admin.remove_user(input("  User ID: ").strip())
        elif c == "4":
            admin.reset_password(
                input("  User ID: ").strip(),
                input("  New password: ").strip())
        elif c == "0":
            break


if __name__ == "__main__":
    main_menu()
