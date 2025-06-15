from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from ultralytics import YOLO
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
import os
import cv2
import serial
import threading
from datetime import datetime
import time
import easyocr
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ========== INITIALIZATION ==========
reader = easyocr.Reader(['en'])
plate_model = YOLO(r"C:\Users\siyam\Documents\thesis-1\content\runs\license_plate_model2\weights\best.pt")
object_model = YOLO("yolov8n.pt")

# ========== ARDUINO SETUP ==========
arduino = None
arduino_lock = threading.Lock()

def connect_arduino():
    global arduino
    try:
        with arduino_lock:
            if arduino:
                arduino.close()
            arduino = serial.Serial('COM4', 9600, timeout=1)
            time.sleep(2)
            print("Arduino connected")
            return True
    except Exception as e:
        print(f"Arduino connection failed: {e}")
        arduino = None
        return False

connect_arduino()

# ========== FIREBASE SETUP ==========
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
drivers_ref = db.collection('drivers')
plates_ref = db.collection('plates')
admins_ref = db.collection('admins')
users_ref = db.collection('users')

# ========== CORE FUNCTIONS ==========
def control_gate(state):
    """Thread-safe gate control with retries"""
    for attempt in range(3):
        try:
            with arduino_lock:
                if not arduino:
                    if not connect_arduino():
                        continue
                
                arduino.reset_input_buffer()
                command = "OPEN\n" if state else "CLOSE\n"
                arduino.write(command.encode())
                time.sleep(0.2)  # Critical delay
                
                # Wait for acknowledgment
                start_time = time.time()
                while time.time() - start_time < 1.0:
                    if arduino.in_waiting > 0:
                        response = arduino.readline().decode().strip()
                        if "OPENED" in response or "CLOSED" in response:
                            return True
                print(f"Retry {attempt+1}: No Arduino response")
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            connect_arduino()
    
    print("Gate control failed after retries")
    return False

def process_detection(frame):
    """Process frame for license plates"""
    # Vehicle detection
    vehicle_results = object_model(frame, verbose=False)
    if not any(int(box.cls) in [2, 3, 5, 7] for res in vehicle_results for box in res.boxes):
        return None

    # Plate recognition
    for result in plate_model(frame, conf=0.5, verbose=False):
        for box in result.boxes.xyxy.cpu().numpy():
            x1, y1, x2, y2 = map(int, box)
            plate_img = frame[y1:y2, x1:x2]
            
            try:
                plate_text = reader.readtext(
                    cv2.threshold(
                        cv2.createCLAHE().apply(
                            cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                        ), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                    detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                )[0]
            except:
                continue

            authorized = plates_ref.document(plate_text).get().exists
            if authorized:
                control_gate(True)
                threading.Timer(5.0, lambda: control_gate(False)).start()
            else:
                control_gate(False)

            return {
                'plate': plate_text,
                'authorized': authorized,
                'coordinates': [x1, y1, x2, y2]
            }
    return None

# ========== ROUTES ==========
@app.route('/control_gate', methods=['POST'])
def api_control_gate():
    try:
        success = control_gate(request.json['state'])
        return jsonify(success=success)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/detect', methods=['POST'])
def api_detect():
    if 'image' not in request.files:
        return jsonify(error="No image"), 400
        
    try:
        file = request.files['image']
        temp_path = "temp.jpg"
        file.save(temp_path)
        frame = cv2.imread(temp_path)
        result = process_detection(frame)
        os.remove(temp_path)
        return jsonify(result if result else {"message": "No plate detected"})
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/')
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
            if users_ref.document(id_number).get().exists:
                return jsonify({"message": "User already exists!"}), 400

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
    return jsonify({
        "registered": plate_doc.exists,
        "details": plate_doc.to_dict() if plate_doc.exists else None
    })

@app.route('/register_plate', methods=['POST'])
def register_plate():
    if 'logged_in' not in session:
        return jsonify({"message": "Please log in to perform this action."}), 401

    id_number = request.form.get('id_number')
    plate = request.form.get('plate')

    if not session.get('is_admin') and id_number != session.get('user_id'):
        return jsonify({"message": "You can only register plates for your own ID."}), 403

    try:
        if plates_ref.document(plate).get().exists:
            return jsonify({"message": "License Plate already registered!"}), 400

        if not drivers_ref.document(id_number).get().exists:
            drivers_ref.document(id_number).set({'id_number': id_number})

        plates_ref.document(plate).set({
            'plate': plate,
            'id_number': id_number,
            'registered_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"message": "License Plate Registered!"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

# ========== ARDUINO LISTENER ==========
def arduino_listener():
    while True:
        try:
            with arduino_lock:
                if arduino and arduino.in_waiting:
                    print(f"Arduino: {arduino.readline().decode().strip()}")
        except:
            time.sleep(1)

# Start Arduino listener thread
threading.Thread(target=arduino_listener, daemon=True).start()

# ========== RUN SERVER ==========
if __name__ == '__main__':
    # Initialize Firebase default admin if not exists
    if not admins_ref.document('admin').get().exists:
        admins_ref.document('admin').set({'username':'admin', 'password':'12341234'})
    
    app.run(host='0.0.0.0', port=5000)