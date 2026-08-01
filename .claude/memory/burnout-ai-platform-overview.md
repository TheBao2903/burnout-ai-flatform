---
name: burnout-ai-platform-overview
description: Tổng quan hệ thống Burnout AI Platform - kiến trúc, modules, và quy trình hoạt động
metadata:
  type: project
---

# Burnout AI Platform - Tổng Quan Hệ Thống

## Mục Tiêu
Xây dựng hệ thống AI đánh giá nguy cơ **Burnout (kiệt quệ tinh thần)** của người dùng.

**Lưu ý quan trọng:**
- AI **KHÔNG chẩn đoán bệnh tâm thần**
- AI chỉ **đánh giá mức độ nguy cơ** và đưa ra khuyến nghị
- Là **công cụ hỗ trợ sàng lọc sớm**

## Luồng Người Dùng

```
Người dùng mở App
       ↓
Camera chụp 1 frame mỗi 3-5 giây (không quay video liên tục)
       ↓
Ảnh gửi lên Server
       ↓
Server phân tích khuôn mặt (DeepFace)
       ↓
Người dùng trả lời vài câu hỏi
       ↓
Server đọc nội dung chat (GPT)
       ↓
AI tổng hợp tất cả dữ liệu (Burnout Engine)
       ↓
Trả kết quả Burnout
```

## 6 Modules Chính

### Module 1: API Nhận Ảnh
- App gửi: ảnh (frame), id người dùng, thời gian
- Đầu ra: Server nhận ảnh → chuyển sang DeepFace

### Module 2: DeepFace Phân Tích Khuôn Mặt
- Nhận diện cảm xúc: Happy, Sad, Neutral, Fear, Angry
- Nếu không nhận diện được → trả về "Unknown"
- **Có thể thay bằng:** MediaPipe, InsightFace, FER+, OpenFace

### Module 3: Đọc Dữ Liệu Hành Vi
- Ngủ: số giờ
- Làm việc: số giờ
- Deadline: Có/Không
- Tăng ca: Có/Không
- Có thể bổ sung: số ngày làm việc liên tục, nhịp tim

### Module 4: GPT Phân Tích Chat
- Đọc nội dung chat của người dùng
- Phân tích ngữ nghĩa → Stress, động lực, dấu hiệu Burnout
- **Lưu ý:** GPT chỉ phân tích ngữ nghĩa, không kết luận bệnh

### Module 5: Burnout Engine (QUAN TRỌNG NHẤT)
Thuật toán **do nhóm tự xây dựng**, không phụ thuộc hoàn toàn vào GPT hay DeepFace.

**Input:**
- Emotion (từ DeepFace)
- Chat/Text (từ GPT)
- Stress (từ survey)
- Sleep
- Working Hour
- Heart Rate (optional)

**Output:**
```
Burnout Risk: 87%
Nguyên nhân lớn nhất:
  45% - Thiếu ngủ
  30% - Công việc quá tải
  15% - Cảm xúc tiêu cực
  10% - Khác
```

### Module 6: Trả JSON Kết Quả
```json
{
  "burnout_score": 81,
  "confidence": 0.92,
  "emotion": {
    "sad": 0.74,
    "neutral": 0.18,
    "happy": 0.08
  },
  "stress_level": "High",
  "recommendation": [
    "Nghỉ giải lao",
    "Ngủ đủ giấc",
    "Trao đổi với quản lý",
    "Nếu kéo dài nên gặp chuyên gia"
  ],
  "timestamp": "2026-08-01T09:30:00"
}
```

## Database Schema (Firestore)

Lưu trữ:
- User
- Lịch sử Burnout
- Emotion
- Stress
- Chat
- Kết quả GPT
- Thời gian

**Bảo mật:**
- Ảnh gốc: chỉ lưu nếu người dùng đồng ý
- Nếu không: chỉ lưu vector đặc trưng hoặc kết quả phân tích

## Dashboard

Hiển thị:
- Lịch sử điểm Burnout theo thời gian
- Biểu đồ thay đổi cảm xúc
- Xu hướng thay đổi

```
User A
01/08 - Burnout 45
03/08 - Burnout 67
05/08 - Burnout 82
```

## Tech Stack

| Công nghệ | Mục đích |
|-----------|-----------|
| Python | Backend |
| FastAPI | API |
| DeepFace | Phân tích khuôn mặt |
| OpenAI API | GPT phân tích chat |
| PostgreSQL/Firebase Firestore | Database |
| Docker | Container |
| R2 Cloudflare | Storage (ảnh) |

## Yêu Cầu Thiết Kế

### 1. Modular AI
- Code sao cho sau này dễ thay AI module
- DeepFace hiện tại là model có sẵn
- Thiết kế theo dạng module để dễ thay bằng model tự train

### 2. Burnout Engine Độc Lập
- Không phụ thuộc hoàn toàn vào GPT hay DeepFace
- Tự xây dựng thuật toán đánh giá

### 3. Mở Rộng Tương Lai
- GPS kết hợp Google Maps → gợi ý địa điểm thư giãn
- Google Trends, tin tức → GPT tóm tắt xu hướng
- Training model riêng

## Giao Diện Kết Quả Chi Tiết

```
Burnout Score: 81/100
Confidence: 92%
Risk Level: HIGH

Factors:
├── Sleep: 45% (Thiếu ngủ)
├── Workload: 30% (Quá tải)
├── Emotion: 15% (Tiêu cực)
└── Other: 10%

Recommendations:
1. Nghỉ giải lao 1-2 ngày
2. Ngủ đủ 7-8 tiếng
3. Trao đổi với quản lý
4. Gặp chuyên gia nếu kéo dài
```

**Why:** Tài liệu tổng quan từ yêu cầu ban đầu của user, làm cơ sở để phát triển tiếp.

**How to apply:** Dùng làm reference khi thiết kế architecture, đối chiếu với models đã tạo.
