# Nhận định bối cảnh dashboard

## Luồng dữ liệu

Các biểu đồ gọi API chỉ số như trước. Nhận định gọi riêng
`GET /api/v1/dashboard/context-insight?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`.
Hai ngày dùng chung bộ lọc dashboard, trọn ngày UTC+7. API chỉ đọc nguồn của
tài khoản đăng nhập; không nhận một user ID khác từ query. Việc AI chậm/lỗi
không giữ màn hình biểu đồ ở trạng thái tải.

`dashboard_evidence.py` tạo bằng chứng có phiên bản `dashboard-context-v2`.
`dashboard_ai_interpreter.py` chứa toàn bộ system prompt tiếng Việt, schema
đầu ra và bộ sinh nhận xét theo quy tắc. Không có nhánh lỗi trả mặc định rằng
người dùng đang cân bằng tốt.

## Dữ liệu đưa vào prompt

| Nguồn | Nội dung và quy tắc |
|---|---|
| Khoảng ngày | Ngày đầu/cuối, múi giờ, số ngày lịch, mốc khảo sát mới nhất |
| Check-in 9 câu | Câu trả lời E1–E3/D1–D3/JD1–JD3; một bản mới nhất mỗi ngày; số mẫu, thiếu mẫu, trung bình, min/max, đầu/cuối, thay đổi giữa các mốc và hai nửa kỳ |
| Phục hồi | Giờ ngủ, điểm hồi phục và số ngày thực sự có giá trị; giữ nguyên 0 giờ nếu được ghi nhận, thiếu là null |
| Quá tải | Mức tự khai từng ngày, số ngày báo cao, số ngày trả lời, số lần chọn từng lý do, ghi chú người dùng được đánh dấu là dữ liệu không tin cậy |
| Biến động công việc | Tăng ca ngày được thu thập, tổng giờ/ngày có tăng ca, áp lực deadline được ghi nhận; không nhân giờ tăng ca nền theo tuần thành giờ tăng ca trong kỳ |
| OLBI | Bài 16 câu có phiên bản hợp lệ; chuỗi E/D sau đảo điểm thang 1–4, so sánh đầu/cuối/lần trước trong khoảng; câu trả lời gốc của hai lần gần nhất |
| Hồ sơ | Chức danh, ngành, giờ chuẩn/ngày, ngày làm/tuần, tăng ca nền/tuần. Không gửi tên, email, điện thoại. Đây là hồ sơ hiện tại, không xác nhận điều kiện công việc trong quá khứ |
| Ngành nghề | Vốn từ và áp lực thường gặp chỉ là bối cảnh/giả thuyết, không phải sự việc người dùng đã gặp |
| Môi trường làm việc | JR1–JR4 và 6 lĩnh vực, từng lần trong kỳ, trung bình/thay đổi từng chỉ số. Điểm cao là nguồn lực/phù hợp tốt hơn; không mượn ngưỡng E/D để diễn giải |
| Khuôn mặt | Phân bố nhãn, trung bình xác suất từng cảm xúc và độ tin cậy mô hình. Không gửi ảnh, giới tính, tuổi hoặc coi đây là chẩn đoán/cảm xúc tự khai |
| Hội thoại | Chỉ tin nhắn user có phân tích trong kỳ: số mẫu, các tín hiệu trích xuất, điểm 0–100 của 8 tín hiệu và độ không chắc chắn. Không gửi nội dung hội thoại đầy đủ hoặc tin nhắn assistant làm bằng chứng |
| Chất lượng | Độ phủ ngày, nguồn lỗi/không truy cập được, dữ liệu phiên bản cũ, thiếu chỉ số, giới hạn lấy mẫu và số lượng nguồn tham chiếu có thật |

Không cộng/trừ trực tiếp daily 1–5 với OLBI 1–4. Không tự chuyển dữ liệu thiếu
thành điểm trung lập. Check-in legacy thiếu đủ ba câu một chiều được đánh dấu
thiếu, không suy ra E/D từ stress hoặc động lực. Ngưỡng ba vùng là quy ước ứng
dụng. Trend daily cần ít nhất ba ngày, hai ngày chỉ so sánh hai mốc. Ngày
không có check-in không được xem là ngày có trạng thái ổn định.

