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
        self.plate_model = YOLO(r"C:\Users\siyam\Documents\thesis-1\content\runs\license_plate_model2\weights\best.pt")
        self.vehicle_model = YOLO("yolov8n.pt")
        self.reader = easyocr.Reader(['en'])
        
        # Initialize Arduino controller
        self.gate_controller = ArduinoGateController(port='COM4')
        
        # Configuration
        self.vehicle_classes = [2, 3, 5, 7]  # COCO classes: car, motorcycle, bus, truck
        self.plate_confidence = 0.5
        self.api_url = "http://localhost:5000"  # Flask API endpoint

    def preprocess_plate(self, plate_img):
        """Enhanced image preprocessing for better OCR"""
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    def extract_plate_text(self, plate_img):
        """Extract text from license plate image"""
        processed = self.preprocess_plate(plate_img)
        results = self.reader.readtext(processed, detail=0,
                                     allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        return results[0] if results else ""

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
        """Process single frame and control gate"""
        # Step 1: Vehicle detection
        vehicle_results = self.vehicle_model(frame, verbose=False)
        vehicle_detected = any(int(box.cls) in self.vehicle_classes 
                             for result in vehicle_results 
                             for box in result.boxes)
        
        if not vehicle_detected:
            self.gate_controller.close_gate()
            return frame, "", False
        
        # Step 2: License plate recognition
        plate_results = self.plate_model(frame, conf=self.plate_confidence, verbose=False)
        authorized = False
        
        for result in plate_results:
            annotated_frame = result.plot()
            
            for box in result.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(int, box)
                plate_img = frame[y1:y2, x1:x2]
                
                plate_text = self.extract_plate_text(plate_img)
                if plate_text:
                    authorized = self.check_authorization(plate_text)
                    status = "AUTHORIZED" if authorized else "UNAUTHORIZED"
                    color = (0, 255, 0) if authorized else (0, 0, 255)
                    
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

    def process_image(self, image_path, output_dir='output'):
        """Process single image"""
        Path(output_dir).mkdir(exist_ok=True)
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Error loading image: {image_path}")
            return False
            
        processed_frame, plate_text, authorized = self.process_frame(frame)
        
        # Save results
        output_path = f"{output_dir}/{Path(image_path).stem}_processed.jpg"
        cv2.imwrite(output_path, processed_frame)
        
        print(f"Processing complete. Gate status: {'OPEN' if authorized else 'CLOSED'}")
        print(f"Detected plate: {plate_text if plate_text else 'None'}")
        
        # Auto-close check
        self.gate_controller.check_auto_close()
        return authorized

    def process_video(self, video_path, output_dir='output', frame_skip=3):
        """Process video file or live camera feed"""
        gui_enabled = True
        try:
            test_window = np.zeros((100,100,3), np.uint8)
            cv2.imshow('test', test_window)
            cv2.destroyAllWindows()
        except:
            gui_enabled = False
            print("GUI not available - running in headless mode")
        
        Path(output_dir).mkdir(exist_ok=True)
        cap = cv2.VideoCapture(video_path if isinstance(video_path, str) else int(video_path))
        if not cap.isOpened():
            print(f"Error opening video source: {video_path}")
            return
            
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if isinstance(video_path, str):
            output_path = f"{output_dir}/{Path(video_path).stem}_processed.mp4"
        else:
            output_path = f"{output_dir}/live_output.mp4"
            
        out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), 
                            fps//frame_skip, (width, height))
        
        frame_count = 0
        plates_data = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            if frame_count % frame_skip != 0:
                continue
                
            processed_frame, plate_text, authorized = self.process_frame(frame)
            out.write(processed_frame)
            
            if gui_enabled:
                cv2.imshow('License Plate Recognition', processed_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            if plate_text:
                plates_data.append({
                    'frame': frame_count,
                    'plate_text': plate_text,
                    'authorized': authorized,
                    'timestamp': f"{frame_count/fps:.2f}s"
                })
            
            self.gate_controller.check_auto_close()
                
        cap.release()
        out.release()
        if gui_enabled:
            cv2.destroyAllWindows()
        
        if plates_data:
            pd.DataFrame(plates_data).to_csv(f"{output_dir}/plate_data.csv", index=False)
            
        self.gate_controller.close_gate()
        print(f"Processing complete. Results saved to {output_path}")

# ========== MAIN EXECUTION ==========
if __name__ == '__main__':
    # Initialize system
    system = LicensePlateSystem()
    
    # Check Arduino connection
    if system.gate_controller.serial_conn is None:
        print("Warning: Running without Arduino connection")
    
    # Process image
    image_path = r"C:\Users\siyam\Pictures\thesis_file\my\photo_13_2025-06-14_19-19-48.jpg"
    system.process_image(image_path)
    
    # OR process video/live camera
    # system.process_video(0)  # For live camera
    # system.process_video("path/to/video.mp4")  # For video file