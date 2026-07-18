# Kế hoạch hoàn thiện production

Tài liệu này là roadmap kỹ thuật cho hệ thống Thư ký Ơi. Mục tiêu là đưa các luồng tài liệu, RAG, soạn thảo và export Word đến mức ổn định để vận hành nội bộ.

## 1. Định nghĩa thành công

- Tài liệu upload có trạng thái xử lý rõ ràng từ lúc nhận file đến lúc RAG-ready.
- Markdown, chunk và vector được lưu/truy xuất ổn định.
- Chat chỉ trả lời dựa trên context người dùng có quyền truy cập.
- Câu trả lời có citation có thể kiểm tra.
- Tác vụ tổng hợp góp ý, dataset extraction, template và export Word có test hồi quy.
- Health/readiness phản ánh đúng trạng thái DB, AI provider và service nội bộ.
- Docker build reproducible, không phụ thuộc cấu hình cục bộ ngoài `.env`.

## 2. Workstream A: Ingest và trạng thái tài liệu

Mục tiêu: tài liệu có vòng đời rõ ràng, dễ debug và dễ hiển thị trên FE.

Việc cần làm:

- Chuẩn hóa trạng thái: `uploaded`, `converting`, `converted`, `vectorizing`, `ready`, `failed`.
- Lưu lỗi xử lý có cấu trúc: code, message, retryable, timestamp.
- Tách convert/OCR và vectorization thành các bước có thể retry.
- Không báo ready nếu chưa có chunk/vector hợp lệ.

Nghiệm thu:

- Upload một `.docx` tạo Markdown, chunks và embeddings.
- Upload file lỗi hiển thị trạng thái failed kèm lý do.
- Retry không tạo duplicate chunk.

## 3. Workstream B: Retrieval và citation

Mục tiêu: truy hồi tốt với tài liệu hành chính tiếng Việt.

Việc cần làm:

- Chuẩn hóa chunk metadata: document id, filename, heading, page/section nếu có.
- Tối ưu hybrid search: vector + full-text + số hiệu/điều/khoản.
- Dedup context trước khi gửi sang LLM.
- Trả citation có cấu trúc thay vì chỉ là text tự do.

Nghiệm thu:

- Recall@8 đạt ngưỡng trên bộ câu hỏi mẫu.
- Tra cứu số hiệu/điều/khoản trả đúng tài liệu.
- Câu trả lời có citation liên kết được về source.

## 4. Workstream C: Grounded generation

Mục tiêu: giảm hallucination và chuẩn hóa hành vi khi thiếu căn cứ.

Việc cần làm:

- System prompt yêu cầu chỉ trả lời từ context.
- Refusal template cho câu hỏi thiếu căn cứ.
- Citation validator sau khi LLM sinh.
- Log request id, repo id, selected chunks và provider latency.

Nghiệm thu:

- Câu hỏi ngoài tài liệu được từ chối.
- Câu trả lời có số liệu phải dẫn nguồn.
- Không có cross-repository leakage trong test.

## 5. Workstream D: Tổng hợp góp ý và báo cáo

Mục tiêu: biến nghiệp vụ cốt lõi thành workflow ổn định.

Việc cần làm:

- Chuẩn hóa schema ý kiến góp ý: đơn vị, vị trí dự thảo, nội dung, phân loại, đề xuất tiếp thu, source.
- Thêm cảnh báo khi không xác định được vị trí trong dự thảo.
- Gom nhóm ý kiến tương đồng nhưng vẫn giữ từng nguồn.
- Xuất bảng tổng hợp và báo cáo giải trình theo mẫu.

Nghiệm thu:

- Không mất ý kiến khi nhiều đơn vị góp ý cùng một nội dung.
- Người dùng chỉnh/sửa/duyệt được từng dòng.
- File Word/Excel xuất ra mở được và đúng cấu trúc.

## 6. Workstream E: Drafting, template và export Word

Mục tiêu: đầu ra văn bản ổn định, đúng mẫu và dễ rà soát.

Việc cần làm:

- Dùng chung retrieval cho drafting và chat.
- Tách dữ liệu nhập, dữ liệu AI sinh và dữ liệu người dùng sửa.
- Thêm regression test cho các mẫu Word quan trọng.
- Kiểm tra format sau export: font, bảng, heading, căn lề, section.

Nghiệm thu:

- Sinh được file `.docx` cho các loại văn bản chính.
- Preview và download thống nhất nội dung.
- Template tùy chỉnh không làm mất format cơ bản.

## 7. Workstream F: Frontend và UX

Mục tiêu: người dùng hiểu trạng thái, biết bước tiếp theo và kiểm soát kết quả AI.

Việc cần làm:

- Hiển thị trạng thái xử lý tài liệu rõ ràng.
- Màn hình chat hiển thị nguồn/citation dễ kiểm tra.
- Workflow tổng hợp góp ý có bảng kiểm duyệt từng dòng.
- Thêm empty/error/loading states nhất quán.
- Tối ưu bundle bằng code-splitting nếu cần.

Nghiệm thu:

- Người dùng mới tạo kho, upload, hỏi đáp và tải kết quả trong một luồng.
- Lỗi provider/convert hiển thị dễ hiểu.
- FE build pass trong Docker.

## 8. Workstream G: Vận hành và bảo mật

Mục tiêu: triển khai nội bộ an toàn và dễ quan sát.

Việc cần làm:

- Tách `/health` và `/ready`.
- Log có request id và không in secret.
- Kiểm tra `.env.example` khi thêm biến mới.
- Backup/restore PostgreSQL và shared volumes.
- Thêm giới hạn file, quota và kiểm soát định dạng upload.

Nghiệm thu:

- Docker stack khởi động sạch từ `.env.example` đã điền secret.
- Readiness fail khi DB/provider không sẵn sàng.
- Không có secret trong source hoặc tài liệu.

## 9. Thứ tự triển khai đề xuất

1. Ingest state + retry an toàn.
2. Citation có cấu trúc.
3. RAG evaluation smoke.
4. Tổng hợp góp ý regression test.
5. Export Word regression test.
6. Readiness/observability.
7. Frontend UX cho trạng thái và citation.

## 10. Kiểm tra bàn giao

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail 80 be
docker compose logs --tail 80 ai
docker compose build fe
```

Nếu chạy build frontend trên host, dùng Node version phù hợp với Vite trong `FE/package.json`.
