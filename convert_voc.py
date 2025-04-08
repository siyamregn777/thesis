import os
import xml.etree.ElementTree as ET
from tqdm import tqdm

def convert_voc_to_yolo(voc_dir, output_dir, classes):
    """Convert VOC format dataset to YOLOv8 format"""
    # Create directories
    os.makedirs(os.path.join(output_dir, 'images', 'train'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'images', 'val'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'labels', 'train'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'labels', 'val'), exist_ok=True)

    # Get class mapping
    class_ids = {name: idx for idx, name in enumerate(classes)}

    # Process annotations
    for split in ['train', 'val']:
        with open(os.path.join(voc_dir, 'ImageSets', 'Main', f'{split}.txt')) as f:
            image_ids = f.read().strip().split()

        for image_id in tqdm(image_ids, desc=f'Processing {split}'):
            # Parse XML
            tree = ET.parse(os.path.join(voc_dir, 'Annotations', f'{image_id}.xml'))
            root = tree.getroot()

            # Get image dimensions
            size = root.find('size')
            width = int(size.find('width').text)
            height = int(size.find('height').text)

            # Process objects
            yolo_lines = []
            for obj in root.iter('object'):
                cls = obj.find('name').text
                if cls not in classes:
                    continue
                
                xmlbox = obj.find('bndbox')
                xmin = float(xmlbox.find('xmin').text)
                ymin = float(xmlbox.find('ymin').text)
                xmax = float(xmlbox.find('xmax').text)
                ymax = float(xmlbox.find('ymax').text)

                # Convert to YOLO format (center x, center y, width, height)
                x_center = ((xmin + xmax) / 2) / width
                y_center = ((ymin + ymax) / 2) / height
                w = (xmax - xmin) / width
                h = (ymax - ymin) / height

                yolo_lines.append(f"{class_ids[cls]} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")

            # Write label file if objects found
            if yolo_lines:
                with open(os.path.join(output_dir, 'labels', split, f'{image_id}.txt'), 'w') as f:
                    f.write('\n'.join(yolo_lines))

                # Copy image (you may need to implement this)
                src_img = os.path.join(voc_dir, 'JPEGImages', f'{image_id}.jpg')
                dst_img = os.path.join(output_dir, 'images', split, f'{image_id}.jpg')
                if os.path.exists(src_img):
                    if not os.path.exists(dst_img):
                        os.symlink(src_img, dst_img)  # or copy file

    # Create data.yaml
    data = {
        'path': os.path.abspath(output_dir),
        'train': 'images/train',
        'val': 'images/val',
        'names': {i: name for i, name in enumerate(classes)}
    }

    with open(os.path.join(output_dir, 'data.yaml'), 'w') as f:
        f.write(f"path: {data['path']}\n")
        f.write(f"train: {data['train']}\n")
        f.write(f"val: {data['val']}\n")
        f.write("names:\n")
        for i, name in enumerate(classes):
            f.write(f"  {i}: {name}\n")

if __name__ == "__main__":
    # Example usage (modify paths as needed)
    convert_voc_to_yolo(
        voc_dir="VOCdevkit/VOC2012",
        output_dir="data/voc2012_yolo",
        classes=["car", "bus", "motorbike", "person"]  # Your selected classes
    )