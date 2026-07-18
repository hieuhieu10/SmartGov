# AGENTS.md - Thư ký Ơi Context

Tài liệu này là context ngắn cho coding agent. Bộ tài liệu đầy đủ nằm trong [`docs/README.md`](docs/README.md).

## Architecture

```text
FE (React/Nginx) -> BE (FastAPI public) -> PostgreSQL 16 + pgvector
                         |
                         +-> AI (FastAPI internal, port 7000)
```

- `FE/` chỉ gọi `/api` trên BE.
- `BE/` sở hữu auth, RBAC, PostgreSQL, repository/document/task/history, upload/download, SSE và Word export.
- `AI/` sở hữu OCR/Markdown, embedding, RAG answer generation, drafting agents, template/dataset/summary services và các tác vụ AI nội bộ.
- BE gọi AI bằng HTTP với `AI_SERVICE_URL` và `X-AI-Internal-Token`.

## Database

- PostgreSQL 16, SQLAlchemy 2 async, asyncpg và Alembic.
- Chỉ BE có `DATABASE_URL`.
- Schema ban đầu nằm trong `BE/alembic/versions/`.
- Dữ liệu cấu trúc dùng JSONB; ID dùng UUID; thời gian dùng UTC `TIMESTAMPTZ`.
- Startup seed `system_admin` idempotent từ biến `ADMIN_*`.
- Không có công cụ chuyển dữ liệu từ database cũ.

## Runtime

```bash
docker compose up -d --build
docker compose logs -f be ai
```

- FE: `http://localhost:3000`
- BE: `http://localhost:6868`
- AI chỉ nằm trong Docker network tại `ai:7000`.
- Shared volumes: uploads, outputs, repo files và templates.

## Documentation

- Tổng quan repo: [`README.md`](README.md)
- Bản đồ tài liệu: [`docs/README.md`](docs/README.md)
- Kiến trúc: [`docs/architecture/overview.md`](docs/architecture/overview.md)
- RAG: [`docs/architecture/rag-system.md`](docs/architecture/rag-system.md)
- API: [`docs/api/api-reference.md`](docs/api/api-reference.md)
- Product spec: [`docs/product/problem-statement.md`](docs/product/problem-statement.md)

## Rules

1. Public API chỉ được định nghĩa trong BE; FE không gọi AI trực tiếp.
2. BE kiểm tra quyền trước khi gửi tài liệu hoặc metadata sang AI.
3. AI không được thêm `DATABASE_URL` hoặc truy cập PostgreSQL.
4. Thay đổi schema phải có Alembic migration.
5. Không hard-code secret; cập nhật `.env.example` khi thêm biến cấu hình.
6. Giữ format SSE `chunk`/`done` và public response tương thích với FE.
7. Chạy compile BE/AI và build FE trước khi bàn giao.
