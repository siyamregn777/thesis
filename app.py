from flask import Flask, request, jsonify, render_template
from ultralytics import YOLO
from database import get_db_connection  # Import the reusable function

app = Flask(__name__)

# Load YOLOv8 model
model = YOLO("yolov8n.pt")  # Ensure the model file is available

def init_db():
    conn = get_db_connection()  # Use the reusable function
    c = conn.cursor()
    
    # Create Drivers table
    
    c.execute('CREATE TABLE IF NOT EXISTS drivers (id_number VARCHAR(255) PRIMARY KEY)')
    
    # Create License Plates table
    c.execute('CREATE TABLE IF NOT EXISTS plates (plate VARCHAR(255) PRIMARY KEY, id_number VARCHAR(255), FOREIGN KEY (id_number) REFERENCES drivers (id_number) ON DELETE CASCADE)')
    
    conn.commit()
    conn.close()

@app.route('/check_plate', methods=['GET'])
def check_plate():
    plate = request.args.get('plate')
    conn = get_db_connection()  # Use the reusable function
    c = conn.cursor()
    c.execute('SELECT * FROM plates WHERE plate = %s', (plate,))
    result = c.fetchone()
    conn.close()
    return jsonify({"registered": result is not None})

@app.route('/register_plate', methods=['POST'])
def register_plate():
    id_number = request.form['id_number']
    plate = request.form['plate']
    
    conn = get_db_connection()  # Use the reusable function
    c = conn.cursor()

    # Check if the driver exists
    c.execute('SELECT * FROM drivers WHERE id_number = %s', (id_number,))
    driver = c.fetchone()
    
    if driver is None:
        # If the driver does not exist, create a new driver entry
        c.execute('INSERT INTO drivers (id_number) VALUES (%s)', (id_number,))
    
    # Check for existing license plates
    c.execute('SELECT * FROM plates WHERE plate = %s', (plate,))
    if c.fetchone() is not None:
        conn.close()
        return jsonify({"message": "License Plate already registered!"}), 400

    c.execute('INSERT INTO plates (plate, id_number) VALUES (%s, %s)', (plate, id_number))
    conn.commit()
    conn.close()
    return jsonify({"message": "License Plate Registered!"}), 200

@app.route('/update_plate', methods=['POST'])
def update_plate():
    id_number = request.form['update_id']
    old_plate = request.form['old_plate']
    new_plate = request.form['new_plate']

    conn = get_db_connection()  # Use the reusable function
    c = conn.cursor()

    # Check if the existing plate belongs to the given ID
    c.execute('SELECT * FROM plates WHERE id_number = %s AND plate = %s', (id_number, old_plate))
    plate = c.fetchone()
    
    if plate is None:
        conn.close()
        return jsonify({"message": "No license plate found for the given ID!"}), 404

    # Update the license plate
    c.execute('UPDATE plates SET plate = %s WHERE id_number = %s AND plate = %s', (new_plate, id_number, old_plate))
    conn.commit()
    conn.close()
    return jsonify({"message": "License Plate Updated!"}), 200

@app.route('/delete_plate', methods=['POST'])
def delete_plate():
    id_number = request.form['delete_id']
    plate = request.form['delete_plate']

    conn = get_db_connection()  # Use the reusable function
    c = conn.cursor()

    # Check if the existing plate belongs to the given ID
    c.execute('SELECT * FROM plates WHERE id_number = %s AND plate = %s', (id_number, plate))
    existing_plate = c.fetchone()
    
    if existing_plate is None:
        conn.close()
        return jsonify({"message": "No license plate found for the given ID!"}), 404

    # Delete the license plate
    c.execute('DELETE FROM plates WHERE id_number = %s AND plate = %s', (id_number, plate))
    conn.commit()
    conn.close()
    return jsonify({"message": "License Plate Deleted!"}), 200

@app.route('/delete_driver', methods=['POST'])
def delete_driver():
    id_number = request.form['delete_driver_id']

    conn = get_db_connection()  # Use the reusable function
    c = conn.cursor()

    # Check if the driver exists
    c.execute('SELECT * FROM drivers WHERE id_number = %s', (id_number,))
    driver = c.fetchone()

    if driver is None:
        conn.close()
        return jsonify({"message": "No driver found with the given ID!"}), 404

    # Delete the driver, which will also delete associated license plates
    c.execute('DELETE FROM drivers WHERE id_number = %s', (id_number,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Driver and associated license plates deleted!"}), 200

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

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)