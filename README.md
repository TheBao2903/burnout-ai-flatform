# 🔥 Burnout AI Platform

> Nền tảng AI phân tích và đánh giá mức độ kiệt sức (burnout) của người dùng thông qua kết hợp phân tích cảm xúc khuôn mặt, khảo sát, và trò chuyện.

## 📋 Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Quy trình hoạt động](#quy-trình-hoạt-động)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cài đặt](#cài-đặt)
- [API Endpoints](#api-endpoints)
- [Dữ liệu mẫu](#dữ-liệu-mẫu)

---

## 🎯 Tổng quan

### Mục tiêu

Phát hiện sớm và đánh giá mức độ burnout của người dùng thông qua phân tích đa chiều:

- **Cảm xúc khuôn mặt** → Phân tích biểu cảm từ ảnh/chụp frame
- **Khảo sát** → Thu thập thông tin về giấc ngủ, công việc, stress
- **Chatbot** → Phân tích ngôn ngữ và hành vi giao tiếp

### Đầu ra

```json
{
  "burnout_score": 72.5,
  "confidence": 0.89,
  "risk_level": "high",
  "factors": [
    {"factor": "emotion", "percentage": 35.0, "details": {...}},
    {"factor": "workload", "percentage": 25.0, "details": {...}},
    {"factor": "sleep", "percentage": 20.0, "details": {...}},
    {"factor": "stress", "percentage": 20.0, "details": {...}}
  ],
  "recommendations": [
    "Nên nghỉ ngơi 1-2 ngày",
    "Giảm giờ làm xuống 8h/ngày"
  ],
  "analyzed_at": "2024-01-20T10:15:00Z"
}
```

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT / MOBILE APP                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │  Emotion API │ │ Survey API   │ │  Chat API    │            │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BURNOUT ENGINE (AI Core)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Input: Emotion + Survey + Chat                           │   │
│  │  Process: Weight & Combine Factors → Calculate Score     │   │
│  │  Output: BurnoutResult + Recommendations                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  DeepFace SDK   │ │   Vector DB     │ │  Knowledge Base │
│  (Face Analysis)│ │ (Pinecone/etc.) │ │   (RAG Docs)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 🔄 Quy trình hoạt động

### 1. Phân tích Cảm xúc (Emotion Analysis)

```
User Upload Image → DeepFace Analysis → EmotionResult → Burnout Engine
```

**Chi tiết:**

1. User chụp ảnh hoặc upload ảnh khuôn mặt
2. DeepFace phân tích và trả về điểm cảm xúc
3. Chuyển đổi sang `EmotionResult` domain model
4. Gửi đến Burnout Engine

**Output mẫu:**

```json
{
  "emotions": {
    "happy": 20.5,
    "sad": 45.2,
    "neutral": 15.0,
    "fear": 8.1,
    "angry": 5.3,
    "surprise": 3.5,
    "disgust": 2.4
  },
  "dominant_emotion": "sad",
  "confidence": 0.87,
  "age": 28,
  "gender": "Man"
}
```

### 2. Khảo sát (Assessment/Survey)

```
User Fill Survey → Assessment API → AssessmentResult → Burnout Engine
```

**Các loại khảo sát:**

- **Sleep Assessment**: Giờ ngủ, chất lượng giấc ngủ
- **Workload Assessment**: Số giờ làm việc, deadline
- **Stress Assessment**: Mức độ stress tự đánh giá
- **Comprehensive Assessment**: Tổng hợp tất cả

### 3. Trò chuyện (Chat Analysis)

```
User Chat → Chat Vector Search → LLM Response → ChatVector → Burnout Engine
```

**Tính năng:**

- RAG (Retrieval Augmented Generation) cho phản hồi contextual
- Phân tích sentiment từ nội dung chat
- Vector search để tìm kiếm knowledge base

### 4. Burnout Engine (Tổng hợp)

```
EmotionResult ─┐
SurveyResult ──┼──→ Burnout Engine ──→ BurnoutResult + Recommendations
ChatAnalysis ──┘
```

**Trọng số mặc định:**
| Factor | Weight | Nguồn dữ liệu |
|--------|--------|----------------|
| Emotion | 35% | DeepFace |
| Workload | 25% | Survey |
| Sleep | 20% | Survey |
| Stress | 20% | Survey + Chat |

---

## 📁 Cấu trúc thư mục

```
burnout-ai-platform/
├── app/                          # Application source code
│   ├── models/                   # Domain Models (Pydantic)
│   │   ├── user.py              # User profile
│   │   ├── session.py           # User session tracking
│   │   ├── emotion.py           # EmotionResult model
│   │   ├── burnout.py           # BurnoutFactor, BurnoutResult
│   │   ├── survey.py            # Survey definitions
│   │   ├── assessment_*.py     # Assessment related models
│   │   ├── chat.py              # Chat message model
│   │   ├── recommendation.py    # Recommendations
│   │   ├── timeline.py          # User timeline events
│   │   ├── notification.py       # Push notifications
│   │   ├── report.py            # Report generation
│   │   └── auth.py              # Authentication models
│   │
│   ├── ai_models/               # AI/ML Models
│   │   ├── base_vector.py       # Base vector model
│   │   ├── burnout_vector.py    # Burnout vector
│   │   ├── chat_vector.py       # Chat vector
│   │   ├── knowledge_vector.py  # Knowledge base vector
│   │   └── search_result.py     # Search result model
│   │
│   └── routes/                  # API Routes (TODO)
│
├── external/                     # External libraries
│   └── deepface/                # DeepFace SDK (embedded)
│       ├── modules/
│       │   ├── detection.py     # Face detection
│       │   ├── demography.py    # Age/gender detection
│       │   ├── verification.py  # Face verification
│       │   ├── recognition.py   # Face recognition
│       │   └── database/        # Vector DB integrations
│       │       ├── pinecone.py
│       │       ├── milvus.py
│       │       ├── pgvector.py
│       │       └── ...
│       ├── models/
│       │   ├── face_detection/  # Detection models
│       │   └── facial_recognition/ # Recognition models
│       └── DeepFace.py          # Main entry point
│
├── uploads/                     # User uploaded files
├── tests/                       # Unit tests
├── requirements.txt             # Python dependencies
└── README.md
```

---

## 🛠️ Công nghệ sử dụng

### Backend

| Technology           | Purpose         |
| -------------------- | --------------- |
| **Python 3.10+**     | Runtime         |
| **FastAPI**          | Web framework   |
| **Pydantic**         | Data validation |
| **DeepFace**         | Face analysis   |
| **TensorFlow/Keras** | ML models       |

### AI/ML

| Technology          | Purpose                          |
| ------------------- | -------------------------------- |
| **DeepFace**        | Face detection, emotion analysis |
| **LLM Integration** | Chatbot (configurable)           |
| **Vector Search**   | Semantic search                  |

### Vector Databases

Hỗ trợ đa database:

- **Pinecone**
- **Milvus**
- **Weaviate**
- **PgVector** (PostgreSQL)
- **Neo4j**
- **MongoDB**

---

## 🚀 Cài đặt

### Yêu cầu

- Python 3.10+
- CUDA (optional, cho GPU acceleration)

### Cài đặt dependencies

```bash
# Clone repository
git clone <repo-url>
cd burnout-ai-platform

# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
.\venv\Scripts\activate   # Windows

# Cài đặt packages
pip install -r external/deepface/requirements.txt
pip install fastapi uvicorn pydantic
```

### Cấu hình

Tạo file `.env`:

```env
# Vector Database
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENV=your_environment

# LLM Configuration
LLM_PROVIDER=openai  # hoặc anthropic, local
OPENAI_API_KEY=your_key

# Storage
UPLOAD_DIR=./uploads
```

---

## 📡 API Endpoints

### Authentication

```
POST   /api/auth/register     # Đăng ký user mới
POST   /api/auth/login        # Đăng nhập
POST   /api/auth/refresh     # Refresh token
```

### Emotion Analysis

```
POST   /api/emotion/analyze   # Phân tích cảm xúc từ ảnh
GET    /api/emotion/history   # Lịch sử phân tích cảm xúc
```

### Assessment

```
GET    /api/assessments/templates      # Danh sách template
POST   /api/assessments/submit         # Submit kết quả khảo sát
GET    /api/assessments/results/{id}   # Xem kết quả
```

### Chat

```
POST   /api/chat/message     # Gửi tin nhắn chat
GET    /api/chat/history     # Lịch sử chat
```

### Burnout Analysis

```
POST   /api/burnout/analyze  # Phân tích burnout tổng hợp
GET    /api/burnout/current   # Lấy kết quả burnout hiện tại
GET    /api/burnout/history   # Lịch sử phân tích
GET    /api/burnout/report    # Xuất báo cáo
```

### Recommendations

```
GET    /api/recommendations/current  # Khuyến nghị hiện tại
GET    /api/recommendations/history  # Lịch sử khuyến nghị
```

---

## 📊 Dữ liệu mẫu

### Kết quả Burnout hoàn chỉnh

```json
{
  "burnout_score": 72.5,
  "confidence": 0.89,
  "risk_level": "high",
  "factors": [
    {
      "factor": "emotion",
      "percentage": 35.0,
      "details": {
        "dominant_emotion": "sad",
        "sad_score": 45.2,
        "happy_score": 20.5
      }
    },
    {
      "factor": "workload",
      "percentage": 25.0,
      "details": {
        "working_hour": 12,
        "overtime_frequency": "daily"
      }
    },
    {
      "factor": "sleep",
      "percentage": 20.0,
      "details": {
        "sleep_hour": 4,
        "sleep_quality": "poor"
      }
    },
    {
      "factor": "stress",
      "percentage": 20.0,
      "details": {
        "stress_level": 8,
        "stress_source": "deadline"
      }
    }
  ],
  "recommendations": [
    "⚠️ Mức độ kiệt sức của bạn đang ở mức cao",
    "💤 Nên ngủ đủ 7-8 tiếng/đêm",
    "🏃 Nên tập thể dục nhẹ nhàng 30 phút/ngày",
    "🧘 Thực hành meditation 10-15 phút/ngày",
    "👥 Nên chia sẻ với người thân hoặc chuyên gia"
  ],
  "analyzed_at": "2024-01-20T10:15:00Z"
}
```

### Risk Levels

| Level        | Score Range | Màu sắc | Hành động                   |
| ------------ | ----------- | ------- | --------------------------- |
| **Low**      | 0-30        | 🟢 Xanh | Theo dõi định kỳ            |
| **Medium**   | 31-50       | 🟡 Vàng | Tự chăm sóc, tăng nghỉ ngơi |
| **High**     | 51-75       | 🟠 Cam  | Cần hỗ trợ chuyên môn       |
| **Critical** | 76-100      | 🔴 Đỏ   | Can thiệp ngay lập tức      |

---

## 📝 TODO

- [ ] Hoàn thiện API Routes
- [ ] Thêm WebSocket cho real-time chat
- [ ] Tích hợp LLM (GPT-4/Claude)
- [ ] Dashboard admin
- [ ] Push notifications
- [ ] Unit tests
- [ ] CI/CD pipeline

---

## 📧 Liên hệ

[Thông tin liên hệ]

## 📄 License

[MIT License]
