from app import app, db, User, AuthCredentials
from werkzeug.security import generate_password_hash

"""
This script sets up hashed passwords for users in the database.

- It takes plain-text password and converts into hashed string
- Hashing is one-way function; users cannot decipher/decrypt the password
- When an external user tries to access our database, they cannot see what the actual password is.

"""

# Define new users and their plain-text passwords
new_users_data = [
    {"id": 1001, "username": "han1001", "name": "Hannah Instructor", "role": "teacher", "password": "HannahPass123"},
    {"id": 1002, "username": "ian1002", "name": "Ian Instructor", "role": "teacher", "password": "IanPass123"},
    {"id": 1003, "username": "jac1003", "name": "Jack Student", "role": "student", "password": "JackPass123"}
]
with app.app_context():
    for udata in new_users_data:
        # Check if user exists
        user = User.query.filter_by(username=udata["username"]).first()
        if not user:
            # Create user
            user = User(id=udata["id"], username=udata["username"], name=udata["name"], role=udata["role"])
            db.session.add(user)
            db.session.commit()
            print(f"👤 Created user '{udata['username']}'")

        # Check if user already has credentials
        if not user.auth:
            hashed_pw = generate_password_hash(udata["password"])
            creds = AuthCredentials(user_id=user.id, password_hash=hashed_pw)
            db.session.add(creds)
            db.session.commit()
            print(f"🔐 Password set for '{udata['username']}'")
        else:
            print(f"ℹ️ '{udata['username']}' already has credentials")

print(" Password setup completed successfully for new users!")
