import cv2
import easyocr
import requests
from ultralytics import YOLO

# Initialize EasyOCR reader globally
reader = easyocr.Reader(['en'])

def check_plate_in_database(plate):
    """
    Check if the license plate exists in the database by sending a request to the API.
    """
    try:
        response = requests.get(f"http://localhost:5000/check_plate?plate={plate}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error checking plate in database: {e}")
        return {"registered": False}

def extract_license_plate(image_path):
    """
    Extract potential license plate text from an image using EasyOCR.
    """
    # Read the image
    frame = cv2.imread(image_path)
    if frame is None:
        print("Error: Could not read image.")
        return None

    # Perform OCR to get the text
    ocr_results = reader.readtext(frame)
    
    detected_texts = []
    for (bbox, text, prob) in ocr_results:
        if len(text) >= 3:  # Filter based on your needs
            detected_texts.append(text.strip())
    
    return detected_texts

def detect_objects_and_license_plate(image_path):
    """
    Use YOLOv8 to detect objects (cars, people, animals) and extract license plates.
    """
    # Load YOLOv8 model
    model = YOLO("yolov8n.pt")

    # Perform object detection
    results = model.predict(source=image_path)

    # Check for cars, people, and animals
    gate_open = False
    for result in results:
        for box in result.boxes:
            class_id = int(box.cls)
            if class_id == 2 or class_id == 7:  # Car (2) or Truck (7)
                gate_open = True
            elif class_id in [0, 1]:  # Person (0) or Animal (1)
                gate_open = False

    # Extract license plate text
    detected_texts = extract_license_plate(image_path)

    if detected_texts:
        for text in detected_texts:
            print(f"Detected License Plate: {text}")

            # Check database
            result = check_plate_in_database(text)
            if result.get("registered"):
                print("Access Granted")
                # If the license plate is registered and a car/truck is detected, open the gate
                if gate_open:
                    print("Gate Open: True")
                else:
                    print("Gate Open: False")
            else:
                print("Access Denied")
                gate_open = False  # Ensure the gate remains closed if the license plate is not registered
    else:
        print("No license plate detected.")
        gate_open = False  # Ensure the gate remains closed if no license plate is detected

    return gate_open

def main(image_path):
    # Detect objects and license plates
    gate_status = detect_objects_and_license_plate(image_path)
    print(f"Final Gate Status: {gate_status}")

if __name__ == "__main__":
    # Example image path
    # image_path = r"C:\Users\siyam\Pictures\1faf1862-1b51-497c-8154-ab8a5e2ba955.png"
    
    # image_path = r"C:\Users\siyam\Pictures\IMG_1242    S.JPG"
        
    # image_path = r"C:\Users\siyam\Pictures\photo_2025-01-02_22-06-21.jpg"
    
    # image_path = r"C:\Users\siyam\Pictures\884fee62-40db-4059-bb75-ba13b5fd6528.png"




    
    
    image_path = r"C:\Users\siyam\Pictures\A_realistic_image_of_a_generic_license_plate_featuring_a_white_background_with_blue_letters_and_numbers_The_plate_should_display_the_fictional_license_plate_number_XYZ_5678_The_edges_of_the_plate_should_be_slightl.jpeg"

    main(image_path)