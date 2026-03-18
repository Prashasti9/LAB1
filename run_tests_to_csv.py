"""
run_tests_to_csv.py

Runs all unit tests from test_checkmygrade.py and saves the results
to test_results.csv so you can open it in Excel or submit it.
"""

import unittest
import csv
import time
import io
import sys

# Import the test module
import test_checkmygrade


def run_tests_to_csv(output_file="test_results.csv"):

    # Load all tests from the test module
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromModule(test_checkmygrade)

    # Flatten the suite into individual test cases
    def flatten(s):
        tests = []
        for t in s:
            if isinstance(t, unittest.TestSuite):
                tests.extend(flatten(t))
            else:
                tests.append(t)
        return tests

    all_tests = flatten(suite)

    results_rows = []
    total_start  = time.perf_counter()

    for test in all_tests:
        # Capture any printed output during the test
        captured = io.StringIO()
        sys.stdout = captured

        start  = time.perf_counter()
        result = unittest.TestResult()
        test.run(result)
        elapsed = (time.perf_counter() - start) * 1000

        sys.stdout = sys.__stdout__
        output = captured.getvalue().strip()

        # Work out the status and any error message
        if result.wasSuccessful():
            status  = "PASS"
            message = output if output else ""
        elif result.failures:
            status  = "FAIL"
            message = result.failures[0][1].strip().splitlines()[-1]
        elif result.errors:
            status  = "ERROR"
            message = result.errors[0][1].strip().splitlines()[-1]
        else:
            status  = "SKIP"
            message = ""

        # Split test id into class and method name
        test_id    = test.id()
        parts      = test_id.split(".")
        class_name = parts[-2] if len(parts) >= 2 else ""
        test_name  = parts[-1] if len(parts) >= 1 else test_id

        results_rows.append({
            "Test Class":   class_name,
            "Test Name":    test_name,
            "Status":       status,
            "Time (ms)":    f"{elapsed:.4f}",
            "Output / Notes": message
        })

        # Also print to terminal so you can see progress
        symbol = "✓" if status == "PASS" else "✗"
        print(f"  {symbol} {class_name}.{test_name} — {status} ({elapsed:.4f} ms)")

    total_elapsed = (time.perf_counter() - total_start) * 1000
    passed  = sum(1 for r in results_rows if r["Status"] == "PASS")
    failed  = sum(1 for r in results_rows if r["Status"] in ("FAIL","ERROR"))
    total   = len(results_rows)

    # Write to CSV
    fieldnames = ["Test Class", "Test Name", "Status", "Time (ms)", "Output / Notes"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_rows)

        # Add a blank row then a summary row at the bottom
        writer.writerow({k: "" for k in fieldnames})
        writer.writerow({
            "Test Class":     "SUMMARY",
            "Test Name":      f"Total: {total}",
            "Status":         f"Passed: {passed}  Failed: {failed}",
            "Time (ms)":      f"{total_elapsed:.4f}",
            "Output / Notes": "All tests completed"
        })

    print(f"\n  Results saved to: {output_file}")
    print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Time: {total_elapsed:.2f} ms")


if __name__ == "__main__":
    run_tests_to_csv()
