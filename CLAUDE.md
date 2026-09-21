# Claude Code - Project Guidelines

## 🤖 Quy tắc bảo mật (BẮT BUỘC)

### 🚫 TUYỆT ĐỐI KHÔNG COMMIT CÁC FILE SAU

**Secrets & Keys:**

- `config/serviceAccountKey.json` - Firebase service account key
- `config/*.json` - Tất cả JSON config files trong config/
- `.env` - Environment variables
- `.env.*` - Bất kỳ .env file nào
- `*.pem`, `*.key` - Private keys
- `credentials.json`, `secrets.json` - Secrets files
- `gcloud-*.json` - GCP credentials
- `*.secret*` - Files chứa secret trong tên

**Cách kiểm tra trước khi commit:**

```bash
git status
# Kiểm tra KHÔNG có file nào ở trên
```

**Nếu lỡ commit secret:**

1. Xoá ngay lập tức: `git rm --cached <file>`
2. Rotate/revoke key đó ngay
3. Thông báo cho team

---

## 📝 Quy tắc Code (BẮT BUỘC)

### ✅ Code phải Clean

1. **Xóa test/debug code trước khi commit**

   - Không để `print()` debug
   - Không để comment code thừa
   - Không để TODO chưa xong (trừ khi có ghi chú rõ)

2. **Không để code chết (dead code)**

   - Xóa function không dùng
   - Xóa import không dùng
   - Xóa file rỗng hoặc chỉ có comment

3. **Test endpoints = test xong xóa ngay**

   - Endpoint `/test/*` chỉ dùng để test trong quá trình dev
   - Xóa trước khi commit hoặc đánh dấu `@app.post("/test/..."` với comment `# TODO: Remove before production`

4. **Kiểm tra trước commit:**

   ```bash
   # Tìm test endpoints còn sót
   grep -r "/test/" app/

   # Tìm print() debug còn sót
   grep -r "print(" app/
   ```

---

## 📁 Cấu trúc Project

```
burnout-ai-platform/
├── app/
│   ├── models/          # Pydantic models (domain)
│   ├── core/            # Core services (firebase, config)
│   └── routes/          # API endpoints
├── external/deepface/   # DeepFace SDK (embedded)
├── config/              # Config files (SECRETS - never commit)
├── uploads/             # User uploads (optional, gitkeep)
└── main.py              # Entry point
```

---

## 🛠️ Commands

### Development

```bash
# Chạy app
python main.py

# Hoặc
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

<!-- Hoặc -->
<!-- .\.venv\Scripts\uvicorn.exe main:app --reload --port 8000 -->

### Dependencies

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Cài ML dependencies (TensorFlow + DeepFace)
pip install -r requirements-ml.txt

# Firebase setup
# 1. Download serviceAccountKey.json from Firebase Console
# 2. Put in config/serviceAccountKey.json
# 3. Set GOOGLE_APPLICATION_CREDENTIALS in .env
```

### Docker Commands (Chi tiết)

#### Start/Stop

```bash
# Start all services
docker compose up -d

# Stop (giữ data)
docker compose down

# Stop + XÓA toàn bộ data (cẩn thận)
docker compose down -v
```

#### Rebuild khi có thay đổi

```bash
# Rebuild tự động khi code thay đổi
docker compose up -d --build

# Rebuild không dùng cache
docker compose build --no-cache
docker compose up -d

# Rebuild chỉ server (khi đổi Dockerfile/requirements)
docker compose build server
docker compose up -d
```

#### Logs & Debug

```bash
# Xem server logs
docker compose logs -f server

# Xem Qdrant logs
docker compose logs -f qdrant

# Shell vào container
docker exec -it burnout_server bash

# Xem container status
docker compose ps
```

#### Xem Qdrant DB

Mở browser → **http://localhost:6333/dashboard**

Dashboard có thể:

- Xem list collections (`burnout_case_memory`, `burnout_knowledge`)
- Inspect points + payload (emotion_id, dominant_emotion, risk_level, ...)
- Search thử với vector
- Xem cluster info, GPU usage

Nếu dashboard không truy cập được:

```bash
docker compose ps   # phải thấy "Up (healthy)"
curl http://localhost:6333/healthz  # trả "healthz check passed"
```

---

## 🐳 Docker Setup

### Cấu trúc Docker

```
├── Dockerfile              # Docker image definition
├── docker-compose.yml     # Multi-service orchestration
├── docker-entrypoint.sh   # Startup script (downloads DeepFace models)
├── app/                   # Source code
├── external/deepface/    # DeepFace SDK (embedded)
├── config/               # Config files (SECRETS - never commit)
├── requirements.txt       # Python dependencies
└── requirements-ml.txt   # ML dependencies (DeepFace)
```

### First Startup (Lần đầu)

Lần đầu chạy, container sẽ tải DeepFace models (~1-3 phút):

```
⚠ First startup detected - downloading DeepFace models...
✓ RetinaFace model ready!
✓ Emotion model ready!
✓ DeepFace models setup complete!
```

### Deploy lên Server Online

```bash
# 1. Pull code mới
git pull origin main

# 2. Rebuild image trên server
docker compose build --no-cache

# 3. Restart với image mới
docker compose up -d

# 4. Monitor logs
docker compose logs -f server

# 5. Health check
curl http://localhost:8000/health
```

### Emergency Recovery

```bash
# Server không khởi động được
docker compose down
docker rmi burnout-ai-platform-server
docker compose up -d --build
docker compose logs --tail=200 server

# Reset Qdrant
docker compose down -v
docker compose up -d

# Full reset
docker compose down -v --rmi local
docker system prune -af
docker compose up -d --build
```

---

## 📝 Ghi chú

- Project dùng Firebase Firestore làm database chính
- Frontend là React app riêng (không trong repo này)
- DeepFace được embed trong `external/deepface/`
