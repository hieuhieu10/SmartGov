# CLAUDE.md - OfficeAI Context

Nguồn context kiến trúc chính là `AGENTS.md`.

Repo có ba service:

- `FE/`: React + Nginx.
- `BE/`: FastAPI public, auth/RBAC, PostgreSQL, task/file và Word export.
- `AI/`: FastAPI internal cho NotebookLM, vLLM, MarkItDown và agents.

Luồng dữ liệu là `FE -> BE -> PostgreSQL` và `BE -> AI`. Chỉ BE truy cập
database; AI nhận dữ liệu đã được BE kiểm quyền. Database dùng PostgreSQL 16,
SQLAlchemy async, asyncpg và Alembic.

Chạy full stack bằng `docker compose up -d --build`. FE ở port 3000, BE ở
port 6868; AI chỉ có port nội bộ 7000.
