---
name: burnout-ai-platform-overview
description: Tổng quan hệ thống Burnout AI Platform - trạng thái hoàn thành, API endpoints, data model, và đồng bộ hóa
metadata:
  type: project
---

# BURNOUT AI PLATFORM – TỔNG QUAN HỆ THỐNG MVP

## Mục Tiêu
Xây dựng hệ thống AI hỗ trợ **đánh giá sớm nguy cơ Burnout (kiệt quệ tinh thần)** cho người dùng.

**Lưu ý quan trọng:**
- AI **KHÔNG chẩn đoán bệnh tâm thần**
- AI **KHÔNG kết luận** người dùng mắc bệnh
- Chỉ **đánh giá Burnout Risk**
- Là **công cụ hỗ trợ sàng lọc sớm**

---

# PHẦN 1: TRẠNG THÁI HOÀN THÀNH

## ✅ MODULES ĐÃ HOÀN THÀNH

| Module | Status | Notes |
|--------|--------|-------|
| Image Input + Emotion | ✅ DONE | DeepFace, R2 upload |
| Assessment Session | ✅ DONE | CRUD, status, data_completeness |
| Survey | ✅ DONE | 7 questions, upsert |
| Chat History | ✅ DONE | GPT 8 signals analysis |
| Emotion → Assessment | ✅ DONE | assessment_id linking |
| BurnoutInputBuilder | ✅ DONE | Data aggregation |
| Burnout Engine v2 | ✅ DONE | Weights: sleep=30%, workload=25%, stress=20%, emotion=15%, behavior=10% |
| POST /analyze | ✅ DONE | Full pipeline |
| GET /result | ✅ DONE | Read-only |
| Dashboard APIs | ✅ DONE | Overview, history |
| Recommendation Engine | ✅ DONE | Rule-based |

---

# PHẦN 2: API ENDPOINTS

## Auth APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| POST | `/api/v1/auth/register` | ✅ | |
| POST | `/api/v1/auth/login` | ✅ | |
| GET | `/api/v1/users/me` | ✅ | |

## Assessment Session APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| POST | `/api/v1/assessments` | ✅ | Tạo assessment mới |
| GET | `/api/v1/assessments` | ✅ | List assessments |
| GET | `/api/v1/assessments/{id}` | ✅ | Chi tiết |
| POST | `/api/v1/assessments/{id}/analyze` | ✅ | Chạy burnout analysis |
| DELETE | `/api/v1/assessments/{id}` | ✅ | Xóa |

## Emotion APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| POST | `/api/emotion/analyze` | ✅ | + assessment_id param |
| POST | `/api/emotion/analyze?assessment_id=xxx` | ✅ | Tự link với assessment |
| GET | `/api/emotion/history` | ✅ | |
| DELETE | `/api/emotion/{id}/image` | ✅ | |

## Survey APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| GET | `/api/v1/assessments/{id}/survey/questions` | ✅ | 7 câu hỏi |
| GET | `/api/v1/assessments/{id}/survey` | ✅ | |
| POST | `/api/v1/assessments/{id}/survey` | ✅ | Submit |
| GET | `/api/v1/assessments/{id}/survey/status` | ✅ | |

## Chat APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| POST | `/api/v1/assessments/{id}/chat` | ✅ | Gửi tin nhắn |
| GET | `/api/v1/assessments/{id}/chat` | ✅ | Lịch sử |
| GET | `/api/v1/assessments/{id}/chat/summary` | ✅ | Tóm tắt |
| DELETE | `/api/v1/assessments/{id}/chat` | ✅ | Xóa |

## Burnout Result APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| GET | `/api/v1/assessments/{id}/result` | ✅ | Kết quả burnout |
| GET | `/api/v1/assessments/{id}/emotions` | ✅ | Emotion history |
| GET | `/api/v1/assessments/{id}/chat` | ✅ | Chat history |
| GET | `/api/v1/assessments/{id}/survey` | ✅ | Survey data |

## Dashboard APIs
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| GET | `/api/v1/dashboard/overview` | ✅ | Tổng quan |
| GET | `/api/v1/dashboard/burnout-history` | ✅ | Lịch sử burnout |
| GET | `/api/v1/dashboard/emotion-history` | ✅ | Lịch sử emotion |

---

# PHẦN 3: DATA MODEL - assessment_id LINKING

## Firestore Collections

| Collection | Key | assessment_id Field | Repository |
|-----------|-----|---------------------|------------|
| `assessments` | Document ID | - | AssessmentSessionRepository |
| `emotions` | Auto ID | ✅ `assessment_id` | EmotionRepository |
| `survey_history` | Auto ID | ✅ `assessment_id` | SurveyHistoryRepository |
| `chat_history` | Auto ID | ✅ `assessment_id` | ChatHistoryRepository |
| `burnout_results` | Auto ID | ✅ `assessment_id` | BurnoutRepository |
| `emotion_assessments` | Auto ID | - | AssessmentRecordRepository |

## assessment_id Usage

