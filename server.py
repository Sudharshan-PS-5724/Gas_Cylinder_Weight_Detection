import os
from ultralytics import YOLO
import cv2
from flask import Flask, request, jsonify

app = Flask(__name__)

# Resolve paths relative to this file so the server runs from any working
# directory and inside a container (no machine-specific absolute paths).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Model weights are looked up next to this file by default, but can be
# overridden with environment variables (handy for Docker / custom layouts).
model_path = os.environ.get(
    "GCWD_TEXT_MODEL", os.path.join(BASE_DIR, "grayscale_text_detect_model.pt")
)
digit_model_path = os.environ.get(
    "GCWD_DIGIT_MODEL", os.path.join(BASE_DIR, "grayscale_digit_detect.pt")
)

# Writable scratch space for the uploaded frame and the cropped ROIs.
work_dir = os.environ.get("GCWD_TMP", BASE_DIR)
image_path = os.path.join(work_dir, "temp_image.jpg")
output_dir = os.path.join(work_dir, "cropped_images")

# Load models once at startup (not per request).
model = YOLO(model_path)
digit_model = YOLO(digit_model_path)


@app.route("/health", methods=["GET"])
def health():
    # Used by run.py to know when the backend is ready to accept requests.
    return jsonify({"status": "ok"})


@app.route('/predict', methods=['POST'])
def predict():
    data = request.files['image']
    data.save(image_path)

    # Call the function that processes the image
    response = process_image(image_path)

    return jsonify(response)


def process_image(image_path):
    try:
        # Decode the frame once and reuse it for detection and cropping.
        image = cv2.imread(image_path)
        if image is None:
            return {"error": "Image not found or cannot be read."}

        # Run text detection model
        results = model(image, verbose=False)
        preds = []
        confidences = []

        os.makedirs(output_dir, exist_ok=True)

        for result in results:
            boxes = result.boxes

            roi_paths = []
            for i, box in enumerate(boxes.xyxy):
                x1, y1, x2, y2 = map(int, box)
                if x2 <= x1 or y2 <= y1:
                    continue
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
                roi_paths.append(new_path)

            # A top view of the cylinder shows the weight stamped in ~3 places,
            # so we read up to 3 text regions and later pick the best-of-2
            # majority (or the highest-confidence one). The text model returns
            # boxes highest-confidence first, so roi_paths[:3] keeps the same
            # top-3 the old code used — but without crashing when the model
            # finds fewer than three (the old range(3) read missing files).
            text_files = [cv2.imread(p) for p in roi_paths[:3]]
            text_files = [t for t in text_files if t is not None]
            if not text_files:
                continue

            digit_res = digit_model(text_files, verbose=False)

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


def main():
    # Host/port are configurable so the same file works natively and in Docker.
    # Default host is 0.0.0.0 so a container can publish the port to the host;
    # run.py passes 127.0.0.1 for local runs to keep it off the network.
    host = os.environ.get("GCWD_HOST", "0.0.0.0")
    port = int(os.environ.get("GCWD_PORT", "5000"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
