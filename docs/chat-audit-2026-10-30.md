# Báo cáo kiểm tra chat cảm xúc — 30/10/2026

**Cập nhật sau audit:** mã nguồn đã có bản sửa và kiểm tra hồi quy; xem [kết quả sửa](chat-fixes-2026-10-30.md). Nội dung bên dưới giữ nguyên làm bằng chứng trạng thái trước khi sửa.

Kết quả: phát hiện **16 nhóm lỗi bổ sung** ngoài lỗi SDK đã báo trước đó. Trong đó có 7 nhóm ưu tiên cao (P1). Các lỗi bổ sung dưới đây chưa được sửa trong lượt kiểm tra này.

Phạm vi gồm giao diện Vercel đang chạy, API Render bằng tài khoản được cung cấp, luồng session/đóng/gia hạn/retry, xử lý lịch sử, phân loại nội dung và đường gọi Gemini. Không thử truy cập dữ liệu của người dùng khác trên production. Các tình huống an toàn, dữ liệu đóng phiên không hợp lệ và gửi trùng đồng thời được tái hiện bằng dữ liệu giả lập ở local.

Đã chạy 112 test của chat, failover, dashboard và questionnaire; tất cả đạt. Các test chạy với SDK Gemini 1.56.0 và Pydantic 2.10.4 được nạp từ thư mục cài riêng. Đây không phải bản sao đầy đủ image Linux production. Các test hiện có bỏ sót các ca biên trong báo cáo này. Có 10 chẩn đoán local bổ sung trong [bằng chứng local](chat-audit-local-evidence-2026-10-30.json), cùng [bằng chứng API live và browser](chat-audit-live-evidence-2026-10-30.json).

Tại thời điểm audit, các lượt gọi chat thật trên Render vẫn trả `is_fallback=true`, `finish_reason=FALLBACK`. Vì vậy chưa thể xác nhận chất lượng hội thoại của model thật trên production. Bản sửa dependency từ lượt trước vẫn nằm ở source local.

P1: nên xử lý trước khi coi chat ổn định; có thể bỏ sót nội dung nguy cơ, làm hỏng trạng thái hoặc trộn/lặp dữ liệu. P2: lỗi chức năng hoặc trải nghiệm cần xử lý tiếp.

