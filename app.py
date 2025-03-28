from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from ultralytics import YOLO
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure secret key

# Load YOLOv8 model
model = YOLO("yolov8n.pt")

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Collection references
drivers_ref = db.collection('drivers')
plates_ref = db.collection('plates')
admins_ref = db.collection('admins')
users_ref = db.collection('users')

def init_firebase():
    """Initialize Firebase collections with default data"""
    try:
        # Add default admin if not exists
        admins_ref.document('admin').set({
            'username': 'admin',
            'password': '12341234'
        })
        print("Firebase initialized successfully")
    except FirebaseError as e:
        print(f"Firebase initialization error: {e}")

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return jsonify({"message": "Username and password are required!"}), 400

        # Check admin first
        admin_doc = admins_ref.document(username).get()
        if admin_doc.exists and admin_doc.to_dict().get('password') == password:
            session.update({
                'logged_in': True,
                'user_id': username,
                'is_admin': True
            })
            return jsonify({"message": "Admin login successful!", "redirect": url_for('dashboard')})
        
        # Check regular user
        user_doc = users_ref.document(username).get()
        if user_doc.exists and user_doc.to_dict().get('password') == password:
            session.update({
                'logged_in': True,
                'user_id': username,
                'is_admin': False
            })
            return jsonify({"message": "User login successful!", "redirect": url_for('dashboard')})
        
        return jsonify({"message": "Invalid username or password!"}), 401
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        id_number = request.form.get('id_number')
        password = request.form.get('password')

        if not id_number or not password:
            return jsonify({"message": "ID Number and password are required!"}), 400

        try:
            # Check if user exists
            if users_ref.document(id_number).get().exists:
                return jsonify({"message": "User already exists!"}), 400

            # Add driver and user
            drivers_ref.document(id_number).set({'id_number': id_number})
            users_ref.document(id_number).set({
                'id_number': id_number,
                'password': password
            })
            return jsonify({"message": "User registered successfully!"}), 200
        except Exception as e:
            return jsonify({"message": f"Error: {str(e)}"}), 500
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/check_plate', methods=['GET'])
def check_plate():
    plate = request.args.get('plate')
    if not plate:
        return jsonify({"error": "Plate number required"}), 400
    plate_doc = plates_ref.document(plate).get()
    return jsonify({"registered": plate_doc.exists})

@app.route('/register_plate', methods=['POST'])
def register_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('id_number')
    plate = request.form.get('plate')

    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only register plates for your own ID."}), 403

    try:
        # Check if plate exists
        if plates_ref.document(plate).get().exists:
            return jsonify({"message": "License Plate already registered!"}), 400

        # Add driver if not exists
        if not drivers_ref.document(id_number).get().exists:
            drivers_ref.document(id_number).set({'id_number': id_number})

        # Register plate
        plates_ref.document(plate).set({
            'plate': plate,
            'id_number': id_number
        })
        return jsonify({"message": "License Plate Registered!"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/update_plate', methods=['POST'])
def update_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('update_id')
    old_plate = request.form.get('old_plate')
    new_plate = request.form.get('new_plate')

    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only update plates for your own ID."}), 403

    try:
        # Check if plate belongs to user
        plate_doc = plates_ref.document(old_plate).get()
        if not plate_doc.exists or plate_doc.to_dict().get('id_number') != id_number:
            return jsonify({"message": "No license plate found for the given ID!"}), 404

        # Update plate
        plates_ref.document(old_plate).delete()
        plates_ref.document(new_plate).set({
            'plate': new_plate,
            'id_number': id_number
        })
        return jsonify({"message": "License Plate Updated!"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/delete_plate', methods=['POST'])
def delete_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('delete_id')
    plate = request.form.get('delete_plate')

    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only delete plates for your own ID."}), 403

    try:
        # Verify plate belongs to user
        plate_doc = plates_ref.document(plate).get()
        if not plate_doc.exists or plate_doc.to_dict().get('id_number') != id_number:
            return jsonify({"message": "No license plate found for the given ID!"}), 404

        plates_ref.document(plate).delete()
        return jsonify({"message": "License Plate Deleted!"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/delete_driver', methods=['POST'])
def delete_driver():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    if not session.get('is_admin'):
        return jsonify({"message": "Only admins can delete drivers."}), 403

    id_number = request.form.get('delete_driver_id')

    try:
        # Delete driver and associated plates
        batch = db.batch()
        
        # Delete all plates for this driver
        plates = plates_ref.where('id_number', '==', id_number).stream()
        for plate in plates:
            batch.delete(plate.reference)
        
        # Delete user and driver
        batch.delete(users_ref.document(id_number))
        batch.delete(drivers_ref.document(id_number))
        
        batch.commit()
        return jsonify({"message": "Driver and associated license plates deleted!"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/detect', methods=['POST'])
def detect():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
        
    file = request.files['image']
    file.save("temp.jpg")
    
    results = model.predict(source="temp.jpg")
    gate_open = any(box.cls == 2 for result in results for box in result.boxes)
    
    return jsonify({"gate_open": gate_open})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_firebase()
    app.run(host='0.0.0.0', port=5000, debug=True)