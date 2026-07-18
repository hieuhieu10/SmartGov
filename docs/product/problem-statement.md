# Mô tả bài toán: AI tổng hợp góp ý và báo cáo

Tài liệu này mô tả bài toán nghiệp vụ trọng tâm của Thư ký Ơi: hỗ trợ cán bộ, công chức tổng hợp ý kiến góp ý dự thảo văn bản và tổng hợp báo cáo từ nhiều phòng ban bằng AI, nhưng vẫn giữ con người ở vai trò rà soát và quyết định cuối cùng.

## 1. Bối cảnh

Trong hoạt động hành chính, cán bộ tổng hợp thường phải xử lý hai nhóm việc tốn nhiều thời gian:

1. Lấy ý kiến góp ý dự thảo văn bản từ nhiều phòng, ban, đơn vị rồi tổng hợp, giải trình và hoàn thiện dự thảo.
2. Thu nhận báo cáo, số liệu, nhận xét từ các phòng ban rồi biên tập thành báo cáo chung của cơ quan hoặc đơn vị.

Quy trình hiện nay thường thủ công: gửi văn bản, nhận file Word/PDF/Excel, đọc từng tài liệu, trích xuất ý kiến hoặc số liệu, lập bảng tổng hợp, đối chiếu, chỉnh sửa dự thảo, sau đó xuất báo cáo cuối cùng. Khi số lượng đầu mối lớn, khối lượng đọc và kiểm tra tăng rất nhanh.

## 2. Vấn đề cần giải quyết

Các điểm đau chính:

- Mất nhiều ngày công để đọc, phân loại và tổng hợp tài liệu.
- Dễ bỏ sót ý kiến, ghi nhầm đơn vị, cộng nhầm số liệu hoặc áp dụng chỉnh sửa không nhất quán.
- Định dạng phản hồi không thống nhất: Word, PDF, scan, bảng Excel, bảng trong văn bản hoặc đoạn văn tự do.
- Khó truy vết nguồn gốc khi lãnh đạo cần biết ý kiến/số liệu đến từ văn bản nào.
- Cán bộ phải lặp lại thao tác khi có phòng ban gửi bổ sung hoặc đính chính.

Thư ký Ơi cần giảm tải các thao tác cơ học nhưng không thay thế thẩm quyền chuyên môn của cán bộ.

## 3. Mục tiêu hệ thống

Mục tiêu tổng quát là xây dựng một trợ lý AI hành chính có khả năng tiếp nhận nhiều tài liệu nguồn, trích xuất nội dung quan trọng, tổng hợp có căn cứ, gợi ý phương án xử lý và xuất tài liệu theo mẫu chuẩn.

Mục tiêu cụ thể:

- Giảm tối thiểu 60-70% thời gian tổng hợp so với quy trình thủ công.
- Không bỏ sót ý kiến/số liệu quan trọng trong bộ hồ sơ đầu vào.
- Mọi nội dung tổng hợp phải truy vết được về tài liệu nguồn và đơn vị gửi.
- Đầu ra có thể xuất thành bảng tổng hợp, báo cáo chung, bản dự thảo hoàn thiện hoặc file Word.
- Người dùng không chuyên kỹ thuật vẫn sử dụng được sau một buổi hướng dẫn.
- AI chỉ tạo dự thảo/gợi ý; cán bộ vẫn phê duyệt trước khi ban hành.

## 4. Trường hợp nghiệp vụ 1: Tổng hợp ý kiến góp ý dự thảo

### Quy trình hiện trạng

1. Đơn vị chủ trì ban hành văn bản xin ý kiến, kèm dự thảo và thời hạn góp ý.
2. Các phòng ban gửi phản hồi: thống nhất, đề nghị chỉnh sửa, không thống nhất, góp ý thể thức hoặc góp ý khác.
3. Cán bộ tổng hợp đọc toàn bộ phản hồi, trích từng ý kiến, xác định vị trí liên quan trong dự thảo.
4. Cán bộ lập bảng tổng hợp, đề xuất tiếp thu/giải trình và cập nhật dự thảo.
5. Lãnh đạo hoặc đơn vị chủ trì rà soát, phê duyệt, ban hành.