| Mã | Ưu tiên | Lỗi và ảnh hưởng | Bằng chứng |
| --- | --- | --- | --- |
| A01 | P1 | Bộ lọc an toàn bỏ sót câu có tín hiệu nguy cơ rõ ràng nếu trước đó có câu phủ định hoặc thành ngữ. | Chẩn đoán local: cả hai ca trong `crisis_scope` đều trả `detected=false`. |
| A02 | P1 | Đóng phiên thủ công ghi `closed_reason` không hợp lệ vào DB, sau đó mới phát sinh lỗi validation. | Local: `status=closed` và `closed_reason=manual_user_decision` đã được ghi trước khi `ChatSession` báo lỗi. |
| A03 | P2 | Lời chào cá nhân hóa luôn rơi vào fallback khi đi qua nhánh gọi generator. | Hàm gọi thiếu `stage` bắt buộc và truyền `include_analysis_in_prompt` đã bị bỏ. Bind chữ ký hàm tái hiện `TypeError`. |
| A04 | P1 | Hiểu nhầm người dùng muốn dừng chat, bỏ qua model và trả lời chào kết thúc. | Local: cả “Mình chỉ thấy mệt thôi, nên nghỉ bao lâu?”, “Công việc không ngừng dồn tới…” và “Cảm ơn, mình muốn hỏi thêm…” đều bị nhận là muốn dừng. |
| A05 | P1 | Hai request cùng `client_message_id` chạy đồng thời vẫn được xử lý hai lần. | Chạy trực tiếp route với kho giả lập: 1 nội dung/ID duy nhất tạo 2 user message, bộ đếm tăng 2, hai response lần lượt báo turn 1 và 2. |
| A06 | P1 | Phiên đã đóng vẫn có thể tự mở lại; retry sau khi đóng tạo phiên phụ trước khi trả response cũ. | Live: gửi sau khi hoàn tất turn 5 tạo session ID mới, turn trở về 1. Chuỗi thử retry sau khi đóng cũng khiến thao tác gia hạn kế tiếp dùng session ID mới. |
| A07 | P1 | Đổi phiên khi đang đợi có thể đưa response của phiên cũ sang màn hình phiên mới. | Browser thật, response POST được giả lập và giữ chậm: màn hình đã chọn “Phiên chat mới” nhưng vẫn hiện `AUDIT_OLD_SESSION_REPLY`. |
| A08 | P1 | Nhánh phục hồi sau `MAX_TOKENS` chấp nhận cả kết quả tiếp tục bị cắt hoặc bị kết thúc vì `SAFETY`. | Local: cả `MAX_TOKENS` và `SAFETY` ở response lần hai đều được return như kết quả thành công khi có text. |
| A09 | P2 | Gắn nhãn nguyên nhân và hành động có thể không cùng chủ đề; fallback không nhận dữ liệu nguyên nhân/hành động từ route. | Local: cùng nội dung workload được chọn lần đầu là `workload`, lần hai thành `recovery`. Route lưu topic lần đầu nhưng action lần hai. |
| A10 | P2 | Lịch sử đưa vào prompt không lọc theo internal session, và lấy 50 tin cũ nhất thay vì mới nhất. | Đối chiếu route/repository: query theo assessment, `ASCENDING.limit(50)`; generator chỉ lấy 6 tin cuối của tập đó. |
| A11 | P2 | “Gia hạn +3 lượt” thực tế chỉ thêm 2 lượt. | Live riêng, không chèn retry: đóng tại turn 3; gia hạn; turn 4 còn mở; turn 5 đã đóng. |
| A12 | P2 | Mất kết nối làm mất bản nháp; gửi lại không giữ ID của lần gửi lỗi. | Browser thật chặn POST trước khi đến server: textarea rỗng, tin nhắn tạm biến mất, chỉ còn banner lỗi. Source tạo UUID mới trong mỗi lần gửi. |
| A13 | P2 | Giờ tin nhắn mới lệch 7 giờ tại Việt Nam/Thái Lan. | Browser đặt Asia/Bangkok: cùng thời điểm `05:52:25` không timezone hiển thị 05:52; thêm `Z` hiển thị đúng 12:52. API đang trả UTC không có timezone. |
| A14 | P2 | Giao diện không cho biết đang dùng câu mẫu dự phòng dù API đã báo fallback. | Các response live có `is_fallback=true`, nhưng ChatPage chỉ đọc content; không xử lý trạng thái này. |
| A15 | P2 | Một key đầu pool lỗi xác thực/quyền truy cập làm ngừng toàn bộ pool dù còn key/model dự phòng. | Local giả lập key đầu lỗi 403: chỉ gọi một cặp key/model rồi raise; key tốt kế tiếp không được thử. |
| A16 | P2 | GET lịch sử chỉ kiểm tra chủ sở hữu qua tin nhắn đầu tiên; lịch sử rỗng có thể trả metadata session của assessment khác. | Local với user giả khác chủ: endpoint vẫn trả `foreign-session` và `can_extend=true`. Chưa thử trên tài khoản khác ở production. |

Chi tiết nguyên nhân và hướng xử lý:

