# Inference backend (Flask + YOLO) for Gas Cylinder Weight Detection.
#
# Multi-arch: builds on an x86 dev machine and natively on a Raspberry Pi
# (arm64 / 64-bit Raspberry Pi OS). Only the Python model server lives in here —
# the Electron UI stays on the host and talks to the published port.
FROM python:3.11-slim-bookworm

# Native libraries OpenCV (via ultralytics) and torch load at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer is cached when only the code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server and bake the model weights into the image.
COPY server.py .
COPY grayscale_text_detect_model.pt grayscale_digit_detect.pt ./

# 0.0.0.0 so the published port is reachable from the host; YOLO_CONFIG_DIR
# keeps ultralytics' settings file in a writable location.
ENV GCWD_HOST=0.0.0.0 \
    GCWD_PORT=5000 \
    OMP_NUM_THREADS=4 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics

EXPOSE 5000

CMD ["python", "server.py"]
