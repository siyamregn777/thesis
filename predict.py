import cv2
import easyocr
import requests
import numpy as np
import pandas as pd
import torch
import serial
import time
from ultralytics import YOLO
import os
from datetime import datetime
import pytesseract

# ========== ARDUINO GATE CONTROLLER ==========
class ArduinoGateController:
    def __init__(self, port='COM4', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.gate_status = False
        self.connect()
        
    def connect(self):
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Allow Arduino to initialize
            print(f"Connected to Arduino on {self.port}")
            self.close_gate()  # Initialize with closed gate
        except Exception as e:
            print(f"Arduino connection error: {e}")
            self.serial_conn = None
    
    def control_gate(self, open_gate):
        """Send gate control command to Arduino"""
        if not self.serial_conn:
            print("No Arduino connection!")
            return False
            
        try:
            if open_gate and not self.gate_status:
                self.serial_conn.write(b'1')  # Send open command
                self.gate_status = True
                print("Gate opened")
            elif not open_gate and self.gate_status:
                self.serial_conn.write(b'0')  # Send close command
                self.gate_status = False
                print("Gate closed")
            return True
        except Exception as e:
            print(f"Gate control error: {e}")
            return False

    def open_gate(self):
        self.control_gate(True)
    
    def close_gate(self):
        self.control_gate(False)
    
    def check_detection(self):
        """Check if Arduino has detected a vehicle"""
        if not self.serial_conn:
            return False
            
        if self.serial_conn.in_waiting > 0:
            line = self.serial_conn.readline().decode().strip()
            if line == "DETECTED":
                return True
        return False
    
    def __del__(self):
        if self.serial_conn:
            self.close_gate()
            self.serial_conn.close()

# ========== LICENSE PLATE RECOGNITION SYSTEM ==========
class LicensePlateSystem:
    def __init__(self):
        torch.serialization.add_safe_globals([])
        
        # Initialize models
        self.object_model = YOLO("yolov8n.pt")  # General object detection
        self.plate_model = YOLO(r"C:\Users\siyam\Documents\thesis-1\runs1\detect\train2\weights\best.pt")  # License plate detection
        self.reader = easyocr.Reader(['en'])
        
        # Initialize Arduino controller
        self.gate_controller = ArduinoGateController(port='COM4')
        
        # Configuration
        self.vehicle_classes = [2, 3, 5, 7]  # COCO classes: car, motorcycle, bus, truck
        self.non_vehicle_classes = {
            0: 'person',
            15: 'dog',
            16: 'cat',
            17: 'horse',
            18: 'sheep',
            19: 'cow'
        }  # Classes to ignore for plate detection
        self.plate_confidence = 0.5
        self.object_confidence = 0.5  # Confidence threshold for object detection
        self.api_url = "http://localhost:5000"  # Flask API endpoint
        self.output_root = "detection_results"  # Root folder for all outputs
        self.detection_timeout = 30  # Seconds to wait for detection
        self.max_capture_attempts = 3  # Maximum number of capture attempts
        self.capture_delay = 1  # Delay between capture attempts
        
        # Tesseract config
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        # Create output directory structure
        self.create_output_dirs()
        
        # Check if GUI is available
        self.gui_enabled = self.check_gui_support()

    def check_gui_support(self):
        """Check if OpenCV GUI functions are available"""
        try:
            test_window = np.zeros((100,100,3), np.uint8)
            cv2.imshow('test', test_window)
            cv2.destroyAllWindows()
            return True
        except:
            print("GUI not available - running in headless mode")
            return False

    def create_output_dirs(self):
        """Create organized directory structure for outputs"""
        os.makedirs(self.output_root, exist_ok=True)
        self.dirs = {
            'original': os.path.join(self.output_root, "original_frames"),
            'processed': os.path.join(self.output_root, "processed_frames"),
            'plates': os.path.join(self.output_root, "plate_crops"),
            'logs': os.path.join(self.output_root, "logs"),
            'tesseract': os.path.join(self.output_root, "tesseract_results"),
            'objects': os.path.join(self.output_root, "object_detections")
        }
        
        for dir_path in self.dirs.values():
            os.makedirs(dir_path, exist_ok=True)

    def preprocess_plate(self, plate_img):
        """Enhanced image preprocessing combining both methods"""
        # Convert to grayscale
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        
        # Denoising
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Binarization
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed

    def extract_text_with_easyocr(self, plate_img):
        """Extract text using EasyOCR"""
        results = self.reader.readtext(plate_img, detail=0,
                                     allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        return results[0] if results else ""

    def extract_text_with_tesseract(self, plate_img, language='amh+eng'):
        """Improved text extraction for license plates with Amharic and English support"""
        # Convert to grayscale
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        
        # Apply preprocessing
        # 1. Denoising
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # 2. Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 3. Binarization
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Try different PSM modes for better results
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text = pytesseract.image_to_string(processed, lang=language, config=custom_config)
        
        # Post-process the extracted text
        text = text.strip()
        text = ' '.join(text.split())  # Remove extra whitespace
        return text

    def extract_plate_text(self, plate_img, save_path=None):
        """Enhanced text extraction with both OCR methods and Amharic support"""
        processed = self.preprocess_plate(plate_img)
        
        # Save processed plate image if requested
        if save_path:
            cv2.imwrite(save_path, processed)
            print(f"Saved processed plate image to: {save_path}")
        
        # Try both OCR methods
        easyocr_text = self.extract_text_with_easyocr(processed)
        tesseract_text = self.extract_text_with_tesseract(plate_img)  # Use original image for Tesseract
        
        # Save Tesseract results separately
        tesseract_path = os.path.join(self.dirs['tesseract'], os.path.basename(save_path or "temp_plate.jpg"))
        with open(tesseract_path.replace('.jpg', '.txt'), 'w') as f:
            f.write(f"EasyOCR: {easyocr_text}\nTesseract: {tesseract_text}")
        
        # Return the most confident result
        if len(easyocr_text) >= len(tesseract_text):
            return easyocr_text
        return tesseract_text

    def check_authorization(self, plate_text):
        """Check if plate is authorized in database via Flask API"""
        try:
            response = requests.get(
                f"{self.api_url}/check_plate?plate={plate_text}",
                timeout=3
            )
            response.raise_for_status()
            data = response.json()
            return data.get("registered", False)
        except requests.RequestException as e:
            print(f"API request error: {e}")
            return False

    def process_frame(self, frame):
        """Process single frame with object detection first"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Step 1: Object detection to identify what's in the frame
        object_results = self.object_model(frame, conf=self.object_confidence, verbose=False)
        
        # Save object detection results
        object_path = os.path.join(self.dirs['objects'], f"object_detection_{timestamp}.jpg")
        annotated_frame = object_results[0].plot()
        cv2.imwrite(object_path, annotated_frame)
        print(f"Saved object detection results to: {object_path}")
        
        # Check for non-vehicle objects (people, animals, etc.)
        for box, cls in zip(object_results[0].boxes.xyxy.cpu().numpy(), 
                           object_results[0].boxes.cls.cpu().numpy()):
            if cls in self.non_vehicle_classes:
                object_name = self.non_vehicle_classes[cls]
                cv2.putText(annotated_frame, f"{object_name.capitalize()} detected - No license plate", 
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                          0.9, (0, 0, 255), 2)
                self.gate_controller.close_gate()
                return annotated_frame, object_name, False
        
        # Step 2: If no non-vehicle objects, proceed with license plate recognition
        plate_results = self.plate_model(frame, conf=self.plate_confidence, verbose=False)
        authorized = False
        
        for result in plate_results:
            annotated_frame = result.plot()
            
            for box in result.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(int, box)
                plate_img = frame[y1:y2, x1:x2]
                
                # Generate unique filename for plate crop
                plate_crop_path = os.path.join(self.dirs['plates'], f"plate_{timestamp}.jpg")
                cv2.imwrite(plate_crop_path, plate_img)
                print(f"Saved plate crop to: {plate_crop_path}")
                
                # Extract text with visualization
                plate_text = self.extract_plate_text(plate_img, 
                                                   os.path.join(self.dirs['plates'], f"plate_processed_{timestamp}.jpg"))
                
                if plate_text:
                    authorized = self.check_authorization(plate_text)
                    status = "AUTHORIZED" if authorized else "UNAUTHORIZED"
                    color = (0, 255, 0) if authorized else (0, 0, 255)
                    
                    # Add visualization
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(annotated_frame, f"{plate_text} - {status}", 
                              (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                              0.9, color, 2)
                    
                    # Control gate based on authorization
                    if authorized:
                        self.gate_controller.open_gate()
                    else:
                        self.gate_controller.close_gate()
                    
                    return annotated_frame, plate_text, authorized
        
        # No plates detected but vehicle present
        self.gate_controller.close_gate()
        return annotated_frame, "No license plate detected", False

    def wait_for_detection(self):
        """Wait for vehicle detection from ultrasonic sensor"""
        print(f"Waiting for vehicle detection (timeout: {self.detection_timeout}s)...")
        start_time = time.time()
        
        while time.time() - start_time < self.detection_timeout:
            if self.gate_controller.check_detection():
                print("Vehicle detected by ultrasonic sensor!")
                return True
            time.sleep(0.1)
        
        print("Timeout waiting for vehicle detection")
        return False

    def capture_frame(self, video_source):
        """Capture single frame from video source"""
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            print(f"Error opening video source: {video_source}")
            return None
            
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            print("Failed to capture frame")
            return None
            
        return frame

    def process_detection(self, video_source):
        """Main processing workflow triggered by detection"""
        # Step 1: Wait for ultrasonic detection
        if not self.wait_for_detection():
            return False
            
        # Step 2: Attempt capture up to max_attempts times
        authorized = False
        attempt = 0
        
        while attempt < self.max_capture_attempts and not authorized:
            attempt += 1
            print(f"\nCapture attempt {attempt} of {self.max_capture_attempts}")
            
            # Step 3: Capture frame when detected
            frame = self.capture_frame(video_source)
            if frame is None:
                time.sleep(self.capture_delay)
                continue
                
            # Step 4: Save original frame
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            original_path = os.path.join(self.dirs['original'], f"attempt_{attempt}_{timestamp}.jpg")
            cv2.imwrite(original_path, frame)
            print(f"Saved detection image to: {original_path}")
            
            # Step 5: Process frame
            processed_frame, detection_result, authorized = self.process_frame(frame)
            
            # Step 6: Save processed frame
            processed_path = os.path.join(self.dirs['processed'], f"processed_{attempt}_{timestamp}.jpg")
            cv2.imwrite(processed_path, processed_frame)
            print(f"Saved processed image to: {processed_path}")
            
            # Step 7: Log results
            log_entry = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'attempt': attempt,
                'image_path': original_path,
                'detected_object': detection_result,
                'plate_text': detection_result if detection_result in self.non_vehicle_classes.values() or 
                               detection_result == "No license plate detected" else "None",
                'authorized': authorized,
                'gate_status': 'OPEN' if authorized else 'CLOSED'
            }
            
            log_path = os.path.join(self.dirs['logs'], "detection_log.csv")
            log_df = pd.DataFrame([log_entry])
            log_df.to_csv(log_path, mode='a', header=not os.path.exists(log_path), index=False)
            print(f"Logged results to: {log_path}")
            
            print(f"\nProcessing complete. Gate status: {'OPEN' if authorized else 'CLOSED'}")
            print(f"Detection result: {detection_result}")
            
            # Display results if GUI available
            if self.gui_enabled:
                try:
                    cv2.imshow("Original Image", frame)
                    cv2.imshow("Processed Image", processed_frame)
                    cv2.waitKey(3000)  # Show for 3 seconds
                    cv2.destroyAllWindows()
                except:
                    self.gui_enabled = False
                    print("Failed to display images - continuing in headless mode")
            
            # Small delay between attempts
            if not authorized and attempt < self.max_capture_attempts:
                time.sleep(self.capture_delay)
        
        return authorized

# ========== MAIN EXECUTION ==========
if __name__ == '__main__':
    # Initialize system
    system = LicensePlateSystem()
    
    # Check Arduino connection
    if system.gate_controller.serial_conn is None:
        print("Warning: Running without Arduino connection")
    
    # IP camera URL or video source (0 for webcam)
    VIDEO_SOURCE = "http://192.168.137.68:8080/video"  # Replace with your IP camera URL
    
    # Main loop
    try:
        while True:
            # This will wait for detection, then process with max attempts
            system.process_detection(VIDEO_SOURCE)
            
            # Small delay before next detection cycle
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nSystem stopped by user")
    finally:
        # Cleanup
        if system.gate_controller.serial_conn:
            system.gate_controller.close_gate()