1. **A01 — phạm vi phủ định và thành ngữ.** [chat_response_generator.py:111](../app/modules/chat/services/chat_response_generator.py#L111) trả `False` ngay khi tìm được một mẫu phủ định ở bất kỳ đâu. Ngoài ra, điều kiện cuối đòi `not has_colloquial`, khiến một thành ngữ có thể triệt tiêu tín hiệu nguy cơ ở câu khác. Cần phân tích theo mệnh đề, kiểm tra lại tín hiệu dương tính ngoài phạm vi phủ định, và thêm ca hồi quy hỗn hợp. Ví dụ đầu trong JSON nói không có hành vi trước đây nhưng có ý muốn ở hiện tại; code hiện vẫn bỏ qua.

2. **A02 — ghi DB trước khi kiểm tra enum.** [chat_history.py:1143](../app/modules/chat/routes/chat_history.py#L1143) truyền `manual_user_decision`, trong khi [chat_session.py](../app/modules/chat/models/chat_session.py) chỉ cho phép `manual` và một số lý do khác. [chat_session_repository.py:328](../app/modules/chat/repositories/chat_session_repository.py#L328) update DB trước rồi mới dựng lại model, nên lỗi không tự rollback. Những lần đọc danh sách session có document đó cũng có thể lỗi tiếp. Frontend còn hiển thị đã đóng ngay cả khi API close thất bại. Cần thống nhất lý do đóng, kiểm tra trước khi ghi, xử lý lỗi UI và xem xét sửa các document cũ nếu production từng tạo giá trị sai.

3. **A03 — sai hợp đồng hàm lời chào.** [chat_history.py:1283](../app/modules/chat/routes/chat_history.py#L1283) dùng chữ ký generator cũ. Cần truyền `stage="greeting_and_probe"`, bỏ tham số không còn hỗ trợ, và kiểm tra nhánh có survey context. Nhánh không có survey không đi qua lệnh gọi này.

4. **A04 — tìm chuỗi con quá rộng.** [probing_questions.py:527](../app/modules/chat/services/probing_questions.py#L527) coi các từ như `thôi`, `ngừng`, `cảm ơn` xuất hiện ở bất kỳ vị trí nào là muốn dừng. Cần nhận ý định kết thúc toàn câu, tôn trọng phủ định và những phần người dùng nói muốn hỏi tiếp. Không được dùng kết quả này để bỏ qua yêu cầu hỗ trợ chỉ vì một từ khóa.

5. **A05 — idempotency chưa nguyên tử.** [chat_history.py:479](../app/modules/chat/routes/chat_history.py#L479) kiểm tra ID trước, nhưng tin nhắn có ID chỉ được lưu sau khi generate xong. Request thứ hai có thể lọt qua khoảng trống đó. Cần claim request bằng ID xác định trong transaction trước khi tăng lượt, lưu trạng thái pending/completed và liên kết response cụ thể với request. Nhánh crisis hiện còn chạy trước cả bước kiểm tra ID này; không được làm chậm tiền kiểm an toàn, nhưng việc lưu tin cần chống trùng.

6. **A06 — đóng phiên, replay và state không thống nhất.** [chat_history.py:373](../app/modules/chat/routes/chat_history.py#L373) kiểm tra `status == "closed"` trên kết quả của `get_active_session`, nhưng [chat_session_repository.py:80](../app/modules/chat/repositories/chat_session_repository.py#L80) chỉ query `status == "active"`. Nhánh chặn phiên đóng vì vậy không bắt được phiên đã đóng. `find_or_create_session` chạy trước kiểm tra replay nên retry có thể tạo phiên rỗng dù cuối cùng trả response của phiên cũ. GET `/chat/state` sau đóng trả `status=none`, turn 0 và `can_extend=false`, trong khi POST vừa báo đóng ở turn 3 và cho phép gia hạn; GET history lại còn cho phép gia hạn. Cần dùng session gần nhất và chính sách mở lại rõ ràng, kiểm tra replay trước khi tạo session, trả state nhất quán.

7. **A07 — response không gắn với màn hình đang chọn.** [ChatPage.tsx:375](../../frontend/src/pages/ChatPage.tsx#L375) cập nhật `messages` sau await mà không kiểm tra selected session còn trùng session của request hay không. GET lịch sử ở [ChatPage.tsx:171](../../frontend/src/pages/ChatPage.tsx#L171) cũng chưa có cơ chế hủy/bỏ response cũ. Cần định danh request theo session và bỏ các response không còn tương ứng; đây là trộn phiên trong cùng tài khoản, chưa có bằng chứng rò dữ liệu giữa tài khoản.

8. **A08 — kiểm tra finish reason ở sai thời điểm.** [chat_response_generator.py:629](../app/modules/chat/services/chat_response_generator.py#L629) return text của retry trước khi đi qua kiểm tra `SAFETY`, và không loại `MAX_TOKENS` lần hai. Lệnh retry cũng gọi thẳng client nên lỗi lần hai không đi qua rotator. Cần dùng cùng bước xác thực response cho mọi lần gọi, chỉ trả thành công khi finish reason hợp lệ, đồng thời giữ chính sách failover.

9. **A09 — probe có tác dụng ghi trạng thái nhưng được gọi hai lần.** [chat_history.py:665](../app/modules/chat/routes/chat_history.py#L665) đã có cached topic từ generator nhưng lại gọi `get_probing_question` để lấy action. Hàm đó đọc/ghi `used_topics`, có thể chuyển sang topic khác. Nó cũng lấy action mặc định thay vì action theo bối cảnh đã đưa vào prompt. Bên cạnh đó, lời gọi generator ở [chat_history.py:645](../app/modules/chat/routes/chat_history.py#L645) không truyền `primary_cause`/`micro_action`; fallback ở stage phản ánh vì vậy thiếu context và trở về câu mẫu trung tính. Cần chọn một lần, mang cùng topic/action qua generator, lưu và fallback.

10. **A10 — lịch sử cũ lấn lịch sử mới.** [chat_history.py:532](../app/modules/chat/routes/chat_history.py#L532) có phương thức query theo session sẵn trong repository nhưng chưa dùng. [chat_history_repository.py:153](../app/modules/chat/repositories/chat_history_repository.py#L153) lấy phần đầu lịch sử; sau hơn 50 tin, context và màn hình có thể không phản ánh tin mới. Cần giới hạn theo session, lấy N tin gần nhất rồi đảo về thứ tự thời gian. Live đã chứng minh một assessment có thể có nhiều internal session ở A06, nên đây không chỉ là tình huống lý thuyết.

11. **A11 — lệch số lượt gia hạn.** [chat_history.py:230](../app/modules/chat/routes/chat_history.py#L230) và frontend thông báo +3, nhưng state machine nhánh chuẩn đóng tại turn 5 sau khi đã đóng lần đầu tại turn 3. Nhánh fatigued tương tự đóng từ 4 lên 6. Cần thống nhất sản phẩm muốn +2 hay +3 và kiểm thử đủ lộ trình.

12. **A12 — mất bản nháp và danh tính request.** [ChatPage.tsx:365](../../frontend/src/pages/ChatPage.tsx#L365) xóa input ngay khi gửi; catch xóa tin tạm nhưng không khôi phục input. Nếu request đã được server xử lý nhưng response mất, UUID mới khiến gửi lại thành request khác. Cần giữ bản nháp cùng ID, cho retry đúng request và khôi phục nội dung khi thất bại.

13. **A13 — UTC thiếu timezone.** [chat_history.py:778](../app/modules/chat/routes/chat_history.py#L778) dùng `datetime.utcnow().isoformat()`, trong khi [ChatPage.tsx:493](../../frontend/src/pages/ChatPage.tsx#L493) parse bằng `new Date`. Cần trả ISO8601 có `Z` hoặc `+00:00` cho mọi endpoint, bao gồm close/extend/crisis/replay. Lịch sử từ Firestore có timezone khác với response mới còn có thể khiến giờ đổi sau reload.

14. **A14 — fallback không hiện trên UI.** [ChatPage.tsx:381](../../frontend/src/pages/ChatPage.tsx#L381) không đọc `is_fallback`/`finish_reason`. Cần trạng thái ngắn gọn để người dùng biết câu trả lời dự phòng đang được dùng. Cũng cần lưu metadata cùng response; replay hiện thiếu các cờ fallback/gia hạn, làm client không nhận lại cùng hợp đồng với lần đầu.

15. **A15 — chưa phân loại đầy đủ lỗi pool.** [gemini_rotator.py:128](../app/core/gemini_rotator.py#L128) chỉ chuyển khi quota hoặc lỗi tạm thời; lỗi key bị thu hồi/không hợp lệ có thể dừng cả pool. Cần phân loại lỗi rõ ràng: lỗi key thử key khác, model không tồn tại thử model khác, lỗi request hợp lệ về mặt SDK nhưng sai nội dung thì trả lỗi phù hợp. Không xoay key để né bộ lọc an toàn hay chính sách nội dung. Ca đã tái hiện là lỗi key 403 giả lập, chưa thử key production hỏng.

16. **A16 — kiểm tra quyền qua dữ liệu phụ.** [chat_history.py:836](../app/modules/chat/routes/chat_history.py#L836) không kiểm tra ownership assessment trước query. Kiểm tra tin nhắn đầu không thay thế được bước này, đặc biệt khi chưa có tin nhắn. Cần dùng cùng kiểm tra ownership như POST và `/chat/state`, trước mọi read/write liên quan. Chẩn đoán chỉ chứng minh lộ metadata khi lịch sử rỗng, không khẳng định đã đọc được nội dung chat của tài khoản khác.

Đề xuất thứ tự xử lý: A01/A02 trước; tiếp theo A05/A06/A07/A08; sau đó A03/A04/A09/A10; cuối cùng các vấn đề hợp đồng API và trải nghiệm còn lại. Mỗi lỗi cần ca hồi quy riêng, rồi kiểm tra lại trên Render sau khi triển khai dependency mới.

Giới hạn của đợt kiểm tra: không có quyền đọc log hoặc biến môi trường Render; không chạy tải nhiều worker; không thử tài khoản người dùng khác; không chờ timeout thật 60 phút/5 giờ; không thực hiện kiểm thử an toàn với model thật trên production. Hai assessment kiểm thử mới được tạo để xác minh vòng đời; không xóa lịch sử có sẵn. Các thử nghiệm mất mạng và trộn UI dùng response giả lập, không gửi những tin marker đó lên server.
