# Kết quả sửa chat cảm xúc — 30/10/2026

Đã triển khai bản sửa cho 16 nhóm lỗi trong báo cáo audit, cùng bản ghim SDK Gemini tương thích. Mã nguồn ở hai repository backend và frontend; chưa push hoặc deploy lên Render/Vercel.

Giữ nguyên mục đích STA: chat bổ sung bối cảnh, không chẩn đoán, không gọi phân tích chấm điểm burnout trong luồng gửi tin. Lộ trình ban đầu vẫn 3 lượt, hoặc 4 lượt với nhánh người dùng trả lời ngắn thể hiện mệt mỏi. Gia hạn là lựa chọn chủ động, một lần, đúng 3 lượt; tổng tối đa tương ứng 6 hoặc 7 lượt. Tiền kiểm nguy cơ vẫn chạy trước khi gọi model và không bị chặn bởi giới hạn lượt thường.

| Lỗi audit | Bản sửa | Kiểm chứng |
| --- | --- | --- |
| A01 — bỏ sót tín hiệu nguy cơ | Chỉ loại đúng đoạn phủ định/thành ngữ; vẫn kiểm tra tín hiệu độc lập ở phần còn lại. Không ghi nội dung nhạy cảm vào log cảnh báo. | Ca có đồng thời phủ định và tín hiệu dương tính; ca chỉ có phủ định/thành ngữ. |
| A02 — đóng phiên ghi lý do sai | Ghi `manual`, xác thực lý do trước khi repository ghi DB; đọc tương thích giá trị cũ `manual_user_decision`. UI chỉ xác nhận đóng sau API thành công. | Đóng phiên, đọc lại, từ chối gia hạn sau khi chủ động đóng; browser mô phỏng close HTTP 500. |
| A03 — sai tham số lời chào | Truyền stage hợp lệ, bỏ tham số cũ. | Test nhánh có survey bằng chữ ký thật của generator. |
| A04 — hiểu nhầm muốn dừng | Nhận câu kết thúc rõ ràng; không dừng chỉ vì từ “thôi”, “ngừng”, “cảm ơn” nằm trong một yêu cầu khác. Khi thật sự dừng, lưu trạng thái đóng thủ công. | Ca phủ định và câu hỏi tiếp; giữ các ca kết thúc cũ. |
| A05 — request trùng đồng thời | Claim theo assessment bằng transaction Firestore; response, cặp message và turn commit nguyên tử. Retry trả snapshot response đã lưu; cùng ID nhưng nội dung khác bị từ chối. | Claim đang xử lý, replay, nội dung khác, hai request đồng thời; rollback trước commit; worker hết lease không ghi đè worker mới. |
| A06 — tự mở lại/phiên rỗng | Kiểm tra replay trước mọi tạo session; phiên hoàn tất chỉ mở lại qua endpoint gia hạn hợp lệ. GET history/state dùng cùng định nghĩa trạng thái. Nguy cơ mới vẫn có đường hỗ trợ riêng. | Đóng rồi retry không tăng số session; từ chối gửi mới sau đóng; state giữ turn và quyền gia hạn; kiểm tra đường nguy cơ sau đóng. |
| A07 — trộn màn hình phiên | Ref phiên hiện tại và số thứ tự request ngăn response POST/GET cũ ghi vào view mới. | Browser giữ chậm POST rồi chọn chat mới; giữ chậm history A rồi chuyển B. |
| A08 — retry chấp nhận output không hợp lệ | Cùng validator cho lần đầu và lần phục hồi; chỉ nhận `STOP` với nội dung không rỗng. Retry nằm trong callback failover. | Từ chối `MAX_TOKENS`, `SAFETY`, `RECITATION` ở lần phục hồi; vẫn nhận recovery `STOP`. |
| A09 — lệch topic/action/fallback | Dùng cùng một lựa chọn cho prompt, action và tag; không chọn probe lần hai. Chủ đề đã dùng vẫn là bằng chứng hợp lệ nếu người dùng nhắc lại. Chỉ lưu topic có bằng chứng trực tiếp; fallback được dùng nguyên nhân/action đã có. | Lặp nội dung workload giữ đúng workload/action; nội dung chung không sinh tag giả. |
| A10 — lịch sử cũ/sai phiên | Query theo internal session, lấy N message mới nhất rồi đảo về thứ tự thời gian. | 60 message chỉ lấy 6 message mới nhất; session khác không lọt vào context; session hết hạn có context mới sạch. |
| A11 — +3 thành +2 | Ba stage gia hạn: làm rõ → phản ánh/hỗ trợ → đúc kết. | Cả lộ trình 3→6 và 4→7; full route giữ cùng session khi gia hạn. |
| A12 — mất bản nháp/ID | Giữ draft và ID khi lỗi; retry cùng nội dung dùng lại ID. Draft tách theo view; response cũ không xóa draft đang soạn ở view khác. | Browser chặn POST, khôi phục draft, gửi lại và so sánh ID. |
| A13 — lệch múi giờ | Response mới có timezone UTC rõ ràng; frontend đọc tương thích timestamp cũ thiếu timezone. | Test API ISO `+00:00`; browser Asia/Bangkok hiển thị 12:00 cho 05:00 UTC. |
| A14 — fallback bị giấu | Lưu cờ fallback/finish reason cùng assistant; truyền qua API, replay và history; hiện thông báo hỗ trợ dự phòng dưới bubble. Không báo gián đoạn khi người dùng chủ động dừng. | Browser kiểm tra notice; unit kiểm tra metadata replay và stage violation. |
| A15 — key/model dự phòng không được dùng | Loại credential bị từ chối rõ ràng, thử key khác; model 404 chuyển model. Lỗi request/nội dung vẫn bị trả về thay vì xoay để vượt policy. Cooldown/client cache có khóa dùng chung giữa thread. | Test key bị thu hồi, model 404, quota, lỗi tạm thời và request 400 không bị gọi lặp. |
| A16 — thiếu ownership khi history rỗng | Xác thực chủ assessment trước mọi query history/state. | HTTP 403 trước khi đọc kho dữ liệu giả lập, kể cả lịch sử rỗng. |

