# STTNB API Documentation — v2.0

> **Base URL**: `http://localhost:6868`  
> **Swagger UI**: `http://localhost:6868/docs`  
> **Auth**: JWT Bearer Token (trừ các endpoint công khai)

---

## Mục Lục

1. [Authentication](#1-authentication)
2. [Repositories (Kho Dữ Liệu)](#2-repositories-kho-dữ-liệu)
3. [Documents (Tài Liệu)](#3-documents-tài-liệu)
4. [Chat Q&A](#4-chat-qa)
5. [Drafting (Soạn Văn Bản)](#5-drafting-soạn-văn-bản)
6. [Legacy — Audio Processing](#6-legacy--audio-processing)
7. [Quick Start (curl)](#7-quick-start-curl)

---

## 1. Authentication

### `POST /api/auth/register` — Đăng ký tài khoản

**Auth**: Không cần

**Request Body:**
```json
{
  "username": "admin",
  "password": "123456",
  "full_name": "Nguyễn Văn A"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `username` | string | ✅ | 3–50 ký tự, unique |
| `password` | string | ✅ | 6–100 ký tự |
| `full_name` | string | ❌ | Max 100 ký tự |

**Response** `201 Created`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "admin",
  "full_name": "Nguyễn Văn A"
}
```

**Errors:**
| Code | Detail |
|------|--------|
| `409` | Tên đăng nhập đã tồn tại |

---

### `POST /api/auth/login` — Đăng nhập

**Auth**: Không cần

**Request Body:**
```json
{
  "username": "admin",
  "password": "123456"
}
```

**Response** `200 OK`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "admin",
  "full_name": "Nguyễn Văn A"
}
```

**Errors:**
| Code | Detail |
|------|--------|
| `401` | Tên đăng nhập hoặc mật khẩu không đúng |

---

### `GET /api/auth/me` — Thông tin user hiện tại

**Auth**: ✅ Bearer Token

**Response** `200 OK`:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "admin",
  "full_name": "Nguyễn Văn A",
  "created_at": "2026-04-10T19:50:00"
}
```

---

## 2. Repositories (Kho Dữ Liệu)

> Mỗi user tối đa **10 kho**. Mỗi kho ánh xạ 1:1 với 1 NotebookLM notebook.

### `POST /api/repositories` — Tạo kho dữ liệu

**Auth**: ✅ Bearer Token

**Request Body:**
```json
{
  "name": "Kho KHCN",
  "description": "Dữ liệu khoa học công nghệ"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | string | ✅ | 1–200 ký tự |
| `description` | string | ❌ | Max 500 ký tự |

**Response** `201 Created`:
```json
{
  "id": "repo-uuid-xxx",
  "name": "Kho KHCN",
  "description": "Dữ liệu khoa học công nghệ",
  "notebook_id": "notebooklm-notebook-id",
  "document_count": 0,
  "created_at": "2026-04-10T19:50:00",
  "updated_at": "2026-04-10T19:50:00"
}
```

**Errors:**
| Code | Detail |
|------|--------|
| `400` | Đã đạt giới hạn 10 kho / Không thể tạo notebook trên NotebookLM |

---

### `GET /api/repositories` — Danh sách kho

**Auth**: ✅ Bearer Token  
**Mô tả**: Trả về tất cả kho dữ liệu của user hiện tại.

**Response** `200 OK`:
```json
[
  {
    "id": "repo-uuid-1",
    "name": "Kho KHCN",
    "description": "Dữ liệu khoa học công nghệ",
    "notebook_id": "nb-xxx",
    "document_count": 5,
    "created_at": "2026-04-10T19:50:00",
    "updated_at": "2026-04-10T20:00:00"
  },
  {
    "id": "repo-uuid-2",
    "name": "Kho Pháp luật",
    "description": "",
    "notebook_id": "nb-yyy",
    "document_count": 12,
    "created_at": "2026-04-10T20:05:00",
    "updated_at": "2026-04-10T20:05:00"
  }
]
```

---

### `GET /api/repositories/{repo_id}` — Chi tiết kho

**Auth**: ✅ Bearer Token

**Response** `200 OK`: Giống object trong danh sách.

**Errors:**
| Code | Detail |
|------|--------|
| `404` | Kho dữ liệu không tồn tại |
| `403` | Không có quyền truy cập kho này |

---

### `PUT /api/repositories/{repo_id}` — Cập nhật kho

**Auth**: ✅ Bearer Token

**Request Body:**
```json
{
  "name": "Kho KHCN (cập nhật)",
  "description": "Mô tả mới"
}
```

> Cả 2 field đều optional. Chỉ cần gửi field muốn thay đổi.

**Response** `200 OK`: Repository object đã cập nhật.

---

### `DELETE /api/repositories/{repo_id}` — Xóa kho

**Auth**: ✅ Bearer Token  
**Mô tả**: Xóa kho + notebook trên NotebookLM + tất cả tài liệu + lịch sử chat.

**Response** `204 No Content`

**Errors:**
| Code | Detail |
|------|--------|
| `404` | Kho dữ liệu không tồn tại |
| `403` | Không có quyền xóa kho này |

---

## 3. Documents (Tài Liệu)

> Tài liệu upload vào kho sẽ tự động được đẩy lên NotebookLM notebook tương ứng.

### `POST /api/repositories/{repo_id}/documents` — Upload tài liệu

**Auth**: ✅ Bearer Token  
**Content-Type**: `multipart/form-data`

**Form Data:**
| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `file` | File | ✅ | Tài liệu cần upload |

**Formats hỗ trợ:**
- Văn bản: `.pdf`, `.docx`, `.doc`, `.txt`, `.rtf`, `.html`, `.htm`, `.md`
- Bảng tính: `.xlsx`, `.xls`, `.csv`
- Trình chiếu: `.pptx`, `.ppt`
- Hình ảnh: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`
- Audio: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`, `.flac`
- Video: `.mp4`, `.avi`, `.mkv`, `.mov`

**Giới hạn**: 50MB/file (cấu hình `MAX_DOC_UPLOAD_MB`)

**Response** `201 Created`:
```json
{
  "id": "doc-uuid-xxx",
  "repository_id": "repo-uuid-xxx",
  "filename": "bao_cao_2026.pdf",
  "file_size": 2048576,
  "file_type": "application/pdf",
  "uploaded_at": "2026-04-10T20:10:00"
}
```

**Errors:**
| Code | Detail |
|------|--------|
| `400` | Định dạng file không được hỗ trợ |
| `413` | File quá lớn (>50MB) |
| `403` | Không có quyền truy cập kho |
| `404` | Kho dữ liệu không tồn tại |

---

### `GET /api/repositories/{repo_id}/documents` — Danh sách tài liệu

**Auth**: ✅ Bearer Token

**Response** `200 OK`:
```json
[
  {
    "id": "doc-uuid-1",
    "repository_id": "repo-uuid-xxx",
    "filename": "bao_cao_2026.pdf",
    "file_size": 2048576,
    "file_type": "application/pdf",
    "uploaded_at": "2026-04-10T20:10:00"
  },
  {
    "id": "doc-uuid-2",
    "repository_id": "repo-uuid-xxx",
    "filename": "ke_hoach_Q2.docx",
    "file_size": 512000,
    "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "uploaded_at": "2026-04-10T20:15:00"
  }
]
```

---

### `DELETE /api/repositories/{repo_id}/documents/{doc_id}` — Xóa tài liệu

**Auth**: ✅ Bearer Token

**Response** `204 No Content`

**Errors:**
| Code | Detail |
|------|--------|
| `404` | Tài liệu không tồn tại trong kho này |
| `403` | Không có quyền |

---

## 4. Chat Q&A

> Gửi câu hỏi, hệ thống hỏi NotebookLM dựa trên dữ liệu trong kho,
> trả về phản hồi dạng **Server-Sent Events (SSE)** simulated streaming.

### `POST /api/repositories/{repo_id}/chat` — Chat hỏi đáp (SSE Streaming)

**Auth**: ✅ Bearer Token

**Request Body:**
```json
{
  "message": "Tóm tắt nội dung tài liệu trong kho"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `message` | string | ✅ | 1–5000 ký tự |

**Response**: `text/event-stream` (SSE)

```
data: {"type": "chunk", "content": "Theo "}

data: {"type": "chunk", "content": "tài liệu "}

data: {"type": "chunk", "content": "trong kho, "}

data: {"type": "chunk", "content": "nội dung "}

data: {"type": "chunk", "content": "chính bao gồm: "}

data: {"type": "chunk", "content": "..."}

data: {"type": "done", "content": ""}
```

**SSE Event Format:**
| type | Mô tả |
|------|--------|
| `chunk` | Một phần nội dung trả lời (word-level, ~35ms/word) |
| `done` | Hoàn thành trả lời |

**Client-side (JavaScript) example:**
```javascript
const eventSource = new EventSource('/api/repositories/{repo_id}/chat', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ message: 'Tóm tắt nội dung' })
});

// Hoặc dùng fetch:
const response = await fetch('/api/repositories/{repo_id}/chat', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ message: 'Tóm tắt nội dung' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  // Parse SSE lines: data: {"type":"chunk","content":"..."}
}
```

**Errors:**
| Code | Detail |
|------|--------|
| `400` | Kho chưa liên kết NotebookLM |
| `500` | Lỗi khi hỏi NotebookLM |

---

### `GET /api/repositories/{repo_id}/chat/history` — Lịch sử chat

**Auth**: ✅ Bearer Token

**Response** `200 OK`:
```json
{
  "repository_id": "repo-uuid-xxx",
  "messages": [
    {
      "id": "msg-uuid-1",
      "role": "user",
      "content": "Tóm tắt nội dung tài liệu",
      "created_at": "2026-04-10T20:20:00"
    },
    {
      "id": "msg-uuid-2",
      "role": "assistant",
      "content": "Theo tài liệu trong kho, nội dung chính bao gồm...",
      "created_at": "2026-04-10T20:20:05"
    }
  ]
}
```

---

### `DELETE /api/repositories/{repo_id}/chat/history` — Xóa lịch sử chat

**Auth**: ✅ Bearer Token

**Response** `204 No Content`

---

## 5. Drafting (Soạn Văn Bản)

> Soạn văn bản hành chính theo **Nghị định 30/2020/NĐ-CP**.
> Hệ thống kết hợp thông tin người dùng nhập + dữ liệu trong kho (qua NotebookLM)
> để soạn nội dung, sau đó xuất Word (.docx) đúng thể thức.

### `GET /api/draft/types` — Danh sách loại văn bản

**Auth**: Không cần

**Response** `200 OK`:
```json
[
  {
    "type_code": "cong_van",
    "name": "Công văn",
    "description": "Văn bản dùng để trao đổi, giao dịch, đề nghị giữa các cơ quan, tổ chức",
    "required_fields": ["co_quan_ban_hanh", "noi_nhan", "trich_yeu", "noi_dung_chinh"],
    "optional_fields": ["co_quan_chu_quan", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"]
  },
  {
    "type_code": "quyet_dinh",
    "name": "Quyết định",
    "description": "Quyết định cá biệt của cơ quan, tổ chức về một vấn đề cụ thể",
    "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
    "optional_fields": ["co_quan_chu_quan", "can_cu", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"]
  },
  {
    "type_code": "ke_hoach",
    "name": "Kế hoạch",
    "description": "Kế hoạch triển khai công việc, hoạt động",
    "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
    "optional_fields": ["co_quan_chu_quan", "muc_dich", "yeu_cau", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"]
  },
  {
    "type_code": "thong_bao",
    "name": "Thông báo",
    "description": "Thông báo nội bộ hoặc bên ngoài về một sự kiện, quyết định, thay đổi",
    "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
    "optional_fields": ["co_quan_chu_quan", "noi_nhan", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"]
  },
  {
    "type_code": "to_trinh",
    "name": "Tờ trình",
    "description": "Văn bản đề xuất, trình bày vấn đề lên cấp trên để xin ý kiến hoặc phê duyệt",
    "required_fields": ["co_quan_ban_hanh", "noi_nhan", "trich_yeu", "noi_dung_chinh"],
    "optional_fields": ["co_quan_chu_quan", "ly_do", "kien_nghi", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"]
  },
  {
    "type_code": "bao_cao",
    "name": "Báo cáo",
    "description": "Báo cáo kết quả, tình hình, tiến độ công việc",
    "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
    "optional_fields": ["co_quan_chu_quan", "ky_bao_cao", "danh_gia", "kien_nghi", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"]
  }
]
```

---

### `POST /api/repositories/{repo_id}/draft` — Soạn văn bản

**Auth**: ✅ Bearer Token

**Request Body:**
```json
{
  "document_type": "cong_van",
  "input_data": {
    "co_quan_ban_hanh": "SỞ KHOA HỌC VÀ CÔNG NGHỆ",
    "co_quan_chu_quan": "UBND TỈNH TÂY NINH",
    "noi_nhan": "Các phòng ban thuộc Sở",
    "trich_yeu": "V/v triển khai kế hoạch ứng dụng CNTT năm 2026",
    "noi_dung_chinh": "Yêu cầu tổng hợp nội dung từ kho dữ liệu và soạn chi tiết",
    "nguoi_ky": "Nguyễn Văn A",
    "chuc_vu_nguoi_ky": "Giám đốc"
  }
}
```

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `document_type` | enum | ✅ | `cong_van`, `quyet_dinh`, `ke_hoach`, `thong_bao`, `to_trinh`, `bao_cao` |
| `input_data` | object | ✅ | Thông tin đầu vào (xem required_fields ở `/api/draft/types`) |

**Các fields trong `input_data`:**

| Field | Mô tả | Dùng cho |
|-------|--------|----------|
| `co_quan_ban_hanh` | Tên cơ quan ban hành (viết HOA) | Tất cả |
| `co_quan_chu_quan` | Cơ quan chủ quản cấp trên | Tất cả (optional) |
| `noi_nhan` | Nơi nhận / Kính gửi | Công văn, Tờ trình, Thông báo |
| `trich_yeu` | Trích yếu nội dung văn bản | Tất cả |
| `noi_dung_chinh` | Yêu cầu nội dung chính (hệ thống sẽ soạn chi tiết từ kho) | Tất cả |
| `nguoi_ky` | Họ tên người ký | Tất cả (optional) |
| `chuc_vu_nguoi_ky` | Chức vụ người ký | Tất cả (optional) |
| `so_van_ban` | Số văn bản (vd: "15") | Tất cả (optional) |
| `can_cu` | Căn cứ pháp lý (text hoặc array) | Quyết định |
| `muc_dich` | Mục đích | Kế hoạch |
| `yeu_cau` | Yêu cầu | Kế hoạch |
| `ly_do` | Lý do trình | Tờ trình |
| `kien_nghi` | Kiến nghị | Tờ trình, Báo cáo |
| `ky_bao_cao` | Kỳ báo cáo (vd: "Quý I/2026") | Báo cáo |
| `danh_gia` | Đánh giá chung | Báo cáo |

**Response** `200 OK`:
```json
{
  "task_id": "task-uuid-xxx",
  "status": "pending",
  "document_type": "cong_van",
  "message": "Đang soạn Công văn..."
}
```

**Errors:**
| Code | Detail |
|------|--------|
| `400` | Kho chưa liên kết NotebookLM |
| `404` | Kho dữ liệu không tồn tại |
| `403` | Không có quyền |
| `422` | Thiếu các trường bắt buộc: co_quan_ban_hanh, trich_yeu, ... |

---

### `GET /api/draft/status/{task_id}` — Trạng thái soạn thảo

**Auth**: Không cần

**Response** `200 OK`:
```json
{
  "task_id": "task-uuid-xxx",
  "status": "completed",
  "document_type": "cong_van",
  "progress_message": "Hoàn thành! File văn bản đã sẵn sàng để tải về.",
  "error_message": "",
  "output_ready": true
}
```

**Giá trị `status`:**
| Status | Mô tả |
|--------|--------|
| `pending` | Đang chờ xử lý |
| `processing` | Đang phân tích tài liệu và soạn nội dung |
| `exporting_word` | Đang xuất file Word |
| `completed` | Hoàn thành |
| `error` | Lỗi (xem `error_message`) |

---

### `GET /api/draft/download/{task_id}` — Download Word

**Auth**: Không cần  
**Mô tả**: Download file .docx đã soạn.

**Response**: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

**Errors:**
| Code | Detail |
|------|--------|
| `400` | Văn bản chưa sẵn sàng |
| `404` | Task / File không tìm thấy |

---

## 6. Legacy — Audio Processing

> Các endpoint gốc v1.0 — chuyển ghi âm thành biên bản họp Word.

### `POST /api/upload-audio` — Upload ghi âm

**Auth**: Không cần

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `file` | File | ✅ | File ghi âm (.mp3, .wav, .m4a, .ogg, .webm, .flac, .aac, .wma) |

**Giới hạn**: 100MB (cấu hình `MAX_UPLOAD_MB`)

**Response** `200 OK`:
```json
{
  "task_id": "task-uuid-xxx",
  "status": "pending",
  "message": "File 'recording.mp3' đã được upload. Đang bắt đầu xử lý..."
}
```

---

### `GET /api/status/{task_id}` — Trạng thái xử lý audio

**Auth**: Không cần

**Response** `200 OK`:
```json
{
  "task_id": "task-uuid-xxx",
  "status": "completed",
  "filename": "recording.mp3",
  "progress_message": "Hoàn thành! File biên bản đã sẵn sàng để tải về.",
  "error_message": "",
  "created_at": "2026-04-10T20:00:00",
  "output_ready": true,
  "minutes": {
    "tieu_de": "BIÊN BẢN",
    "tieu_de_noi_dung": "Họp triển khai dự án Q2",
    "chu_tri": "Đ/c Nguyễn Văn A - Giám đốc Sở",
    "..."
  }
}
```

---

### `GET /api/download/{task_id}` — Download biên bản Word

**Auth**: Không cần

**Response**: File `.docx`

---

### `GET /api/health` — Health check

**Auth**: Không cần

**Response** `200 OK`:
```json
{
  "status": "ok",
  "service": "STTNB - Speech To Text NoteBook",
  "version": "2.0.0",
  "notebooklm_auth": "authenticated"
}
```

---

### `GET /api/tasks` — Danh sách tasks (Debug)

**Auth**: Không cần

**Response** `200 OK`:
```json
{
  "total": 2,
  "tasks": [
    {
      "task_id": "uuid-1",
      "status": "completed",
      "filename": "recording.mp3",
      "created_at": "2026-04-10T20:00:00",
      "progress": "Hoàn thành!"
    }
  ]
}
```

---

## 7. Quick Start (curl)

```bash
# ────────────────────────────────────────────────
# 1. Đăng ký tài khoản
# ────────────────────────────────────────────────
curl -X POST http://localhost:6868/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","full_name":"Admin"}'

# ────────────────────────────────────────────────
# 2. Đăng nhập → lấy token
# ────────────────────────────────────────────────
TOKEN=$(curl -s -X POST http://localhost:6868/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}' | jq -r '.access_token')

echo "Token: $TOKEN"

# ────────────────────────────────────────────────
# 3. Tạo kho dữ liệu
# ────────────────────────────────────────────────
curl -X POST http://localhost:6868/api/repositories \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Kho KHCN","description":"Dữ liệu khoa học công nghệ"}'

# → Ghi lại REPO_ID từ response

# ────────────────────────────────────────────────
# 4. Upload tài liệu vào kho
# ────────────────────────────────────────────────
curl -X POST http://localhost:6868/api/repositories/{REPO_ID}/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/document.pdf"

# ────────────────────────────────────────────────
# 5. Xem danh sách tài liệu
# ────────────────────────────────────────────────
curl http://localhost:6868/api/repositories/{REPO_ID}/documents \
  -H "Authorization: Bearer $TOKEN"

# ────────────────────────────────────────────────
# 6. Chat hỏi đáp (SSE streaming)
# ────────────────────────────────────────────────
curl -N -X POST http://localhost:6868/api/repositories/{REPO_ID}/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Tóm tắt nội dung tài liệu trong kho"}'

# ────────────────────────────────────────────────
# 7. Xem lịch sử chat
# ────────────────────────────────────────────────
curl http://localhost:6868/api/repositories/{REPO_ID}/chat/history \
  -H "Authorization: Bearer $TOKEN"

# ────────────────────────────────────────────────
# 8. Xem loại văn bản hỗ trợ
# ────────────────────────────────────────────────
curl http://localhost:6868/api/draft/types

# ────────────────────────────────────────────────
# 9. Soạn công văn từ dữ liệu trong kho
# ────────────────────────────────────────────────
curl -X POST http://localhost:6868/api/repositories/{REPO_ID}/draft \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "cong_van",
    "input_data": {
      "co_quan_ban_hanh": "SỞ KHOA HỌC VÀ CÔNG NGHỆ",
      "co_quan_chu_quan": "UBND TỈNH TÂY NINH",
      "noi_nhan": "Các phòng ban thuộc Sở",
      "trich_yeu": "V/v triển khai ứng dụng CNTT năm 2026",
      "noi_dung_chinh": "Soạn nội dung từ dữ liệu kho",
      "nguoi_ky": "Nguyễn Văn A",
      "chuc_vu_nguoi_ky": "Giám đốc"
    }
  }'

# → Ghi lại TASK_ID từ response

# ────────────────────────────────────────────────
# 10. Kiểm tra trạng thái soạn thảo
# ────────────────────────────────────────────────
curl http://localhost:6868/api/draft/status/{TASK_ID}

# ────────────────────────────────────────────────
# 11. Download file Word
# ────────────────────────────────────────────────
curl -o cong_van.docx http://localhost:6868/api/draft/download/{TASK_ID}

# ────────────────────────────────────────────────
# 12. Soạn báo cáo
# ────────────────────────────────────────────────
curl -X POST http://localhost:6868/api/repositories/{REPO_ID}/draft \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "bao_cao",
    "input_data": {
      "co_quan_ban_hanh": "SỞ KHOA HỌC VÀ CÔNG NGHỆ",
      "trich_yeu": "Báo cáo tình hình ứng dụng CNTT quý I/2026",
      "noi_dung_chinh": "Tổng hợp từ dữ liệu kho",
      "ky_bao_cao": "Quý I/2026",
      "nguoi_ky": "Nguyễn Văn A",
      "chuc_vu_nguoi_ky": "Giám đốc"
    }
  }'

# ────────────────────────────────────────────────
# 13. Soạn tờ trình
# ────────────────────────────────────────────────
curl -X POST http://localhost:6868/api/repositories/{REPO_ID}/draft \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "to_trinh",
    "input_data": {
      "co_quan_ban_hanh": "SỞ KHOA HỌC VÀ CÔNG NGHỆ",
      "noi_nhan": "UBND tỉnh Tây Ninh",
      "trich_yeu": "Về việc đề xuất kinh phí triển khai dự án CNTT",
      "noi_dung_chinh": "Soạn nội dung đề xuất từ dữ liệu kho",
      "nguoi_ky": "Nguyễn Văn A",
      "chuc_vu_nguoi_ky": "Giám đốc"
    }
  }'

# ────────────────────────────────────────────────
# 14. Xóa lịch sử chat
# ────────────────────────────────────────────────
curl -X DELETE http://localhost:6868/api/repositories/{REPO_ID}/chat/history \
  -H "Authorization: Bearer $TOKEN"

# ────────────────────────────────────────────────
# 15. Xóa kho dữ liệu
# ────────────────────────────────────────────────
curl -X DELETE http://localhost:6868/api/repositories/{REPO_ID} \
  -H "Authorization: Bearer $TOKEN"
```

---

## Error Responses

Tất cả lỗi trả về dạng:
```json
{
  "detail": "Mô tả lỗi bằng tiếng Việt"
}
```

| HTTP Code | Mô tả chung |
|-----------|-------------|
| `400` | Bad Request — dữ liệu không hợp lệ |
| `401` | Unauthorized — token không hợp lệ/hết hạn |
| `403` | Forbidden — không có quyền truy cập |
| `404` | Not Found — tài nguyên không tồn tại |
| `409` | Conflict — trùng lặp (vd: username) |
| `413` | Payload Too Large — file quá lớn |
| `422` | Unprocessable Entity — thiếu trường bắt buộc |
| `500` | Internal Server Error — lỗi server |

---

## Authentication Header

Tất cả endpoint có Auth ✅ cần header:

```
Authorization: Bearer <JWT_TOKEN>
```

Token nhận được từ `/api/auth/register` hoặc `/api/auth/login`, có hiệu lực **24 giờ**.