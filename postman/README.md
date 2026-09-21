# Postman Test - Burnout AI Platform

Test collection cho flow phân tích emotion qua ảnh.

## Cấu trúc

```
postman/
├── burnout-ai-platform.postman_collection.json  # Collection 9 requests
├── burnout-ai-platform.postman_environment.json # Environment dev
└── README.md                                     # File này
```

## Auth thay đổi

Trước đây dùng Firebase Auth REST API (email/password) → **đã bỏ**.
Giờ dùng **custom JWT HS256** (username/password) tự build:

- `POST /api/auth/signup` → user tự đăng ký (email REQUIRED) → trả JWT.
- `POST /api/auth/login` → verify user/pass → trả JWT.
- `POST /api/auth/bootstrap-admin` → tạo admin ĐẦU TIÊN (1 lần duy nhất).
- `POST /api/auth/admin/create-user` → admin tạo user (full_name REQUIRED, email optional).
- `GET /api/auth/me` → verify JWT → trả thông tin user.

**Flow khởi tạo lần đầu (DB rỗng)**:

1. Request 1.0 → `bootstrap-admin` tạo admin đầu tiên (cần email).
2. Request 1.1 → `login` để lấy token.
3. Request 1.4 → admin dùng token tạo user mới (không cần email).

## Setup (1 lần)

### 1. Import vào Postman

- Mở Postman → **Import** → chọn 2 file JSON trong folder này.
- Chọn environment **"burnout-ai-platform (dev)"** ở dropdown góc trên phải.

### 2. Chuẩn bị 4 file test ảnh

Đặt tại đường dẫn dễ nhớ (vd `C:/test_images/`):

| File            | Yêu cầu                  | Cách tạo                                                                   |
| --------------- | ------------------------ | -------------------------------------------------------------------------- |
| `test_face.jpg` | 500x500 px, khuôn mặt rõ | Chụp selfie / dùng ảnh mẫu                                                 |
| `big_file.jpg`  | > 5MB                    | Python: `Image.new('RGB', (3000, 3000)).save('big_file.jpg', quality=100)` |
| `4k_image.jpg`  | 3840x2160 px             | `Image.new('RGB', (3840, 2160)).save('4k_image.jpg')`                      |
| `any.pdf`       | PDF bất kỳ               | Tải / tạo PDF mẫu                                                          |

### 3. Update environment variables

Mở environment **"burnout-ai-platform (dev)"** và sửa:

| Variable               | Giá trị mặc định               | Ghi chú                                           |
| ---------------------- | ------------------------------ | ------------------------------------------------- |
| `base_url`             | `http://localhost:8000`        | URL server                                        |
| `admin_username`       | `admin`                        | Username cho admin đầu tiên                       |
| `admin_password`       | `ChangeMe123!`                 | Password (>= 6 ký tự, khuyến nghị mạnh)           |
| `admin_email`          | `admin@burnout.local`          | Email cho admin đầu tiên (bắt buộc cho bootstrap) |
| `test_image_path`      | `C:/test_images/test_face.jpg` |                                                   |
| `oversized_image_path` | `C:/test_images/big_file.jpg`  |                                                   |
| `huge_image_path`      | `C:/test_images/4k_image.jpg`  |                                                   |
| `test_pdf_path`        | `C:/test_images/any.pdf`       |                                                   |

## Chạy server

```bash
cd burnout-ai-platform
# Đảm bảo .env đã có GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_API_KEY, R2_*, JWT_SECRET
uvicorn main:app --reload
```

Server chạy tại `http://localhost:8000`.

**JWT_SECRET bắt buộc** — generate bằng:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Chạy collection

Trong Postman:

1. Chọn collection **"Burnout AI Platform - Emotion API"**.
2. Bấm **Run** (hoặc click phải → **Run collection**).
3. Bấm **Run Burnout AI Platform - Emotion API**.

## Request flow

```
1.0 Bootstrap admin đầu tiên (chạy 1 lần duy nhất khi DB rỗng)
   ↓ (lưu id_token với role=admin, user_id)
1.1 Login admin (verify credentials)
   ↓
1.2 GET /api/auth/me (verify token, role=admin)
   ↓
1.3 Login sai password (expect 401)
   ↓
1.4 Admin create user nhan_vien_01 (dùng admin token)
   ↓ (lưu created_user_id)
1.5 Non-admin gọi admin endpoint (expect 403)
   ↓
2.1 GET /health (verify server alive)
   ↓
3.1 Analyze ảnh OK ← happy path
   ↓ (lưu last_request_id, last_image_key)
3.2 Analyze không có token ← expect 401
3.3 Analyze file > 5MB ← expect 413
3.4 Analyze ảnh > 1920x1080 ← expect 413
3.5 Analyze file PDF ← expect 400
   ↓
4.1 DELETE image ← cleanup R2 + Firestore
```

