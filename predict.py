from ultralytics import YOLO
import cv2
import os
import numpy as np
from pathlib import Path
import easyocr
import pytesseract

# Initialize models
model = YOLO(r"C:\Users\siyam\Documents\thesis-1\content\runs\license_plate_model2\weights\best.pt")
reader = easyocr.Reader(['en'])  # English only
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Create output directory
output_dir = "extracted_text"
os.makedirs(output_dir, exist_ok=True)

def extract_text(image, is_amharic=False):
    """Extract text from image using appropriate OCR"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    if is_amharic:
        # Use Tesseract for Amharic
        text = pytesseract.image_to_string(thresh, lang='amh', config='--psm 6').strip()
    else:
        # Use EasyOCR for English/alphanumeric
        results = reader.readtext(thresh, detail=0)
        text = results[0] if results else ""
    
    return text if text else "No text detected"

def process_image(image_path):
    # Read the image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Error: Could not read image from {image_path}")
        return
    
    # Run detection
    results = model.predict(source=frame, conf=0.3)  # Lower confidence for general text
    
    # Store all detected components
    text_components = []
    
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            class_id = int(box.cls)
            
            # Extract the component image
            component_img = frame[y1:y2, x1:x2]
            
            # Determine text type based on class_id or region characteristics
            is_amharic = (class_id == 1)  # Adjust based on your model's class IDs
            
            # Extract text
            extracted_text = extract_text(component_img, is_amharic)
            
            # Store component info
            text_components.append({
                'coordinates': (x1, y1, x2, y2),
                'text': extracted_text,
                'is_amharic': is_amharic,
                'image': component_img
            })
            
            # Draw bounding box and label
            color = (0, 255, 0) if not is_amharic else (0, 0, 255)  # Green for English, Red for Amharic
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{'Amh' if is_amharic else 'Eng'}: {extracted_text[:15]}..."  # Show first 15 chars
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    # Print all extracted text to terminal
    print("\n=== EXTRACTED TEXT ===")
    for i, comp in enumerate(text_components, 1):
        lang = "Amharic" if comp['is_amharic'] else "English"
        print(f"Text {i} ({lang}): {comp['text']}")
    
    # Save individual text crops
    for i, comp in enumerate(text_components, 1):
        cv2.imwrite(f"{output_dir}/text_{i}.jpg", comp['image'])
    
    # Save annotated image
    annotated_path = f"{output_dir}/annotated_{Path(image_path).name}"
    cv2.imwrite(annotated_path, frame)
    
    # Display results
    cv2.imshow('Text Detection', frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# Process image
image_path = r"C:\Users\siyam\Pictures\images3.jpeg"
process_image(image_path)