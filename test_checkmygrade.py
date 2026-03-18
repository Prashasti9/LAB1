"""
Unit Tests - CheckMyGrade Application
DATA 200 - Lab 1
Professor: Paramdeep Saini, SJSU

We use Python's built-in unittest framework to test every major feature of
the application. Each test class focuses on one entity (Student, Course, etc.)
and each test method covers one specific behaviour we want to verify.

All tests use separate temp files (test_*.csv) so they never touch the real
data files. The setUp and tearDown methods handle creating and cleaning up
those files around each individual test.
"""

import unittest
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
        logout()
        self.lu = app.LoginUser()

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
