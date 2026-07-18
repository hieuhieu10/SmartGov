# Audit kỹ thuật hệ thống

Tài liệu này tổng hợp trạng thái kỹ thuật của hệ thống Thư ký Ơi sau khi thống nhất lại tài liệu. Trọng tâm là ranh giới kiến trúc, RAG, vòng đời tài liệu, xuất Word, frontend và vận hành Docker.

## 1. Kết luận ngắn

Hệ thống có kiến trúc hợp lý cho một nền tảng trợ lý văn bản hành chính: frontend tách khỏi backend public API; backend sở hữu dữ liệu, quyền và PostgreSQL; AI service xử lý các tác vụ nội bộ qua HTTP có token.

Các điểm mạnh hiện tại:

- Ranh giới FE/BE/AI rõ ràng.
- PostgreSQL 16 + pgvector phù hợp cho dữ liệu nghiệp vụ và RAG.
- Backend có nhóm API cho auth, admin, repository, documents, chat, revision và dataset.
- AI service có các endpoint cho convert/OCR, embedding, RAG answer, drafting, template và summary.
- Docker Compose chạy được toàn bộ stack local.

Các điểm cần tiếp tục hoàn thiện:

- Chuẩn hóa trạng thái lập chỉ mục tài liệu để người dùng biết tài liệu đang OCR, vectorizing, ready hay failed.
- Nâng chất lượng citation để mỗi câu trả lời quan trọng có source object rõ ràng.
- Bổ sung evaluation set cho truy hồi tiếng Việt, số hiệu văn bản, điều/khoản/điểm.
- Tách liveness và readiness cho BE/AI.
- Bổ sung test hồi quy cho export Word, tổng hợp góp ý và dataset extraction.

## 2. Ranh giới kiến trúc

```text
FE React/Nginx
  -> BE FastAPI public API
      -> PostgreSQL 16 + pgvector
      -> AI FastAPI internal service
```

Nguyên tắc cần giữ:

- FE chỉ gọi `/api` trên BE.
- BE kiểm quyền trước khi truy xuất hoặc gửi dữ liệu sang AI.
- AI không truy cập database.
- Mọi schema change đi qua Alembic migration.
- Secret chỉ nằm trong `.env`, không hard-code vào source hoặc tài liệu.

## 3. Subsystem readiness

| Subsystem | Trạng thái | Ghi chú |
| --- | --- | --- |
| Auth/RBAC | Đã có nền tảng | Cần test phân quyền theo vai trò và đơn vị |
| Repository/document | Đã có API chính | Cần trạng thái ingest rõ hơn |
| OCR/Markdown | Đã có service | Cần quality gate cho file scan xấu |
| Embedding/pgvector | Đúng hướng | Cần đo recall và exact lookup |
| Chat RAG | Đã có luồng | Cần citation có cấu trúc và refusal rõ |
| Drafting/template | Đã có service | Cần test đầu ra Word theo mẫu |
| Tổng hợp góp ý | Giá trị cao | Cần regression test với bộ mẫu thực tế |
| Revision/dataset | Có API | Cần xác nhận runtime thật và lỗi typed |
| Frontend | Build Docker pass | Bundle lớn, có thể code-split sau |
| Observability | Cơ bản | Cần readiness, metrics, trace request |

## 4. Rủi ro chính

| Mức | Rủi ro | Hướng xử lý |
| --- | --- | --- |
| Cao | Kết quả AI thiếu căn cứ hoặc citation yếu | Bắt buộc source object, validation trước khi trả lời |
| Cao | Sai số liệu khi tổng hợp báo cáo | Không tự suy diễn; giữ nguồn và cảnh báo mâu thuẫn |
| Trung bình | Người dùng tưởng tài liệu đã RAG-ready khi index chưa xong | Tách trạng thái OCR/vector/ready/failed |
| Trung bình | Quyền truy cập kho/tài liệu bị bỏ sót trong truy hồi | Test RBAC và repository isolation |
| Thấp | Frontend bundle lớn | Code-splitting các màn hình nặng |

## 5. Khuyến nghị ưu tiên

1. Hoàn thiện trạng thái ingest: `uploaded`, `converting`, `converted`, `vectorizing`, `ready`, `failed`.
2. Chuẩn hóa citation: document id, filename, section/page nếu có, chunk id và excerpt ngắn.
3. Thêm evaluation smoke cho RAG: recall@k, exact lookup số hiệu, câu hỏi không có đáp án.
4. Viết test hồi quy cho export Word và tổng hợp góp ý.
5. Tách health endpoint thành liveness/readiness để vận hành Docker tốt hơn.
6. Cập nhật tài liệu API mỗi khi router đổi.

## 6. Kiểm tra đã chạy gần nhất

- `docker compose ps`: BE, AI, Postgres healthy; FE chạy port `3000`.
- `docker compose exec -T be python -m compileall app`: pass.
- `docker compose exec -T ai python -m compileall app`: pass.
- `docker compose build fe`: pass với Docker Node 22.

Build frontend trực tiếp trên host cần Node phù hợp với Vite hiện tại. Nếu host đang thấp hơn yêu cầu, dùng Docker build hoặc nâng Node.
