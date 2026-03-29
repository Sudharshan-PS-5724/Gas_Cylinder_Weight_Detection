import sys
import json
from ultralytics import YOLO
import cv2
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.files['image']
    image_path = 'temp_image.jpg'
    data.save(image_path)
    
    # Call the function that processes the image
    response = process_image(image_path)
    
    return jsonify(response)

# Load models once
model_path = r"C:\Users\suraj\Downloads\gcdnew_final\gcd\grayscale_text_detect_model.pt"
digit_model_path = r"C:\Users\suraj\Downloads\gcdnew_final\gcd\grayscale_digit_detect.pt"

model = YOLO(model_path)
digit_model = YOLO(digit_model_path)

def process_image(image_path):
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"error": "Image not found or cannot be read."}
        img = cv2.resize(img, (640, 640))
        
        # Run text detection model
        results = model(image_path)
        preds = []
        confidences = []
        
        output_dir = 'cropped_images'
        os.makedirs(output_dir, exist_ok=True)
        
        for result in results:
            boxes = result.boxes
            image = cv2.imread(image_path)
            
            for i, box in enumerate(boxes.xyxy):
                x1, y1, x2, y2 = map(int, box)
                w_h_ratio = (x2 - x1) / (y2 - y1)
                roi = image[y1:y2, x1:x2]
                
                if w_h_ratio >= 1.33 and (y1 + y2) / 2 <= 320:
                    roi = cv2.rotate(roi, cv2.ROTATE_180)
                elif w_h_ratio < 1.33 and (x1 + x2) / 2 > 320:
                    roi = cv2.rotate(roi, cv2.ROTATE_90_CLOCKWISE)
                elif w_h_ratio < 1.33 and (x1 + x2) / 2 <= 320:
                    roi = cv2.rotate(roi, cv2.ROTATE_90_COUNTERCLOCKWISE)
                roi = cv2.resize(roi, (640, 640))
                
                new_path = os.path.join(output_dir, f'roi_{i}.jpg')
                cv2.imwrite(new_path, roi)

            # Read the cropped images before running digit model
            text_files = [cv2.imread(os.path.join(output_dir, f'roi_{i}.jpg')) for i in range(3)]
            
            digit_res = digit_model(text_files)
            
            for dig_res in digit_res:
                digit_1, digit_2, digit_3 = '', '', ''
                d_boxes = dig_res.boxes
                d_conf = dig_res.boxes.conf
                d_cls = dig_res.boxes.cls
                d_x_coord = []
                
                for d_box in d_boxes.xyxy:
                    dx1, dy1, dx2, dy2 = map(int, d_box)
                    d_x_coord.append(dx1)
                
                digit_map = []
                for j in range(len(d_boxes)):
                    digit_map.append((d_x_coord[j], int(d_cls[j]), float(d_conf[j])))

                # Sort and assign digits
                digit_map.sort(key=lambda x: x[0])
                if len(digit_map) > 0:
                    digit_1 = str(digit_map[0][1])
                if len(digit_map) > 1:
                    digit_2 = str(digit_map[1][1])
                if len(digit_map) > 2:
                    digit_3 = str(digit_map[2][1])
                
                if digit_1 and digit_2 and digit_3:
                    prediction = digit_1 + digit_2 + "." + digit_3
                    preds.append(prediction)
                    confidences.append(sum([digit_map[k][2] for k in range(3)]) / 3)
            
            # Cleanup: Remove temporary cropped images
            for file_path in os.listdir(output_dir):
                file = os.path.join(output_dir, file_path)
                if os.path.exists(file):
                    os.remove(file)

        valid_preds = [pred.replace('.', '') for pred in preds if 150 <= float(pred.replace('.', '')) <= 199]
        
        if valid_preds:
            majority_pred = max(set(valid_preds), key=valid_preds.count)
            majority_count = valid_preds.count(majority_pred)
            if majority_count >= 2:
                final_prediction = majority_pred
            else:
                highest_conf_pred = valid_preds[confidences.index(max(confidences))]
                final_prediction = highest_conf_pred
        else:
            final_prediction = "Couldn't be read"
        
        return {"prediction": final_prediction}
    
    except Exception as e:
        return {"error": str(e)}

def main(): app.run(host='127.0.0.1', port=5000)

if __name__ == "__main__": main()