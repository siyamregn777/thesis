import cv2
import easyocr
import requests
import numpy as np
from pathlib import Path
import pandas as pd
import torch
import serial
import time
from ultralytics import YOLO
from ultralytics.nn.modules.conv import Conv
from ultralytics.nn.tasks import DetectionModel
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
        self.last_open_time = 0
        self.gate_open_duration = 5000  # 5 seconds in milliseconds
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
                self.last_open_time = time.time() * 1000  # Current time in ms
                print("Gate opened")
            elif not open_gate and self.gate_status:
                self.serial_conn.write(b'0')  # Send close command
                self.gate_status = False
                print("Gate closed")
            return True
        except Exception as e:
            print(f"Gate control error: {e}")
            return False
    
    def check_auto_close(self):
        """Auto-close gate after duration if open"""
        if self.gate_status and ((time.time() * 1000) - self.last_open_time > self.gate_open_duration):
            self.control_gate(False)
    
    def open_gate(self):
        self.control_gate(True)
    
    def close_gate(self):
        self.control_gate(False)
    
    def __del__(self):
        if self.serial_conn:
            self.close_gate()
            self.serial_conn.close()

# ========== LICENSE PLATE RECOGNITION SYSTEM ==========
class LicensePlateSystem:
    def __init__(self):
        torch.serialization.add_safe_globals([Conv, DetectionModel])
        
        # Initialize models
        self.plate_model = YOLO(r"C:\Users\siyam\Documents\thesis-1\runs1\detect\train2\weights\best.pt")
        self.reader = easyocr.Reader(['en'])
        
        # Initialize Arduino controller
        self.gate_controller = ArduinoGateController(port='COM4')
        
        # Configuration
        self.vehicle_classes = [2, 3, 5, 7]  # COCO classes: car, motorcycle, bus, truck
        self.plate_confidence = 0.5
        self.api_url = "http://localhost:5000"  # Flask API endpoint
        self.output_root = "detection_results"  # Root folder for all outputs
        
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
            'tesseract': os.path.join(self.output_root, "tesseract_results")
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
        """Process single frame and control gate with visualization"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Step 1: License plate recognition
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
        return frame, "", False

    def process_image(self, image_path):
        """Process single image with comprehensive output"""
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Error loading image: {image_path}")
            return False
        
        # Save original frame
        original_path = os.path.join(self.dirs['original'], os.path.basename(image_path))
        cv2.imwrite(original_path, frame)
        print(f"Saved original image to: {original_path}")
            
        processed_frame, plate_text, authorized = self.process_frame(frame)
        
        # Save processed frame
        processed_path = os.path.join(self.dirs['processed'], f"processed_{os.path.basename(image_path)}")
        cv2.imwrite(processed_path, processed_frame)
        print(f"Saved processed image to: {processed_path}")
        
        # Save log
        log_entry = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'image_path': image_path,
            'plate_text': plate_text if plate_text else "None",
            'authorized': authorized,
            'gate_status': 'OPEN' if authorized else 'CLOSED'
        }
        
        log_path = os.path.join(self.dirs['logs'], "detection_log.csv")
        log_df = pd.DataFrame([log_entry])
        log_df.to_csv(log_path, mode='a', header=not os.path.exists(log_path), index=False)
        print(f"Logged results to: {log_path}")
        
        print(f"\nProcessing complete. Gate status: {'OPEN' if authorized else 'CLOSED'}")
        print(f"Detected plate: {plate_text if plate_text else 'None'}")
        
        # Auto-close check
        self.gate_controller.check_auto_close()
        
        # Display results only if GUI is available
        if self.gui_enabled:
            try:
                cv2.imshow("Original Image", frame)
                cv2.imshow("Processed Image", processed_frame)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            except:
                self.gui_enabled = False
                print("Failed to display images - continuing in headless mode")
        
        return authorized

# ========== MAIN EXECUTION ==========
if __name__ == '__main__':
    # Initialize system
    system = LicensePlateSystem()
    
    # Check Arduino connection
    if system.gate_controller.serial_conn is None:
        print("Warning: Running without Arduino connection")
    
    # Process image
    image_path = r"C:\Users\siyam\Pictures\thesis_file\images\download1.jpeg"
    system.process_image(image_path)
    
    # OR process video/live camera
    # system.process_video(0)  # For live camera
    # system.process_video("path/to/video.mp4")  # For video file