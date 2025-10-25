# -------------------------------------------------
# Import necessary libraries for this project
# -------------------------------------------------
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, case

# -------------------------------------------------
# Flask app configuration
# -------------------------------------------------
app = Flask(__name__)

# Secret key used for session management (keep confidential in production)
app.secret_key = "c7ae658a3c96d53ee963160fe2c0fbb6f9813300cdc2831c6735c520330e8f2d"

# Database connection setup (PostgreSQL: our backend engine)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql+psycopg2://postgres:Sansen27%40@127.0.0.1:5432/attendance_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy ORM
db = SQLAlchemy(app)

# =================================================
# DATABASE MODELS
# =================================================

class User(db.Model):
    """
    User model: represents both students and teachers.
    Each user has a name, username, and role.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'student' or 'teacher'
    auth = db.relationship('AuthCredentials', backref='user', uselist=False, cascade="all, delete")


class AuthCredentials(db.Model):
    """
    Stores hashed passwords associated with each user (1-to-1 relationship).
    """
    __tablename__ = 'auth_credentials'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Term(db.Model):
    """
    Represents an academic term (example: Fall 2025).
    """
    __tablename__ = 'terms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)


class Course(db.Model):
    """
    Represents a course (example: CS102 - Data Structures).
    """
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100), nullable=False)


class Section(db.Model):
    """
    Represents a course section.
    Includes instructor, meeting schedule, and location.
    """
    __tablename__ = 'sections'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    term_id = db.Column(db.Integer, db.ForeignKey('terms.id'))
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    meeting_days = db.Column(db.String(20))
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    room = db.Column(db.String(50))

    # Relationships
    course = db.relationship("Course")
    term = db.relationship("Term")
    instructor = db.relationship("User")


class Enrollment(db.Model):
    """
    Maps students to the sections they are enrolled in.
    """
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    section = db.relationship("Section")
    student = db.relationship("User")


class ClassSession(db.Model):
    """
    Represents a specific class meeting (session) for a section.
    """
    __tablename__ = 'class_sessions'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    session_date = db.Column(db.Date)

    section = db.relationship("Section")


class AttendanceRecord(db.Model):
    """
    Stores each student's attendance status ('present' or 'absent')
    for a given class session.
    """
    __tablename__ = 'attendance_records'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20))  # e.g., 'present', 'absent'

    session = db.relationship("ClassSession")
    student = db.relationship("User")

# =================================================
# ROUTES AND VIEWS
# =================================================

@app.route("/")
def home():
    """Redirects to login page as the default route."""
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles login for both students and teachers.
    Verifies credentials and redirects to respective dashboards.
    """
    if request.method == "POST":
        username = request.form["identifier"].strip()
        password = request.form["password"].strip()
        role = request.form["role"].strip()

        # Validate user existence and credentials
        user = User.query.filter_by(username=username, role=role).first()
        if not user or not user.auth:
            return render_template("login.html", error="Invalid username, password, or role")

        # Verify password hash
        if check_password_hash(user.auth.password_hash, password):
            session["user_id"] = user.id
            session["role"] = user.role

            # Redirect based on role
            if user.role == "student":
                return redirect(url_for("student"))
            elif user.role == "teacher":
                return redirect(url_for("teacher"))
        else:
            return render_template("login.html", error="Invalid username, password, or role")

    return render_template("login.html")