## Test assertions mỗi request

### 1.0 Signup (200 OK hoặc 400 "da ton tai")

- 200: có `access_token`, `user.id`, `user.username == "admin"`.
- 400: detail chứa "da ton tai" → OK skip, tiếp tục flow.

### 1.1 Login (200 OK)

- `access_token` không rỗng
- `token_type == "bearer"`
- `expires_in_hours > 0`
- `user.username == "admin"`

### 1.2 GET /me (200 OK)

- `id == user_id`
- `username == "admin"`

### 1.3 Login sai password (401)

- Status 401

### 3.1 Happy Path (200 OK)

- `request_id` không rỗng
- `emotion.dominant_emotion` ∈ 7 emotion
- `emotion.confidence` ∈ [0, 1]
- `emotion.emotions` có đúng 7 field
- `saved_to_r2` = `true`
- `image_url` chứa `X-Amz-` (presigned URL)
- Nếu `generate_ai=true` → `assessment.risk_level` ∈ {low, medium, high}

### 3.2 No Auth (401)

- Status 401

### 3.3 Oversize file (413)

- Status 413
- Detail chứa "MB" hoặc "bytes"

### 3.4 Oversize resolution (413)

- Status 413
- Detail chứa "Resolution" hoặc "pixels"

### 3.5 Wrong content type (400)

- Status 400
- Detail chứa "Unsupported"

### 4.1 DELETE image (200 hoặc 404)

- Status 200 hoặc 404

## Kết quả mong đợi (Full pass)

```
✓ 1.0 Bootstrap admin         → 200 (lần đầu) hoặc 409 (đã có admin)
✓ 1.1 Login admin              → 200, có access_token (role=admin)
✓ 1.2 GET /me                  → 200
✓ 1.3 Login sai password       → 401
✓ 1.4 Admin create user        → 200, tạo nhan_vien_01 thành công
✓ 1.5 Non-admin gọi admin API  → 403
✓ 2.1 GET /health              → 200
✓ 3.1 Analyze happy path       → 200, có emotion + assessment + image_url
✓ 3.2 No auth                  → 401
✓ 3.3 Oversize file            → 413
✓ 3.4 Oversize resolution      → 413
✓ 3.5 Wrong content type       → 400
✓ 4.1 DELETE image             → 200 hoặc 404
```

## Troubleshooting

| Lỗi                                | Nguyên nhân                                 | Cách sửa                                                 |
| ---------------------------------- | ------------------------------------------- | -------------------------------------------------------- |
| 1.0 Signup 400 "qữa ngan"          | Password < MIN_PASSWORD_LENGTH (mặc định 6) | `123456` đã OK; đổi admin_password nếu cần               |
| 1.0 Signup 400 "đã tồn tại"        | User đã tạo lần trước                       | OK — request vẫn pass (auto-skip), chuyển sang 1.1 Login |
| 1.1 Login 401                      | Sai username/password                       | Sửa `admin_password` trong env                           |
| 3.1 401 Unauthorized               | Token hết hạn (24h) hoặc chưa chạy 1.0/1.1  | Re-run 1.0 Signup hoặc 1.1 Login                         |
| 3.1 401 với token hợp lệ           | Server mới restart nhưng `JWT_SECRET` đổi   | Đảm bảo `.env` không đổi giữa các lần restart            |
| 3.1 500 "FIREBASE not init"        | Thiếu service account JSON                  | Check `GOOGLE_APPLICATION_CREDENTIALS`                   |
| 3.1 200 nhưng `assessment: null`   | Gemini fail                                 | Check `GOOGLE_API_KEY`                                   |
| 3.1 200 nhưng `saved_to_r2: false` | R2 fail                                     | Check `R2_*` env                                         |

## Test với Newman (CLI)

```bash
npm install -g newman
newman run burnout-ai-platform.postman_collection.json \
  -e burnout-ai-platform.postman_environment.json
```

Có thể dùng trong CI/CD.

## Tạo admin user thủ công

Nếu không muốn dùng Postman, có thể tạo user qua curl:

```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_hours": 24,
  "user": {
    "id": "abc123",
    "username": "admin",
    "created_at": "2026-08-03T10:00:00Z",
    "last_login_at": null
  }
}
```