### Vai trò của AI

Hệ thống cần hỗ trợ:

- Nhận dự thảo gốc và toàn bộ văn bản góp ý.
- Trích xuất từng ý kiến riêng lẻ, kể cả khi nhiều ý kiến nằm trong cùng một đoạn.
- Gắn ý kiến với vị trí dự thảo: chương, mục, điều, khoản, điểm, trang hoặc đoạn.
- Phân loại ý kiến: thống nhất, thống nhất có chỉnh sửa, không thống nhất, góp ý thể thức, ý kiến khác.
- Nhận diện ý kiến trùng lặp/tương đồng giữa các đơn vị.
- Sinh bảng tổng hợp ý kiến góp ý theo mẫu.
- Gợi ý phương án tiếp thu, tiếp thu một phần hoặc giải trình không tiếp thu.
- Áp dụng các chỉnh sửa đã được cán bộ duyệt vào dự thảo và xuất bản so sánh trước/sau.

### Đầu ra kỳ vọng

- Bảng tổng hợp ý kiến góp ý.
- Thống kê số đơn vị đã/chưa góp ý và số ý kiến theo loại.
- Báo cáo tiếp thu, giải trình.
- Dự thảo hoàn chỉnh sau tiếp thu.
- Bản so sánh trước/sau hoặc track changes nếu được hỗ trợ.

## 5. Trường hợp nghiệp vụ 2: Tổng hợp báo cáo từ phòng ban

### Quy trình hiện trạng

1. Đơn vị chủ quản ban hành yêu cầu báo cáo, thường kèm đề cương hoặc biểu mẫu.
2. Phòng ban gửi báo cáo thành phần với mức độ tuân thủ mẫu khác nhau.
3. Cán bộ đọc từng báo cáo, trích số liệu và nội dung diễn giải.
4. Cán bộ cộng gộp, đối chiếu, phát hiện thiếu/mâu thuẫn, rồi biên tập thành báo cáo chung.
5. Khi có bổ sung/đính chính, cán bộ cập nhật lại bảng số liệu và văn bản báo cáo.

### Vai trò của AI

Hệ thống cần hỗ trợ:

- Nhận đề cương/biểu mẫu và các báo cáo thành phần.
- Phân biệt số liệu, bảng biểu, chỉ tiêu và nội dung diễn giải.
- Ánh xạ nội dung từng phòng ban vào cấu trúc đề cương chung.
- Chuẩn hóa kỳ báo cáo, đơn vị tính, tên chỉ tiêu.
- Cộng gộp số liệu và cảnh báo thiếu, mâu thuẫn hoặc bất thường.
- Tổng hợp phần diễn giải theo văn phong hành chính thống nhất.
- Chỉ rõ phòng ban chưa gửi hoặc gửi thiếu nội dung.
- Cập nhật báo cáo chung khi có bổ sung/đính chính.

### Đầu ra kỳ vọng

- Văn bản báo cáo chung.
- Bảng số liệu tổng hợp có dẫn nguồn theo phòng ban.
- Danh sách phòng ban chưa gửi hoặc gửi thiếu.
- Cảnh báo số liệu bất thường.
- File Word/Excel theo mẫu nếu cấu hình có sẵn.

## 6. Yêu cầu chức năng

### Tiếp nhận và xử lý đầu vào

- Hỗ trợ `.doc`, `.docx`, `.pdf`, PDF scan cần OCR, `.xlsx` và ảnh chụp văn bản.
- Nhận diện metadata: đơn vị gửi, số/ký hiệu, ngày ban hành, trích yếu, người ký.
- Theo dõi danh sách đầu mối phải phản hồi và trạng thái đã/chưa gửi.
- Lưu tài liệu nguồn để phục vụ truy vết.

### Trích xuất và tổng hợp

- Tách nội dung theo ý kiến, chỉ tiêu, đoạn báo cáo hoặc bảng số liệu.
- Gắn nội dung trích xuất với nguồn gốc rõ ràng.
- Gom nhóm ý kiến/nội dung tương đồng.
- Cảnh báo dữ liệu thiếu, mâu thuẫn hoặc khó xác định.
- Cho phép người dùng sửa, duyệt hoặc loại bỏ từng kết quả AI.

