from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from ultralytics import YOLO
from database import get_db_connection
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Load YOLOv8 model
model = YOLO("yolov8n.pt")

def init_db():
    """
    Initialize the database and create necessary tables.
    Handles errors during table creation.
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to initialize database: No connection.")
        return

    try:
        c = conn.cursor()
        
        # Create Drivers table
        c.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                id_number VARCHAR(255) PRIMARY KEY
            )
        ''')
        
        # Create License Plates table
        c.execute('''
            CREATE TABLE IF NOT EXISTS plates (
                plate VARCHAR(255) PRIMARY KEY,
                id_number VARCHAR(255),
                FOREIGN KEY (id_number) REFERENCES drivers (id_number) ON DELETE CASCADE
            )
        ''')
        
        # Create Admins table
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                username VARCHAR(255) PRIMARY KEY,
                password VARCHAR(255) NOT NULL
            )
        ''')
        
        # Create Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id_number VARCHAR(255) PRIMARY KEY,
                password VARCHAR(255) NOT NULL,
                FOREIGN KEY (id_number) REFERENCES drivers (id_number) ON DELETE CASCADE
            )
        ''')
        
        # Insert default admin account
        c.execute('''
            INSERT IGNORE INTO admins (username, password)
            VALUES ('admin', '12341234')
        ''')
        
        conn.commit()
        print("Database initialized successfully.")
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

@app.route('/home')
def home():
    # Render the home page without logging out the user
    return render_template('home.html')

# About Page Route
@app.route('/about')
def about():
    return render_template('about.html')

# Login Page Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return jsonify({"message": "Username and password are required!"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"message": "Failed to connect to the database!"}), 500

        c = conn.cursor()

        try:
            # Check if the user is an admin
            c.execute('SELECT * FROM admins WHERE username = %s AND password = %s', (username, password))
            admin = c.fetchone()

            if admin:
                session['logged_in'] = True
                session['user_id'] = username  # Store the admin's username
                session['is_admin'] = True
                return jsonify({"message": "Admin login successful!", "redirect": url_for('dashboard')}), 200

            # Check if the user is a regular user
            c.execute('SELECT * FROM users WHERE id_number = %s AND password = %s', (username, password))
            user = c.fetchone()

            if user:
                session['logged_in'] = True
                session['user_id'] = username  # Store the user's Unique ID Number
                session['is_admin'] = False
                return jsonify({"message": "User login successful!", "redirect": url_for('dashboard')}), 200

            return jsonify({"message": "Invalid username or password!"}), 401
        except mysql.connector.Error as e:
            return jsonify({"message": f"Database error: {e}"}), 500
        finally:
            if conn:
                conn.close()
    else:
        return render_template('login.html')

# Signup Page Route (Admin Only)
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Check if the user is an admin
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get form data
        id_number = request.form.get('id_number')
        password = request.form.get('password')

        # Validate inputs
        if not id_number or not password:
            return jsonify({"message": "ID Number and password are required!"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"message": "Failed to connect to the database!"}), 500

        c = conn.cursor()

        try:
            # Check if the user already exists
            c.execute('SELECT * FROM users WHERE id_number = %s', (id_number,))
            if c.fetchone() is not None:
                return jsonify({"message": "User already exists!"}), 400

            # Insert the new driver into the drivers table
            c.execute('INSERT INTO drivers (id_number) VALUES (%s)', (id_number,))

            # Insert the new user into the users table
            c.execute('INSERT INTO users (id_number, password) VALUES (%s, %s)', (id_number, password))
            conn.commit()

            # Signup successful
            return jsonify({"message": "User registered successfully!"}), 200
        except mysql.connector.Error as e:
            conn.rollback()  # Rollback in case of error
            return jsonify({"message": f"Database error: {e}"}), 500
        finally:
            if conn:
                conn.close()
    else:
        # Render the signup page for GET requests
        return render_template('signup.html')

# Logout Route
@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    return redirect(url_for('home'))

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    # Check if the user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

# Check Plate Route
@app.route('/check_plate', methods=['GET'])
def check_plate():
    plate = request.args.get('plate')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM plates WHERE plate = %s', (plate,))
    result = c.fetchone()
    conn.close()
    return jsonify({"registered": result is not None})

# Register Plate Route
@app.route('/register_plate', methods=['POST'])
def register_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('id_number')
    plate = request.form.get('plate')

    # Validate if the user is trying to use their own ID
    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only register plates for your own ID."}), 403

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Check if the driver exists
        c.execute('SELECT * FROM drivers WHERE id_number = %s', (id_number,))
        driver = c.fetchone()
        
        if driver is None:
            # If the driver does not exist, create a new driver entry
            c.execute('INSERT INTO drivers (id_number) VALUES (%s)', (id_number,))
        
        # Check for existing license plates
        c.execute('SELECT * FROM plates WHERE plate = %s', (plate,))
        if c.fetchone() is not None:
            return jsonify({"message": "License Plate already registered!"}), 400

        # Register the license plate
        c.execute('INSERT INTO plates (plate, id_number) VALUES (%s, %s)', (plate, id_number))
        conn.commit()
        return jsonify({"message": "License Plate Registered!"}), 200
    except mysql.connector.Error as e:
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

# Update Plate Route
@app.route('/update_plate', methods=['POST'])
def update_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('update_id')
    old_plate = request.form.get('old_plate')
    new_plate = request.form.get('new_plate')

    # Validate if the user is trying to use their own ID
    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only update plates for your own ID."}), 403

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Check if the existing plate belongs to the given ID
        c.execute('SELECT * FROM plates WHERE id_number = %s AND plate = %s', (id_number, old_plate))
        plate = c.fetchone()
        
        if plate is None:
            return jsonify({"message": "No license plate found for the given ID!"}), 404

        # Update the license plate
        c.execute('UPDATE plates SET plate = %s WHERE id_number = %s AND plate = %s', (new_plate, id_number, old_plate))
        conn.commit()
        return jsonify({"message": "License Plate Updated!"}), 200
    except mysql.connector.Error as e:
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

# Delete Plate Route
@app.route('/delete_plate', methods=['POST'])
def delete_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('delete_id')
    plate = request.form.get('delete_plate')

    # Validate if the user is trying to use their own ID
    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only delete plates for your own ID."}), 403

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Check if the existing plate belongs to the given ID
        c.execute('SELECT * FROM plates WHERE id_number = %s AND plate = %s', (id_number, plate))
        existing_plate = c.fetchone()
        
        if existing_plate is None:
            return jsonify({"message": "No license plate found for the given ID!"}), 404

        # Delete the license plate
        c.execute('DELETE FROM plates WHERE id_number = %s AND plate = %s', (id_number, plate))
        conn.commit()
        return jsonify({"message": "License Plate Deleted!"}), 200
    except mysql.connector.Error as e:
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

# Delete Driver Route
@app.route('/delete_driver', methods=['POST'])
def delete_driver():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('delete_driver_id')

    # Validate if the user is an admin
    if not session.get('is_admin'):
        return jsonify({"message": "Only admins can delete drivers."}), 403

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Check if the driver exists
        c.execute('SELECT * FROM drivers WHERE id_number = %s', (id_number,))
        driver = c.fetchone()

        if driver is None:
            return jsonify({"message": "No driver found with the given ID!"}), 404

        # Delete the driver, which will also delete associated license plates
        c.execute('DELETE FROM drivers WHERE id_number = %s', (id_number,))
        conn.commit()
        return jsonify({"message": "Driver and associated license plates deleted!"}), 200
    except mysql.connector.Error as e:
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

# Detect Route
@app.route('/detect', methods=['POST'])
def detect():
    # Get the image file from the request
    file = request.files['image']
    image_path = "temp.jpg"
    file.save(image_path)

    # Perform object detection using YOLOv8
    results = model.predict(source=image_path)

    # Check for cars, animals, and people
    gate_open = False
    for result in results:
        for box in result.boxes:
            class_id = int(box.cls)
            if class_id == 2:  # Car
                gate_open = True
            elif class_id in [0, 1]:  # Person or animal
                gate_open = False

    # Return the gate status
    return jsonify({"gate_open": gate_open})

# Index Route
@app.route('/')
def index():
    return render_template('index.html')

# Run the Flask app
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)