### ✅ EmotionRepository
```python
def save(user_id, emotion, image_key=None, assessment_id=None)
def list_by_assessment(assessment_id, limit=100)
def count_by_assessment(assessment_id)
def delete_by_assessment(assessment_id)
```

### ✅ SurveyHistoryRepository
```python
def save(assessment_id, user_id, survey)
def get_by_assessment(assessment_id)
def delete_by_assessment(assessment_id)
```

### ✅ ChatHistoryRepository
```python
def save_message(assessment_id, user_id, role, content, analysis)
def get_messages_by_assessment(assessment_id, limit)
def get_session_summary(assessment_id)
def delete_by_assessment(assessment_id)
```

### ✅ BurnoutRepository
```python
def save(user_id, result, assessment_id=None, emotion_id=None)
def get_by_assessment(assessment_id)
def delete_by_assessment(assessment_id)
```

---

# PHẦN 4: DATA COMPLETENESS

## Assessment Data Completeness

Assessment tự động tính `data_completeness` dựa trên:

| Component | Weight | Field |
|-----------|--------|-------|
| Emotion Frames | 30% | `has_emotion` |
| Survey | 30% | `has_survey` |
| Chat | 20% | `has_chat` |
| Result | 20% | `has_result` |

```python
data_completeness = 0.0
if has_emotion: data_completeness += 0.30
if has_survey: data_completeness += 0.30
if has_chat: data_completeness += 0.20
if has_result: data_completeness += 0.20
# Max = 1.0
```

## BurnoutInput Data Completeness

BurnoutInputBuilder tính riêng cho Burnout Engine:

| Factor | Weight |
|--------|--------|
| Sleep | 15% |
| Workload | 15% |
| Stress | 20% |
| Emotion | 30% |
| Trend/Behavior | 20% |

---

# PHẦN 5: BURNOUT ENGINE v2

## Weights (Bắt buộc)

```python
BURNOUT_WEIGHTS = {
    "sleep": 0.30,      # 30%
    "workload": 0.25,   # 25%
    "stress": 0.20,     # 20%
    "emotion": 0.15,   # 15%
    "behavior": 0.10,   # 10%
}
# Total = 100%
```

## Sub-scores

### Sleep Score (0-100)
| Hours | Score |
|-------|-------|
| >= 8h | 0 |
| 7h | 25 |
| 6h | 50 |
| 5h | 75 |
| < 5h | 100 |

### Workload Score (0-100)
| Hours | Score |
|-------|-------|
| <= 8h | 0 |
| 9h | 25 |
| 10h | 50 |
| > 10h | 100 |

### Stress Score (0-100)
- Survey: 60% weight (1-10 → 0-100)
- Chat: 40% weight

### Emotion Score (0-100)
- Dựa trên `negative_ratio`
- `negative_ratio = (sad + fear + angry + disgust) / total`

### Behavior Score (0-100)
- Trend increasing: +15
- Trend decreasing: -10
- Trend stable: 0

## Risk Level
| Score | Level |
|-------|-------|
| 0-39 | low |
| 40-69 | medium |
| 70-100 | high |

## Trend
| Value | Description |
|-------|-------------|
| increasing | Xu hướng tăng |
| decreasing | Xu hướng giảm |
| stable | Ổn định |
| insufficient_data | Chưa đủ data |

---

# PHẦN 6: END-TO-END FLOW

```
USER
  │
  ▼
┌─────────────────────────────────────────┐
│ Tạo Assessment                         │
│ POST /api/v1/assessments               │
│ → assessment_id                        │
│ → status=collecting                    │
│ → data_completeness=0.0               │
└──────────────────┬────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ Emotion │ │ Survey  │ │  Chat   │
   │  Frame  │ │         │ │         │
   └────┬────┘ └────┬────┘ └────┬────┘
        │          │          │
        │          │          │
        ▼          ▼          ▼
   ┌─────────────────────────────────┐
   │   Tất cả link via assessment_id │
   └─────────────────┬───────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ POST /analyze          │
        │                        │
        │ BurnoutInputBuilder    │
        │   ├─ EmotionAggregator  │
        │   ├─ ChatAggregator    │
        │   ├─ TrendAnalyzer     │
        │   └─ SurveyNormalizer  │
        │                        │
        │ BurnoutEngine          │
        │   ├─ sleep_score       │
        │   ├─ workload_score    │
        │   ├─ stress_score      │
        │   ├─ emotion_score     │
        │   └─ behavior_score   │
        │                        │
        │ RecommendationEngine    │
        └───────────┬────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────┐
   │ Firestore: burnout_results          │
   │ Assessment: status=completed         │
   └──────────────────┬────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────┐
   │ GET /result                          │
   │ GET /dashboard/overview             │
   └─────────────────────────────────────┘
```

---

# PHẦN 7: R2 STORAGE CONVENTION

## Path Format
```
{module}/assessments/{assessment_id}/{type}/{filename}
```

## Examples
```
emotion/assessments/asm_123/frames/frame_001.jpg
emotion/assessments/asm_123/frames/frame_002.jpg
chat/assessments/asm_123/audio/message_001.wav
assessment/asm_123/documents/example.pdf
```