### Xuất kết quả

- Sinh bảng tổng hợp theo mẫu cấu hình được.
- Sinh văn bản báo cáo/dự thảo theo văn phong hành chính.
- Xuất `.docx` và, khi phù hợp, `.xlsx`.
- Lưu lịch sử thao tác và phiên bản kết quả.

## 7. Yêu cầu phi chức năng

- Bảo mật dữ liệu hành chính; ưu tiên triển khai on-premise hoặc hạ tầng được phê duyệt.
- Không xử lý văn bản mật nếu chưa đáp ứng tiêu chuẩn bảo mật tương ứng.
- Mọi nội dung AI sinh ra phải có căn cứ và được con người phê duyệt.
- Hỗ trợ tốt tiếng Việt có dấu, văn phong hành chính và cấu trúc văn bản pháp lý.
- Xử lý được một đợt thông thường 10-30 văn bản trong vài phút, tùy dung lượng file và provider AI.
- Cho phép tùy biến mẫu bảng, đề cương, quy trình duyệt và danh mục phân loại theo từng cơ quan.

## 8. Đầu vào và đầu ra

| Nghiệp vụ        | Đầu vào                                                             | Đầu ra                                                                    |
| ---------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Góp ý dự thảo    | Dự thảo gốc, văn bản góp ý, danh sách đơn vị, mẫu bảng tổng hợp     | Bảng tổng hợp ý kiến, báo cáo giải trình, dự thảo hoàn chỉnh, bản so sánh |
| Tổng hợp báo cáo | Đề cương/mẫu, báo cáo thành phần, bảng số liệu, danh sách phòng ban | Báo cáo chung, bảng số liệu tổng hợp, cảnh báo dữ liệu, danh sách thiếu   |

## 9. Thách thức chính

- Đầu vào rất không đồng nhất về định dạng, cấu trúc và chất lượng scan.
- Ý kiến góp ý có thể mô tả gián tiếp, không chỉ rõ vị trí dự thảo.
- Số liệu cần chính xác tuyệt đối; AI không được tự suy diễn.
- Citation/truy vết nguồn là yêu cầu bắt buộc để chống hallucination.
- Mỗi cơ quan có mẫu biểu và quy trình khác nhau.
- Cần cân bằng giữa tự động hóa và quyền kiểm soát của cán bộ.

## 10. Phạm vi giai đoạn 1

Giai đoạn 1 tập trung vào hai nghiệp vụ cốt lõi:

- Tổng hợp ý kiến góp ý dự thảo.
- Tổng hợp số liệu và nội dung báo cáo từ phòng ban.

Đầu vào ưu tiên là file điện tử có thể trích xuất hoặc OCR: `.docx`, `.pdf`, PDF scan tiếng Việt và `.xlsx`. Đầu ra ưu tiên là bảng tổng hợp, báo cáo chung, bản dự thảo hoàn thiện và file Word.

Các phần như tích hợp hệ thống quản lý văn bản điều hành, ký số, luồng phê duyệt điện tử nhiều cấp và mở rộng sang nghiệp vụ khác có thể đưa vào giai đoạn sau.

## 11. Tiêu chí nghiệm thu gợi ý

- Trích xuất đúng và đủ tối thiểu 95% ý kiến góp ý trên bộ kiểm thử thực tế.
- Phân loại ý kiến đúng tối thiểu 90%.
- Gắn đúng vị trí ý kiến vào dự thảo tối thiểu 90%.
- Trích xuất số liệu đúng tối thiểu 98% với báo cáo thành phần rõ nguồn.
- Ánh xạ nội dung báo cáo vào đúng mục đề cương tối thiểu 90%.
- 100% số liệu/nội dung trong kết quả có thể truy vết về tài liệu nguồn.
- Thời gian tổng hợp một đợt điển hình giảm tối thiểu 60%.
- Cán bộ tổng hợp dùng được các chức năng chính sau một buổi đào tạo.
