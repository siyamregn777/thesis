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

class ArduinoGateController:
    def __init__(self, port='COM4', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.gate_status = False
        self.last_open_time = 0
        self.gate_open_duration = 5000
        self.connect()
        
    def connect(self):
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            print(f"Connected to Arduino on {self.port}")
            self.close_gate()
        except Exception as e:
            print(f"Arduino connection error: {e}")
            self.serial_conn = None
    
    def control_gate(self, open_gate):
        if not self.serial_conn:
            print("No Arduino connection!")
            return False
            
        try:
            if open_gate and not self.gate_status:
                self.serial_conn.write(b'1')
                self.gate_status = True
                self.last_open_time = time.time() * 1000
                print("Gate opened")
            elif not open_gate and self.gate_status:
                self.serial_conn.write(b'0')
                self.gate_status = False
                print("Gate closed")
            return True
        except Exception as e:
            print(f"Gate control error: {e}")
            return False
    
    def check_auto_close(self):
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

class LicensePlateSystem:
    def __init__(self):
        torch.serialization.add_safe_globals([Conv, DetectionModel])
        
        self.plate_model = YOLO(r"C:\Users\siyam\Documents\thesis-1\content\runs\license_plate_model2\weights\best.pt")
        self.vehicle_model = YOLO("yolov8n.pt")
        self.reader = easyocr.Reader(['en'], gpu=False)
        
        self.gate_controller = ArduinoGateController(port='COM4')
        
        self.vehicle_classes = [2, 3, 5, 7]
        self.plate_confidence = 0.6
        self.api_url = "http://localhost:5000"
        
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

    def preprocess_plate(self, plate_img):
        try:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            _, thresh1 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            thresh2 = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 11, 2)
            combined = cv2.bitwise_or(thresh1, thresh2)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            cleaned = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
            return cleaned
        except Exception as e:
            print(f"Preprocessing error: {e}")
            return plate_img

    def extract_plate_text(self, plate_img):
        best_result = ""
        max_confidence = 0
        
        processed_images = [
            self.preprocess_plate(plate_img),
            cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY),
            cv2.threshold(cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        ]
        
        for img in processed_images:
            results = self.reader.readtext(img, detail=1,
                                         allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                                         width_ths=2.0, height_ths=1.0)
            
            for result in results:
                text, confidence = result[1], result[2]
                if confidence > max_confidence and len(text) >= 3:
                    best_result = text.upper()
                    max_confidence = confidence
        
        return best_result if best_result else ""

    def check_authorization(self, plate_text):
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

    def process_frame(self, frame, debug=False):
        if debug and self.gui_enabled:
            cv2.imshow("Original Frame", frame)
            cv2.waitKey(1)
        
        vehicle_results = self.vehicle_model(frame, verbose=False)
        vehicle_detected = any(int(box.cls) in self.vehicle_classes 
                             for result in vehicle_results 
                             for box in result.boxes if box.conf > 0.5)
        
        if not vehicle_detected:
            self.gate_controller.close_gate()
            if debug:
                print("No valid vehicle detected")
            return frame, "", False
        
        plate_results = self.plate_model(frame, conf=self.plate_confidence, verbose=False)
        authorized = False
        
        for result in plate_results:
            annotated_frame = result.plot()
            
            for box in result.boxes:
                if box.conf < self.plate_confidence:
                    continue
                    
                x1, y1, x2, y2 = map(int, box.xyxy.cpu().numpy()[0])
                plate_img = frame[y1:y2, x1:x2]
                
                if debug and self.gui_enabled:
                    cv2.imshow("Plate ROI", plate_img)
                    cv2.waitKey(1)
                
                plate_text = self.extract_plate_text(plate_img)
                
                if plate_text:
                    if debug:
                        print(f"Raw OCR result: {plate_text}")
                    
                    clean_text = ''.join(c for c in plate_text if c.isalnum()).upper()
                    
                    if len(clean_text) < 3:
                        continue
                        
                    if debug:
                        print(f"Cleaned plate: {clean_text}")
                    
                    authorized = self.check_authorization(clean_text)
                    status = "AUTHORIZED" if authorized else "UNAUTHORIZED"
                    color = (0, 255, 0) if authorized else (0, 0, 255)
                    
                    cv2.putText(annotated_frame, f"{clean_text} - {status}", 
                               (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.9, color, 2)
                    
                    if authorized:
                        self.gate_controller.open_gate()
                    else:
                        self.gate_controller.close_gate()
                    
                    return annotated_frame, clean_text, authorized
        
        self.gate_controller.close_gate()
        if debug:
            print("No valid license plates detected")
        return frame, "", False

    def process_image(self, image_path, output_dir='output', debug=False):
        Path(output_dir).mkdir(exist_ok=True)
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Error loading image: {image_path}")
            return False
            
        processed_frame, plate_text, authorized = self.process_frame(frame, debug)
        
        output_path = f"{output_dir}/{Path(image_path).stem}_processed.jpg"
        cv2.imwrite(output_path, processed_frame)
        
        print(f"Processing complete. Gate status: {'OPEN' if authorized else 'CLOSED'}")
        print(f"Detected plate: {plate_text if plate_text else 'None'}")
        
        self.gate_controller.check_auto_close()
        return authorized

    def process_video(self, video_path, output_dir='output', frame_skip=3, debug=False):
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
                
            processed_frame, plate_text, authorized = self.process_frame(frame, debug)
            out.write(processed_frame)
            
            if self.gui_enabled:
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
        if self.gui_enabled:
            cv2.destroyAllWindows()
        
        if plates_data:
            pd.DataFrame(plates_data).to_csv(f"{output_dir}/plate_data.csv", index=False)
            
        self.gate_controller.close_gate()
        print(f"Processing complete. Results saved to {output_path}")

if __name__ == '__main__':
    system = LicensePlateSystem()
    
    if system.gate_controller.serial_conn is None:
        print("Warning: Running without Arduino connection")
    
    image_path = r"C:\Users\siyam\Pictures\thesis_file\my\photo_13_2025-06-14_19-19-48.jpg"
    system.process_image(image_path, debug=True)