Kiểm chứng hoàn tất:

- **142 test backend đạt**, gồm chat, failover, các ca audit mới, dashboard và questionnaire. Chạy với SDK Gemini **1.56.0** và Pydantic **2.10.4** từ thư mục cài riêng để kiểm tra pin production đã sửa.
- **Build frontend đạt** (`npm run build`).
- **4 nhóm ca browser đạt** bằng script [chat_browser_regression.py](../../frontend/tests/chat_browser_regression.py): bản nháp/ID/fallback/giờ; POST đến chậm; GET history đến chậm; close lỗi. Script dùng Firebase và backend giả lập, không cần tài khoản, không ghi production.
- **2 lượt gọi Gemini thật đạt**, `is_fallback=false`, `finish_reason=STOP`, dùng SDK đã ghim. Không lưu hội thoại thử này vào dữ liệu người dùng.
- `git diff --check` đạt.

Phần thay đổi cấu trúc tập trung ở đường ghi chat: [chat_request_repository.py](../app/modules/chat/repositories/chat_request_repository.py) giữ claim có lease và cache response. Cặp message, số lượt và trạng thái phiên được ghi cùng transaction sau khi model trả lời. Khi generate lỗi ngoài dự kiến, số lượt và cặp message chưa được commit, nên retry không tự tiêu tốn thêm lượt. Close/extend dùng chung khóa theo assessment. Context khảo sát dùng lại helper hiện có thay cho hai bản build context riêng.

Kiểm tra cuối bổ sung: timestamp của assistant được ghi sau timestamp của user, tránh thứ tự bị đảo khi Firestore phân giải hai document có cùng thời điểm bằng document ID. Có thêm ca không nhận nhầm từ “từ từ” thành tín hiệu nguy cơ khi bỏ dấu tiếng Việt.

Đọc document cũ có `closed_reason=manual_user_decision` đã được hỗ trợ; không chạy migration hoặc sửa dữ liệu production trong đợt này. Response lưu trước cơ chế cache mới có đường replay tương thích theo lịch sử. Cache mới giữ nguyên nội dung/metadata phản hồi gốc; frontend đồng bộ state hiện tại khi nhận replay.

Giới hạn kiểm chứng: transaction được thử bằng kho mô phỏng có rollback và ràng buộc đọc trước ghi, chưa chạy Firestore emulator hoặc kiểm thử nhiều worker trên Render. Test pin SDK/Pydantic không phải bản sao đầy đủ Docker Linux. Chưa xác nhận end-to-end với bản sửa trên production vì chưa deploy.

Để áp dụng: triển khai backend Render với `requirements.txt` mới, sau đó triển khai frontend Vercel. Kiểm tra lại một phiên thường, một phiên gia hạn, refresh history và retry trên bản production mới. Bộ sưu tập claim/cache `emotion_chat_operations` được backend Admin SDK tạo khi có request; không cần đổi luồng đăng nhập, schema questionnaire hoặc công thức tính điểm.
