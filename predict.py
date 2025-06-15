from ultralytics import YOLO
import cv2
import os
import pytesseract
import numpy as np
from datetime import datetime

# Initialize models
plate_detector = YOLO(r"C:\Users\siyam\Documents\thesis-1\runs\detect\train\weights\best.pt")  # Model 1: Finds plates on cars
plate_analyzer = YOLO(r"C:\Users\siyam\Documents\thesis-1\content\runs\license_plate_model2\weights\best.pt")  # Model 2: Extracts plate components
vehicle_verifier = YOLO("yolov8n.pt")  # Model 3: Verifies if it's a car

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configuration
OUTPUT_DIR = "detected_plates"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Simplified component regions (using percentages for flexibility)
REGIONS = {
    "circle_number": (0.0, 0.0, 0.25, 1.0),   # Left 25%
    "amharic_text": (0.25, 0.0, 0.5, 1.0),    # Middle-left 25-50%
    "plate_number": (0.5, 0.0, 0.75, 1.0),    # Middle-right 50-75%
    "english_text": (0.75, 0.0, 1.0, 1.0)     # Right 25%
}

def extract_circle_number(img):
    """Extract numbers from circle with preprocessing"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2,2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    text = pytesseract.image_to_string(cleaned, config='--psm 10 digits')
    return text.strip()

def extract_amharic(img):
    """Extract Amharic text with enhanced preprocessing"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    blur = cv2.GaussianBlur(enhanced, (3,3), 0)
    text = pytesseract.image_to_string(blur, lang='amh', config='--psm 6')
    return text.strip()

def extract_plate_number(img):
    """Extract alphanumeric plate number"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config='--psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    return text.strip()

def extract_english(img):
    """Extract English text"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    return text.strip()

def is_vehicle(frame):
    """Check if the detected object is a vehicle using Model 3"""
    results = vehicle_verifier(frame)
    vehicle_classes = [2, 3, 5, 7]  # COCO classes for cars, trucks, buses, etc.
    
    for result in results:
        for box in result.boxes:
            if int(box.cls) in vehicle_classes and box.conf > 0.5:
                return True
    return False

def process_license_plate(plate_img, save_dir):
    """Process plate image and save results"""
    height, width = plate_img.shape[:2]
    results = {}
    
    for name, (x1_pct, y1_pct, x2_pct, y2_pct) in REGIONS.items():
        # Convert percentages to pixel coordinates
        x1 = int(x1_pct * width)
        y1 = int(y1_pct * height)
        x2 = int(x2_pct * width)
        y2 = int(y2_pct * height)
        
        roi = plate_img[y1:y2, x1:x2]
        
        # Select appropriate extraction method
        if "circle" in name:
            results[name] = extract_circle_number(roi)
        elif "amharic" in name:
            results[name] = extract_amharic(roi)
        elif "plate" in name:
            results[name] = extract_plate_number(roi)
        else:
            results[name] = extract_english(roi)
        
        # Save component image
        cv2.imwrite(f"{save_dir}/{name}.jpg", roi)
    
    # Save the full plate image
    cv2.imwrite(f"{save_dir}/full_plate.jpg", plate_img)
    
    # Save results to text file
    with open(f"{save_dir}/plate_info.txt", "w", encoding="utf-8") as f:
        for name, text in results.items():
            f.write(f"{name.replace('_', ' ').title()}: {text}\n")
    
    return results

def process_video(video_path, output_dir=OUTPUT_DIR, min_confidence=0.5):
    """Process video file and save detected plates"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error opening video: {video_path}")
        return
    
    frame_count = 0
    plate_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Skip frames for better performance (process every 5th frame)
        if frame_count % 5 != 0:
            continue
        
        # Step 1: Verify it's a vehicle first
        if not is_vehicle(frame):
            continue
            
        # Step 2: Detect license plates
        plate_results = plate_detector(frame, conf=min_confidence)
        
        for result in plate_results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                plate_img = frame[y1:y2, x1:x2]
                
                # Create unique directory for this plate
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                plate_dir = os.path.join(output_dir, f"plate_{plate_count}_{timestamp}")
                os.makedirs(plate_dir, exist_ok=True)
                plate_count += 1
                
                try:
                    # Step 3: Process and save plate information
                    plate_data = process_license_plate(plate_img, plate_dir)
                    
                    # Print results to console
                    print(f"\nDetected Plate {plate_count}:")
                    for name, text in plate_data.items():
                        print(f"{name.replace('_', ' ').title()}: {text}")
                    
                    # Draw rectangle on frame
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"Plate {plate_count}", (x1, y1-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                except Exception as e:
                    print(f"Error processing plate: {e}")
        
        # Display the frame with detections
        cv2.imshow('License Plate Detection', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

def process_image(image_path, output_dir=OUTPUT_DIR):
    """Process single image"""
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Error loading image: {image_path}")
        return
    
    # Step 1: Verify it's a vehicle first
    if not is_vehicle(frame):
        print("No vehicle detected in the image")
        return
    
    # Create unique directory for this plate
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plate_dir = os.path.join(output_dir, f"plate_{timestamp}")
    os.makedirs(plate_dir, exist_ok=True)
    
    # Step 2: Detect license plates
    plate_results = plate_detector(frame)
    plates = []
    
    for result in plate_results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            plate_img = frame[y1:y2, x1:x2]
            plates.append(plate_img)
    
    if not plates:
        print("No license plates detected")
        return
    
    # Step 3: Process first detected plate
    plate_data = process_license_plate(plates[0], plate_dir)
    
    print("\nExtracted License Plate Information:")
    for name, text in plate_data.items():
        print(f"{name.replace('_', ' ').title()}: {text}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ethiopian License Plate Recognition')
    parser.add_argument('input_path', type=str, help='Path to input image or video')
    parser.add_argument('--output_dir', type=str, help='Output directory for results', default=OUTPUT_DIR)
    parser.add_argument('--min_confidence', type=float, help='Minimum detection confidence', default=0.5)
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Determine if input is image or video
    input_path = args.input_path
    if not os.path.exists(input_path):
        print(f"Error: Input path does not exist: {input_path}")
        return

    if input_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        process_image(input_path, args.output_dir)
    elif input_path.lower().endswith(('.mp4', '.avi', '.mov')):
        process_video(input_path, args.output_dir, args.min_confidence)
    else:
        print("Error: Unsupported file format. Please provide an image or video file.")

if __name__ == "__main__":
    main()