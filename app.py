from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from ultralytics import YOLO
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
import os
import cv2
import threading
from datetime import datetime
import time
import easyocr

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure secret key

# ========== SYSTEM INITIALIZATION ==========
# Initialize OCR reader
reader = easyocr.Reader(['en'])

# ========== MODELS INITIALIZATION ==========
plate_model = YOLO(r"C:\Users\siyam\Documents\thesis-1\content\runs\license_plate_model2\weights\best.pt")
object_model = YOLO("yolov8n.pt")

# ========== FIREBASE INITIALIZATION ==========
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
        if not admins_ref.document('admin').get().exists:
            admins_ref.document('admin').set({
                'username': 'admin',
                'password': '12341234'
            })
            print("Firebase admin initialized")
    except FirebaseError as e:
        print(f"Firebase initialization error: {e}")

def extract_plate_text(plate_img):
    """Enhanced plate text extraction with EasyOCR"""
    try:
        # Preprocess image
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # OCR with character whitelist
        results = reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        return results[0] if results else ""
    except Exception as e:
        print(f"OCR error: {e}")
        return ""

def process_capture_request():
    """Process image capture request"""
    print("Processing capture request")
    
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    if ret:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("captures", exist_ok=True)
        save_path = f"captures/capture_{timestamp}.jpg"
        cv2.imwrite(save_path, frame)
        
        # Process the image
        process_detection(frame, save_path)
    else:
        print("Failed to capture image")
    
    cap.release()

def process_detection(frame, image_path=None):
    """Process frame for vehicles and license plates"""
    # Vehicle detection
    vehicle_results = object_model(frame, verbose=False)
    vehicle_detected = any(int(box.cls) in [2, 3, 5, 7]  # Cars, motorcycles, buses, trucks
                          for result in vehicle_results 
                          for box in result.boxes)
    
    if not vehicle_detected:
        print("No vehicle detected")
        return None
    
    # License plate recognition
    plate_results = plate_model(frame, conf=0.5, verbose=False)
    authorized = False
    
    for result in plate_results:
        for box in result.boxes.xyxy.cpu().numpy():
            x1, y1, x2, y2 = map(int, box)
            plate_img = frame[y1:y2, x1:x2]
            
            plate_text = extract_plate_text(plate_img)
            if plate_text:
                print(f"Detected plate: {plate_text}")
                # Check database
                plate_doc = plates_ref.document(plate_text).get()
                authorized = plate_doc.exists
                
                # Print access status
                if authorized:
                    print(f"Access granted for {plate_text}")
                else:
                    print(f"Access denied for {plate_text}")
                
                # Save plate image if path provided
                if image_path:
                    plate_path = f"captures/plate_{plate_text}_{datetime.now().strftime('%H%M%S')}.jpg"
                    cv2.imwrite(plate_path, plate_img)
                
                return {
                    'plate': plate_text,
                    'authorized': authorized,
                    'coordinates': [x1, y1, x2, y2]
                }
    
    print("No valid license plates detected")
    return None

# ========== ROUTES ==========
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

@app.route('/detect', methods=['POST'])
def detect():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
        
    file = request.files['image']
    temp_path = "temp_upload.jpg"
    file.save(temp_path)
    
    try:
        frame = cv2.imread(temp_path)
        if frame is None:
            return jsonify({"error": "Could not read image"}), 400
            
        result = process_detection(frame, temp_path)
        if result:
            return jsonify(result)
        return jsonify({"message": "No valid license plates detected"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/test_gate', methods=['POST'])
def test_gate():
    if 'logged_in' not in session or not session.get('is_admin'):
        return jsonify({"message": "Admin access required"}), 403
        
    state = request.json.get('state')
    if state not in [True, False]:
        return jsonify({"message": "Invalid state"}), 400
        
    return jsonify({
        "success": True,
        "message": f"Gate {'opened' if state else 'closed'} (simulated)"
    })

if __name__ == '__main__':
    init_firebase()
    app.run(host='0.0.0.0', port=5000, debug=True)