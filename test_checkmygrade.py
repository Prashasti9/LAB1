"""
Unit Tests - CheckMyGrade Application

We use Python's built-in unittest framework to test every major feature of
the application. Each test class focuses on one entity (Student, Course, etc.)
and each test method covers one specific behaviour we want to verify.

All tests use separate temp files (test_*.csv) so they never touch the real
data files. The setUp and tearDown methods handle creating and cleaning up
those files around each individual test.
"""

import unittest
import csv
import io
import sys
import tempfile
from unittest.mock import MagicMock, patch
import os
import time
import random
import string

import checkmygrade as app

# Point the app at temp files so our tests are fully isolated from real data.
# The test file overrides these module-level variables before any test runs.
app.STUDENTS_FILE   = "test_students.csv"
app.COURSES_FILE    = "test_courses.csv"
app.PROFESSORS_FILE = "test_professors.csv"
app.LOGIN_FILE      = "test_login.csv"

# Constants so Suite 1 setUp methods can reset paths after Suite 2 changes them
_ORIG_STUDENTS   = "test_students.csv"
_ORIG_COURSES    = "test_courses.csv"
_ORIG_PROFESSORS = "test_professors.csv"
_ORIG_LOGIN      = "test_login.csv"


def cleanup():
    """Delete all temp CSV files so each test starts with a clean slate."""
    for f in [app.STUDENTS_FILE, app.COURSES_FILE,
              app.PROFESSORS_FILE, app.LOGIN_FILE]:
        if os.path.exists(f):
            os.remove(f)


def login_as(role):
    """Simulate a logged-in user with the given role. Used in test setup."""
    app.session.login(f"{role}@test.edu", role)


def logout():
    """Clear the session between tests so roles don't bleed across."""
    app.session.user_id = None
    app.session.role    = None


def rand_email():
    """Generate a random email address for tests that need unique students."""
    return "".join(random.choices(string.ascii_lowercase, k=5)) + "@test.edu"


# ── Session Tests ─────────────────────────────────────────────────────────────
# These tests make sure the session correctly tracks roles and enforces access.

class TestSession(unittest.TestCase):

    def tearDown(self): logout()

    def test_admin_is_admin(self):
        # Admin should pass both is_admin() and is_professor() checks
        login_as("admin")
        self.assertTrue(app.session.is_admin())
        self.assertTrue(app.session.is_professor())

    def test_professor_not_admin(self):
        # Professor should not have admin privileges
        login_as("professor")
        self.assertFalse(app.session.is_admin())
        self.assertTrue(app.session.is_professor())

    def test_student_role(self):
        # Student should only pass the is_student() check
        login_as("student")
        self.assertTrue(app.session.is_student())
        self.assertFalse(app.session.is_admin())

    def test_require_pass(self):
        # require() should return True when the role matches
        login_as("admin")
        self.assertTrue(app.session.require("admin"))

    def test_require_denied(self):
        # require() should return False when the role doesn't match
        login_as("student")
        self.assertFalse(app.session.require("admin"))

    def test_logout(self):
        # After logout, the role should be cleared back to None
        login_as("admin")
        app.session.logout()
        self.assertIsNone(app.session.role)


# ── Student Tests ─────────────────────────────────────────────────────────────
# Covers add, delete, update, check grades/marks, search, sort, and bulk load.

class TestStudent(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.s = app.Student()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_add_student(self):
        # Basic add — student should appear in the linked list after adding
        r = self.s.add_new_student(
            "alice@test.edu","Alice","Smith","DATA200","A","95")
        self.assertTrue(r)
        self.assertIsNotNone(self.s._ll.find("alice@test.edu"))

    def test_multi_enrollment(self):
        # Same student can enroll in a second course — should get two records
        self.s.add_new_student("alice@test.edu","Alice","S","DATA200","A","95")
        r = self.s.add_new_student("alice@test.edu","Alice","S","DATA220","B","82")
        self.assertTrue(r)
        self.assertEqual(len(self.s._ll.find_all("alice@test.edu")), 2)

    def test_duplicate_enrollment_rejected(self):
        # Adding the same student to the same course twice should fail
        self.s.add_new_student("bob@test.edu","Bob","J","DATA200","B","80")
        r = self.s.add_new_student("bob@test.edu","Bob","J","DATA200","B","80")
        self.assertFalse(r)

    def test_delete_one_enrollment(self):
        # Deleting one enrollment should leave the other one intact
        self.s.add_new_student("c@test.edu","C","D","DATA200","A","90")
        self.s.add_new_student("c@test.edu","C","D","DATA220","B","82")
        self.s.delete_new_student("c@test.edu","DATA200")
        remaining = self.s._ll.find_all("c@test.edu")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["Course_id"], "DATA220")

    def test_delete_all_enrollments(self):
        # Calling delete without a course_id should wipe all enrollments
        self.s.add_new_student("d@test.edu","D","E","DATA200","A","90")
        self.s.delete_new_student("d@test.edu")
        self.assertIsNone(self.s._ll.find("d@test.edu"))

    def test_update_recalculates_grade(self):
        # When marks are updated, the grade letter should update automatically
        self.s.add_new_student("e@test.edu","E","F","DATA200","C","72")
        self.s.update_student_record("e@test.edu","Marks","88")
        rec = self.s._ll.find("e@test.edu")
        self.assertEqual(rec["Grade"], "B")

    def test_check_my_grades(self):
        # Students should be able to view their own grades without errors
        self.s.add_new_student("f@test.edu","F","G","DATA200","A","92")
        login_as("student")
        app.session.user_id = "f@test.edu"
        s2 = app.Student()
        s2.check_my_grades("f@test.edu")  # should not raise

    def test_student_cannot_add(self):
        # Students should not be allowed to add new student records
        login_as("student")
        s = app.Student()
        r = s.add_new_student("x@test.edu","X","Y","DATA200","A","90")
        self.assertFalse(r)

    def test_professor_cannot_add(self):
        # Professors also should not be able to add student records
        login_as("professor")
        s = app.Student()
        r = s.add_new_student("x@test.edu","X","Y","DATA200","A","90")
        self.assertFalse(r)

    def test_bulk_1000_with_search_timing(self):
        """
        Step 5 requirement: student file must have at least 1000 records,
        and we must load from CSV and print search timing.

        We write 1000 rows in one batch (instead of 1000 individual adds)
        to keep the test fast, then reload from CSV to simulate a real run.
        """
        import csv as _csv, random as _rand

        # Build 1000 student rows in memory
        emails = []
        rows   = []
        for i in range(1000):
            email = f"student{i:04d}@test.edu"
            marks = str(_rand.randint(50, 100))
            rows.append({
                "Email_address": email,
                "First_name":    f"First{i}",
                "Last_name":     f"Last{i}",
                "Course_id":     "DATA200",
                "Grade":         app.Grades.marks_to_grade(marks),
                "Marks":         marks
            })
            emails.append(email)

        # Write all 1000 in a single file operation
        app.write_csv(app.STUDENTS_FILE, rows,
                      ["Email_address","First_name","Last_name",
                       "Course_id","Grade","Marks"])

        # Reload from CSV — this simulates loading data from a previous run
        login_as("admin")
        fresh = app.Student()
        self.assertEqual(len(fresh.get_all()), 1000)

        # Run 10 searches and print the total and average time
        targets = _rand.sample(emails, 10)
        total   = 0.0
        for target in targets:
            start = time.perf_counter()
            rec   = fresh._ll.find(target)
            total += time.perf_counter() - start
            self.assertIsNotNone(rec)
        print(f"\n  [search] 10 searches in 1000 records: "
              f"{total*1000:.4f} ms total | {total/10*1000:.4f} ms avg")

    def test_sort_marks_ascending_timed(self):
        # Sort by marks ascending and verify the order, printing the time taken
        for m in ["70","90","55","85"]:
            self.s.add_new_student(rand_email(),"A","B","DATA200",
                                   app.Grades.marks_to_grade(m), m)
        start = time.perf_counter()
        rows  = self.s.sort_records("marks", False)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"\n  [sort] marks ascending: {elapsed:.4f} ms")
        marks = [float(r["Marks"]) for r in rows]
        self.assertEqual(marks, sorted(marks))

    def test_sort_marks_descending_timed(self):
        # Sort by marks descending and verify the order, printing the time taken
        for m in ["70","90","55","85"]:
            self.s.add_new_student(rand_email(),"A","B","DATA200",
                                   app.Grades.marks_to_grade(m), m)
        start = time.perf_counter()
        rows  = self.s.sort_records("marks", True)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"\n  [sort] marks descending: {elapsed:.4f} ms")
        marks = [float(r["Marks"]) for r in rows]
        self.assertEqual(marks, sorted(marks, reverse=True))

    def test_sort_email_timed(self):
        # Sort by email address and verify alphabetical order
        for prefix in ["zara","alice","mike"]:
            self.s.add_new_student(f"{prefix}@test.edu",prefix,"T",
                                   "DATA200","A","90")
        start = time.perf_counter()
        rows  = self.s.sort_records("email", False)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"\n  [sort] email ascending: {elapsed:.4f} ms")
        emails = [r["Email_address"].lower() for r in rows]
        self.assertEqual(emails, sorted(emails))

    def test_sort_name_timed(self):
        # Sort by student name and verify the result is alphabetically ordered
        for fn,ln in [("Zara","Ali"),("Alice","Brown"),("Mike","Chen")]:
            self.s.add_new_student(f"{fn.lower()}@test.edu",fn,ln,
                                   "DATA200","A","90")
        start = time.perf_counter()
        rows  = self.s.sort_records("name", False)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"\n  [sort] name ascending: {elapsed:.4f} ms")
        names = [(r["First_name"].lower(), r["Last_name"].lower()) for r in rows]
        self.assertEqual(names, sorted(names))


