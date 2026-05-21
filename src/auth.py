import hashlib
import json
import os
from hmac import compare_digest

from src.config_loader import load_config


PAGE_ACCESS_OPTIONS = [
    {"key": "dashboard", "label": "Dashboard"},
    {"key": "add_customer", "label": "Add Customer"},
    {"key": "import_customers", "label": "Import Customers"},
    {"key": "all_balances", "label": "All Balances"},
    {"key": "add_payment", "label": "Add Payment"},
    {"key": "last_7_days_report", "label": "Last 7 Days Report"},
    {"key": "user_management", "label": "User Management"},
]


def load_users():
    config = load_config()

    try:
        with open(config["users_file"], "r") as file:
            users = json.load(file)

        if not isinstance(users, list):
            return []

        return users

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_users(users):
    config = load_config()

    with open(config["users_file"], "w") as file:
        json.dump(users, file, indent=4)


def hash_password(password):
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000,
    )

    return {
        "salt": salt.hex(),
        "password_hash": password_hash.hex(),
    }


def verify_password(password, stored_salt, stored_hash):
    salt = bytes.fromhex(stored_salt)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000,
    ).hex()

    return compare_digest(password_hash, stored_hash)


def find_user(username):
    users = load_users()

    for user in users:
        if user["username"].lower() == username.lower():
            return user

    return None


def users_exist():
    return len(load_users()) > 0


def create_user(username, password, allowed_pages, is_admin=False):
    users = load_users()

    if find_user(username):
        return False, "User already exists"

    password_data = hash_password(password)

    user = {
        "username": username,
        "salt": password_data["salt"],
        "password_hash": password_data["password_hash"],
        "allowed_pages": allowed_pages,
        "is_admin": is_admin,
        "is_active": True,
    }

    users.append(user)
    save_users(users)

    return True, "User created successfully"


def authenticate_user(username, password):
    user = find_user(username)

    if not user:
        return None

    if not user.get("is_active", True):
        return None

    if verify_password(password, user["salt"], user["password_hash"]):
        return user

    return None


def user_has_access(user, page_key):
    if not user:
        return False

    if user.get("is_admin"):
        return True

    return page_key in user.get("allowed_pages", [])