# Hướng dẫn sử dụng Thư ký Ơi

Tài liệu này dành cho cán bộ, chuyên viên và quản trị viên sử dụng giao diện Thư ký Ơi. Mục tiêu là giúp người dùng biết nên vào đâu, làm gì trước và kết quả nhận được là gì.

## 1. Đăng nhập

1. Mở hệ thống tại địa chỉ do quản trị viên cung cấp, ví dụ `http://localhost:3000` khi chạy local.
2. Nhập tên đăng nhập và mật khẩu.
3. Sau khi đăng nhập, hệ thống mở vào khu vực làm việc chính.

Nếu quên mật khẩu hoặc không thấy đúng quyền, liên hệ quản trị viên hệ thống.

## 2. Trang tổng quan

Trang tổng quan cho biết tình trạng dữ liệu và các lối vào nhanh:

- Số kho dữ liệu đang có.
- Số tài liệu đã tải lên.
- Trạng thái xử lý tài liệu hoặc kết nối AI nếu giao diện hiển thị.
- Các kho dữ liệu gần đây để vào nhanh phần chat hoặc soạn thảo.

## 3. Kho dữ liệu

Kho dữ liệu là nơi gom tài liệu theo một chủ đề, hồ sơ, nhiệm vụ hoặc đợt xử lý.

### Tạo kho

1. Vào mục Kho dữ liệu.
2. Chọn tạo kho mới.
3. Đặt tên rõ nghĩa, ví dụ `Góp ý dự thảo quy chế 2026` hoặc `Báo cáo chuyển đổi số quý II`.
4. Chọn chế độ riêng tư/công khai nếu hệ thống hỗ trợ.

### Tải tài liệu

1. Mở kho dữ liệu.
2. Chọn tải lên hoặc kéo thả file.
3. Đợi hệ thống xử lý tài liệu.

Các định dạng thường dùng: Word, PDF, Excel, ảnh scan và một số định dạng media nếu backend đã bật.

### Lưu ý

- Đặt tên file dễ hiểu để truy vết nhanh.
- Không tải văn bản mật nếu hệ thống chưa được phê duyệt cho cấp độ bảo mật tương ứng.
- Khi tài liệu xử lý lỗi, xem thông báo trạng thái hoặc tải lại bản rõ hơn.

## 4. Chat với tài liệu

Tính năng chat giúp hỏi đáp trên nội dung trong kho dữ liệu.

1. Chọn kho dữ liệu cần hỏi.
2. Nhập câu hỏi cụ thể.
3. Đọc câu trả lời và kiểm tra nguồn/citation nếu hệ thống hiển thị.
4. Với câu hỏi tiếp nối, nêu rõ bối cảnh nếu câu trước chưa đủ.

Ví dụ câu hỏi tốt:

- `Tóm tắt các điểm chính trong dự thảo này.`
- `Đơn vị nào đề xuất sửa Điều 5?`
- `Các số liệu về hồ sơ trực tuyến trong quý II là bao nhiêu?`
- `Nội dung nào còn thiếu căn cứ trong báo cáo?`

AI chỉ là công cụ hỗ trợ. Các nội dung quan trọng cần được đối chiếu với tài liệu nguồn trước khi sử dụng chính thức.

## 5. Soạn thảo văn bản

Tính năng soạn thảo hỗ trợ tạo dự thảo văn bản hành chính từ mẫu hoặc từ yêu cầu người dùng.

Quy trình gợi ý:

1. Chọn loại văn bản hoặc mẫu.
2. Nhập thông tin bắt buộc: cơ quan ban hành, trích yếu, căn cứ, nội dung chính.
3. Chọn kho dữ liệu nguồn nếu muốn AI dùng tài liệu đã tải lên.
4. Sinh dự thảo.
5. Rà soát, chỉnh sửa, sau đó xuất Word.

Các đầu ra AI sinh ra cần được cán bộ phụ trách kiểm tra trước khi trình ký hoặc phát hành.

## 6. Tổng hợp góp ý và báo cáo

Khi cần tổng hợp nhiều văn bản góp ý hoặc báo cáo thành phần:

1. Tạo một kho dữ liệu riêng cho đợt tổng hợp.
2. Tải lên dự thảo/đề cương và toàn bộ văn bản phản hồi.
3. Chạy tác vụ tổng hợp nếu giao diện có nút tương ứng.
4. Kiểm tra bảng tổng hợp, nguồn trích dẫn, cảnh báo thiếu/mâu thuẫn.
5. Chỉnh sửa kết quả, duyệt nội dung được tiếp thu và xuất file.

Nên giữ nguyên bộ tài liệu nguồn trong kho để phục vụ kiểm tra lại sau này.

## 7. Quản trị hệ thống

Chỉ người dùng có quyền quản trị mới thấy khu vực quản trị.

Quản trị viên có thể:

- Tạo và chỉnh sửa đơn vị/phòng ban.
- Tạo tài khoản người dùng.
- Cấp vai trò phù hợp.
- Đặt lại mật khẩu.
- Kiểm tra dữ liệu/kho dùng chung nếu được phân quyền.

## 8. Thực hành tốt

- Mỗi nhiệm vụ hoặc đợt báo cáo nên có một kho riêng.
- Tên kho và tên file nên có thời gian, đơn vị và nội dung.
- Luôn kiểm tra nguồn trước khi dùng kết quả AI trong văn bản chính thức.
- Với số liệu, ưu tiên đối chiếu lại bảng gốc.
- Khi phát hiện AI tổng hợp sai, chỉnh trực tiếp trong kết quả và ghi nhận nguồn đúng.
