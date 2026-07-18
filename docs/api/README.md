# API

Backend public API chạy tại `http://localhost:6868`. Swagger UI khả dụng tại `http://localhost:6868/docs`.

Tài liệu chi tiết endpoint nằm trong [`api-reference.md`](api-reference.md).

## Nguyên tắc tích hợp

- Client bên ngoài chỉ gọi `BE/`, không gọi trực tiếp `AI/`.
- Hầu hết endpoint yêu cầu JWT Bearer token.
- API nội bộ giữa BE và AI dùng header `X-AI-Internal-Token`.
- Streaming chat dùng SSE; frontend đang kỳ vọng event/data theo format hiện có.

## Nhóm endpoint chính

| Nhóm | Mục đích |
| --- | --- |
| Auth | Đăng ký, đăng nhập, lấy thông tin người dùng hiện tại. |
| Admin | Quản lý đơn vị, phòng ban, tài khoản và vai trò. |
| Repositories | Tạo, sửa, chia sẻ và chọn kho dữ liệu. |
| Documents | Upload, chuyển đổi, lập chỉ mục, tải xuống và quản lý tài liệu. |
| Chat | Hỏi đáp với kho dữ liệu, lưu lịch sử, stream phản hồi. |
| Drafting / revision / dataset | Soạn thảo, biên tập, trích xuất dữ liệu và xuất file Word. |
| Internal retrieval | Endpoint nội bộ phục vụ AI agents truy hồi qua BE. |

## Quick check

```bash
curl http://localhost:6868/api/health
```

Khi API thay đổi, cập nhật cả Swagger schema trong code và [`api-reference.md`](api-reference.md).
