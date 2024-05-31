from db import db
import os
from dotenv import load_dotenv
from helpers.helper import create_random_string
from datetime import datetime, timezone
import bcrypt

load_dotenv()

User = db[os.getenv("USER_COLLECTION_NAME")]


def create_admin_user():
    user_count = User.count_documents({"role": "ADMIN"})

    if user_count != 0:
        return

    email = "admin@alphabi.co"
    password = create_random_string(8)
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    name = "Admin"
    role = "ADMIN"

    User.update_one(
        {
            "email": email
        },
        {
            "$set": {
                "name": name,
                "email": email,
                "password": password_hash,
                "role": role,
                "createdAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
                "is_gmail_connected": False
            }
        }
        , upsert=True)

    print("========================Admin User Created========================")
    print("Email: ", email, "\nPassword: ", password)
    print("==================================================================")


def initialize():
    create_admin_user()
