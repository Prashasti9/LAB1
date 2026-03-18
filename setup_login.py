"""
Run this ONCE to create a fresh login.csv with correct encrypted passwords.
Place this file in the same folder as checkmygrade.py and run:
    python setup_login.py
"""

import csv
import base64
import os

def encrypt_password(plain):
    return base64.b64encode(plain.encode()).decode()

# Always recreate login.csv from scratch
accounts = [
    {"User_id": "admin@mycsu.edu",  "Password": encrypt_password("Admin123!"),    "Role": "admin"},
    {"User_id": "saini@sjsu.edu",   "Password": encrypt_password("Prof123!"),      "Role": "professor"},
    {"User_id": "sam@mycsu.edu",    "Password": encrypt_password("Student123!"),   "Role": "student"},
]

with open("login.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["User_id", "Password", "Role"])
    writer.writeheader()
    writer.writerows(accounts)

print("login.csv created successfully!")
print()
print("Accounts ready:")
print("  admin@mycsu.edu   /  Admin123!     (admin)")
print("  saini@sjsu.edu    /  Prof123!      (professor)")
print("  sam@mycsu.edu     /  Student123!   (student)")
print()
print("Now run:  python checkmygrade.py")
