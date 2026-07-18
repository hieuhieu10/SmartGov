# ── Stage 1: builder — cài dependency vào venv ──────────────────────────────
# build-essential chỉ tồn tại ở stage này (phòng khi thiếu wheel phải compile),
# không đi vào image chạy thật.
FROM python:3.12-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# Cache mount: pip cache giữ lại giữa các lần build -> đổi requirements chỉ
# tải phần thiếu, không tải lại toàn bộ.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && pip install "notebooklm-py[browser]" "markitdown[all]"

# ── Stage 2: runtime — slim + venv đã cài ───────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# curl: healthcheck; ffmpeg: markitdown xử lý audio (Audio -> biên bản họp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .
RUN mkdir -p uploads outputs repo_files user_templates

EXPOSE 7000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]