# =================================================
# STUDENT DASHBOARD
# =================================================
@app.route("/student")
def student():
    """
    Displays student's attendance records and summary statistics.
    Uses aggregate SQL functions (SUM, AVG, COUNT).
    """
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    # Fetch detailed attendance records
    enrollments = db.session.query(
        Enrollment, Section, Course, Term, ClassSession, AttendanceRecord
    ).join(Section, Enrollment.section_id == Section.id)\
     .join(Course, Section.course_id == Course.id)\
     .join(Term, Section.term_id == Term.id)\
     .join(ClassSession, ClassSession.section_id == Section.id)\
     .join(AttendanceRecord, (AttendanceRecord.session_id == ClassSession.id) &
                              (AttendanceRecord.student_id == user.id))\
     .filter(Enrollment.student_id == user.id).all()

    # Attendance aggregates per course
    attendance_summary = db.session.query(
        Section.id,
        Course.code,
        Course.title,
        func.count(ClassSession.id).label('total_sessions'),
        func.sum(case((AttendanceRecord.status == 'present', 1), else_=0)).label('attended'),
        (func.avg(case((AttendanceRecord.status == 'present', 1), else_=0)) * 100).label('attendance_percent')
    ).select_from(Enrollment)\
     .join(Section, Enrollment.section_id == Section.id)\
     .join(Course, Section.course_id == Course.id)\
     .join(ClassSession, ClassSession.section_id == Section.id)\
     .join(AttendanceRecord, (AttendanceRecord.session_id == ClassSession.id) &
                              (AttendanceRecord.student_id == Enrollment.student_id))\
     .filter(Enrollment.student_id == user.id)\
     .group_by(Section.id, Course.code, Course.title).all()

    # Collect unique course list for dropdown filters
    course_list = []
    for e, s, c, t, sess, a in enrollments:
        if (c.code, c.title) not in course_list:
            course_list.append((c.code, c.title))

    return render_template(
        "student.html",
        username=user.username,
        full_name=user.name,
        enrollments=enrollments,
        course_list=course_list,
        summary=attendance_summary
    )


# =================================================
# TEACHER DASHBOARD
# =================================================
@app.route("/teacher")
def teacher():
    """
    Displays teacher’s sections, enrolled students,
    and attendance performance summaries.
    """
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    # Fetch all attendance data for sections taught by this instructor
    sections = db.session.query(
        Section, Course, Term, Enrollment, User, ClassSession, AttendanceRecord
    ).join(Course, Section.course_id == Course.id)\
     .join(Term, Section.term_id == Term.id)\
     .join(Enrollment, Enrollment.section_id == Section.id)\
     .join(User, Enrollment.student_id == User.id)\
     .join(ClassSession, ClassSession.section_id == Section.id)\
     .join(AttendanceRecord, (AttendanceRecord.session_id == ClassSession.id) &
                              (AttendanceRecord.student_id == User.id))\
     .filter(Section.instructor_id == user.id).all()

    # Summary: attendance statistics per student per course
    summary = db.session.query(
        Course.code,
        Course.title,
        User.name.label("student_name"),
        func.count(AttendanceRecord.id).label("total_sessions"),
        func.sum(case((AttendanceRecord.status == 'absent', 1), else_=0)).label("absences"),
        (func.sum(case((AttendanceRecord.status == 'present', 1), else_=0)) * 100.0 /
         func.count(AttendanceRecord.id)).label("attendance_percent")
    ).join(Section, Section.course_id == Course.id)\
     .join(Enrollment, Enrollment.section_id == Section.id)\
     .join(User, User.id == Enrollment.student_id)\
     .join(ClassSession, ClassSession.section_id == Section.id)\
     .join(AttendanceRecord, (AttendanceRecord.session_id == ClassSession.id) &
                              (AttendanceRecord.student_id == User.id))\
     .filter(Section.instructor_id == user.id)\
     .group_by(Course.id, User.id)\
     .order_by(Course.code, User.name)\
     .all()

    # Unique courses for dropdown filters
    course_list = []
    for s, c, t, e, u, sess, a in sections:
        if (c.code, c.title) not in course_list:
            course_list.append((c.code, c.title))

    return render_template(
        "teacher.html",
        username=user.username,
        full_name=user.name,
        sections=sections,
        course_list=course_list,
        summary=summary
    )


# =================================================
# LOGOUT
# =================================================
@app.route("/logout")
def logout():
    """Clears session data and redirects to login."""
    session.clear()
    return redirect(url_for("login"))


# -------------------------------------------------
# Run Flask app on local port
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5097)