Ngủ/hồi phục/quá tải từ bản ghi cũ có thể là giá trị mặc định của giao diện;
nguồn được trình bày là dữ liệu tự theo dõi, không phải phép đo khách quan.

## Độ đầy đủ và giới hạn kích thước

Thống kê khảo sát tính trên toàn bộ bản ghi hợp lệ trong khoảng. Chuỗi dài
hơn 120 ngày/bài lấy mẫu đều, giữ đầu/cuối và công bố `timeline_sampling`;
không lấy mẫu trước khi tính thống kê. OLBI kèm nguyên 16 câu của hai lần cuối.
Môi trường làm việc kèm 12 lần cuối và thống kê toàn bộ kỳ. Khuôn mặt/hội thoại
đọc tối đa 500 bản gần nhất; khi chạm giới hạn, metadata và lời nhắc nêu rõ có
thể thiếu dữ liệu lịch sử, không khẳng định không có tín hiệu khi nguồn trống.

Nguồn phụ lỗi được ghi `unavailable`, không biến thành tình trạng bình thường.
Nếu không có daily đủ E/D và không có OLBI hợp lệ, API trả nhận xét thiếu dữ
liệu theo quy tắc và không gọi mô hình để suy đoán sức khỏe từ nguồn phụ.

## Prompt và đầu ra

System prompt quy định rõ vai trò, phạm vi ngày, chiều các thang, cách dùng
trend và coverage, phân biệt hồ sơ/ngành nghề với quan sát thực tế, giới hạn
nguồn mô hình phụ, dữ liệu không tin cậy, không chẩn đoán/nhân quả và hành động
nhỏ. Dữ liệu được gửi dưới JSON có dấu phân cách, tách với system instruction.

Gemini chỉ tạo `summary`, `key_observations`, `suggested_action`,
`reflection_question`, `evidence_refs`. Các reference phải thuộc danh sách
backend cung cấp. Schema, kiểu, độ dài, khóa lạ và reference được kiểm tra
trước khi chấp nhận; không chấp nhận mọi chuỗi JSON là kết quả hợp lệ.
Schema gửi qua Gemini bỏ `additionalProperties` vì API không hỗ trợ trường
này; kiểm tra khóa lạ vẫn thực hiện ở backend bằng Pydantic.

Ứng dụng tự gắn nguồn `ai` hoặc `rules`, lý do fallback, model (chỉ khi AI
thành công), thời gian tạo, cache, phiên bản prompt, khoảng ngày, độ phủ và các
giới hạn. Không gửi key hoặc thông báo lỗi nội bộ ra giao diện. Người dùng thấy
nguồn nhận xét, số ngày/bài được dùng, một hành động nhỏ, câu hỏi gợi mở và
mục mở rộng về dữ liệu/giới hạn. Không hiển thị mọi fallback dưới nhãn Gemini.

## Hiệu năng và cache

Cache theo tài khoản + toàn bộ bằng chứng + phiên bản prompt; timestamp tạo
kết quả không được đưa vào bằng chứng để gây cache miss. AI hợp lệ lưu 30 phút,
fallback lỗi lưu 60 giây. Yêu cầu đồng thời cùng bằng chứng chia sẻ một lượt
gọi, tối đa hai lượt mô hình đang chạy; không xếp hàng vô hạn. HTTP mỗi lượt
tối đa 35 giây, tổng vòng xoay khoảng 45 giây, chờ API tối đa 50 giây. Nếu đã
trả fallback nhưng AI hoàn tất muộn, kết quả hợp lệ vẫn được đưa vào cache.
Đổi kỳ hoặc rời trang sẽ hủy tải phía trình duyệt và không cập nhật nhầm nhận
định của kỳ cũ.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_questionnaire_contract.py tests/test_dashboard_insight.py -q
```

Test mô hình dùng fake client, gồm schema/prompt đầy đủ, cache riêng tài khoản,
thiếu dữ liệu, tách thang, nguồn lỗi, callback đồng thời, timeout và kết quả đến
muộn. Kiểm tra kết nối thật dùng dữ liệu giả lập, không dùng dữ liệu cá nhân.
