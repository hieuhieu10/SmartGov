# Kiến trúc tổng quan

Thư ký Ơi là hệ thống trợ lý văn bản hành chính được tổ chức dưới dạng monorepo gồm ba service ứng dụng và một database PostgreSQL. Thiết kế ưu tiên tách ranh giới bảo mật: backend là lớp public duy nhất sở hữu người dùng, quyền và dữ liệu; AI service chỉ xử lý yêu cầu nội bộ đã được backend kiểm soát.

## Sơ đồ runtime

```text
Người dùng
   |
   v
FE React/Nginx
   |
   | /api
   v
BE FastAPI public
   |----------------------.
   |                      |
   v                      v
PostgreSQL 16 + pgvector  AI FastAPI internal
```

## Trách nhiệm từng service

| Thành phần | Trách nhiệm |
| --- | --- |
| `FE/` | Giao diện đăng nhập, dashboard, kho dữ liệu, chat, soạn thảo, quản trị. Chỉ gọi `/api` trên BE. |
| `BE/` | Auth, RBAC, org/dept/user, repository, document, chat history, task state, upload/download, SSE, Word export, PostgreSQL. |
| `AI/` | Convert/OCR tài liệu, Markdown, chunking, embedding, RAG answer, drafting agents, template, dataset extraction, tổng hợp nội dung. |
| PostgreSQL | Dữ liệu nghiệp vụ, metadata tài liệu, chunks, vector, lịch sử chat, task và audit trail. |

## Luồng xử lý chính

### Upload và lập chỉ mục tài liệu

1. Người dùng upload tài liệu qua FE.
2. BE kiểm quyền, lưu file và metadata vào PostgreSQL.
3. BE gọi AI service để convert/OCR sang Markdown.
4. AI chunk và tạo embedding.
5. BE lưu chunk, metadata và vector vào PostgreSQL/pgvector.
6. Tài liệu chuyển sang trạng thái sẵn sàng cho RAG khi quá trình lập chỉ mục hoàn tất.

### Chat với kho dữ liệu

1. FE gửi câu hỏi tới BE.
2. BE kiểm quyền truy cập repository/tài liệu.
3. BE tạo embedding truy vấn qua AI.
4. BE tìm kiếm lai bằng vector + full-text search.
5. BE gửi context đã chọn sang AI để sinh câu trả lời.
6. BE stream kết quả về FE bằng SSE.

### Soạn thảo và tổng hợp

1. Người dùng chọn mẫu, nhập yêu cầu hoặc chọn tài liệu nguồn.
2. BE chuẩn hóa task, kiểm quyền và gọi AI.
3. AI tạo nội dung dự thảo hoặc bảng tổng hợp.
4. BE xuất Word/preview, lưu lịch sử và trả kết quả cho FE.

## Nguyên tắc thiết kế

- FE không biết endpoint nội bộ của AI.
- AI không có `DATABASE_URL` và không truy cập database.
- Mọi dữ liệu đưa sang AI phải đi qua kiểm quyền ở BE.
- Public response và SSE cần giữ tương thích ngược với FE.
- Dữ liệu cấu trúc dùng JSONB khi cần linh hoạt; ID dùng UUID; thời gian lưu UTC.
- Schema đổi bằng Alembic migration, không sửa database thủ công.

## Tài liệu liên quan

- RAG chi tiết: [`rag-system.md`](rag-system.md)
- API: [`../api/README.md`](../api/README.md)
- Kế hoạch production: [`../roadmap/production-plan.md`](../roadmap/production-plan.md)
