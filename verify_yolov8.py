from ultralytics import YOLO

# Load the YOLOv8 model (you can use 'yolov8n.pt' for the lightweight model)
model = YOLO("yolov8n.pt")  # Download this model if you don't have it yet

# Run prediction on an image (Replace "test.jpg" with the path to your test image)
model.predict(r"C:\Users\siyam\Pictures\884fee62-40db-4059-bb75-ba13b5fd6528.png", show=True)
