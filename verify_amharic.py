import cv2
import pytesseract
import numpy as np

# Configure Tesseract path (if not in system PATH)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_ethiopian_plate(image_path):
    """Special processing for Ethiopian license plates"""
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Image not found at {image_path}")
        
        # Convert to LAB color space
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a, b = cv2.split(lab)
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l_channel)
        
        # Merge channels and convert back to BGR
        limg = cv2.merge((cl,a,b))
        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        
        # Convert to grayscale and threshold
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return thresh
    
    except Exception as e:
        print(f"Preprocessing error: {e}")
        return None

def recognize_amharic_plate(image_path):
    try:
        processed = preprocess_ethiopian_plate(image_path)
        if processed is None:
            return None
        
        # OCR with both Amharic and English
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed, lang='amh+eng', config=custom_config)
        
        # Clean and format the output
        allowed_chars = set('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZአኡኢኣኤእኦኧከኩኪካኬክኮኯ')  # Add more Amharic chars as needed
        cleaned_text = ''.join(c for c in text if c.upper() in allowed_chars or c.isspace())
        
        print("Raw OCR Output:", text)
        print("Cleaned Plate:", cleaned_text.strip())
        
        # Display processed image
        cv2.imshow("Processed Plate", processed)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return cleaned_text.strip()
    
    except Exception as e:
        print(f"Recognition error: {e}")
        return None

if __name__ == "__main__":
    image_path = r"C:\Users\siyam\Desktop\New folder\download.png"  # Change to your image path
    plate_text = recognize_amharic_plate(image_path)
    print("\nFinal Recognized Plate:", plate_text)