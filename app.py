from flask import Flask, render_template, request, redirect, url_for, session
from config import Config
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper


def role_required(required_role):

    def decorator(route_function):

        @wraps(route_function)
        def wrapper(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("login"))

            if session.get("user_role") != required_role:
                return redirect(url_for("login"))

            return route_function(*args, **kwargs)

        return wrapper

    return decorator


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if not name or not email or not password or not role:

            return render_template(
                "register.html",
                error="Please fill all fields."
            )

        if role not in ["patient", "doctor"]:

            return render_template(
                "register.html",
                error="Invalid role selected."
            )

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check existing email
        cursor.execute(
            "SELECT user_id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            connection.close()

            return render_template(
                "register.html",
                error="An account with this email already exists."
            )

        # Hash password
        password_hash = generate_password_hash(password)

        # Insert user
        cursor.execute(
            """
            INSERT INTO users
            (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            """,
            (
                name,
                email,
                password_hash,
                role
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session["user_id"] = user["user_id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_role"] = user["role"]

            if user["role"] == "doctor":

                return redirect(
                    url_for("doctor_dashboard")
                )

            return redirect(
                url_for("patient_dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# =========================================================
# PATIENT DASHBOARD
# =========================================================

@app.route("/patient/dashboard")
@login_required
@role_required("patient")
def patient_dashboard():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Appointments
    cursor.execute(
        """
        SELECT
            a.appointment_id,
            a.appointment_date,
            a.appointment_time,
            a.reason,
            a.status,
            d.name AS doctor_name
        FROM appointments a
        JOIN users d
            ON a.doctor_id = d.user_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC
        """,
        (session["user_id"],)
    )

    appointments = cursor.fetchall()

    # Medical records
    cursor.execute(
        """
        SELECT
            m.record_id,
            m.diagnosis,
            m.prescription,
            m.notes,
            m.record_date,
            d.name AS doctor_name
        FROM medical_records m
        JOIN users d
            ON m.doctor_id = d.user_id
        WHERE m.patient_id = %s
        ORDER BY m.record_date DESC
        """,
        (session["user_id"],)
    )

    records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "patient_dashboard.html",
        name=session["user_name"],
        appointments=appointments,
        records=records
    )


# =========================================================
# DOCTOR DASHBOARD
# =========================================================

@app.route("/doctor/dashboard")
@login_required
@role_required("doctor")
def doctor_dashboard():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            a.appointment_id,
            a.appointment_date,
            a.appointment_time,
            a.reason,
            a.status,
            p.name AS patient_name
        FROM appointments a
        JOIN users p
            ON a.patient_id = p.user_id
        WHERE a.doctor_id = %s
        ORDER BY a.appointment_date DESC
        """,
        (session["user_id"],)
    )

    appointments = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "doctor_dashboard.html",
        name=session["user_name"],
        appointments=appointments
    )


# =========================================================
# BOOK APPOINTMENT
# =========================================================

@app.route("/book-appointment", methods=["GET", "POST"])
@login_required
@role_required("patient")
def book_appointment():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get doctors
    cursor.execute(
        """
        SELECT user_id, name, email
        FROM users
        WHERE role = 'doctor'
        ORDER BY name
        """
    )

    doctors = cursor.fetchall()

    if request.method == "POST":

        doctor_id = request.form.get("doctor_id")
        appointment_date = request.form.get(
            "appointment_date"
        )
        appointment_time = request.form.get(
            "appointment_time"
        )
        reason = request.form.get("reason")

        cursor.execute(
            """
            INSERT INTO appointments
            (
                patient_id,
                doctor_id,
                appointment_date,
                appointment_time,
                reason,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                doctor_id,
                appointment_date,
                appointment_time,
                reason,
                "Scheduled"
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(
            url_for("patient_dashboard")
        )

    cursor.close()
    connection.close()

    return render_template(
        "book_appointment.html",
        doctors=doctors
    )


# =========================================================
# ADD DIAGNOSIS
# =========================================================

@app.route(
    "/add-diagnosis/<int:appointment_id>",
    methods=["GET", "POST"]
)
@login_required
@role_required("doctor")
def add_diagnosis(appointment_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Find appointment
    cursor.execute(
        """
        SELECT
            a.*,
            p.name AS patient_name
        FROM appointments a
        JOIN users p
            ON a.patient_id = p.user_id
        WHERE a.appointment_id = %s
        AND a.doctor_id = %s
        """,
        (
            appointment_id,
            session["user_id"]
        )
    )

    appointment = cursor.fetchone()

    if not appointment:

        cursor.close()
        connection.close()

        return redirect(
            url_for("doctor_dashboard")
        )

    if request.method == "POST":

        diagnosis = request.form.get("diagnosis")
        prescription = request.form.get(
            "prescription"
        )
        notes = request.form.get("notes")

        cursor.execute(
            """
            INSERT INTO medical_records
            (
                appointment_id,
                patient_id,
                doctor_id,
                diagnosis,
                prescription,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                appointment_id,
                appointment["patient_id"],
                session["user_id"],
                diagnosis,
                prescription,
                notes
            )
        )

        cursor.execute(
            """
            UPDATE appointments
            SET status = 'Completed'
            WHERE appointment_id = %s
            """,
            (appointment_id,)
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(
            url_for("doctor_dashboard")
        )

    cursor.close()
    connection.close()

    return render_template(
        "add_diagnosis.html",
        appointment=appointment
    )


# =========================================================
# MEDICAL HISTORY
# =========================================================

@app.route("/medical-history")
@login_required
@role_required("patient")
def medical_history():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            m.*,
            d.name AS doctor_name
        FROM medical_records m
        JOIN users d
            ON m.doctor_id = d.user_id
        WHERE m.patient_id = %s
        ORDER BY m.record_date DESC
        """,
        (session["user_id"],)
    )

    records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "medical_history.html",
        records=records,
        name=session["user_name"]
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)