# Tài liệu Thư ký Ơi

Thư mục này là nguồn tài liệu chính của dự án. Các tài liệu được chia theo mục đích đọc để người mới vào dự án, người dùng nghiệp vụ và kỹ sư triển khai đều tìm được đúng thứ cần đọc.

## Đọc theo vai trò

| Vai trò | Bắt đầu từ |
| --- | --- |
| Lãnh đạo, product owner, người thẩm định | [`product/problem-statement.md`](product/problem-statement.md) |
| Người dùng cuối | [`user/user-guide.md`](user/user-guide.md) |
| Kỹ sư backend/frontend/AI | [`architecture/overview.md`](architecture/overview.md) |
| Người tích hợp API | [`api/README.md`](api/README.md) |
| Người vận hành hoặc reviewer kỹ thuật | [`audits/technical-audit.md`](audits/technical-audit.md) và [`roadmap/production-plan.md`](roadmap/production-plan.md) |

## Cấu trúc

```text
docs/
  product/       Bài toán và phạm vi sản phẩm
  architecture/  Kiến trúc hệ thống, RAG, dữ liệu và luồng xử lý
  api/           Tài liệu API và cách xác thực
  user/          Hướng dẫn sử dụng cho người dùng cuối
  roadmap/       Kế hoạch hoàn thiện và tiêu chí triển khai
  audits/        Audit kỹ thuật, phân tích chuyên sâu
```

## Quy ước duy trì tài liệu

- README root chỉ đóng vai trò cửa vào dự án; chi tiết dài đưa vào `docs/`.
- Tài liệu đang được app dùng như dữ liệu mẫu hoặc knowledge base giữ nguyên trong `AI/sample_doc`, `AI/app/knowledge`, `BE/app/knowledge`.
- Khi đổi public API, cập nhật `docs/api/api-reference.md`.
- Khi đổi kiến trúc FE/BE/AI/PostgreSQL, cập nhật `docs/architecture/overview.md` và `AGENTS.md`.
- Khi thêm biến môi trường, cập nhật `.env.example` và tài liệu triển khai liên quan.
