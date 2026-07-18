# Thư ký Ơi API Reference

Base URL khi chạy local: `http://localhost:6868`

Swagger UI: `http://localhost:6868/docs`

## Xác thực

Public API dùng JWT Bearer token sau khi đăng nhập.

```http
Authorization: Bearer <access_token>
```

API nội bộ giữa BE và AI dùng header:

```http
X-AI-Internal-Token: <AI_INTERNAL_TOKEN>
```

Frontend không gọi trực tiếp AI service.

## Health

| Method | Path          | Ghi chú                         |
| ------ | ------------- | ------------------------------- |
| `GET`  | `/api/health` | Health check backend public API |

AI service có health riêng tại `/health`, chỉ dùng trong Docker network hoặc khi debug nội bộ.

## Auth

Prefix: `/api/auth`

| Method | Path               | Ghi chú                           |
| ------ | ------------------ | --------------------------------- |
| `POST` | `/login`           | Đăng nhập, trả JWT                |
| `GET`  | `/me`              | Lấy thông tin người dùng hiện tại |
| `POST` | `/change-password` | Đổi mật khẩu                      |

## Admin

Prefix: `/api/admin`

| Method   | Path                                  | Ghi chú             |
| -------- | ------------------------------------- | ------------------- |
| `POST`   | `/organizations`                      | Tạo đơn vị          |
| `GET`    | `/organizations`                      | Danh sách đơn vị    |
| `GET`    | `/organizations/{org_id}`             | Chi tiết đơn vị     |
| `PUT`    | `/organizations/{org_id}`             | Cập nhật đơn vị     |
| `DELETE` | `/organizations/{org_id}`             | Xóa đơn vị          |
| `POST`   | `/organizations/{org_id}/departments` | Tạo phòng ban       |
| `GET`    | `/organizations/{org_id}/departments` | Danh sách phòng ban |
| `PUT`    | `/departments/{dept_id}`              | Cập nhật phòng ban  |
| `DELETE` | `/departments/{dept_id}`              | Xóa phòng ban       |
| `POST`   | `/users`                              | Tạo tài khoản       |
| `GET`    | `/users`                              | Danh sách tài khoản |
| `PUT`    | `/users/{user_id}`                    | Cập nhật tài khoản  |
| `DELETE` | `/users/{user_id}`                    | Xóa tài khoản       |

## Repositories

Prefix: `/api/repositories`

| Method   | Path                        | Ghi chú                                       |
| -------- | --------------------------- | --------------------------------------------- |
| `POST`   | `(prefix root)`             | Tạo kho dữ liệu                               |
| `GET`    | `(prefix root)`             | Danh sách kho dữ liệu người dùng có quyền xem |
| `GET`    | `/storage-usage`            | Thống kê dung lượng                           |
| `GET`    | `/categories`               | Danh sách nhóm kho                            |
| `POST`   | `/categories`               | Tạo nhóm kho                                  |
| `PUT`    | `/categories/{category_id}` | Cập nhật nhóm kho                             |
| `DELETE` | `/categories/{category_id}` | Xóa nhóm kho                                  |
| `GET`    | `/{repo_id}`                | Chi tiết kho                                  |
| `PUT`    | `/{repo_id}`                | Cập nhật kho                                  |
| `DELETE` | `/{repo_id}`                | Xóa kho                                       |

## Documents

Prefix: `/api/repositories/{repo_id}/documents`

| Method   | Path                 | Ghi chú                      |
| -------- | -------------------- | ---------------------------- |
| `POST`   | `(prefix root)`      | Upload/tạo tài liệu          |
| `POST`   | `/consolidate`       | Tổng hợp tài liệu/góp ý      |
| `GET`    | `(prefix root)`      | Danh sách tài liệu trong kho |
| `PUT`    | `/{doc_id}`          | Cập nhật metadata tài liệu   |
| `POST`   | `/{doc_id}/convert`  | Chạy convert/OCR/index lại   |
| `GET`    | `/{doc_id}/preview`  | Xem preview HTML             |
| `GET`    | `/{doc_id}/file`     | Tải file gốc/kết quả         |
| `GET`    | `/{doc_id}/markdown` | Lấy Markdown đã chuyển đổi   |
| `DELETE` | `/{doc_id}`          | Xóa tài liệu                 |

