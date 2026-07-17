# SmartGov / OfficeAI

Monorepo trợ lý văn phòng tiếng Việt, tách thành ba service:

```text
FE/  -> React + Nginx, chỉ gọi /api
BE/  -> FastAPI public, auth/RBAC, PostgreSQL, task/file/Word export
AI/  -> FastAPI internal, NotebookLM, vLLM, scan tài liệu và drafting agents
```

Luồng chính là `FE -> BE -> PostgreSQL` và `BE -> AI`. AI không kết nối
database và không tự quyết định quyền người dùng.

## Chạy bằng Docker

1. Thay các giá trị local trong `.env` và cấu hình model trong `AI/.env`.
2. Đăng nhập NotebookLM trên host nếu dùng engine NotebookLM.
3. Chạy:

```bash
docker compose up -d --build
docker compose logs -f be ai
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:6868`
- Swagger: `http://localhost:6868/docs`

BE chạy `alembic upgrade head` trước khi khởi động và seed tài khoản
`system_admin` từ `ADMIN_USERNAME`/`ADMIN_PASSWORD`.

## Phát triển

```bash
cd BE
alembic upgrade head
uvicorn app.main:app --reload --port 6868

cd AI
uvicorn app.main:app --reload --port 7000

cd FE
npm run dev
```