## Lưu ý
- Firestore **CHỈ** lưu `object_key` (path)
- Firestore **KHÔNG** lưu full URL
- Frontend tự ghép: `R2_PUBLIC_BASE_URL + object_key`

---

# PHẦN 8: FILES STRUCTURE

```
app/
├── modules/
│   ├── assessment/
│   │   ├── repositories/
│   │   │   └── assessment_session_repository.py  ✅
│   │   └── routes/
│   │       └── assessment_session.py  ✅
│   │
│   ├── emotion/
│   │   ├── repositories/
│   │   │   └── emotion_repository.py  ✅
│   │   └── routes/
│   │       └── emotion.py  ✅
│   │
│   ├── survey/
│   │   ├── repositories/
│   │   │   └── survey_history_repository.py  ✅
│   │   └── routes/
│   │       └── survey_history.py  ✅
│   │
│   ├── chat/
│   │   ├── repositories/
│   │   │   └── chat_history_repository.py  ✅
│   │   └── routes/
│   │       └── chat_history.py  ✅
│   │
│   ├── burnout/
│   │   ├── models/
│   │   │   └── burnout.py  ✅ (v2)
│   │   ├── repositories/
│   │   │   └── burnout_repository.py  ✅
│   │   ├── routes/
│   │   │   └── burnout_result.py  ✅ (new)
│   │   └── services/
│   │       ├── burnout_engine.py  ✅ (v2)
│   │       └── burnout_input_builder.py  ✅ (new)
│   │
│   ├── recommendation/
│   │   └── services/
│   │       └── recommendation_engine.py  ✅
│   │
│   └── dashboard/
│       └── routes/
│           └── dashboard.py  ✅ (new)
│
└── main.py  ✅ (registered routers)
```

---

# PHẦN 9: FILES ĐÃ TẠO/SỬA GẦN ĐÂY

## Files mới (Phase 3-7)
| File | Description |
|------|-------------|
| `app/modules/burnout/services/burnout_input_builder.py` | Builder cho BurnoutInput |
| `app/modules/burnout/routes/burnout_result.py` | GET /result endpoints |
| `app/modules/dashboard/routes/dashboard.py` | Dashboard APIs |
| `app/modules/dashboard/__init__.py` | Module init |

## Files đã sửa
| File | Changes |
|------|---------|
| `app/modules/burnout/services/burnout_engine.py` | v2: new weights, stress/behavior |
| `app/modules/burnout/models/burnout.py` | Added data_completeness, trend |
| `app/modules/burnout/repositories/burnout_repository.py` | assessment_id support |
| `app/modules/recommendation/services/recommendation_engine.py` | Added stress, behavior templates |
| `app/modules/assessment/routes/assessment_session.py` | Full analyze pipeline |
| `app/modules/emotion/routes/emotion.py` | Enhanced with assessment_id |
| `app/modules/emotion/repositories/emotion_repository.py` | assessment_id field |
| `main.py` | Registered new routers |

---

# PHẦN 10: CHECKLIST

## ✅ Đã hoàn thành

- [x] Assessment Session CRUD
- [x] Survey (7 questions)
- [x] Chat + GPT Analysis (8 signals)
- [x] Emotion analysis + R2 upload
- [x] assessment_id linking (tất cả modules)
- [x] BurnoutInputBuilder (aggregators)
- [x] Burnout Engine v2 (correct weights)
- [x] Recommendation Engine (rule-based)
- [x] POST /analyze (full pipeline)
- [x] GET /result
- [x] Dashboard APIs

## 🔨 Cần kiểm tra/Test

- [ ] E2E test flow
- [ ] Verify Firestore indexes
- [ ] Error handling edge cases
- [ ] Idempotency test (retry /analyze)

---

# PHẦN 11: NHỮNG THỨ KHÔNG LÀM TRONG MVP

```
❌ WHO ICD-11 auto sync
❌ Psychological Research API
❌ Google Trends / News crawling
❌ Social media crawling
❌ Qdrant / RAG phức tạp
❌ Model training riêng
❌ Heart-rate integration
❌ Microservice / Kubernetes / Kafka
❌ Redis
```

---

# PHẦN 12: QUY TẮC quan trọng

1. **assessment_id là central identifier** - Tất cả modules phải link về assessment_id
2. **R2 chỉ lưu object_key** - KHÔNG lưu full URL
3. **Burnout Engine là single source of truth** - KHÔNG tính lại ở dashboard
4. **Dashboard CHỈ đọc** - KHÔNG gọi AI/Burnout Engine
5. **Weights bắt buộc** - sleep=30%, workload=25%, stress=20%, emotion=15%, behavior=10%

---

**Why:** Cập nhật chi tiết sau khi hoàn thành tất cả phases. Phản ánh chính xác trạng thái modules, APIs, và data model.

**How to apply:**
1. Backend MVP hoàn thành
2. Tất cả assessment_id linking đã đồng bộ
3. Burnout Engine với weights đúng
4. Dashboard read-only
