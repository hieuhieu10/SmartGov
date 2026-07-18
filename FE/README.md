# Frontend Thư ký Ơi

Frontend là ứng dụng React phục vụ giao diện người dùng cho Thư ký Ơi. Ứng dụng chỉ gọi backend qua `/api`; mọi xác thực, phân quyền, dữ liệu và tác vụ AI đều đi qua `BE/`.

## Tech stack

- React 19
- TypeScript
- Vite
- React Router
- Axios
- Tailwind CSS
- Lucide React
- Nginx khi chạy bằng Docker

## Chạy local

```bash
npm install
npm run dev
```

Mặc định Vite chạy tại <http://localhost:5173>. Khi chạy full Docker stack, frontend được Nginx phục vụ tại <http://localhost:3000>.

## Build

```bash
npm run build
```

Docker image dùng multi-stage build: Node build static assets, Nginx phục vụ production bundle và proxy `/api` về backend theo cấu hình trong `nginx.conf`.

## Cấu trúc quan trọng

```text
FE/
  src/
    api/          API client
    components/   Layout, sidebar, shared UI
    pages/        Login, dashboard/document/chat/admin screens
  public/         Icon/static assets
  nginx.conf      Nginx config cho Docker runtime
```

## Quy tắc phát triển

- Không gọi `AI/` trực tiếp từ frontend.
- Không hard-code token, secret hoặc URL nội bộ.
- Giữ tương thích với response và SSE format hiện có của BE.
- Khi thêm route hoặc workflow lớn, cập nhật [`../docs/user/user-guide.md`](../docs/user/user-guide.md) nếu ảnh hưởng người dùng cuối.
