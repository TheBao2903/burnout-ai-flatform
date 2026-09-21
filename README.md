# 🔥 Burnout AI Platform

> Nền tảng AI phân tích và đánh giá mức độ kiệt sức (burnout) của người dùng thông qua kết hợp phân tích cảm xúc khuôn mặt (DeepFace), khảo sát sinh lý/công việc, trò chuyện tư vấn tâm lý (RAG Chat), và hệ thống gợi ý địa điểm thư giãn (Geoapify + Open-Meteo).

---

## 📋 MỤC LỤC

- [Tổng quan](#-tổng-quan)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Quy trình hoạt động](#-quy-trình-hoạt-động)
- [Các chỉ số đo & Công thức (Summary)](#-các-chỉ-số-đo--công-thức-summary)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
- [Cài đặt & Khởi động Server](#-cài-đặt--khởi-động-server)
- [API Endpoints](#-api-endpoints)
- [Dữ liệu mẫu](#-dữ-liệu-mẫu)
- [Tài liệu kỹ thuật chi tiết](#-tài-liệu-kỹ-thuật-chi-tiết)

---

## 🎯 TỔNG QUAN

### Mục tiêu

Phát hiện sớm và đánh giá mức độ burnout của người dùng thông qua phân tích đa chiều:

- **Cảm xúc khuôn mặt** → Phân tích biểu cảm từ ảnh/frame chụp webcam (7 cảm xúc qua DeepFace SDK).
- **Khảo sát sinh lý & công việc** → Giấc ngủ, số giờ làm việc, làm thêm (OT), áp lực deadline, nhịp tim.
- **Chatbot tư vấn tâm lý** → Phân tích ngôn ngữ, trích xuất tín hiệu né việc, cảm xúc tiêu cực và stress từ văn bản hội thoại.
- **Khuyến nghị & Tìm kiếm địa điểm** → Đề xuất thói quen, bài tập và tìm kiếm các địa điểm thư giãn thực tế (công viên, quán cafe, gym) theo tọa độ GPS & điều kiện thời tiết.

### Output JSON mẫu

```json
{
  "id": "burnout_result_001",
  "assessment_id": "asm_xyz789",
  "user_id": "user_123",
  "engine_version": "v2.1",
  "burnout_score": 72.5,
  "risk_level": "high",
  "confidence": 1.0,
  "data_completeness": 0.85,
  "trend": "increasing",
  "factors": [
    {
      "factor": "sleep",
      "score": 95.0,
      "weight": 0.30,
      "contribution": 28.5,
      "details": { "sleep_hours": 4.5, "label": "Thiếu ngủ" }
    },
    {
      "factor": "workload",
      "score": 75.0,
      "weight": 0.25,
      "contribution": 18.75,
      "details": { "working_hours": 11.0, "label": "Công việc quá tải" }
    },
    {
      "factor": "stress",
      "score": 60.0,
      "weight": 0.20,
      "contribution": 12.0,
      "details": { "survey_stress": 7, "label": "Stress cao" }
    }
  ],
  "recommendations": [
    {
      "type": "behavior",
      "priority": "high",
      "title": "Cải thiện giấc ngủ",
      "description": "Đặt mục tiêu ngủ 7-8 tiếng mỗi đêm để khôi phục sức khỏe tâm lý."
    }
  ],
  "analyzed_at": "2026-09-21T10:15:00Z"
}
```

---

## 🏗️ KIẾN TRÚC HỆ THỐNG

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT / MOBILE APP                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI)                     │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │
│ │  Emotion API │ │  Survey API  │ │   Chat API   │ │ Admin API│ │
│ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────┬─────┘ │
└────────┼────────────────┼────────────────┼─────────────┼────────┘
         │                │                │             │
         ▼                ▼                ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BURNOUT ENGINE (AI Core)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Pure Function Engine (clean architecture)                │   │
│  │ Input: EmotionAggregate + SurveyData + ChatAggregate     │   │
│  │ Process: Calculate Sub-Scores -> Normalize Weights ->    │   │
│  │ Output: BurnoutResult + Risk Level + Recommendations     │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬────────────────┬────────────────┬─────────────┬────────┘
         │                │                │             │
         ▼                ▼                ▼             ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐
│  DeepFace SDK   │ │  Qdrant Vector  │ │  Google Gemini  │ │ Firestore DB │
│(Face Analysis)  │ │ (RAG & Memory)  │ │ (AI Studio SDK) │ │ (Persistence)│
└─────────────────┘ └─────────────────┘ └─────────────────┘ └──────────────┘
```

---

## 🔄 QUY TRÌNH HOẠT ĐỘNG

```
1. Collect Emotion (Webcam/Image)  ─┐
2. Submit Survey (Sleep, Work)     ──┼──→ Assessment Session ──→ Burnout Engine ──→ BurnoutResult & Recommendations
3. Chat Conversation (RAG/Signals) ─┘
```

---

## 📊 CÁC CHỈ SỐ ĐO & CÔNG THỨC (SUMMARY)

> 📖 **Xem tài liệu kỹ thuật đầy đủ tại**: [docs/SYSTEM_SPEC_AND_METRICS.md](file:///d:/Projects/DeepFace/burnout-ai-platform/docs/SYSTEM_SPEC_AND_METRICS.md)

### 1. Phân Cấp Nguy Cơ Burnout (Risk Levels)
Mã nguồn tại [weights.py](file:///d:/Projects/DeepFace/burnout-ai-platform/app/modules/burnout/helpers/weights.py#L32-L55):

- **`low` (Thấp)**: `burnout_score < 40.0`
- **`medium` (Trung bình)**: `40.0 <= burnout_score < 60.0`
- **`high` (Cao)**: `60.0 <= burnout_score < 80.0`
- **`critical` (Nghiêm trọng)**: `burnout_score >= 80.0`
- **`insufficient_data`**: Khi không đủ dữ liệu đánh giá.

### 2. Bảng Trọng Số Yếu Tố chuẩn (Base Factor Weights)
Mã nguồn tại [weights.py](file:///d:/Projects/DeepFace/burnout-ai-platform/app/modules/burnout/helpers/weights.py#L17-L25):

| Factor | Weight (%) | Nguồn dữ liệu | Công thức điểm thành phần (Sub-Score) |
| :--- | :--- | :--- | :--- |
| **`sleep`** | **30% (0.30)** | Survey | `>=8h`: 0 điểm; `7-8h`: `(7-h)*50`; `4-7h`: `50+(7-h)*16.67`; `<4h`: `min(100, 50+(4-h)*25)` |
| **`workload`** | **25% (0.25)** | Survey | `Working Hours (70%) + Deadline (30%)`. `<=8h`: 0, `>=12h`: 100, `8-12h`: `((h-8)/4)*100`. Deadline: `low`=0, `med`=25, `high`=75, `ext`=100. |
| **`stress`** | **20% (0.20)** | Survey + Chat | `Survey Stress (60%) + Chat Stress (40%)`. Survey: `(level - 1) / 9 * 100`. |
| **`emotion`** | **15% (0.15)** | DeepFace | `negative_ratio * 100`. (Tiêu cực = `sad` + `fear` + `angry` + `disgust`). |
| **`behavior`** | **10% (0.10)** | Trend / Chat | Historical Trend (`increasing`: +15, `decreasing`: -10, `stable`: 0) hoặc Chat signals fallback: `(avoidance*0.4 + burnout*0.4 + emotional*0.2)`. |

*Hệ thống tự động dùng **Dynamic Weight Normalization** chia lại trọng số khi thiếu 1 số yếu tố để tổng trọng số luôn bằng 100%.*

### 3. Trọng số Độ Hoàn Thiện Dữ Liệu (`data_completeness`)
Mã nguồn tại [completeness.py](file:///d:/Projects/DeepFace/burnout-ai-platform/app/modules/burnout/helpers/completeness.py):
- `emotion`: 30%
- `survey`: 30%
- `chat`: 20%
- `trend`: 20%

---

## 📁 CẤU TRÚC THƯ MỤC

```
burnout-ai-platform/
├── app/
│   ├── core/                     # Configuration, Firebase Admin, Settings, Rate Limiters
│   └── modules/                  # Modular Architecture
│       ├── assessment/           # Assessment session lifecycle & Qdrant vectors
│       ├── auth/                 # Signup, Login, JWT HS256, Refresh tokens
│       ├── burnout/              # BurnoutEngine, scoring, weights, completeness helpers
│       ├── chat/                 # Chat routes, RAG search, sentiment signals
│       ├── dashboard/            # User & Admin dashboard stats
│       ├── emotion/              # DeepFace SDK integration & face emotion models
│       ├── recommendation/       # Recommendation engine & Geoapify places + weather
│       ├── report/               # Report generation service
│       ├── survey/               # Survey templates & history
│       ├── timeline/             # Timeline event tracking
│       └── user/                 # User profile management
├── config/
│   └── serviceAccountKey.json    # Firebase Admin SDK Credentials
├── docs/
│   ├── SYSTEM_SPEC_AND_METRICS.md# Tài liệu kỹ thuật chi tiết & toàn bộ công thức
│   └── QDRANT_SETUP.md          # Hướng dẫn cài đặt Vector DB Qdrant
├── external/
│   └── deepface/                 # DeepFace embedded SDK
├── .env                          # File môi trường
├── main.py                       # FastAPI entry point & lifespan handler
├── requirements.txt              # Dependencies
└── README.md
```

---

## 🛠️ CÔNG NGHỆ SỬ DỤNG

| Công nghệ | Vai trò trong hệ thống |
| :--- | :--- |
| **Python 3.10** | Runtime environment |
| **FastAPI** | High-performance REST API Framework |
| **DeepFace / TensorFlow** | Nhận diện khuôn mặt & 7 chỉ số cảm xúc |
| **Qdrant Vector DB** | Lưu trữ case memory & Similarity vector search |
| **Firebase Firestore** | NoSQL database cho user, session, history |
| **Google Gemini API** | AI LLM cho hội thoại & tổng hợp insight |
| **Geoapify & Open-Meteo** | Gợi ý địa điểm thư giãn theo vị trí & thời tiết thực tế |

---

## 🚀 CÀI ĐẶT & KHỞI ĐỘNG SERVER

### Yêu cầu hệ thống
- Python 3.10+
- File `config/serviceAccountKey.json` từ Firebase Console.

### 1. Cài đặt môi trường ảo & dependencies

```bash
# Clone repository
git clone <repo-url>
cd burnout-ai-platform

# Tạo virtual environment
python -m venv .venv

# Kích hoạt venv (Linux/Mac)
source .venv/bin/activate
# Hoặc (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Cài đặt thư viện từ requirements.txt
pip install -r requirements.txt
```

### 2. Cấu hình File `.env`
Đảm bảo biến `GOOGLE_APPLICATION_CREDENTIALS` trỏ đúng tới file service account key:
```env
GOOGLE_APPLICATION_CREDENTIALS=config/serviceAccountKey.json
FIREBASE_PROJECT_ID=burnout-ai-platform
JWT_SECRET=your_32char_jwt_secret_key
GOOGLE_API_KEY=your_gemini_api_key
```

### 3. Khởi động Server API (FastAPI)

#### 🔹 Cách 1: Kích hoạt môi trường ảo trước (Khuyên dùng)
- **Windows (PowerShell)**:
  ```pwsh
  .\.venv\Scripts\Activate.ps1
  uvicorn main:app --reload
  ```
- **Windows (CMD)**:
  ```cmd
  .venv\Scripts\activate.bat
  uvicorn main:app --reload
  ```
- **Linux / Mac**:
  ```bash
  source .venv/bin/activate
  uvicorn main:app --reload
  ```

#### 🔹 Cách 2: Chạy trực tiếp qua Python trong môi trường ảo `.venv`
Nếu bạn không muốn kích hoạt `venv` trong terminal, chạy trực tiếp file thực thi Python của `.venv`:

- **Windows (PowerShell / CMD)**:
  ```pwsh
  .\.venv\Scripts\python.exe -m uvicorn main:app --reload
  ```
- **Linux / Mac**:
  ```bash
  ./.venv/bin/python -m uvicorn main:app --reload
  ```

 TRUY CẬP SWAGGER API DOCS TẠI: `http://localhost:8000/docs`

---

## 📡 API ENDPOINTS (CHÍNH)

| Nhóm | Endpoint | Method | Mô tả |
| :--- | :--- | :--- | :--- |
| **Auth** | `/api/auth/register` | `POST` | Đăng ký tài khoản người dùng mới |
| **Auth** | `/api/auth/login` | `POST` | Đăng nhập nhận Access Token & Refresh Token |
| **Emotion** | `/api/emotion/analyze` | `POST` | Phân tích 7 chỉ số cảm xúc từ ảnh khuôn mặt |
| **Assessment** | `/api/v1/assessments/start` | `POST` | Bắt đầu 1 Assessment Session mới |
| **Survey** | `/api/v1/assessments/{id}/survey` | `POST` | Submit dữ liệu khảo sát giấc ngủ, công việc |
| **Chat** | `/api/v1/assessments/{id}/chat` | `POST` | Gửi tin nhắn tư vấn tâm lý với AI |
| **Burnout** | `/api/burnout/analyze` | `POST` | Chạy BurnoutEngine tính composite score & risk level |
| **Burnout** | `/api/burnout/current` | `GET` | Lấy kết quả burnout mới nhất |
| **Recommend**| `/api/v1/assessments/{id}/recommendations/places` | `GET` | Gợi ý địa điểm thư giãn theo GPS & thời tiết |
| **Dashboard**| `/api/v1/dashboard/summary` | `GET` | Thống kê tổng quan tình trạng burnout |

---

## 📖 TÀI LIỆU KỸ THUẬT CHI TIẾT

Để xem toàn bộ công thức chi tiết, giải thích giải thuật, cách chuẩn hóa trọng số và bảng đối chiếu mã nguồn, vui lòng đọc tài liệu:

👉 **[docs/SYSTEM_SPEC_AND_METRICS.md](file:///d:/Projects/DeepFace/burnout-ai-platform/docs/SYSTEM_SPEC_AND_METRICS.md)**
