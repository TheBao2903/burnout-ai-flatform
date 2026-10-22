# 🔥 Burnout AI Platform - Backend Services & Core AI Engine

> **Nền tảng B2B SaaS Đa phương thức (Multimodal AI) Tiên phong trong Phát hiện Sớm, Định lượng và Ngăn ngừa Hội chứng Kiệt sức Nghề nghiệp (Workplace Burnout) cho Doanh nghiệp.**
> 
> *Dự án giải pháp công nghệ chuyển đổi số quản trị sức khỏe tinh thần doanh nghiệp — Ứng dụng mô hình tam giác chẩn đoán đa tầng (Triangulation Diagnostics): Thị giác máy tính nhận diện cảm xúc (DeepFace Computer Vision), Khảo sát vi mô tâm trắc học hàng ngày (STA & OLBI Psychometrics), và Trợ lý AI Tham vấn Tâm lý thích ứng (Google Gemini Clinical Agent).*

---

## 📑 MỤC LỤC

1. [TỔNG QUAN DỰ ÁN & BÀI TOÁN THỊ TRƯỜNG (INVESTOR EXECUTIVE SUMMARY)](#1-tổng-quan-dự-án--bài-toán-thị-trường-investor-executive-summary)
2. [GIẢI PHÁP ĐỘC BẢN & MÔ HÌNH TAM GIÁC ĐA PHƯƠNG THỨC](#2-giải-pháp-độc-bản--mô-hình-tam-giác-đa-phương-thức)
3. [CƠ SỞ KHOA HỌC & CÁC CHUẨN TÂM TRẮC Y KHOA](#3-cơ-sở-khoa-học--các-chuẩn-tâm-trắc-y-khoa)
4. [KIẾN TRÚC HỆ THỐNG & LUỒNG XỬ LÝ DỮ LIỆU (SYSTEM ARCHITECTURE)](#4-kiến-trúc-hệ-thống--luồng-xử-lý-dữ-liệu-system-architecture)
5. [CÁC PHÂN HỆ TRỌNG TÂM (CORE BACKEND MODULES)](#5-các-phân-hệ-trọng-tâm-core-backend-modules)
6. [THUẬT TOÁN SCORING & ĐỘNG CƠ CẢNH BÁO SỚM (BURNOUT ENGINE)](#6-thuật-toán-scoring--động-cơ-cảnh-báo-sớm-burnout-engine)
7. [BẢO MẬT DỮ LIỆU, QUYỀN RIÊNG TƯ & ĐẠO ĐỨC AI (PRIVACY-BY-DESIGN)](#7-bảo-mật-dữ-liệu-quyền-riêng-tư--đạo-đức-ai-privacy-by-design)
8. [DANH SÁCH TÀI LIỆU API (API ENDPOINTS SPECIFICATION)](#8-danh-sách-tài-liệu-api-api-endpoints-specification)
9. [HƯỚNG DẪN CÀI ĐẶT, KHỞI CHẠY & DEPLOY CLOUD (DOCKER / RENDER)](#9-hướng-dẫn-cài-đặt-khởi-chạy--deploy-cloud-docker--render)
10. [MÔ HÌNH KINH DOANH & ĐỀ XUẤT GIÁ TRỊ ĐẦU TƯ (BUSINESS MODEL & ROI)](#10-mô-hình-kinh-doanh--đề-xuất-giá-trị-đầu-tư-business-model--roi)

---

## 1. TỔNG QUAN DỰ ÁN & BÀI TOÁN THỊ TRƯỜNG (INVESTOR EXECUTIVE SUMMARY)

### 1.1. Nỗi đau thị trường (The Problem)
- **Đại dịch thầm lặng nơi công sở**: Theo Tổ chức Y tế Thế giới (WHO ICD-11: QD85), kiệt sức nghề nghiệp (*Occupational Burnout*) được chính thức công nhận là một hiện tượng suy kiệt thể chất và tinh thần mạn tính do căng thẳng kéo dài tại nơi làm việc mà không được xử lý thành công.
- **Tổn thất kinh tế khổng lồ**: Theo ước tính của Gallup và Diễn đàn Kinh tế Thế giới (WEF), tình trạng kiệt sức và căng thẳng của nhân viên gây thiệt hại hơn **322 tỷ USD mỗi năm** trên quy mô toàn cầu do suy giảm năng suất (*Presenteeism*), nghỉ ốm bất thường (*Absenteeism*) và làn sóng thôi việc âm thầm (*Quiet Quitting*).
- **Chi phí thay thế nhân sự đắt đỏ**: Chi phí để tuyển dụng và đào tạo lại một nhân sự cấp trung hoặc chuyên gia có chuyên môn cao bị burnout nghỉ việc dao động từ **1.5x đến 2x mức lương hàng năm** của họ.

### 1.2. Sự thất bại của các giải pháp truyền thống
| Tiêu chí | Khảo sát nhân sự truyền thống (Annual Survey) | Ứng dụng EAP / Thiền / Trị liệu rời rạc | **Burnout AI Platform** |
| :--- | :--- | :--- | :--- |
| **Tính thời điểm** | Trễ từ 6–12 tháng; khi có kết quả thì nhân tài đã nộp đơn nghỉ việc. | Tùy thuộc vào việc nhân viên chủ động tìm đến; thường chỉ tìm khi đã suy sụp nặng. | **Thời gian thực (Real-time)**: Cảnh báo nguy cơ Allostatic Overload trước 14–30 ngày. |
| **Độ trung thực** | Thấp do tâm lý e ngại ("Faking Good"), trả lời đối phó. | Không có số liệu đo lường định lượng và đối chiếu. | **Tam giác đối chứng**: Kết hợp Sinh trắc cảm xúc + Khảo sát vi mô + AI Hội thoại. |
| **Thời gian làm** | Dài (30–60 câu hỏi), nhân viên chán nản, tỷ lệ hoàn thành < 35%. | Yêu cầu cam kết thời gian dài (15–30 phút/buổi). | **Micro-checkin cực ngắn**: Chỉ **60 giây/ngày** với 9 câu hỏi trọng tâm. |
| **Giá trị Doanh nghiệp** | Báo cáo PDF tổng kết tĩnh, không có hành động cụ thể. | Dữ liệu đóng kín, HR và Ban Giám đốc không nắm được điểm nóng tổ chức. | **Executive Heatmap & Top Stressors**: Phân tích nguyên nhân gốc rễ và đề xuất hành động. |

---

## 2. GIẢI PHÁP ĐỘC BẢN & MÔ HÌNH TAM GIÁC ĐA PHƯƠNG THỨC

Khác biệt cốt lõi (*Unfair Advantage*) của **Burnout AI Platform** nằm ở **Thuật toán Tam giác Đa phương thức (Multimodal Triangulation Framework)**. Hệ thống không tin vào một nguồn dữ liệu đơn lẻ mà liên tục đối chiếu và cân bằng trọng số giữa 3 nguồn tín hiệu:

```
                                  ▲
                                 / \
                                /   \
                               /     \
                              /  AI   \
                             /  CORE   \
                            / BURNOUT   \
                           /   ENGINE    \
                          /               \
                         /_________________\
                        ▲                   ▲
                       /                     \
                      /                       \
                     /                         \
    ┌───────────────────────┐             ┌────────────────────────┐
    │  TÍN HIỆU SINH HỌC &  │             │  TÍN HIỆU TÂM TRẮC HỌC │
    │   THỊ GIÁC MÁY TÍNH   │◄───────────►│  VI MÔ HÀNG NGÀY & ĐỊNH KỲ
    │ (DeepFace Vision AI)  │             │   (STA 9-Item & OLBI)  │
    └───────────────────────┘             └────────────────────────┘
                 ▲                                     ▲
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │    TÍN HIỆU HỘI THOẠI &   │
                      │   TÂM LÝ NHẬN THỨC SÂU    │
                      │ (4-Stage Gemini Pro Agent)│
                      └───────────────────────────┘
```

1. **Tín hiệu Khảo sát Vi mô (Psychometric State Signal)**: Bộ 9 câu hỏi STA hàng ngày đo lường trực diện 3 chiều cốt lõi: Kiệt sức thể chất/tinh thần (E1-E3), Mất gắn kết hoài nghi (D1-D3), và Áp lực quá tải công việc (JD1-JD3) kèm thời lượng giấc ngủ và mức độ phục hồi.
2. **Tín hiệu Cảm xúc Khuôn mặt (Affective Computer Vision Signal)**: Tận dụng camera/webcam với DeepFace SDK nhận diện 7 biểu cảm vi mô (*Micro-expressions*), phát hiện sự suy giảm biên độ cảm xúc (*Emotional Flattening*) hoặc ức chế nụ cười gượng gạo.
3. **Tín hiệu Hội thoại Nhận thức (Conversational Cognitive Signal)**: Chatbot tâm lý thích ứng 4 giai đoạn ứng dụng mô hình ngôn ngữ lớn (Google Gemini 2.0 / Flash), phân tích văn phong, cơ chế tự vệ né tránh, phát hiện các điểm nghẽn nhận thức (*Cognitive Biases*) mà bảng câu hỏi số học không đo lường được.

---

## 3. CƠ SỞ KHOA HỌC & CÁC CHUẨN TÂM TRẮC Y KHOA

Burnout AI Platform được xây dựng trên nền tảng tâm lý học hành vi và y học lao động vững chắc:

### 3.1. Thang đo Trạng thái Hàng ngày (STA Daily Check-in `sta-daily-9-v1`)
Bộ 9 câu hỏi vi mô chuẩn hóa Likert 1–5 (thời gian làm 45–60 giây):
- **Exhaustion - Kiệt sức (E1–E3)**: Đo lường sự cạn kiệt năng lượng thể chất và cảm xúc cuối ngày làm việc.
- **Disengagement - Xa cách / Hoài nghi (D1–D3)**: Đo lường mức độ thờ ơ, mất gắn kết và cái nhìn tiêu cực với công việc.
- **Job Demands - Áp lực công việc (JD1–JD3)**: Đo lường cường độ deadline, sự phân mảnh công việc và kỳ vọng thời gian.
- **Phục hồi & Giấc ngủ**: Slider thời lượng ngủ (3.0h – 12.0h) và Điểm số cảm nhận phục hồi sau giấc ngủ (1 – 5).
- **Phân nhánh quá tải (Drill-down Overload)**: Khi mức độ quá tải $\ge 4/5$, hệ thống mở rộng xác định nguyên nhân gốc: *Khối lượng quá lớn, Deadline gấp, Đa nhiệm ngắt quãng, Thiếu hỗ trợ từ cấp trên/đồng nghiệp, Thiếu quyền tự chủ*.

### 3.2. Thang đo Định kỳ Toàn diện (OLBI & Areas of Worklife Scale)
- **Thang đo OLBI 16 câu (`olbi-16-4pt-vi-v1`)**: Bản chuyển hóa từ nghiên cứu của Demerouti et al. (2010), đánh giá định kỳ 14 ngày/lần với kỹ thuật đảo điểm câu hỏi tích cực (`5 - answer`) để đo lường Burnout mạn tính (Trait Burnout).
- **Thang đo 6 Trụ cột Đời sống Công việc (Maslach AWS - Areas of Worklife Scale)**:
  1. *Workload (Khối lượng công việc)*: Tỷ lệ giữa thời gian và năng lượng bỏ ra.
  2. *Control (Sự tự chủ)*: Quyền ra quyết định và cách thực thi nhiệm vụ.
  3. *Reward (Ghi nhận & Khen thưởng)*: Lương thưởng tài chính và sự công nhận từ tổ chức.
  4. *Community (Môi trường đồng nghiệp)*: Sự gắn kết, tin cậy và an toàn tâm lý nội bộ.
  5. *Fairness (Sự công bằng)*: Tính minh bạch trong đánh giá, phân chia cơ hội.
  6. *Values (Sự hòa hợp giá trị)*: Mức độ tương đồng giữa giá trị cá nhân và sứ mệnh doanh nghiệp.

---

## 4. KIẾN TRÚC HỆ THỐNG & LUỒNG XỬ LÝ DỮ LIỆU (SYSTEM ARCHITECTURE)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                CLIENT APPLICATIONS                                     │
│     React 19 SPA (Vite + Tailwind CSS + Ant Design + Recharts + Vercel Edge CDN)       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTPS / WSS / REST API
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND RUNTIME (DOCKER / RENDER)                       │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              API GATEWAY & MIDDLEWARES                           │  │
│  │   • CORS Manager    • Firebase ID Token Verification Auth   • Rate Limiting      │  │
│  └──────────────────────────────────────────┬───────────────────────────────────────┘  │
│                                             │                                          │
│  ┌──────────────────────────────────────────┴───────────────────────────────────────┐  │
│  │                              SERVICE DOMAIN MODULES                              │  │
│  │  ┌───────────────┐ ┌───────────────┐ ┌────────────────┐ ┌──────────────────────┐ │  │
│  │  │ EmotionService│ │ SurveyService │ │  ChatService   │ │ RecommendationService│ │  │
│  │  │  (DeepFace)   │ │  (STA / OLBI) │ │(Gemini 4-Stage)│ │ (Geoapify + Weather) │ │  │
│  │  └───────┬───────┘ └───────┬───────┘ └────────┬───────┘ └──────────┬───────────┘ │  │
│  └──────────┼─────────────────┼──────────────────┼────────────────────┼─────────────┘  │
│             │                 │                  │                    │                │
│             ▼                 ▼                  ▼                    ▼                │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         BURNOUT AI FUSION & SCORING ENGINE                       │  │
│  │   • 7-Day Rolling Stats        • Allostatic Overload Rule Engine                 │  │
│  │   • Triangulated Risk Gating   • MD5 In-Memory Cache (TTL 30m, Latency < 1ms)    │  │
│  │   • Rapid Fallback (< 3.5s)    • Gemini Medical Synthesis                        │  │
│  └──────────────────────────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────────────────────────┼──────────────────────────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
┌───────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│           CLOUD STORAGE & DATABASE        │   │          EXTERNAL AI & CLOUD APIS      │
│  • Google Firestore (NoSQL Document Store)│   │  • Google Gemini 2.0 / Flash API       │
│  • Cloudflare R2 (S3-Compatible Image BLOB│   │  • DeepFace Weights (On-premise / RAM) │
│  • Qdrant Cloud (Vector Similarity DB)    │   │  • Geoapify Places & Open-Meteo Weather│
└───────────────────────────────────────────┘   └────────────────────────────────────────┘
```

---

## 5. CÁC PHÂN HỆ TRỌNG TÂM (CORE BACKEND MODULES)

### 5.1. Module Thị giác máy tính nhận diện Cảm xúc (`app.modules.emotion`)
- Tích hợp **DeepFace SDK** với TensorFlow Keras tối ưu CPU thuần (`CUDA_VISIBLE_DEVICES=-1`, `TF_ENABLE_ONEDNN_OPTS=0`).
- Cơ chế đa tầng dò tìm khuôn mặt: Ưu tiên `opencv` (siêu tốc ~0.05s) $\rightarrow$ `ssd` (chính xác cao ~0.3s) $\rightarrow$ `mediapipe` $\rightarrow$ `retinaface`.
- Phân tích 7 vector cảm xúc: *Happy, Sad, Angry, Fear, Surprise, Neutral, Disgust*.
- Safeguard tính toán độ tin cậy (*Reliability Scoring*): Kiểm tra góc chụp, độ phân giải, tự động downscale ảnh webcam lớn về 720p để bảo toàn RAM.
- Tự động bọc bảo vệ chống lỗi phụ thuộc thư viện mã hóa (`lightphe`/`lightdsa` graceful import fallback).

### 5.2. Module Khảo sát & Tâm trắc học (`app.modules.survey`)
- Quản lý vòng đời hợp đồng khảo sát hàng ngày (`sta-daily-9-v1`) và định kỳ (`olbi-16-4pt-vi-v1`).
- Đảo điểm tự động các câu tích cực theo chuẩn tâm trắc học y khoa.
- Kiểm tra tính toàn vẹn (Payload Integrity Validation) phía Server: Khóa thang đo, chống gian lận client-side.
- Bộ đệm lịch sử theo múi giờ địa phương (UTC+7), nhóm dữ liệu theo từng ngày độc lập.

### 5.3. Module Trợ lý AI Tham vấn Tâm lý thích ứng (`app.modules.chat`)
- Được thiết kế dựa trên kỹ thuật phỏng vấn tâm lý lâm sàng chuyên sâu với **4 giai đoạn tiếp cận tuần tự**:
  1. **Stage 1 (Opening & Rapport Building)**: Chào đón, tạo không gian an toàn, xác nhận tâm trạng ban đầu.
  2. **Stage 2 (Context Probing)**: Đặt câu hỏi thăm dò trọng tâm vào các chỉ số kiệt sức cao nhất trong ngày.
  3. **Stage 3 (In-depth Exploration)**: Khám phá sâu nguyên nhân gốc rễ (xung đột công việc, ranh giới cá nhân, suy nghĩ tự trách).
  4. **Stage 4 (Actionable Resolution)**: Đúc kết phiên tham vấn thành 1–2 giải pháp vi mô tức thời (*Micro-habits*) có thể thực hiện ngay.
- Cơ chế **Gemini Rotator**: Tự động luân phiên xoay vòng giữa 3–5 API Keys dự phòng khi chạm giới hạn Rate Limit (HTTP 429).
- Bọc bất đồng bộ `asyncio.to_thread` giải phóng hoàn toàn Event Loop của FastAPI.

### 5.4. Module Đề xuất Phục hồi theo Ngữ cảnh thực (`app.modules.recommendation`)
- Tích hợp **Geoapify Places API**: Tự động tìm kiếm các địa điểm phục hồi năng lượng trong bán kính 5km quanh tọa độ GPS người dùng: Công viên cây xanh, Spa & Wellness, Quán cà phê yên tĩnh, Khu tập Yoga/Gym.
- Tích hợp **Open-Meteo Weather API**: Đọc dữ liệu nhiệt độ, thời tiết thực tế để đưa ra gợi ý phù hợp (ví dụ: trời mưa đề xuất nghe nhạc thư giãn trong nhà; trời mát đề xuất đi bộ 15 phút ngoài trời).

---

## 6. THUẬT TOÁN SCORING & ĐỘNG CƠ CẢNH BÁO SỚM (BURNOUT ENGINE)

### 6.1. Thuật toán Trung bình trượt 7 ngày (7-Day Rolling Average)
Để triệt tiêu các biến động ngẫu nhiên trong ngày (*Day-to-day noise*), hệ thống tính toán trung bình trượt trên cửa sổ 7 ngày gần nhất:
$$\text{Rolling Mean} = \frac{1}{k} \sum_{i=1}^{k} \text{Score}_i \quad (1 \le k \le 7)$$

- **Xác định Xu hướng (Trend Analysis)**:
  $$\Delta = \text{Mean}(\text{Day}_{t-2} \dots \text{Day}_t) - \text{Mean}(\text{Day}_{t-6} \dots \text{Day}_{t-3})$$
  - $\Delta > +0.3$: **Increasing (Gia tăng rủi ro - Báo động)**.
  - $\Delta < -0.3$: **Decreasing (Hồi phục tích cực)**.
  - $|\Delta| \le 0.3$: **Stable (Ổn định)**.

### 6.2. Quy tắc Cảnh báo Allostatic Overload (Quá tải Sinh học Tích tụ)
Hiện tượng quá tải Allostatic xảy ra khi cơ thể phải liên tục huy động năng lượng chống đỡ stress mà không có chu kỳ tái tạo, dẫn đến nguy cơ đột quỵ, trầm cảm hoặc suy nhược thần kinh:

$$\text{Allostatic Alert} \iff \begin{cases} \text{Mean}(\text{Exhaustion})_{3\text{ ngày liên tiếp}} \ge 4.0 / 5.0 \\ \text{VÀ} \\ \text{Mean}(\text{Sleep Hours})_{3\text{ ngày liên tiếp}} < 6.0\text{ giờ} \end{cases}$$

Khi kích hoạt, hệ thống lập tức gắn cờ **CRITICAL (Đỏ)**, ưu tiên hiển thị banner cảnh báo khẩn cấp cho người dùng và gửi tín hiệu ẩn danh lên Dashboard của Quản trị viên để có phương án điều phối nhân sự.

### 6.3. Tối ưu hóa Hiệu năng Dashboard AI Interpreter (Cache MD5 + Fast Fallback)
- **MD5 In-Memory Cache (TTL 30 phút)**: Băm dữ liệu thống kê đầu vào thành mã hash MD5; nếu người dùng truy cập lại mà dữ liệu không đổi, kết quả phân tích AI trả về trong **0.0001 giây (Cache Hit)**.
- **Fast Fallback Engine (< 3.5 giây)**: Nếu Gemini AI phản hồi chậm hơn 3.5 giây, hệ thống tự động kích hoạt bộ luật chuyên gia chuẩn y khoa (Rule-based Fallback) trả về kết quả tức thì, đảm bảo Dashboard không bao giờ bị đơ hay giật lag.

---

## 7. BẢO MẬT DỮ LIỆU, QUYỀN RIÊNG TƯ & ĐẠO ĐỨC AI (PRIVACY-BY-DESIGN)

- **Zero-Storage Camera Guarantee**: Khi quét cảm xúc khuôn mặt, khung hình camera được xử lý trực tiếp trong RAM và giải phóng bộ nhớ ngay sau khi tính toán xong điểm số. Hệ thống **tuyệt đối không lưu trữ ảnh khuôn mặt của nhân viên lên server trừ khi nhân viên chủ động bấm tích chọn đồng ý lưu**.
- **Anonymized Enterprise Aggregation**: Trên Dashboard của Quản trị viên và HR, dữ liệu nhân viên được nhóm theo phòng ban và mã hóa ẩn danh. Lãnh đạo chỉ nhìn thấy các chỉ số phân bổ rủi ro và các yếu tố gây stress chung của tập thể, bảo vệ trọn vẹn **An toàn Tâm lý (Psychological Safety)**.
- **Tuân thủ Chuẩn Bảo mật**: Cấu trúc dữ liệu và quy trình xử lý được thiết kế tương thích với các nguyên tắc bảo vệ quyền riêng tư người dùng theo chuẩn GDPR và HIPAA.

---

## 8. DANH SÁCH TÀI LIỆU API (API ENDPOINTS SPECIFICATION)

### Authentication & User Management
- `POST /api/auth/sync`: Đồng bộ Profile và Firebase ID Token vào Firestore.
- `GET /api/v1/users/me`: Lấy thông tin cá nhân và Work Baseline Profile của nhân viên.
- `PUT /api/v1/users/me`: Cập nhật cấu hình công việc (giờ làm, giờ OT, chức danh).

### Assessment & Survey Engine
- `GET /api/v1/assessments/questions`: Danh mục câu hỏi khảo sát hàng ngày (STA 9 items) và định kỳ.
- `POST /api/v1/assessments/{id}/survey`: Submit kết quả khảo sát vi mô hàng ngày.
- `GET /api/survey/questionnaire-status`: Kiểm tra trạng thái làm bài hôm nay và chu kỳ làm lại OLBI.
- `GET /api/survey/rolling-stats`: Thống kê trung bình trượt 7 ngày và phân tích xu hướng.
- `GET /api/survey/alerts`: Danh sách các cảnh báo quá tải Allostatic Overload đang kích hoạt.
- `POST /api/v1/assessments/periodic`: Submit bài khảo sát định kỳ môi trường làm việc 6 trụ cột (AWS).

### Emotion & DeepFace Computer Vision
- `POST /api/emotion/analyze`: Upload/chụp ảnh khuôn mặt, phân tích 7 vector cảm xúc và độ tin cậy.
- `GET /api/emotion/history`: Lấy lịch sử biến thiên cảm xúc theo dòng thời gian.

### AI Psychological Consultation (Chat)
- `POST /api/v1/assessments/{id}/chat`: Gửi tin nhắn tham vấn AI với cơ chế 4 giai đoạn thích ứng.
- `GET /api/v1/assessments/{id}/chat/history`: Lấy toàn bộ lịch sử phiên hội thoại tâm lý.
- `POST /api/v1/assessments/{id}/chat/complete`: Đóng phiên tham vấn và trích xuất kế hoạch hành động.

### Analytics & Enterprise Dashboard
- `GET /api/v1/dashboard/analytics`: Thống kê tổng hợp cá nhân (Survey, Emotion, Sleep, Trend).
- `GET /api/v1/dashboard/burnout-analytics`: Phân tích chuyên sâu chỉ số kiệt sức, radar yếu tố đóng góp và khuyến nghị AI.
- `GET /api/v1/admin/dashboard/overview`: Dashboard Ban Giám đốc về sức khỏe tổ chức toàn công ty.
- `GET /api/v1/admin/dashboard/top-stressors`: Bảng xếp hạng Top các nguyên nhân gây stress nhiều nhất trong tổ chức.

### Contextual Healing & Recommendations
- `GET /api/v1/weather/current`: Đọc dữ liệu thời tiết thực tế tại tọa độ người dùng.
- `POST /api/survey/places`: Gợi ý địa điểm nghỉ dưỡng/phục hồi gần nhất qua GPS.

---

## 9. HƯỚNG DẪN CÀI ĐẶT, KHỞI CHẠY & DEPLOY CLOUD (DOCKER / RENDER)

### 9.1. Khởi chạy Local Development

```bash
# 1. Di chuyển vào thư mục backend
cd burnout-ai-platform

# 2. Tạo môi trường ảo Python 3.10
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Trên Windows
# source .venv/bin/activate  # Trên Linux/macOS

# 3. Cài đặt các thư viện phụ thuộc
pip install --upgrade pip
pip install -r requirements.txt

# 4. Khởi tạo file môi trường .env (tham khảo file mẫu trong tài liệu)
# Đặt file credentials Firebase vào config/serviceAccountKey.json

# 5. Khởi chạy FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Truy cập tài liệu Swagger UI tự động tại: `http://localhost:8000/docs`

### 9.2. Triển khai Production với Docker & Cloud (Render)

Hệ thống đã có sẵn file [`Dockerfile`](./Dockerfile) và [`render.yaml`](./render.yaml) chuẩn production:
- Tự động tải trước model DeepFace (`facial_expression_model_weights.h5`, `deploy.prototxt`, `res10_300x300_ssd_iter_140000.caffemodel`) trong lúc build image.
- Cấu hình khởi chạy với 1 worker duy nhất (`--workers 1`) để tối ưu hóa việc quản lý bộ nhớ RAM dưới 512MB trên Render Free/Starter.
- Tự động nhận diện Secret Files tại `/etc/secrets/serviceAccountKey.json` hoặc biến môi trường `FIREBASE_SERVICE_ACCOUNT_JSON`.

---

## 10. MÔ HÌNH KINH DOANH & ĐỀ XUẤT GIÁ TRỊ ĐẦU TƯ (BUSINESS MODEL & ROI)

### 10.1. Mô hình Doanh thu (B2B SaaS)
- **Gói Starter (Doanh nghiệp nhỏ 20–50 nhân sự)**: \$3 - \$4 / nhân viên / tháng. Bao gồm Khảo sát vi mô hàng ngày, Phân tích Cảm xúc và Dashboard cơ bản.
- **Gói Enterprise (Doanh nghiệp 50–500+ nhân sự)**: \$5 - \$7 / nhân viên / tháng. Mở khóa toàn bộ: AI Chatbot tham vấn chuyên sâu, Bản đồ nhiệt rủi ro phòng ban (Heatmap), Top Stressors Leaderboard, API tích hợp hệ sinh thái HR (Slack/Teams).

### 10.2. Tính toán Lợi tức Đầu tư (ROI) cho Khách hàng Doanh nghiệp
- Giả định công ty quy mô **100 nhân viên IT / Tài chính**, mức lương bình quân \$1,500/tháng:
  - Tỷ lệ nghỉ việc do burnout trung bình hàng năm: **15%** (15 người/năm).
  - Chi phí tuyển dụng và đào tạo lại: \$1,500 $\times$ 2 tháng = \$3,000/người $\rightarrow$ Tổng thiệt hại: **\$45,000/năm**.
  - Thiệt hại do ngày nghỉ ốm và suy giảm năng suất: Ước tính **\$20,000/năm**.
  - **Chi phí thuê Burnout AI Platform**: 100 người $\times$ \$5/tháng = **\$6,000/năm**.
  - **Lợi ích mang lại**: Giúp giảm ít nhất 30% tỷ lệ nghỉ việc (giữ lại 5 nhân sự) $\rightarrow$ Tiết kiệm trực tiếp \$15,000 chi phí tuyển dụng + \$6,000 năng suất = **\$21,000**.
  - 👉 **Lợi tức đầu tư (ROI) đạt: 350% (Gấp 3.5 lần chi phí đầu tư)** ngay trong năm đầu tiên triển khai.

---

*© 2026 Burnout AI Platform. All rights reserved. Sáng kiến Đổi mới Sáng tạo Chăm sóc Sức khỏe Tinh thần Nơi Công sở bằng Trí tuệ Nhân tạo.*
