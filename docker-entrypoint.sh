#!/bin/bash
# ===============================================================
# Docker Entrypoint - Preload DeepFace models on startup
# ===============================================================

set -e

echo "=========================================="
echo "Burnout AI Platform - Starting..."
echo "=========================================="

# Suppress TensorFlow oneDNN warnings
export TF_ENABLE_ONEDNN_OPTS=0

# Preload DeepFace models
PRELOAD_MARKER="/root/.deepface/weights/.preloaded"
if [ ! -f "$PRELOAD_MARKER" ]; then
    echo "⚠ First startup detected - downloading DeepFace models..."

    python3 << 'PYEOF'
import os
import warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

try:
    from deepface import DeepFace

    # Preload all models needed for emotion analysis
    print("  Downloading emotion model...")
    DeepFace.build_model(model_name="Emotion")

    print("  Downloading age model...")
    DeepFace.build_model(model_name="Age")

    print("  Downloading gender model...")
    DeepFace.build_model(model_name="Gender")

    # Create marker file
    with open("/root/.deepface/weights/.preloaded", "w") as f:
        f.write("preloaded\n")

    print("✓ DeepFace models setup complete!")

except Exception as e:
    print(f"⚠ DeepFace preload warning: {e}")
    print("  Models will be downloaded on first use (slower first request)")
PYEOF

    echo "=========================================="
else
    echo "✓ DeepFace models already preloaded"
fi

echo "✓ Starting FastAPI server..."
echo "=========================================="

# Execute the CMD
exec "$@"