## Chat

Prefix: `/api/repositories/{repo_id}/chat`

| Method   | Path            | Ghi chú                     |
| -------- | --------------- | --------------------------- |
| `POST`   | `(prefix root)` | Gửi câu hỏi tới kho dữ liệu |
| `GET`    | `/history`      | Lấy lịch sử chat            |
| `DELETE` | `/history`      | Xóa lịch sử chat            |

Chat response có thể dùng SSE tùy implementation hiện tại của backend/frontend. Khi thay đổi format streaming, cần cập nhật frontend cùng lúc.

## Revision tasks

Prefix: `/api/revision-tasks`

| Method   | Path                        | Ghi chú                |
| -------- | --------------------------- | ---------------------- |
| `POST`   | `(prefix root)`             | Tạo tác vụ revision    |
| `GET`    | `(prefix root)`             | Danh sách tác vụ       |
| `GET`    | `/{task_id}`                | Chi tiết tác vụ        |
| `GET`    | `/{task_id}/review`         | Lấy kết quả review     |
| `GET`    | `/{task_id}/preview/{kind}` | Preview HTML theo loại |
| `POST`   | `/{task_id}/approve`        | Duyệt tác vụ           |
| `POST`   | `/{task_id}/reject`         | Từ chối tác vụ         |
| `GET`    | `/{task_id}/download/final` | Tải file cuối          |
| `DELETE` | `/{task_id}`                | Xóa tác vụ             |

## Document datasets

Prefix: `/api/document-datasets`

| Method | Path             | Ghi chú                                    |
| ------ | ---------------- | ------------------------------------------ |
| `POST` | `/extract`       | Trích xuất dữ liệu có cấu trúc từ tài liệu |
| `POST` | `/word/preview`  | Preview Word dưới dạng HTML                |
| `POST` | `/word/download` | Xuất/tải file Word                         |

## Internal retrieval

Prefix: `/internal/retrieval`

| Method | Path      | Ghi chú                                      |
| ------ | --------- | -------------------------------------------- |
| `POST` | `/search` | Endpoint nội bộ để AI agents truy hồi qua BE |

Endpoint này không phải public API cho frontend. BE vẫn là lớp kiểm quyền trước khi truy hồi dữ liệu.

## AI internal service

AI service chạy nội bộ ở port `7000`. Các endpoint chính trong `AI/app/main.py`:

| Method | Path                              | Ghi chú                         |
| ------ | --------------------------------- | ------------------------------- |
| `GET`  | `/health`                         | Health check AI                 |
| `POST` | `/internal/documents/convert`     | Convert/OCR tài liệu            |
| `POST` | `/internal/documents/chunk-embed` | Chunk và embedding Markdown     |
| `POST` | `/internal/embeddings/create`     | Tạo embedding                   |
| `POST` | `/internal/rag/answer`            | Sinh câu trả lời RAG từ context |
| `POST` | `/internal/chat/self-hosted`      | Chat self-hosted legacy path    |
| `POST` | `/internal/dataset/extract`       | Trích xuất dataset              |
| `POST` | `/internal/summary/consolidate`   | Tổng hợp góp ý/nội dung         |
| `POST` | `/internal/draft/generate`        | Sinh dự thảo                    |
| `POST` | `/internal/draft/edit`            | Chỉnh sửa dự thảo               |
| `POST` | `/internal/template/extract`      | Phân tích template              |
| `POST` | `/internal/template/generate`     | Sinh văn bản từ template        |

## Quick checks

```bash
curl http://localhost:6868/api/health
curl http://localhost:6868/docs
```
