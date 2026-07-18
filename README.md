# Thư ký Ơi

Thư ký Ơi, còn được gọi là Hệ thống AI tóm tắt và tạo báo cáo, là nền tảng trợ lý văn bản hành chính tiếng Việt. Hệ thống giúp cơ quan, đơn vị quản lý kho tài liệu, hỏi đáp theo ngữ cảnh, tổng hợp ý kiến góp ý, soạn thảo văn bản và xuất file Word theo quy trình có kiểm soát.

## Năng lực chính

- Quản lý kho dữ liệu, tài liệu, lịch sử xử lý và phân quyền người dùng.
- Chuyển đổi/OCR tài liệu, chunking, embedding và tìm kiếm lai trên PostgreSQL/pgvector.
- Soạn thảo văn bản hành chính, tổng hợp ý kiến góp ý, trích xuất dữ liệu và xuất `.docx`.
- Hỏi đáp với tài liệu theo mô hình RAG, có truy xuất ngữ cảnh và streaming qua SSE.

## Kiến trúc

```text
FE (React + Nginx) -> BE (FastAPI public API) -> PostgreSQL 16 + pgvector
                              |
                              +-> AI (FastAPI internal, port 7000)
```

- `FE/`: giao diện React, build bằng Vite, phục vụ qua Nginx trong Docker.
- `BE/`: FastAPI public API, auth/RBAC, repository/document/task/history, upload/download, SSE và Word export.
- `AI/`: FastAPI nội bộ cho OCR/Markdown, embedding, RAG, drafting agents, template và xử lý tài liệu.
- `docker-compose.yml`: chạy toàn bộ stack local gồm `postgres`, `ai`, `be`, `fe`.

## Chạy nhanh bằng Docker

1. Tạo/cập nhật `.env` ở root từ `.env.example`.
2. Tạo/cập nhật `AI/.env` từ `AI/.env.example` nếu cần cấu hình provider AI riêng.
3. Đảm bảo `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `JWT_SECRET`, `AI_INTERNAL_TOKEN` và các biến provider không còn giá trị placeholder.
4. Chạy:

```bash
docker compose up -d --build
docker compose logs -f be ai
```

Sau khi healthcheck hoàn tất:

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:6868>
- Swagger UI: <http://localhost:6868/docs>
- AI service: chỉ dùng nội bộ trong Docker network tại `ai:7000`

Backend tự chạy `alembic upgrade head` trước khi khởi động và seed tài khoản quản trị từ `ADMIN_*`.

## Phát triển local

Backend:

```bash
cd BE
alembic upgrade head
uvicorn app.main:app --reload --port 6868
```

AI service:

```bash
cd AI
uvicorn app.main:app --reload --port 7000
```

Frontend:

```bash
cd FE
npm install
npm run dev
```

## Tài liệu

Bộ tài liệu chính nằm trong [`docs/`](docs/README.md):

- [`docs/product/problem-statement.md`](docs/product/problem-statement.md): mô tả bài toán, phạm vi và tiêu chí nghiệm thu.
- [`docs/architecture/overview.md`](docs/architecture/overview.md): kiến trúc tổng quan và nguyên tắc thiết kế.
- [`docs/architecture/rag-system.md`](docs/architecture/rag-system.md): RAG, embedding, pgvector và citation.
- [`docs/api/README.md`](docs/api/README.md): bản đồ API và liên kết tới tài liệu chi tiết.
- [`docs/user/user-guide.md`](docs/user/user-guide.md): hướng dẫn sử dụng cho người dùng cuối.
- [`docs/roadmap/production-plan.md`](docs/roadmap/production-plan.md): kế hoạch hoàn thiện production.
- [`docs/audits/technical-audit.md`](docs/audits/technical-audit.md): audit kỹ thuật toàn hệ thống.

`AGENTS.md` và `CLAUDE.md` được giữ ở root vì là context vận hành cho các coding agent.

## Quy tắc kỹ thuật cần giữ

1. Public API chỉ định nghĩa trong `BE/`.
2. `FE/` không gọi trực tiếp `AI/`.
3. `BE/` kiểm tra quyền trước khi gửi tài liệu hoặc metadata sang `AI/`.
4. `AI/` không truy cập PostgreSQL và không dùng `DATABASE_URL`.
5. Mọi thay đổi schema phải có Alembic migration.
6. Không hard-code secret; cập nhật `.env.example` khi thêm biến cấu hình.
7. Giữ tương thích format SSE `chunk`/`done` với frontend.

## Kiểm tra trước khi bàn giao

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail 80 be
docker compose logs --tail 80 ai

cd FE
npm run build
```
