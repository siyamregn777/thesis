import cv2
import easyocr
import requests
import numpy as np
from pathlib import Path
import pandas as pd
import torch
import torch.serialization
from ultralytics import YOLO
from ultralytics.nn.modules.conv import Conv
from ultralytics.nn.tasks import DetectionModel

# ========== INITIALIZATION ==========
# Add YOLOv8 modules to safe globals
torch.serialization.add_safe_globals([Conv, DetectionModel])

# Initialize models
plate_model_path = r"C:\Users\siyam\Documents\ThesisMain\Licence-Plate-Detection-using-YOLO-V8\runs\detect\train\weights\best.pt"
plate_model = YOLO(plate_model_path)  # Custom license plate detection
object_model = YOLO("yolov8n.pt")    # General object detection
reader = easyocr.Reader(['en'])      # Initialize OCR for English characters

# ========== CORE FUNCTIONS ==========
def preprocess_plate(plate_img):
    """Enhanced preprocessing for better OCR results"""
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY_INV, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return cleaned

def extract_plate_text(plate_img):
    """High-accuracy text extraction with OCR"""
    processed = preprocess_plate(plate_img)
    results = reader.readtext(processed, detail=0, 
                            allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                            width_ths=3, height_ths=1)
    return results[0] if results else ""

def check_plate_in_database(plate):
    """Check if license plate exists in database via API"""
    try:
        response = requests.get(f"http://localhost:5000/check_plate?plate={plate}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error checking plate in database: {e}")
        return {"registered": False}

# ========== PROCESSING FUNCTIONS ==========
def process_image(image_path, output_dir='output'):
    """Process an image with detection and text extraction"""
    Path(output_dir).mkdir(exist_ok=True)
    image = cv2.imread(image_path)
    if image is None:
        print("Error: Could not read image.")
        return False
    
    plates_data = []
    gate_open = False
    
    # Detect objects with general model
    object_results = object_model.predict(source=image)
    for result in object_results:
        for box in result.boxes:
            class_id = int(box.cls)
            if class_id in [2, 3, 5, 7]:  # Cars, motorcycles, buses, trucks
                gate_open = True
    
    # Detect license plates with custom model
    plate_results = plate_model.predict(source=image, conf=0.5)
    
    for i, result in enumerate(plate_results):
        # Save detection visualization
        detections = result.plot()
        output_path = f'{output_dir}/detection_{Path(image_path).stem}.jpg'
        cv2.imwrite(output_path, detections)
        
        # Process each detected plate
        for j, box in enumerate(result.boxes.xyxy.cpu().numpy()):
            x1, y1, x2, y2 = map(int, box)
            plate_img = image[y1:y2, x1:x2]
            
            # Save cropped plate
            plate_path = f'{output_dir}/plate_{Path(image_path).stem}_{j}.jpg'
            cv2.imwrite(plate_path, plate_img)
            
            # Extract text
            plate_text = extract_plate_text(plate_img)
            print(f"Plate {j+1}: {plate_text}")
            
            if plate_text:
                # Check database
                result = check_plate_in_database(plate_text)
                if result.get("registered"):
                    print("Access Granted")
                    gate_open = True
                else:
                    print("Access Denied")
                    gate_open = False
            
            # Annotate image with extracted text
            cv2.putText(detections, plate_text, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)
            cv2.imwrite(f'{output_dir}/annotated_{Path(image_path).stem}.jpg', detections)
            
            # Store plate data
            plates_data.append({
                'image': Path(image_path).name,
                'plate_img': plate_path,
                'plate_text': plate_text,
                'coordinates': f"{x1},{y1},{x2},{y2}",
                'access_granted': gate_open
            })
    
    # Save plate data to CSV
    if plates_data:
        pd.DataFrame(plates_data).to_csv(f'{output_dir}/plate_data.csv', index=False)
    
    print(f"Image processing complete. Results saved in '{output_dir}'")
    print(f"Final Gate Status: {gate_open}")
    return gate_open

def process_video(video_path, output_dir='video_output', frame_skip=3):
    """Process video file with plate detection and OCR"""
    Path(output_dir).mkdir(exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Prepare video writer
    output_path = f'{output_dir}/annotated_{Path(video_path).stem}.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    frame_count = 0
    plates_data = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        if frame_count % frame_skip != 0:
            continue
            
        gate_open = False
        
        # Detect objects with general model
        object_results = object_model.predict(source=frame)
        for result in object_results:
            for box in result.boxes:
                class_id = int(box.cls)
                if class_id in [2, 3, 5, 7]:  # Cars, motorcycles, buses, trucks
                    gate_open = True
        
        # Detect license plates with custom model
        plate_results = plate_model.predict(source=frame, conf=0.5)
        
        for result in plate_results:
            annotated_frame = result.plot()
            
            # Process each detected plate
            for j, box in enumerate(result.boxes.xyxy.cpu().numpy()):
                x1, y1, x2, y2 = map(int, box)
                plate_img = frame[y1:y2, x1:x2]
                
                # Extract text
                plate_text = extract_plate_text(plate_img)
                if plate_text:
                    # Save cropped plate
                    plate_filename = f'frame_{frame_count}_plate_{j}.jpg'
                    cv2.imwrite(f'{output_dir}/{plate_filename}', plate_img)
                    
                    # Check database
                    result = check_plate_in_database(plate_text)
                    if result.get("registered"):
                        gate_open = True
                    
                    # Annotate frame with plate text and access status
                    status = "ACCESS GRANTED" if gate_open else "ACCESS DENIED"
                    color = (0, 255, 0) if gate_open else (0, 0, 255)
                    cv2.putText(annotated_frame, f"{plate_text} - {status}", (x1, y1-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                    
                    # Store plate data
                    plates_data.append({
                        'frame': frame_count,
                        'timestamp': f"{frame_count/fps:.2f}s",
                        'plate_img': plate_filename,
                        'plate_text': plate_text,
                        'coordinates': f"{x1},{y1},{x2},{y2}",
                        'access_granted': gate_open
                    })
            
            # Write frame to output video
            out.write(annotated_frame)
            
        # Display progress
        cv2.imshow('Processing...', annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release resources
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    
    # Save plate data to CSV
    if plates_data:
        pd.DataFrame(plates_data).to_csv(f'{output_dir}/plate_data.csv', index=False)
    
    print(f"Video processing complete. Results saved in '{output_dir}'")

# ========== MAIN EXECUTION ==========
if __name__ == '__main__':
    # ===== EDIT THESE PATHS =====
    IMAGE_PATH = r"C:\Users\siyam\Pictures\images (2).jpeg"  # ← Your image path here
    # VIDEO_PATH = r"C:\Users\siyam\Pictures\mc pgoto\video_2025-05-05_03-11-42.mp4"  # ← Your video path here
    
    # ===== CHOOSE WHAT TO PROCESS =====
    # Uncomment ONE of these lines:
    
    # For images:
    process_image(IMAGE_PATH)
    
    # For videos (with frame skipping):
    # process_video(VIDEO_PATH, frame_skip=3)