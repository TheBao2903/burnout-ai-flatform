# Khảo sát trạng thái: hợp đồng và nghiệp vụ

## Hai loại khảo sát

| Loại | Phiên bản | Câu bắt buộc | Thang trả lời |
|---|---|---|---|
| `daily_checkin` | `sta-daily-9-v1` | E1–E3, D1–D3, JD1–JD3 | 1–5, từ không đồng ý đến đồng ý |
| `olbi_periodic` | `olbi-16-4pt-vi-v1` | E1–E8, D1–D8 | 1–4, từ không đồng ý đến đồng ý |

Daily có 9 câu lõi. Giấc ngủ, hồi phục và quá tải là thông tin bổ sung,
không tham gia điểm E/D. OLBI không thu thập hoặc tự điền các trường này.
STA daily là bộ câu hỏi vận hành của dự án; không tuyên bố là một thang
đánh giá hằng ngày đã được kiểm định tâm trắc độc lập.

OLBI dựa trên phụ lục Demerouti, Mostert & Bakker (2010),
[doi:10.1037/a0019408](https://doi.org/10.1037/a0019408).
Bản dịch tiếng Việt dùng để tham khảo, chưa được kiểm định trong dự án.
Ứng dụng dùng hướng trả lời 1=không đồng ý, 4=đồng ý, ngược hướng đánh số
trong phụ lục. Vì vậy các câu tích cực được đảo bằng `5 - answer`.

| Nhóm | ID trong ứng dụng → số thứ tự trong phụ lục | Câu tích cực cần đảo |
|---|---|---|
| E | E1–E8 → 2, 4, 5, 8, 10, 12, 14, 16 | E3, E5, E7, E8 |
| D | D1–D8 → 1, 3, 6, 7, 9, 11, 13, 15 | D1, D4, D7, D8 |

## Chấm và lưu

Frontend gửi câu trả lời nguyên bản cùng loại và phiên bản. Backend kiểm
tra đủ khóa, điểm nguyên và khoảng thang đo trước khi lưu. Không nhận điểm
trung bình từ client làm kết quả chính thức. Backend tính `questionnaire_scores`
và lưu cùng các câu trả lời gốc trong `survey_history`.

E/D là trung bình của mỗi nhóm sau đảo điểm, JD là bối cảnh daily. Điểm
0–100 để hiển thị được tính bằng `(mean(E,D) - 1) / (scale_max - 1) * 100`.
Hai phần ba chia thang thành ba vùng tham khảo: thấp, trung bình, cao.
Đây là quy ước ứng dụng, không phải điểm cắt lâm sàng. Kết quả trả ngay và
BurnoutEngine dùng chung hàm chấm. Kết quả engine giữ thang gốc trong core
và có `questionnaire_scores.scale_max` để giải thích.

Gửi lại cùng assessment và cùng câu trả lời không ghi thêm survey hoặc
đổi thời điểm hoàn tất. ID được giữ khi frontend thử lại; bản ghi mới dùng
document ID xác định từ user/assessment. Kiểm tra chủ sở hữu trước cập nhật.
Nếu AI không khả dụng, giao diện vẫn dùng được kết quả chấm đã lưu.

## Thời gian và lịch sử

- `GET /api/survey/questionnaire-status`: daily hôm nay, OLBI gần nhất,
  ngày khuyến nghị làm lại và trạng thái đến hạn.
- Chu kỳ nhắc OLBI là 14 ngày, một quy ước vận hành; không chặn người dùng
  làm lại sớm. Không có tác vụ gửi thông báo tự động.
- AI daily có thể tham chiếu mức nền OLBI trong 14 ngày, có ghi rõ khác thang.
- Xu hướng daily lấy bản mới nhất mỗi ngày theo UTC+7 và lọc cửa sổ ngày
  thực tế. Loại OLBI ra khỏi rolling stats, cảnh báo daily và STA dashboard.
- Cảnh báo liên tục cần ba ngày khác nhau, liền nhau; ba lần gửi trong ngày
  không được xem là ba ngày. Dữ liệu lịch sử so sánh phải cùng loại khảo sát.
- OLBI hiển thị lại đủ 16 câu nguyên bản; daily hiển thị lại đủ 9 câu.

`periodic_surveys` hiện có là khảo sát môi trường làm việc JR/Six Areas,
khác với OLBI định kỳ. Không chuyển đổi hoặc xóa collection này.

## Tương thích và giới hạn

Client không có metadata vẫn dùng nhánh legacy. Các bài OLBI cũ từng được
nén thành ba câu lặp không thể phục dựng hoặc tự nhận diện chắc chắn;
không tự gán chúng thành OLBI mới. Không có migration suy đoán dữ liệu.

Truy vấn lịch sử hiện dùng lọc user rồi sắp xếp/lọc trong ứng dụng để tránh
phụ thuộc composite index Firestore và tránh mất bản mới do limit không
sắp xếp. Khi lượng lịch sử lớn, cần bổ sung index và phân trang phía database.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_questionnaire_contract.py -q
# Trong frontend:
npm run build
```

Các test dùng repository giả lập; không ghi vào Firestore thật, không gọi AI.

## Tiến triển OLBI trên dashboard

Dashboard có khu duy nhất `#olbi-progress` dành cho lịch sử OLBI. Biểu đồ daily
được ghi rõ là check-in thang 1–5. OLBI dùng thang 1–4 sau đảo điểm, hai đường
cạn kiệt (cam, liền) và mất gắn kết (tím, đứt); không gộp với daily hoặc kết quả
nhận diện cảm xúc khuôn mặt. Đường nối giữa các bài không đại diện cho ngày chưa đo.

`GET /api/v1/dashboard/olbi-history?start_date=2026-09-01&end_date=2026-09-30`
trả lịch sử của tài khoản đăng nhập. Không nhận user ID thay thế. Dashboard chỉ
có một bộ lọc thời gian: preset hoặc lịch ngày tùy chỉnh. OLBI, check-in và
phần tổng hợp nhận cùng hai ngày, tính trọn cả ngày đầu/cuối theo UTC+7.
API vẫn hỗ trợ `days` cho client cũ; giao diện không có bộ chọn ngày riêng cho OLBI.

Nguồn là survey đã hoàn tất, có đủ 16 câu, phiên bản
`olbi-16-4pt-vi-v1`, điểm lưu `core-ed-v1` và thang 4. Endpoint đọc điểm đã lưu,
không chạy AI, không ghi dữ liệu. Loại bản ghi thiếu điểm/câu trả lời, sai phiên
bản, điểm ngoài thang và thời gian tương lai. Trùng assessment lấy bản mới nhất.
Không suy đoán OLBI từ những bản ghi legacy không có loại khảo sát.

Biểu đồ, các thẻ và nhận xét chỉ dùng những bài trong khoảng đã chọn. Mốc đầu
là bài sớm nhất, mốc cuối là bài muộn nhất trong khoảng; “lần trước” cũng phải
nằm trong khoảng này. Chỉ một bài thì chưa có độ thay đổi. Không có bài thì
không hiển thị thẻ so sánh từ ngoài khoảng, không tự mở rộng lịch sử, hướng dẫn
đổi bộ lọc chung. Hai chiều trái hướng được mô tả riêng; không suy ra đã hồi
phục hoặc hiệu quả nhân quả của một hành động.

Mỗi điểm và bảng số liệu mở được câu trả lời gốc tại
`/survey-test?survey_id=<document-id>`, kể cả bài nằm ngoài 20 bản ghi của danh
sách lịch sử. API chi tiết vẫn kiểm tra chủ sở hữu. Nút “Xem tiến triển OLBI
của tôi” dẫn từ khảo sát đến `/dashboard#olbi-progress`; nút làm OLBI mở
`/survey-test?mode=olbi16` đúng chế độ.

Biểu đồ có trạng thái tải, tải lỗi/thử lại, chưa có lịch sử, chỉ một điểm và
bảng số liệu thay thế. Dữ liệu tải lại khi mở dashboard, đổi khoảng hoặc bấm
tải lại; hủy request cũ khi đổi khoảng hay rời trang để tránh hiện nhầm kết quả.

Cache dashboard dùng user + ngày bắt đầu + ngày kết thúc, không chỉ số ngày.
Khi thay khoảng, không dùng dữ liệu cũ cho nhãn ngày mới; hủy request cũ và
kiểm tra thứ tự response. Reset đưa toàn bộ về cùng khoảng mặc định. Các API
kiểm tra cặp ngày đầy đủ, thứ tự hợp lệ, khoảng không quá 3650 ngày. Biểu đồ
check-in tính các ngày lịch tính đến ngày cuối đã chọn, kể cả khi xem quá khứ.
