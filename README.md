# SmartGov — Trợ lý Ơi

SmartGov là nền tảng trợ lý nghiệp vụ dành cho cơ quan, đơn vị hành chính. Hệ thống tập trung vào quản lý kho tài liệu nội bộ, hỏi đáp có căn cứ từ tài liệu và hỗ trợ xây dựng, hoàn thiện dự thảo văn bản.

## Chức năng chính

### Kho dữ liệu

- Tạo kho, nhóm kho theo danh mục và quản lý mô tả.
- Upload, xem trạng thái xử lý và xóa tài liệu trong từng kho.
- Chia sẻ kho theo đơn vị để người cùng cơ quan có thể xem và sử dụng tài liệu được cấp quyền.
- Chuyển đổi tài liệu thành nội dung có thể tìm kiếm; dữ liệu gốc được lưu trong hạ tầng của hệ thống.

### Xây dựng dự thảo

- Chọn tài liệu góp ý từ kho dữ liệu để tổng hợp ý kiến.
- Chọn **một** file dự thảo có sẵn trong kho.
- Kết hợp file dự thảo và bảng tổng hợp ý kiến để hoàn thiện dự thảo.
- Tạo và chỉnh sửa các loại văn bản hành chính, sau đó xuất Word theo thể thức NĐ 30/2020/NĐ-CP.

### Trợ lý chat

- Hỏi đáp theo kho dữ liệu mà người dùng đã chọn và được cấp quyền truy cập.
- Tìm kiếm lai trên các đoạn tài liệu, sau đó tạo câu trả lời có căn cứ từ nội dung kho.
- Khi câu trả lời có dữ liệu định lượng phù hợp, tự sinh biểu đồ cột, đường, tròn, phân tán hoặc bảng số liệu ngay trong khung chat.
- Chỉ ghép số liệu cùng chỉ tiêu, đơn vị, phạm vi và kỳ báo cáo vào một biểu đồ.

### Quản trị

- Quản lý tài khoản, đơn vị, phòng ban và phân quyền.
- Theo dõi giới hạn dung lượng và quyền sử dụng kho dữ liệu.

## Kiến trúc

```text
Người dùng
    │
    ▼
FE (React + Nginx, :3000)
    │ /api
    ▼
BE (FastAPI, :6868) ───── PostgreSQL 16 + pgvector
    │
    ▼
AI nội bộ (FastAPI, :7000)
    ├── chuyển đổi và quét tài liệu
    ├── retrieval / drafting agents
    ├── mô hình LLM tự host
    └── tạo cấu trúc biểu đồ
```

- `FE/` chỉ gọi API công khai của BE.
- `BE/` sở hữu xác thực, RBAC, PostgreSQL, upload/download, lịch sử chat và xuất Word.
- `AI/` là dịch vụ nội bộ: không truy cập trực tiếp PostgreSQL và chỉ nhận tài liệu sau khi BE đã kiểm tra quyền.

## Chạy bằng Docker

1. Tạo tệp cấu hình từ mẫu:

```bash
cp .env.example .env
cp AI/.env.example AI/.env
```

2. Điền các biến bắt buộc trong `.env`: `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `AI_INTERNAL_TOKEN` và `JWT_SECRET`.

3. Cấu hình mô hình tại `.env`/`AI/.env`:

- `VLLM_BASE_URL`, `VLLM_MODEL_NAME`, `VLLM_API_KEY`: mô hình nội bộ.
- `EMBEDDING_API_KEY`: token dịch vụ embedding, cần thiết cho tìm kiếm vector.
- `GEMINI_API_KEY` (tùy chọn): tạo biểu đồ và fallback trả lời khi mô hình nội bộ tạm thời không sẵn sàng.

4. Build và khởi động:

```bash
docker compose up -d --build
docker compose logs -f be ai
```

| Dịch vụ | Địa chỉ |
| --- | --- |
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:6868 |
| Swagger API | http://localhost:6868/docs |

BE tự chạy Alembic migration khi khởi động và seed tài khoản quản trị từ `ADMIN_USERNAME`/`ADMIN_PASSWORD`.

## Phát triển cục bộ

```bash
# Backend
cd BE && alembic upgrade head && uvicorn app.main:app --reload --port 6868

# AI nội bộ (terminal khác)
cd AI && uvicorn app.main:app --reload --port 7000

# Frontend (terminal khác)
cd FE && npm install && npm run dev
```

## Thư mục chính

| Thư mục | Vai trò |
| --- | --- |
| `FE/` | Giao diện React/Vite và Nginx |
| `BE/` | Public API, nghiệp vụ, RBAC, Alembic và Word export |
| `AI/` | Xử lý tài liệu, retrieval, soạn thảo và tạo biểu đồ |
| `docker-compose.yml` | Cấu hình chạy toàn bộ hệ thống |