# ── Course Tests ──────────────────────────────────────────────────────────────
# Basic add, delete, modify, and duplicate/permission checks for courses.

class TestCourse(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.c = app.Course()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_add_course(self):
        # Simple add — should return True and persist to courses.csv
        r = self.c.add_new_course("DATA200","Data Science","3","DS intro")
        self.assertTrue(r)

    def test_duplicate_rejected(self):
        # Adding the same course ID twice should fail on the second attempt
        self.c.add_new_course("DATA200","Data Science","3","DS")
        r = self.c.add_new_course("DATA200","Data Science","3","DS")
        self.assertFalse(r)

    def test_delete_course(self):
        # Deleting an existing course should return True
        self.c.add_new_course("CS101","Intro CS","3","Basics")
        r = self.c.delete_new_course("CS101")
        self.assertTrue(r)

    def test_modify_course(self):
        # Modifying a field should update the value in courses.csv
        self.c.add_new_course("DATA220","Stats","3","Statistics")
        self.c.modify_course("DATA220","Course_name","Advanced Stats")
        rows = app.read_csv(app.COURSES_FILE)
        m = next((r for r in rows if r["Course_id"]=="DATA220"), None)
        self.assertEqual(m["Course_name"], "Advanced Stats")

    def test_student_cannot_add(self):
        # Students should not be able to add courses
        login_as("student")
        c = app.Course()
        r = c.add_new_course("X101","X","3","X")
        self.assertFalse(r)


# ── Professor Tests ───────────────────────────────────────────────────────────
# Basic add, delete, modify, and duplicate/permission checks for professors.

class TestProfessor(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.p = app.Professor()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_add_professor(self):
        # Simple add — should return True and persist to professors.csv
        r = self.p.add_new_professor(
            "prof@test.edu","Dr. Smith","Senior Professor","DATA200")
        self.assertTrue(r)

    def test_duplicate_rejected(self):
        # Adding the same professor ID twice should fail on the second attempt
        self.p.add_new_professor("p@test.edu","Dr. X","Prof","DATA200")
        r = self.p.add_new_professor("p@test.edu","Dr. X","Prof","DATA200")
        self.assertFalse(r)

    def test_delete_professor(self):
        # Deleting an existing professor should return True
        self.p.add_new_professor("p2@test.edu","Dr. Y","Assistant","DATA200")
        r = self.p.delete_professore("p2@test.edu")
        self.assertTrue(r)

    def test_modify_professor(self):
        # Modifying a field should update the value in professors.csv
        self.p.add_new_professor("p3@test.edu","Dr. Z","Lecturer","CS101")
        self.p.modify_professor_details("p3@test.edu","Rank","Professor")
        rows = app.read_csv(app.PROFESSORS_FILE)
        m = next((r for r in rows if r["Professor_id"]=="p3@test.edu"), None)
        self.assertEqual(m["Rank"], "Professor")

    def test_student_cannot_add(self):
        # Students should not be able to add professors
        login_as("student")
        p = app.Professor()
        r = p.add_new_professor("x@test.edu","X","X","X")
        self.assertFalse(r)


# ── LoginUser Tests ───────────────────────────────────────────────────────────
# Tests for login, logout, password change, and encryption.

class TestLoginUser(unittest.TestCase):

    def setUp(self):
        cleanup()
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        logout()
        self.lu = app.LoginUser()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def _add(self, uid, pw, role):
        """Helper to insert a user record directly into login.csv for testing."""
        self.lu._rows.append({"User_id": uid,
                               "Password": app.encrypt_password(pw),
                               "Role": role})
        self.lu._save()
        self.lu._rows = app.read_csv(app.LOGIN_FILE)

    def test_login_success(self):
        # Correct credentials should return the user's role
        self._add("u@test.edu","Pass1!","student")
        role = self.lu.Login("u@test.edu","Pass1!")
        self.assertEqual(role, "student")

    def test_wrong_password(self):
        # Wrong password should return None
        self._add("u2@test.edu","Pass1!","student")
        role = self.lu.Login("u2@test.edu","wrong")
        self.assertIsNone(role)

    def test_password_encrypted_in_file(self):
        # The password stored in the CSV should not match the plain-text version
        self._add("u3@test.edu","Plain1","student")
        rows = app.read_csv(app.LOGIN_FILE)
        rec  = next((r for r in rows if r["User_id"]=="u3@test.edu"), None)
        self.assertNotEqual(rec["Password"], "Plain1")

    def test_change_password(self):
        # After changing password, login with new password should succeed
        self._add("u4@test.edu","OldPw1!","student")
        login_as("student")
        app.session.user_id = "u4@test.edu"
        self.lu.Change_password("u4@test.edu","OldPw1!","NewPw2!")
        self.lu._rows = app.read_csv(app.LOGIN_FILE)
        logout()
        role = self.lu.Login("u4@test.edu","NewPw2!")
        self.assertEqual(role, "student")

    def test_encrypt_decrypt(self):
        # Encrypting and then decrypting should give back the original string
        enc = self.lu.Encrypt_password("hello")
        dec = self.lu.decrypt_password(enc)
        self.assertEqual(dec, "hello")


# ── Admin Tests ───────────────────────────────────────────────────────────────
# Tests for admin-specific operations: add/remove users, reset passwords.

class TestAdmin(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.admin = app.Admin()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_admin_is_loginuser(self):
        # Admin inherits from LoginUser (IS-A relationship)
        self.assertIsInstance(self.admin, app.LoginUser)

    def test_add_remove_user(self):
        # Adding and then removing a user should both succeed
        r = self.admin.add_user("new@test.edu","Pass1!","student")
        self.assertTrue(r)
        r = self.admin.remove_user("new@test.edu")
        self.assertTrue(r)

    def test_reset_password(self):
        # Admin should be able to reset a password without knowing the old one
        self.admin._rows.append({"User_id":"rst@test.edu",
                                  "Password":app.encrypt_password("Old1!"),
                                  "Role":"student"})
        self.admin._save()
        self.admin._rows = app.read_csv(app.LOGIN_FILE)
        r = self.admin.reset_password("rst@test.edu","New1!")
        self.assertTrue(r)

    def test_student_cannot_use_admin(self):
        # Students should not be able to remove users
        login_as("student")
        a = app.Admin()
        r = a.remove_user("anyone@test.edu")
        self.assertFalse(r)

    def test_cannot_delete_own_account(self):
        # An admin should not be able to delete their own login account
        login_as("admin")
        app.session.user_id = "admin@test.edu"
        self.admin._rows.append({"User_id":"admin@test.edu",
                                  "Password":app.encrypt_password("A1!"),
                                  "Role":"admin"})
        self.admin._save()
        self.admin._rows = app.read_csv(app.LOGIN_FILE)
        r = self.admin.remove_user("admin@test.edu")
        self.assertFalse(r)


# ── Additional Student Tests ──────────────────────────────────────────────────
# Extra edge cases for search, marks, stats, sync behaviour, and linked list.

class TestStudentExtra(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.s = app.Student()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_search_student_timed(self):
        # Search should find the student and print the time taken
        self.s.add_new_student("s@test.edu","S","T","DATA200","A","90")
        rec = self.s.search_student("s@test.edu")
        self.assertIsNotNone(rec)

    def test_search_not_found(self):
        # Searching for a non-existent student should return None
        rec = self.s.search_student("nobody@test.edu")
        self.assertIsNone(rec)

    def test_check_my_marks(self):
        # Students should be able to see their own numeric marks
        self.s.add_new_student("m@test.edu","M","N","DATA200","A","92")
        login_as("student")
        app.session.user_id = "m@test.edu"
        s2 = app.Student()
        s2.check_my_marks("m@test.edu")  # should not raise

    def test_student_cannot_see_others_marks(self):
        # A student logged in as one person should not see another person's marks
        login_as("admin")
        self.s.add_new_student("o@test.edu","O","P","DATA200","A","90")
        login_as("student")
        app.session.user_id = "me@test.edu"
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        self.s.check_my_marks("o@test.edu")
        sys.stdout = sys.__stdout__
        self.assertIn("Access denied", captured.getvalue())

    def test_course_stats_avg_median(self):
        # Stats output should include both Avg and Median labels
        for m in ["70","80","90","100"]:
            self.s.add_new_student(rand_email(),"A","B","DATA200",
                                   app.Grades.marks_to_grade(m),m)
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        self.s.course_stats("DATA200")
        sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("Avg", out)
        self.assertIn("Median", out)

    def test_course_stats_no_records(self):
        # Stats for a course with no students should say "No records"
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        self.s.course_stats("NOEXIST")
        sys.stdout = sys.__stdout__
        self.assertIn("No records", captured.getvalue())

    def test_update_first_name(self):
        # Updating First_name should change it in the linked list
        self.s.add_new_student("upd@test.edu","Old","Name","DATA200","A","90")
        self.s.update_student_record("upd@test.edu","First_name","New")
        rec = self.s._ll.find("upd@test.edu")
        self.assertEqual(rec["First_name"], "New")

    def test_update_nonexistent_student(self):
        # Trying to update a student that doesn't exist should return False
        r = self.s.update_student_record("ghost@test.edu","Marks","90")
        self.assertFalse(r)

    def test_grades_marks_to_grade_all_ranges(self):
        # Every grade range should map to the correct letter
        self.assertEqual(app.Grades.marks_to_grade("95"), "A")
        self.assertEqual(app.Grades.marks_to_grade("85"), "B")
        self.assertEqual(app.Grades.marks_to_grade("75"), "C")
        self.assertEqual(app.Grades.marks_to_grade("65"), "D")
        self.assertEqual(app.Grades.marks_to_grade("50"), "F")

    def test_grades_invalid_marks(self):
        # Non-numeric marks input should default to "F"
        result = app.Grades.marks_to_grade("abc")
        self.assertEqual(result, "F")

    def test_linked_list_find_all(self):
        # find_all should return both records when a student has two enrollments
        self.s.add_new_student("ll@test.edu","L","L","DATA200","A","90")
        self.s.add_new_student("ll@test.edu","L","L","DATA220","B","80")
        recs = self.s._ll.find_all("ll@test.edu")
        self.assertEqual(len(recs), 2)

    def test_linked_list_delete_specific(self):
        # Deleting one specific enrollment should leave the other untouched
        self.s.add_new_student("dl@test.edu","D","L","DATA200","A","90")
        self.s.add_new_student("dl@test.edu","D","L","DATA220","B","80")
        self.s._ll.delete("dl@test.edu","DATA200")
        recs = self.s._ll.find_all("dl@test.edu")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["Course_id"], "DATA220")

    def test_auto_sync_course_created_on_student_add(self):
        # Adding a student to a new course should auto-create that course
        self.s.add_new_student("nc@test.edu","N","C","NEWCOURSE","A","90")
        courses = app.read_csv(app.COURSES_FILE)
        self.assertTrue(any(r["Course_id"]=="NEWCOURSE" for r in courses))

    def test_auto_sync_login_created_on_student_add(self):
        # Adding a student should automatically create their login account
        self.s.add_new_student("nl@test.edu","N","L","DATA200","A","90")
        logins = app.read_csv(app.LOGIN_FILE)
        self.assertTrue(any(r["User_id"]=="nl@test.edu" for r in logins))

    def test_auto_sync_login_removed_on_student_delete(self):
        # Deleting a student's only enrollment should remove their login too
        self.s.add_new_student("rd@test.edu","R","D","DATA200","A","90")
        self.s.delete_new_student("rd@test.edu")
        logins = app.read_csv(app.LOGIN_FILE)
        self.assertFalse(any(r["User_id"]=="rd@test.edu" for r in logins))

    def test_auto_sync_login_kept_if_other_enrollment(self):
        # If a student still has another enrollment, their login should stay
        self.s.add_new_student("ke@test.edu","K","E","DATA200","A","90")
        self.s.add_new_student("ke@test.edu","K","E","DATA220","B","80")
        self.s.delete_new_student("ke@test.edu","DATA200")
        logins = app.read_csv(app.LOGIN_FILE)
        self.assertTrue(any(r["User_id"]=="ke@test.edu" for r in logins))

    def test_display_records_professor_scoped(self):
        # A professor should only see records for their own course
        app.write_csv(app.PROFESSORS_FILE,
                      [{"Professor_id":"prof@test.edu",
                        "Professor_name":"P","Rank":"Prof",
                        "Course_id":"DATA200"}],
                      ["Professor_id","Professor_name","Rank","Course_id"])
        self.s.add_new_student("sc@test.edu","S","C","DATA200","A","90")
        self.s.add_new_student("sc2@test.edu","S2","C2","DATA220","B","80")
        login_as("professor")
        app.session.user_id = "prof@test.edu"
        s2 = app.Student()
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        s2.display_records()
        sys.stdout = sys.__stdout__
        self.assertIn("DATA200", captured.getvalue())
        self.assertNotIn("DATA220", captured.getvalue())

    def test_get_all_returns_list(self):
        # get_all() should return a plain list with at least one item
        self.s.add_new_student("g@test.edu","G","H","DATA200","A","90")
        rows = self.s.get_all()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)


# ── Additional Course Tests ───────────────────────────────────────────────────
# Edge cases for course deletion cascades and permission enforcement.

class TestCourseExtra(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.c = app.Course()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_delete_course_removes_students(self):
        # Deleting a course should remove all students enrolled in it
        s = app.Student()
        s.add_new_student("ds@test.edu","D","S","DATA200","A","90")
        self.c.add_new_course("DATA200","DS","3","desc")
        self.c.delete_new_course("DATA200")
        rows = app.read_csv(app.STUDENTS_FILE)
        self.assertFalse(any(r.get("Course_id")=="DATA200" for r in rows))

    def test_delete_course_unassigns_professor(self):
        # Deleting a course should clear the Course_id from the assigned professor
        app.write_csv(app.PROFESSORS_FILE,
                      [{"Professor_id":"p@test.edu","Professor_name":"P",
                        "Rank":"Prof","Course_id":"DATA200"}],
                      ["Professor_id","Professor_name","Rank","Course_id"])
        self.c.add_new_course("DATA200","DS","3","desc")
        self.c.delete_new_course("DATA200")
        profs = app.read_csv(app.PROFESSORS_FILE)
        p = next((r for r in profs if r["Professor_id"]=="p@test.edu"), None)
        self.assertEqual(p["Course_id"], "")

    def test_modify_credits(self):
        # Updating the Credits field should persist to courses.csv
        self.c.add_new_course("DATA226","ML","3","ML desc")
        self.c.modify_course("DATA226","Credits","4")
        rows = app.read_csv(app.COURSES_FILE)
        m = next((r for r in rows if r["Course_id"]=="DATA226"), None)
        self.assertEqual(m["Credits"], "4")

    def test_delete_nonexistent_course(self):
        # Trying to delete a course that doesn't exist should return False
        r = self.c.delete_new_course("NOEXIST")
        self.assertFalse(r)

    def test_professor_cannot_delete_course(self):
        # Professors should not be able to delete courses
        self.c.add_new_course("DATA200","DS","3","desc")
        login_as("professor")
        c2 = app.Course()
        r = c2.delete_new_course("DATA200")
        self.assertFalse(r)


# ── Additional Professor Tests ────────────────────────────────────────────────
# Edge cases for professor login sync, scoped views, and permission checks.

class TestProfessorExtra(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.p = app.Professor()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_show_course_by_professor(self):
        # show_course_details_by_professor should print the correct course ID
        self.p.add_new_professor("p@test.edu","Dr.X","Prof","DATA200")
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        self.p.show_course_details_by_professor("p@test.edu")
        sys.stdout = sys.__stdout__
        self.assertIn("DATA200", captured.getvalue())

    def test_auto_sync_login_on_add(self):
        # Adding a professor should automatically create their login account
        self.p.add_new_professor("np@test.edu","New Prof","Lecturer","CS101")
        logins = app.read_csv(app.LOGIN_FILE)
        self.assertTrue(any(r["User_id"]=="np@test.edu" for r in logins))

    def test_auto_sync_login_on_delete(self):
        # Deleting a professor should also remove their login account
        self.p.add_new_professor("dp@test.edu","Del Prof","Asst","CS101")
        self.p.delete_professore("dp@test.edu")
        logins = app.read_csv(app.LOGIN_FILE)
        self.assertFalse(any(r["User_id"]=="dp@test.edu" for r in logins))

    def test_professor_sees_only_own_profile(self):
        # A logged-in professor should only see their own record, not others'
        self.p.add_new_professor("s@test.edu","Saini","Prof","DATA200")
        self.p.add_new_professor("m@test.edu","Masum","Prof","DATA220")
        login_as("professor")
        app.session.user_id = "s@test.edu"
        p2 = app.Professor()
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        p2.professors_details()
        sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("Saini", out)
        self.assertNotIn("Masum", out)

    def test_delete_nonexistent_professor(self):
        # Trying to delete a professor that doesn't exist should return False
        r = self.p.delete_professore("ghost@test.edu")
        self.assertFalse(r)


# ── Additional Admin Tests ────────────────────────────────────────────────────

class TestAdminExtra(unittest.TestCase):

    def setUp(self):
        cleanup()
        login_as("admin")
        self.admin = app.Admin()

    def tearDown(self):
        app.STUDENTS_FILE   = _ORIG_STUDENTS
        app.COURSES_FILE    = _ORIG_COURSES
        app.PROFESSORS_FILE = _ORIG_PROFESSORS
        app.LOGIN_FILE      = _ORIG_LOGIN
        cleanup()
        logout()

    def test_add_professor_role(self):
        # Admin should be able to add a user with the professor role
        r = self.admin.add_user("newp@test.edu","Pass1!","professor")
        self.assertTrue(r)
        logins = app.read_csv(app.LOGIN_FILE)
        rec = next((r for r in logins if r["User_id"]=="newp@test.edu"), None)
        self.assertEqual(rec["Role"], "professor")

    def test_invalid_role_rejected(self):
        # Made-up roles like "superuser" should not be accepted
        r = self.admin.add_user("x@test.edu","Pass1!","superuser")
        self.assertFalse(r)

    def test_list_users(self):
        # list_users() should run without errors when there are users present
        self.admin._rows.append({"User_id":"u@test.edu",
                                  "Password":app.encrypt_password("p"),
                                  "Role":"student"})
        self.admin._save()
        self.admin._rows = app.read_csv(app.LOGIN_FILE)
        self.admin.list_users()  # should not raise

    def test_student_cannot_add_admin(self):
        # A student should not be able to create an admin account
        login_as("student")
        a = app.Admin()
        r = a.add_user("newadmin@test.edu","Pass1!","admin")
        self.assertFalse(r)


import tempfile
from unittest.mock import MagicMock, patch


##############################################################################
# SUITE 2 — Extended tests (BaseTestCase with seeded CSV data)
# ===========================================================================

def seed_csv(path, fieldnames, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app.STUDENTS_FILE = os.path.join(self.tmp.name, 'students.csv')
        app.COURSES_FILE = os.path.join(self.tmp.name, 'courses.csv')
        app.PROFESSORS_FILE = os.path.join(self.tmp.name, 'professors.csv')
        app.LOGIN_FILE = os.path.join(self.tmp.name, 'login.csv')

        seed_csv(app.STUDENTS_FILE, app.Student.FIELDS, [
            {
                'Email_address': 'sam@mycsu.edu',
                'First_name': 'Sam',
                'Last_name': 'Carpenter',
                'Course_id': 'DATA200',
                'Grade': 'A',
                'Marks': '91',
            },
            {
                'Email_address': 'sam@mycsu.edu',
                'First_name': 'Sam',
                'Last_name': 'Carpenter',
                'Course_id': 'CS101',
                'Grade': 'B',
                'Marks': '84',
            },
            {
                'Email_address': 'alex@mycsu.edu',
                'First_name': 'Alex',
                'Last_name': 'Stone',
                'Course_id': 'DATA200',
                'Grade': 'C',
                'Marks': '74',
            },
        ])
        seed_csv(app.COURSES_FILE, app.Course.FIELDS, [
            {'Course_id': 'DATA200', 'Course_name': 'Data Programming', 'Credits': '3', 'Description': 'Core lab'},
            {'Course_id': 'CS101', 'Course_name': 'Intro CS', 'Credits': '4', 'Description': 'Basics'},
        ])
        seed_csv(app.PROFESSORS_FILE, app.Professor.FIELDS, [
            {'Professor_id': 'saini@sjsu.edu', 'Professor_name': 'Prof Saini', 'Rank': 'Senior Professor', 'Course_id': 'DATA200'},
            {'Professor_id': 'masum@sjsu.edu', 'Professor_name': 'Prof Masum', 'Rank': 'Professor', 'Course_id': 'CS101'},
        ])
        seed_csv(app.LOGIN_FILE, app.LoginUser.FIELDS, [
            {'User_id': 'admin@mycsu.edu', 'Password': app.encrypt_password('Admin123!'), 'Role': 'admin'},
            {'User_id': 'saini@sjsu.edu', 'Password': app.encrypt_password('Prof123!'), 'Role': 'professor'},
            {'User_id': 'masum@sjsu.edu', 'Password': app.encrypt_password('Prof123!'), 'Role': 'professor'},
            {'User_id': 'sam@mycsu.edu', 'Password': app.encrypt_password('Student123!'), 'Role': 'student'},
        ])
        app.session.user_id = None
        app.session.role = None

    def login_as(self, role):
        mapping = {
            'admin': ('admin@mycsu.edu', 'admin'),
            'professor': ('saini@sjsu.edu', 'professor'),
            'student': ('sam@mycsu.edu', 'student'),
        }
        uid, r = mapping[role]
        app.session.login(uid, r)


class TestCsvHelpers(BaseTestCase):
    def test_read_csv_missing_file_returns_empty(self):
        self.assertEqual(app.read_csv(os.path.join(self.tmp.name, 'missing.csv')), [])

    def test_read_csv_bad_file_returns_empty(self):
        bad = os.path.join(self.tmp.name, 'bad.csv')
        with open(bad, 'w', encoding='utf-8') as f:
            f.write('\x00\x00')
        result = app.read_csv(bad)
        self.assertIsInstance(result, list)

    def test_write_csv_writes_rows(self):
        path = os.path.join(self.tmp.name, 'out.csv')
        rows = [{'a': '1', 'b': '2'}]
        app.write_csv(path, rows, ['a', 'b'])
        with open(path, newline='') as f:
            read_back = list(csv.DictReader(f))
        self.assertEqual(read_back, rows)


class TestSecuritySessionNodeListGrades(BaseTestCase):
    def test_text_security_encrypt_decrypt_roundtrip(self):
        sec = app.TextSecurity(13)
        enc = sec.encrypt('Welcome12#_')
        self.assertNotEqual(enc, 'Welcome12#_')
        self.assertEqual(sec.decrypt(enc), 'Welcome12#_')

    def test_password_wrapper_roundtrip(self):
        enc = app.encrypt_password('Pass123!')
        self.assertEqual(app.decrypt_password(enc), 'Pass123!')

    def test_session_state_and_require(self):
        s = app.Session()
        self.assertFalse(s.is_logged_in())
        s.login('user@test.edu', 'admin')
        self.assertTrue(s.is_logged_in())
        self.assertTrue(s.is_admin())
        self.assertTrue(s.is_professor())
        self.assertFalse(s.is_student())
        self.assertTrue(s.require('admin'))
        with patch('builtins.print') as p:
            self.assertFalse(s.require('student'))
            p.assert_called()
        with patch('builtins.print'):
            s.logout()
        self.assertFalse(s.is_logged_in())

    def test_node_holds_data(self):
        n = app.Node({'x': 1})
        self.assertEqual(n.data, {'x': 1})
        self.assertIsNone(n.next)

    def test_linked_list_append_find_find_all_delete(self):
        ll = app.LinkedList()
        self.assertFalse(ll.delete('nobody@test.edu'))
        ll.append({'Email_address': 'a@test.edu', 'Course_id': 'C1'})
        ll.append({'Email_address': 'a@test.edu', 'Course_id': 'C2'})
        ll.append({'Email_address': 'b@test.edu', 'Course_id': 'C3'})
        self.assertEqual(len(ll.to_list()), 3)
        self.assertEqual(ll.find('a@test.edu')['Course_id'], 'C1')
        self.assertEqual(ll.find('a@test.edu', 'C2')['Course_id'], 'C2')
        self.assertIsNone(ll.find('x@test.edu'))
        self.assertEqual(len(ll.find_all('a@test.edu')), 2)
        self.assertTrue(ll.delete('a@test.edu', 'C1'))
        self.assertTrue(ll.delete('b@test.edu'))
        self.assertFalse(ll.delete('b@test.edu'))

    def test_grades_helpers_and_boundaries(self):
        self.assertEqual(app.Grades.marks_to_grade('90'), 'A')
        self.assertEqual(app.Grades.marks_to_grade('89'), 'B')
        self.assertEqual(app.Grades.marks_to_grade('79'), 'C')
        self.assertEqual(app.Grades.marks_to_grade('69'), 'D')
        self.assertEqual(app.Grades.marks_to_grade('59'), 'F')
        self.assertEqual(app.Grades.marks_to_grade('bad'), 'F')
        g = app.Grades.add_grade('g1', 'A', '90-100')
        with patch('builtins.print') as p:
            g.display_grade_report()
            p.assert_called()
        grades = [g, app.Grades('g2', 'B', '80-89')]
        grades = app.Grades.modify_grade(grades, 'g2', 'A', '90-100')
        self.assertEqual(grades[1].grade, 'A')
        grades = app.Grades.delete_grade(grades, 'g1')
        self.assertEqual([x.grade_id for x in grades], ['g2'])


class TestStudentFull(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.login_as('admin')
        self.student = app.Student()

    def test_load_and_save(self):
        self.assertEqual(len(self.student.get_all()), 3)
        self.student._ll.append({
            'Email_address': 'new@mycsu.edu', 'First_name': 'New', 'Last_name': 'User',
            'Course_id': 'CS101', 'Grade': 'A', 'Marks': '95'
        })
        self.student._save()
        fresh = app.Student()
        self.assertEqual(len(fresh.get_all()), 4)

    def test_sync_login_add_and_no_duplicate(self):
        self.student._sync_login_add('alex2@mycsu.edu')
        rows = app.read_csv(app.LOGIN_FILE)
        self.assertTrue(any(r['User_id'] == 'alex2@mycsu.edu' for r in rows))
        count = len(rows)
        self.student._sync_login_add('alex2@mycsu.edu')
        self.assertEqual(len(app.read_csv(app.LOGIN_FILE)), count)

    def test_sync_login_remove_only_when_no_enrollments_left(self):
        self.student._sync_login_add('sam@mycsu.edu')
        self.student._sync_login_remove('sam@mycsu.edu')
        self.assertTrue(any(r['User_id'] == 'sam@mycsu.edu' for r in app.read_csv(app.LOGIN_FILE)))
        self.student.delete_new_student('sam@mycsu.edu')
        self.assertFalse(any(r['User_id'] == 'sam@mycsu.edu' for r in app.read_csv(app.LOGIN_FILE)))

    def test_sync_course_add_and_no_duplicate(self):
        self.student._sync_course_add('NEW123')
        courses = app.read_csv(app.COURSES_FILE)
        self.assertTrue(any(r['Course_id'] == 'NEW123' for r in courses))
        count = len(courses)
        self.student._sync_course_add('NEW123')
        self.assertEqual(len(app.read_csv(app.COURSES_FILE)), count)

    def test_display_records_admin_and_professor_filter(self):
        with patch('builtins.print') as p:
            self.student.display_records()
            self.assertTrue(p.called)
        self.login_as('professor')
        prof_student = app.Student()
        with patch('builtins.print') as p:
            prof_student.display_records()
            printed = ' '.join(' '.join(map(str, c.args)) for c in p.call_args_list)
        self.assertIn('DATA200', printed)
        self.assertNotIn('CS101', printed)

    def test_display_records_denied_or_empty(self):
        self.login_as('student')
        with patch('builtins.print') as p:
            app.Student().display_records()
            self.assertTrue(any('Access denied' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.login_as('admin')
        seed_csv(app.STUDENTS_FILE, app.Student.FIELDS, [])
        with patch('builtins.print') as p:
            app.Student().display_records()
            self.assertTrue(any('No records found' in ' '.join(map(str, c.args)) for c in p.call_args_list))

    def test_add_new_student_and_validations(self):
        self.assertTrue(self.student.add_new_student('new@mycsu.edu', 'New', 'User', 'DATA300', 'A', '96'))
        self.assertFalse(self.student.add_new_student('new@mycsu.edu', 'New', 'User', 'DATA300', 'A', '96'))
        self.assertFalse(self.student.add_new_student('', 'New', 'User', 'DATA300', 'A', '96'))
        self.assertFalse(self.student.add_new_student('bad@mycsu.edu', 'Bad', 'User', 'DATA300', 'A', 'xx'))
        self.login_as('student')
        self.assertFalse(app.Student().add_new_student('x@y.com', 'X', 'Y', 'C1', 'A', '90'))

    def test_delete_new_student_specific_and_all_and_not_found(self):
        self.assertTrue(self.student.delete_new_student('sam@mycsu.edu', 'CS101'))
        self.assertIsNone(self.student._ll.find('sam@mycsu.edu', 'CS101'))
        self.assertTrue(self.student.delete_new_student('alex@mycsu.edu'))
        self.assertFalse(self.student.delete_new_student('ghost@mycsu.edu'))
        self.assertFalse(self.student.delete_new_student(''))
        self.login_as('student')
        self.assertFalse(app.Student().delete_new_student('sam@mycsu.edu'))

    def test_update_student_record_and_marks_regrade(self):
        self.assertTrue(self.student.update_student_record('alex@mycsu.edu', 'Marks', '95'))
        rec = self.student._ll.find('alex@mycsu.edu')
        self.assertEqual(rec['Grade'], 'A')
        self.assertFalse(self.student.update_student_record('alex@mycsu.edu', 'Marks', 'oops'))
        self.assertFalse(self.student.update_student_record('ghost@mycsu.edu', 'First_name', 'Ghost'))
        self.login_as('student')
        self.assertFalse(app.Student().update_student_record('alex@mycsu.edu', 'First_name', 'X'))

    def test_check_my_grades_and_marks_access(self):
        self.login_as('student')
        with patch('builtins.print') as p:
            app.Student().check_my_grades('sam@mycsu.edu')
            self.assertTrue(any('Grades for sam@mycsu.edu' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            app.Student().check_my_marks('sam@mycsu.edu')
            self.assertTrue(any('Marks for sam@mycsu.edu' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            app.Student().check_my_grades('alex@mycsu.edu')
            self.assertTrue(any('Access denied' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.login_as('admin')
        with patch('builtins.print') as p:
            app.Student().check_my_marks('ghost@mycsu.edu')
            self.assertTrue(any('Student not found' in ' '.join(map(str, c.args)) for c in p.call_args_list))

    def test_search_sort_stats_and_get_all(self):
        rec = self.student.search_student('alex@mycsu.edu')
        self.assertIsNotNone(rec)
        self.assertIsNone(self.student.search_student('ghost@mycsu.edu'))
        marks_asc = self.student.sort_records('marks', False)
        self.assertEqual([r['Marks'] for r in marks_asc], ['74', '84', '91'])
        marks_desc = self.student.sort_records('marks', True)
        self.assertEqual([r['Marks'] for r in marks_desc], ['91', '84', '74'])
        email_sort = self.student.sort_records('email', False)
        self.assertEqual(email_sort[0]['Email_address'], 'alex@mycsu.edu')
        name_sort = self.student.sort_records('name', False)
        self.assertEqual(name_sort[0]['First_name'], 'Alex')
        with patch('builtins.print') as p:
            self.student.course_stats('DATA200')
            self.assertTrue(any('Avg' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            self.student.course_stats('NOPE')
            self.assertTrue(any('No records for NOPE' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.assertEqual(len(self.student.get_all()), 3)
        self.login_as('student')
        self.assertEqual(app.Student().sort_records(), [])


class TestCourseFull(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.login_as('admin')
        self.course = app.Course()

    def test_save_and_display_courses(self):
        self.course._rows.append({'Course_id': 'MATH1', 'Course_name': 'Math', 'Credits': '3', 'Description': 'd'})
        self.course._save()
        self.assertTrue(any(r['Course_id'] == 'MATH1' for r in app.read_csv(app.COURSES_FILE)))
        with patch('builtins.print') as p:
            self.course.display_courses()
            self.assertTrue(p.called)

    def test_display_courses_professor_filter_student_and_empty(self):
        self.login_as('professor')
        with patch('builtins.print') as p:
            app.Course().display_courses()
            printed = ' '.join(' '.join(map(str, c.args)) for c in p.call_args_list)
            self.assertIn('DATA200', printed)
            self.assertNotIn('CS101', printed)
        self.login_as('student')
        with patch('builtins.print') as p:
            app.Course().display_courses()
            self.assertTrue(p.called)
        seed_csv(app.COURSES_FILE, app.Course.FIELDS, [])
        with patch('builtins.print') as p:
            app.Course().display_courses()
            self.assertTrue(any('No courses found' in ' '.join(map(str, c.args)) for c in p.call_args_list))

    def test_add_modify_delete_course_and_permissions(self):
        self.assertTrue(self.course.add_new_course('BIO1', 'Biology', '3', 'Lab'))
        self.assertFalse(self.course.add_new_course('BIO1', 'Biology', '3', 'Lab'))
        self.assertFalse(self.course.add_new_course('', 'Biology', '3', 'Lab'))
        self.assertTrue(self.course.modify_course('BIO1', 'Course_name', 'Biology I'))
        self.assertFalse(self.course.modify_course('NOPE', 'Course_name', 'X'))
        self.assertTrue(self.course.delete_new_course('CS101'))
        prof_rows = app.read_csv(app.PROFESSORS_FILE)
        self.assertEqual(next(r for r in prof_rows if r['Professor_id'] == 'masum@sjsu.edu')['Course_id'], '')
        self.assertFalse(self.course.delete_new_course('NOPE'))
        self.login_as('student')
        c = app.Course()
        self.assertFalse(c.add_new_course('X', 'X', '1', 'x'))
        self.assertFalse(c.modify_course('DATA200', 'Course_name', 'X'))
        self.assertFalse(c.delete_new_course('DATA200'))


class TestProfessorFull(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.login_as('admin')
        self.prof = app.Professor()

    def test_save_and_display_professors(self):
        self.prof._rows.append({'Professor_id': 'new@sjsu.edu', 'Professor_name': 'New Prof', 'Rank': 'Adjunct', 'Course_id': 'DATA200'})
        self.prof._save()
        self.assertTrue(any(r['Professor_id'] == 'new@sjsu.edu' for r in app.read_csv(app.PROFESSORS_FILE)))
        with patch('builtins.print') as p:
            self.prof.professors_details()
            self.assertTrue(p.called)

    def test_professor_details_filter_and_empty(self):
        self.login_as('professor')
        with patch('builtins.print') as p:
            app.Professor().professors_details()
            printed = ' '.join(' '.join(map(str, c.args)) for c in p.call_args_list)
            self.assertIn('saini@sjsu.edu', printed)
            self.assertNotIn('masum@sjsu.edu', printed)
        seed_csv(app.PROFESSORS_FILE, app.Professor.FIELDS, [])
        with patch('builtins.print') as p:
            app.Professor().professors_details()
            self.assertTrue(any('No professors found' in ' '.join(map(str, c.args)) for c in p.call_args_list))

    def test_add_modify_delete_show_professor(self):
        self.assertTrue(self.prof.add_new_professor('new@sjsu.edu', 'New Prof', 'Adjunct', 'CS101'))
        self.assertFalse(self.prof.add_new_professor('new@sjsu.edu', 'New Prof', 'Adjunct', 'CS101'))
        self.assertFalse(self.prof.add_new_professor('', 'New Prof', 'Adjunct', 'CS101'))
        self.assertTrue(any(r['User_id'] == 'new@sjsu.edu' for r in app.read_csv(app.LOGIN_FILE)))
        self.assertTrue(self.prof.modify_professor_details('new@sjsu.edu', 'Rank', 'Senior'))
        self.assertFalse(self.prof.modify_professor_details('ghost@sjsu.edu', 'Rank', 'Senior'))
        with patch('builtins.print') as p:
            self.prof.show_course_details_by_professor('new@sjsu.edu')
            self.assertTrue(any('teaches CS101' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.assertTrue(self.prof.delete_professore('new@sjsu.edu'))
        self.assertFalse(any(r['User_id'] == 'new@sjsu.edu' for r in app.read_csv(app.LOGIN_FILE)))
        self.assertFalse(self.prof.delete_professore('ghost@sjsu.edu'))
        with patch('builtins.print') as p:
            self.prof.show_course_details_by_professor('ghost@sjsu.edu')
            self.assertTrue(any('not found' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.login_as('student')
        pr = app.Professor()
        self.assertFalse(pr.add_new_professor('x@y.com', 'X', 'Adj', 'DATA200'))
        self.assertFalse(pr.modify_professor_details('saini@sjsu.edu', 'Rank', 'X'))
        self.assertFalse(pr.delete_professore('saini@sjsu.edu'))


class TestLoginAdminReportStartup(BaseTestCase):
    def test_loginuser_find_login_logout_change_password_register(self):
        lu = app.LoginUser()
        self.assertIsNotNone(lu._find('ADMIN@MYCSU.EDU'))
        self.assertIsNone(lu._find('ghost'))
        self.assertEqual(lu.Login('admin@mycsu.edu', 'Admin123!'), 'admin')
        self.assertIsNone(lu.Login('admin@mycsu.edu', 'bad'))
        self.assertIsNone(lu.Login('', ''))
        lu.Logout()
        with patch('builtins.print') as p:
            lu.Logout()
            self.assertTrue(any('No user logged in' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        app.session.login('sam@mycsu.edu', 'student')
        self.assertTrue(lu.Change_password('sam@mycsu.edu', 'Student123!', 'NewPass1!'))
        self.assertFalse(lu.Change_password('sam@mycsu.edu', 'wrong', 'x'))
        self.assertFalse(lu.Change_password('admin@mycsu.edu', 'Admin123!', 'Nope'))
        self.assertEqual(lu.decrypt_password(lu.Encrypt_password('Hello1!')), 'Hello1!')
        lu.Logout()
        self.assertTrue(lu.register('newstudent@mycsu.edu', 'Abc123!', 'student'))
        self.assertFalse(lu.register('newstudent@mycsu.edu', 'Abc123!', 'student'))
        self.assertFalse(lu.register('bad@mycsu.edu', 'Abc123!', 'ta'))
        self.assertFalse(lu.register('newprof@sjsu.edu', 'Prof123!', 'professor'))
        app.session.login('admin@mycsu.edu', 'admin')
        self.assertTrue(lu.register('newprof@sjsu.edu', 'Prof123!', 'professor'))
        self.assertTrue(lu.register('otheradmin@mycsu.edu', 'Admin123!', 'admin'))

    def test_admin_list_add_remove_reset(self):
        self.login_as('admin')
        admin = app.Admin()
        with patch('builtins.print') as p:
            admin.list_users()
            self.assertTrue(p.called)
        self.assertTrue(admin.add_user('fresh@mycsu.edu', 'Fresh123!', 'student'))
        self.assertTrue(admin.reset_password('fresh@mycsu.edu', 'Reset123!'))
        self.assertFalse(admin.reset_password('ghost@mycsu.edu', 'Reset123!'))
        self.assertTrue(admin.remove_user('fresh@mycsu.edu'))
        self.assertFalse(admin.remove_user('ghost@mycsu.edu'))
        self.assertFalse(admin.remove_user('admin@mycsu.edu'))
        self.login_as('student')
        bad_admin = app.Admin()
        self.assertFalse(bad_admin.remove_user('sam@mycsu.edu'))
        self.assertFalse(bad_admin.reset_password('sam@mycsu.edu', 'X'))

    def test_report_generator_by_course_professor_student(self):
        student = app.Student()
        report = app.ReportGenerator(student)
        self.login_as('admin')
        with patch('builtins.print') as p:
            report.display_grade_report('course', 'DATA200')
            self.assertTrue(any('Grade Report: Course DATA200' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            report.display_grade_report('professor', 'saini@sjsu.edu')
            self.assertTrue(any('Grade Report: Professor Prof Saini' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            report.display_grade_report('student', 'sam@mycsu.edu')
            self.assertTrue(any('Grade Report: Student sam@mycsu.edu' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            report.display_grade_report('course', 'NOPE')
            self.assertTrue(any('No records found' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        with patch('builtins.print') as p:
            report.display_grade_report('professor', 'ghost@sjsu.edu')
            self.assertTrue(any('Professor not found' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.login_as('student')
        with patch('builtins.print') as p:
            report.display_grade_report('student', 'alex@mycsu.edu')
            self.assertTrue(any('Access denied' in ' '.join(map(str, c.args)) for c in p.call_args_list))
        self.login_as('professor')
        with patch('builtins.print') as p:
            report.display_grade_report('course', 'CS101')
            self.assertTrue(any('Access denied. Not your course' in ' '.join(map(str, c.args)) for c in p.call_args_list))

    def test_startup_sync_creates_missing_accounts(self):
        seed_csv(app.LOGIN_FILE, app.LoginUser.FIELDS, [
            {'User_id': 'admin@mycsu.edu', 'Password': app.encrypt_password('Admin123!'), 'Role': 'admin'}
        ])
        app.startup_sync()
        rows = app.read_csv(app.LOGIN_FILE)
        ids = {r['User_id'] for r in rows}
        self.assertIn('saini@sjsu.edu', ids)
        self.assertIn('sam@mycsu.edu', ids)
        before = len(rows)
        app.startup_sync()
        self.assertEqual(len(app.read_csv(app.LOGIN_FILE)), before)


class TestMenus(BaseTestCase):
    def test_student_menu_routes_all_options(self):
        self.login_as('admin')
        student = MagicMock()
        with patch('builtins.input', side_effect=[
            '1',
            '2', 'new@mycsu.edu', 'New', 'User', 'DATA200', '91',
            '3', 'new@mycsu.edu', 'DATA200',
            '4', 'sam@mycsu.edu', 'First_name', 'Samuel',
            '5', 'sam@mycsu.edu',
            '6', '1', 'y',
            '8', 'DATA200',
            '0'
        ]):
            app.student_menu(student)
        student.display_records.assert_called_once()
        student.add_new_student.assert_called_once_with('new@mycsu.edu', 'New', 'User', 'DATA200', 'A', '91')
        student.delete_new_student.assert_called_once_with('new@mycsu.edu', 'DATA200')
        student.update_student_record.assert_called_once_with('sam@mycsu.edu', 'First_name', 'Samuel')
        student.search_student.assert_called_once_with('sam@mycsu.edu')
        student.sort_records.assert_called_once_with('marks', True)
        student.course_stats.assert_called_once_with('DATA200')

    def test_student_menu_student_view(self):
        self.login_as('student')
        student = MagicMock()
        with patch('builtins.input', side_effect=['9', '0']):
            app.student_menu(student)
        student.check_my_grades.assert_called_once_with('sam@mycsu.edu')
        student.check_my_marks.assert_called_once_with('sam@mycsu.edu')

    def test_course_professor_report_user_menus(self):
        self.login_as('admin')
        course = MagicMock()
        with patch('builtins.input', side_effect=['1', '2', 'C1', 'Course 1', '3', 'Desc', '3', 'C1', '4', 'C1', 'Course_name', 'Updated', '0']):
            app.course_menu(course)
        course.display_courses.assert_called_once()
        course.add_new_course.assert_called_once_with('C1', 'Course 1', '3', 'Desc')
        course.delete_new_course.assert_called_once_with('C1')
        course.modify_course.assert_called_once_with('C1', 'Course_name', 'Updated')

        professor = MagicMock()
        with patch('builtins.input', side_effect=['1', '2', 'p@sjsu.edu', 'Prof', 'Adjunct', 'DATA200', '3', 'p@sjsu.edu', '4', 'p@sjsu.edu', 'Rank', 'Senior', '5', 'p@sjsu.edu', '0']):
            app.professor_menu(professor)
        professor.professors_details.assert_called_once()
        professor.add_new_professor.assert_called_once_with('p@sjsu.edu', 'Prof', 'Adjunct', 'DATA200')
        professor.delete_professore.assert_called_once_with('p@sjsu.edu')
        professor.modify_professor_details.assert_called_once_with('p@sjsu.edu', 'Rank', 'Senior')
        professor.show_course_details_by_professor.assert_called_once_with('p@sjsu.edu')

        report = MagicMock()
        with patch('builtins.input', side_effect=['1', 'DATA200', '2', 'saini@sjsu.edu', '3', 'sam@mycsu.edu', '0']):
            app.report_menu(report)
        self.assertEqual(report.display_grade_report.call_count, 3)

        admin = MagicMock()
        with patch('builtins.input', side_effect=['1', '2', 'u@x.com', 'Pwd1!', 'student', '3', 'u@x.com', '4', 'u@x.com', 'New1!', '0']):
            app.user_menu(admin)
        admin.list_users.assert_called_once()
        admin.add_user.assert_called_once_with('u@x.com', 'Pwd1!', 'student')
        admin.remove_user.assert_called_once_with('u@x.com')
        admin.reset_password.assert_called_once_with('u@x.com', 'New1!')

    def test_report_menu_student_role_uses_session_user(self):
        self.login_as('student')
        report = MagicMock()
        with patch('builtins.input', side_effect=['3', '0']):
            app.report_menu(report)
        report.display_grade_report.assert_called_once_with('student', 'sam@mycsu.edu')

    def test_main_menu_not_logged_in_paths_and_logged_in_paths(self):
        fake_student = MagicMock()
        fake_course = MagicMock()
        fake_prof = MagicMock()
        fake_lu = MagicMock()
        fake_admin = MagicMock()
        fake_report = MagicMock()

        with patch('checkmygrade.startup_sync') as sync, \
             patch('checkmygrade.Student', return_value=fake_student), \
             patch('checkmygrade.Course', return_value=fake_course), \
             patch('checkmygrade.Professor', return_value=fake_prof), \
             patch('checkmygrade.LoginUser', return_value=fake_lu), \
             patch('checkmygrade.Admin', return_value=fake_admin), \
             patch('checkmygrade.ReportGenerator', return_value=fake_report), \
             patch('builtins.input', side_effect=['2', 'self@mycsu.edu', 'Stud1!', '0']):
            app.session.user_id = None
            app.session.role = None
            app.main_menu()
        sync.assert_called_once()
        fake_lu.register.assert_called_once_with('self@mycsu.edu', 'Stud1!', 'student')

        with patch('checkmygrade.startup_sync'), \
             patch('checkmygrade.Student', return_value=fake_student), \
             patch('checkmygrade.Course', return_value=fake_course), \
             patch('checkmygrade.Professor', return_value=fake_prof), \
             patch('checkmygrade.LoginUser', return_value=fake_lu), \
             patch('checkmygrade.Admin', return_value=fake_admin), \
             patch('checkmygrade.ReportGenerator', return_value=fake_report), \
             patch('builtins.input', side_effect=['1', 'admin@mycsu.edu', 'Admin123!', '0']):
            app.session.user_id = None
            app.session.role = None
            app.main_menu()
        fake_lu.Login.assert_called_with('admin@mycsu.edu', 'Admin123!')

        with patch('checkmygrade.startup_sync'), \
             patch('checkmygrade.Student', return_value=fake_student), \
             patch('checkmygrade.Course', return_value=fake_course), \
             patch('checkmygrade.Professor', return_value=fake_prof), \
             patch('checkmygrade.LoginUser', return_value=fake_lu), \
             patch('checkmygrade.Admin', return_value=fake_admin), \
             patch('checkmygrade.ReportGenerator', return_value=fake_report), \
             patch('checkmygrade.student_menu') as sm, \
             patch('checkmygrade.course_menu') as cm, \
             patch('checkmygrade.professor_menu') as pm, \
             patch('checkmygrade.report_menu') as rm, \
             patch('checkmygrade.user_menu') as um, \
             patch('builtins.input', side_effect=['1', '2', '3', '4', '5', '6', 'old', 'new', '7', '0']):
            app.session.login('admin@mycsu.edu', 'admin')
            app.main_menu()
        sm.assert_called_once_with(fake_student)
        cm.assert_called_once_with(fake_course)
        pm.assert_called_once_with(fake_prof)
        rm.assert_called_once_with(fake_report)
        um.assert_called_once_with(fake_admin)
        fake_lu.Change_password.assert_called_once_with('admin@mycsu.edu', 'old', 'new')
        fake_lu.Logout.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
