# 🔥 Burnout AI Platform - Backend Services

> Nền tảng AI phân tích và đánh giá mức độ kiệt sức (burnout) đa chiều thông qua cảm xúc khuôn mặt (DeepFace), khảo sát trạng thái hàng ngày khoa học (OLBI & JD-R v3.0), khảo sát định kỳ tổ chức (AWS 6 Areas), hội thoại tư vấn AI (RAG Chat), và hệ thống đề xuất phục hồi (Geoapify + Open-Meteo).

---

## 📋 MỤC LỤC
- [1. Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
- [2. Kiến trúc & Luồng dữ liệu](#2-kiến-trúc--luồng-dữ-liệu)
- [3. Hệ thống Khảo sát & Đo lường Stress (Survey v3.0)](#3-hệ-thống-khảo-sát--đo-lường-stress-survey-v30)
- [4. Thuật toán Scoring & Cảnh báo khoa học](#4-thuật-toán-scoring--cảnh-báo-khoa-học)
- [5. API Endpoints](#5-api-endpoints)
- [6. Hướng dẫn cài đặt & Khởi chạy](#6-hướng-dẫn-cài-đặt--khởi-chạy)

---

## 1. TỔNG QUAN HỆ THỐNG

Phát hiện sớm và ngăn ngừa burnout trong tổ chức bằng mô hình tam giác đa chiều (**Triangulation Assessment**):
1. **Phân tích Cảm xúc khuôn mặt (DeepFace SDK)**: Nhận diện 7 chỉ số cảm xúc qua webcam/hình ảnh.
2. **Khảo sát trạng thái hàng ngày (Daily Check-in v3.0)**: Rút gọn còn 8 câu hỏi core (60-90s) chuẩn OLBI & JD-R.
3. **Khảo sát định kỳ môi trường làm việc (Periodic Survey)**: Đánh giá 6 trụ cột văn hóa tổ chức (AWS - Areas of Worklife Scale).
4. **AI Psychological Chatbot (RAG + Gemini)**: Phân tích hành vi né tránh, quá tải nhận thức qua hội thoại.
5. **Smart Recommendation Engine**: Đề xuất địa điểm thư giãn & thói quen phục hồi theo GPS và thời tiết.

---

## 2. KIẾN TRÚC & LUỒNG DỮ LIỆU

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             CLIENT / FRONTEND                            │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND MODULES                          │
│ ┌──────────────┐ ┌───────────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Auth & User  │ │  Survey v3.0 Engine│ │ Face Emotion │ │ Admin Stats  │ │
│ └──────┬───────┘ └─────────┬─────────┘ └──────┬───────┘ └──────┬───────┘ │
└────────┼───────────────────┼──────────────────┼────────────────┼─────────┘
         │                   │                  │                │
         ▼                   ▼                  ▼                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        BURNOUT ENGINE (AI CORE)                          │
│   • Rolling Average 7 ngày (Exhaustion, Recovery, Sleep, Demands)        │
│   • Allostatic Overload Detection (Cảnh báo quá tải kéo dài)             │
│   • Dynamic Weight Normalization (Xử lý dữ liệu khuyết thiếu)           │
└────────┬───────────────────┬──────────────────┬────────────────┼─────────┘
         │                   │                  │                │
         ▼                   ▼                  ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐
│  DeepFace SDK   │ │ Vector DB Qdrant│ │  Google Gemini  │ │ Firestore DB │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └──────────────┘
```

---

## 3. HỆ THỐNG KHẢO SÁT & ĐO LƯỜNG STRESS (SURVEY V3.0)

Hệ thống phân tách khảo sát thành 2 tầng rõ ràng: **Khảo sát hàng ngày (Daily Check-in)** và **Khảo sát định kỳ (Periodic Survey)**.

### 3.1. Daily Check-in Survey (Khảo sát trạng thái hàng ngày)
- **Thiết kế**: Ultra-short 8 câu core (thời gian làm 60–90 giây), loại bỏ các câu thừa và gộp thông tin công việc từ Work Baseline Profile.
- **Thang đo Likert**: 1-5 điểm.

| Stt | Yếu tố (Dimension) | Mã câu hỏi | Nội dung câu hỏi (Chuẩn OLBI & JD-R) |
|---|---|---|---|
| 1 | **Exhaustion (Kiệt sức)** | `e1` | Hôm nay tôi cảm thấy rất mệt sau khi làm việc. |
| 2 | **Exhaustion (Kiệt sức)** | `e2` | Hôm nay công việc làm tôi cảm thấy cạn kiệt năng lượng. |
| 3 | **Disengagement (Mất gắn kết)** | `d1` | Càng ngày tôi càng ít muốn gắn bó với công việc này. |
| 4 | **Job Demands (Áp lực công việc)** | `jd1` | Hôm nay tôi phải xử lý khối lượng công việc quá nhiều. |
| 5 | **Job Demands (Áp lực công việc)** | `jd2` | Tôi phải làm việc dưới áp lực thời gian quá gấp. |
| 6 | **Sleep (Giấc ngủ)** | `sleep_hours` | Thời lượng ngủ đêm qua (Slider 3.0h - 12.0h). |
| 7 | **Recovery (Hồi phục)** | `recovery_score` | Cảm nhận mức độ hồi phục sau giấc ngủ (1: Rất mệt → 5: Rất sảng khoái). |
| 8 | **Quick Overload (Quá tải)** | `quick_overload` | Cảm giác công việc quá tải hôm nay (1: Không → 5: Nghiêm trọng). |

> **Phân nhánh điều kiện (Conditional Drill-down)**: Khi `quick_overload >= 4`, hệ thống mở rộng chọn nguyên nhân: *Quá nhiều việc, Áp lực deadline, Xử lý nhiều việc cùng lúc, Thiếu hỗ trợ, Khó chủ động, Khác (Text input)*.

---

### 3.2. Periodic Survey (Khảo sát định kỳ Hàng tuần / Hàng tháng)
Khảo sát định kỳ giúp Admin hiểu **Nguyên nhân gốc rễ tổ chức (Organizational Drivers)** gây ra stress cho nhân sự.

#### 1. Job Resources (Nguồn lực hỗ trợ công việc - 4 câu)
- `jr1`: Nhận được hỗ trợ đủ để hoàn thành công việc.
- `jr2`: Quyền tự chủ trong cách thực hiện công việc.
- `jr3`: Được hướng dẫn / phản hồi khi gặp khó khăn.
- `jr4`: Nỗ lực đóng góp được cấp trên & tổ chức ghi nhận.

#### 2. Maslach Areas of Worklife Scale (AWS - 6 Trụ cột văn hóa môi trường làm việc)
- **Workload (Khối lượng)**: Đánh giá sự cân bằng khối lượng công việc tổng thể.
- **Control (Tự chủ)**: Mức độ kiểm soát và ra quyết định trong công việc.
- **Reward (Khen thưởng & Ghi nhận)**: Đãi ngộ tài chính và tinh thần.
- **Community (Cộng đồng & Đồng nghiệp)**: Mối quan hệ, niềm tin và sự hỗ trợ nội bộ.
- **Fairness (Công bằng)**: Sự công bằng trong đánh giá, thăng tiến và phân công.
- **Values (Giá trị)**: Sự đồng điệu giữa giá trị cá nhân và sứ mệnh công ty.

---

## 4. THUẬT TOÁN SCORING & CẢNH BÁO KHOA HỌC

### 4.1. Rolling Average 7 ngày (Xu hướng biến thiên)
Thay vì phụ thuộc vào snapshot 1 ngày đơn lẻ, hệ thống tính toán trung bình trượt 7 ngày:
$$\text{Rolling Average} = \frac{\sum_{i=1}^{7} \text{Score}_i}{N}$$

- **Đánh giá Trend**: So sánh trung bình 3 ngày gần nhất vs 4 ngày trước đó.
  - `diff > +0.3`: **Increasing** (Gia tăng rủi ro / Kiệt sức tăng).
  - `diff < -0.3`: **Decreasing** (Giảm rủi ro / Trạng thái hồi phục tốt).
  - Khác: **Stable** (Ổn định).

### 4.2. Quy tắc Cảnh báo Allostatic Overload (Quá tải sinh học kéo dài)
Được kích hoạt tự động khi cơ thể người dùng rơi vào trạng thái tích tụ quá tải không kịp phục hồi:

$$\text{RULE}: \begin{cases} \text{Mean Exhaustion (3 ngày liên tiếp)} \ge 4.0 / 5.0 \\ \text{AND} \\ \text{Sleep Hours (3 ngày liên tiếp)} < 6.0 \text{ giờ} \end{cases} \implies \text{CRITICAL ALERT}$$

- **Level**: `critical` (Đỏ)
- **Thông điệp**: *Cảnh báo quá tải kéo dài: Bạn đang trong trạng thái kiệt sức liên tục kèm thiếu ngủ nghiêm trọng. Hệ thống khuyến cáo giảm tải công việc và nghỉ ngơi khẩn cấp.*

---

## 5. API ENDPOINTS

### Survey & Analytics APIs
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/assessments/questions` | Lấy danh sách câu hỏi Daily (8 items) & Periodic |
| `POST` | `/api/v1/assessments/{id}/survey` | Submit kết quả khảo sát hàng ngày |
| `POST` | `/api/survey/analyze` | Phân tích quy tắc nhanh & tính risk score |
| `GET` | `/api/survey/rolling-stats?days=7` | **[Mới v3.0]** Lấy chỉ số trung bình trượt 7 ngày & trend |
| `GET` | `/api/survey/alerts` | **[Mới v3.0]** Lấy danh sách cảnh báo Allostatic Overload |
| `POST` | `/api/v1/assessments/periodic` | Submit bài khảo sát định kỳ môi trường làm việc (AWS) |
| `GET` | `/api/v1/assessments/periodic/latest` | Lấy bài khảo sát định kỳ mới nhất |
| `GET` | `/api/survey/history` | Lấy lịch sử khảo sát cá nhân |
| `POST` | `/api/survey/recommendations` | Đề xuất địa điểm nghỉ ngơi theo GPS |

---

## 6. HƯỚNG DẪN CÀI ĐẶT & KHỞI CHẠY

```bash
# 1. Tạo môi trường ảo Python
python -m venv .venv
source .venv/bin/activate  # Trên Windows: .\.venv\Scripts\Activate.ps1

# 2. Cài đặt thư viện phụ thuộc
pip install -r requirements.txt

# 3. Chạy server API với Uvicorn
uvicorn main:app --reload --port 8000
```
- Swagger UI Docs: `http://localhost:8000/docs`
