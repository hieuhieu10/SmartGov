# CLAUDE.md - Thư ký Ơi Context

Nguồn context chính là [`AGENTS.md`](AGENTS.md). Bộ tài liệu dự án đầy đủ nằm trong [`docs/README.md`](docs/README.md).

Repo có ba service:

- `FE/`: React + Nginx, chỉ gọi `/api`.
- `BE/`: FastAPI public, auth/RBAC, PostgreSQL, task/file, retrieval và Word export.
- `AI/`: FastAPI internal cho OCR/Markdown, embedding, RAG, MarkItDown, drafting agents, template và dataset services.

Luồng dữ liệu là `FE -> BE -> PostgreSQL` và `BE -> AI`. Chỉ BE truy cập database; AI nhận dữ liệu đã được BE kiểm quyền.

Database dùng PostgreSQL 16, SQLAlchemy async, asyncpg, Alembic và pgvector.

Chạy full stack bằng:

```bash
docker compose up -d --build
```

FE ở port `3000`, BE ở port `6868`; AI chỉ có port nội bộ `7000`.
