# ==============================================================
# Burnout AI Platform - Production Dockerfile
# Optimized for Cloud Deployment (Render, Railway, Fly.io)
# ==============================================================

FROM python:3.10-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CUDA_VISIBLE_DEVICES=-1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    TF_ENABLE_ONEDNN_OPTS=0 \
    PORT=8000

# Cài đặt curl và thư viện cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency list
COPY requirements.txt .

# Cài đặt Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download DeepFace Emotion weights & Face Detection weights
# Giúp ứng dụng khởi động tức thì trên Cloud mà không cần tải mạng lúc runtime
RUN mkdir -p /root/.deepface/weights && \
    curl -L -o /root/.deepface/weights/facial_expression_model_weights.h5 \
    https://github.com/serengil/deepface_models/releases/download/v1.0/facial_expression_model_weights.h5 && \
    curl -L -o /root/.deepface/weights/deploy.prototxt \
    https://github.com/opencv/opencv/raw/3.4.0/samples/dnn/face_detector/deploy.prototxt && \
    curl -L -o /root/.deepface/weights/res10_300x300_ssd_iter_140000.caffemodel \
    https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel

# Copy toàn bộ source code
COPY . .

# Expose port (Render sẽ tự động gắn cổng thông qua $PORT)
EXPOSE 8000

# Chạy với 1 worker để tiết kiệm RAM trên Cloud (TensorFlow chiếm ~350MB RAM)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

