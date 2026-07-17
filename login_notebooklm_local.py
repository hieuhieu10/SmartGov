#!/usr/bin/env python3
"""
🔐 NotebookLM Login Helper — Chạy trên máy LOCAL (Windows/Mac/Linux)
=====================================================================
KHÔNG CẦN CÀI THÊM GÌ — chỉ cần Python + Google Chrome.

Script này sẽ:
  1. Mở Google Chrome trên máy local
  2. Bạn đăng nhập tài khoản Google → NotebookLM
  3. Lưu session cookies
  4. Tự động copy lên server

Cách dùng:
  python login_notebooklm_local.py
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─── CẤU HÌNH ────────────────────────────────────────────────────────
SERVER_IP = "10.184.231.78"
SERVER_USER = "root"
REMOTE_DIR = "~/.notebooklm"
DEBUG_PORT = 9222
# ────────────────────────────────────────────────────────────────────

NOTEBOOKLM_DIR = Path.home() / ".notebooklm"
STORAGE_STATE_FILE = NOTEBOOKLM_DIR / "storage_state.json"
PROFILES_DIR = NOTEBOOKLM_DIR / "profiles" / "default"


def find_chrome():
    """Tìm Google Chrome trên hệ thống."""
    system = platform.system()

    if system == "Windows":
        paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    elif system == "Darwin":  # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        ]
    else:  # Linux
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
        # Also check via which
        for cmd in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
            chrome = shutil.which(cmd)
            if chrome:
                return chrome

    for p in paths:
        if os.path.exists(p):
            return p

    return None


def get_cdp_json(path):
    """Gọi Chrome DevTools Protocol HTTP API."""
    url = f"http://127.0.0.1:{DEBUG_PORT}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def send_cdp_command(ws_url_unused, method, params=None):
    """Gửi command CDP qua HTTP endpoint (dùng /json/protocol thay vì WebSocket)."""
    # Use the HTTP-based CDP endpoint
    url = f"http://127.0.0.1:{DEBUG_PORT}/json"
    try:
        tabs = get_cdp_json("/json")
        if not tabs:
            return None

        # Find the target page
        target_id = None
        for tab in tabs:
            if tab.get("type") == "page":
                target_id = tab.get("id")
                break

        if not target_id:
            return None

        # We'll use a different approach - fetch via page evaluation
        return None
    except Exception as e:
        print(f"  CDP error: {e}")
        return None


def get_cookies_via_cdp():
    """Lấy tất cả cookies từ Chrome qua CDP (bao gồm httpOnly)."""
    try:
        # Use the CDP HTTP endpoint to send commands
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", DEBUG_PORT)

        # First get the list of targets
        conn.request("GET", "/json")
        resp = conn.getresponse()
        targets = json.loads(resp.read().decode("utf-8"))

        # Find a page target
        page_target = None
        for t in targets:
            if t.get("type") == "page":
                page_target = t
                break

        if not page_target:
            print("  ❌ Không tìm thấy tab Chrome")
            return None

        # Use WebSocket to send CDP command (stdlib only)
        ws_url = page_target.get("webSocketDebuggerUrl", "")
        if not ws_url:
            print("  ❌ Không có WebSocket URL")
            return None

        # Simple WebSocket implementation using stdlib
        cookies = _get_cookies_websocket(ws_url)
        conn.close()
        return cookies

    except Exception as e:
        print(f"  ❌ Lỗi CDP: {e}")
        return None


def _get_cookies_websocket(ws_url):
    """Lấy cookies qua WebSocket CDP protocol."""
    import socket
    import hashlib
    import base64
    import struct
    import ssl

    # Parse WebSocket URL
    ws_url = ws_url.replace("ws://", "")
    host_port, path = ws_url.split("/", 1) if "/" in ws_url else (ws_url, "")
    path = "/" + path
    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 80

    # Connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # WebSocket handshake
    key = base64.b64encode(os.urandom(16)).decode("utf-8")
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.send(handshake.encode())

    # Read response
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)

    # Send CDP command: Network.getAllCookies
    msg = json.dumps({
        "id": 1,
        "method": "Network.getAllCookies",
        "params": {}
    })
    _ws_send(sock, msg)

    # Receive response
    result = _ws_recv(sock)

    # Send CDP command: get localStorage for notebooklm.google.com
    msg2 = json.dumps({
        "id": 2,
        "method": "Runtime.evaluate",
        "params": {
            "expression": "JSON.stringify(Object.fromEntries(Object.entries(localStorage)))",
            "returnByValue": True
        }
    })
    _ws_send(sock, msg2)
    result2 = _ws_recv(sock)

    sock.close()

    if result:
        data = json.loads(result)
        return data.get("result", {})
    return None


def _ws_send(sock, message):
    """Gửi WebSocket frame."""
    data = message.encode("utf-8")
    frame = bytearray()

    # Opcode: text
    frame.append(0x81)

    # Length + mask bit
    length = len(data)
    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(length.to_bytes(2, "big"))
    else:
        frame.append(0x80 | 127)
        frame.extend(length.to_bytes(8, "big"))

    # Masking key
    mask = os.urandom(4)
    frame.extend(mask)

    # Masked data
    for i, b in enumerate(data):
        frame.append(b ^ mask[i % 4])

    sock.send(bytes(frame))


def _ws_recv(sock):
    """Nhận WebSocket frame."""
    try:
        sock.settimeout(10)

        # Read header
        header = sock.recv(2)
        if len(header) < 2:
            return None

        opcode = header[0] & 0x0F
        masked = (header[1] & 0x80) != 0
        length = header[1] & 0x7F

        if length == 126:
            length = int.from_bytes(sock.recv(2), "big")
        elif length == 127:
            length = int.from_bytes(sock.recv(8), "big")

        if masked:
            mask = sock.recv(4)

        # Read data
        data = bytearray()
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), 65536))
            if not chunk:
                break
            data.extend(chunk)

        if masked:
            for i in range(len(data)):
                data[i] ^= mask[i % 4]

        return data.decode("utf-8")
    except socket.timeout:
        return None


def convert_to_playwright_format(cdp_cookies):
    """Chuyển đổi cookies từ CDP format sang Playwright storage_state format."""
    playwright_cookies = []

    for cookie in cdp_cookies:
        pc = {
            "name": cookie.get("name", ""),
            "value": cookie.get("value", ""),
            "domain": cookie.get("domain", ""),
            "path": cookie.get("path", "/"),
            "expires": cookie.get("expires", -1),
            "httpOnly": cookie.get("httpOnly", False),
            "secure": cookie.get("secure", False),
            "sameSite": cookie.get("sameSite", "None"),
        }
        playwright_cookies.append(pc)

    return {
        "cookies": playwright_cookies,
        "origins": []
    }


def main():
    print()
    print("=" * 55)
    print("  🔐 NotebookLM Login → Upload to Server")
    print("  STTNB — OfficeAI (Zero Dependencies)")
    print("=" * 55)
    print()

    # Step 1: Find Chrome
    chrome_path = find_chrome()
    if not chrome_path:
        print("  ❌ Google Chrome không tìm thấy!")
        print("  Cài Chrome từ: https://www.google.com/chrome/")
        sys.exit(1)
    print(f"  ✅ Chrome: {chrome_path}")

    # Step 2: Create temp profile
    user_data_dir = str(NOTEBOOKLM_DIR / "chrome_login_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    print(f"  📁 Profile: {user_data_dir}")

    # Step 3: Launch Chrome
    print()
    print("  🌐 Đang mở Chrome...")
    chrome_args = [
        chrome_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://notebooklm.google.com",
    ]

    try:
        chrome_proc = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"  ❌ Không mở được Chrome: {e}")
        sys.exit(1)

    # Wait for Chrome to start
    print("  ⏳ Đang đợi Chrome khởi động...")
    for i in range(30):
        time.sleep(1)
        result = get_cdp_json("/json/version")
        if result:
            print(f"  ✅ Chrome đã sẵn sàng (v{result.get('Browser', 'unknown')})")
            break
    else:
        print("  ❌ Chrome không phản hồi sau 30s")
        chrome_proc.terminate()
        sys.exit(1)

    print()
    print("  ┌─────────────────────────────────────────┐")
    print("  │  📋 HƯỚNG DẪN:                          │")
    print("  │  1. Đăng nhập Google trong cửa sổ Chrome│")
    print("  │  2. Đợi trang NotebookLM load xong      │")
    print("  │  3. Quay lại đây nhấn ENTER              │")
    print("  └─────────────────────────────────────────┘")
    print()

    input("  ⏳ Nhấn ENTER sau khi đã đăng nhập NotebookLM thành công... ")

    # Step 4: Get cookies via CDP
    print()
    print("  🔄 Đang lấy cookies từ Chrome...")
    cookie_data = get_cookies_via_cdp()

    if not cookie_data or "cookies" not in cookie_data:
        print("  ❌ Không lấy được cookies!")
        chrome_proc.terminate()
        sys.exit(1)

    cdp_cookies = cookie_data["cookies"]
    google_cookies = [c for c in cdp_cookies if "google" in c.get("domain", "")]

    print(f"  🍪 Tổng cookies: {len(cdp_cookies)}")
    print(f"  🍪 Google cookies: {len(google_cookies)}")

    if not google_cookies:
        print("  ⚠️  Không có Google cookies! Đảm bảo đã đăng nhập Google.")
        chrome_proc.terminate()
        sys.exit(1)

    # Step 5: Convert and save
    storage_state = convert_to_playwright_format(cdp_cookies)

    NOTEBOOKLM_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    with open(STORAGE_STATE_FILE, "w") as f:
        json.dump(storage_state, f, indent=2)

    profile_file = PROFILES_DIR / "storage_state.json"
    with open(profile_file, "w") as f:
        json.dump(storage_state, f, indent=2)

    print(f"  ✅ Đã lưu: {STORAGE_STATE_FILE}")
    print(f"  ✅ Đã lưu: {profile_file}")

    # Close Chrome
    print("  🔄 Đang đóng Chrome...")
    chrome_proc.terminate()
    try:
        chrome_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        chrome_proc.kill()
    print("  ✅ Chrome đã đóng")

    # Step 6: Upload to server
    print()
    print("  " + "=" * 45)
    print(f"  📤 UPLOAD LÊN SERVER ({SERVER_IP})")
    print("  " + "=" * 45)
    print()

    # Create remote dir
    subprocess.run(
        ["ssh", f"{SERVER_USER}@{SERVER_IP}",
         f"mkdir -p {REMOTE_DIR}/profiles/default"],
        capture_output=True
    )

    # Upload files
    print("  🔄 Upload storage_state.json...")
    r1 = subprocess.run(
        ["scp", str(STORAGE_STATE_FILE),
         f"{SERVER_USER}@{SERVER_IP}:{REMOTE_DIR}/storage_state.json"],
        capture_output=True, text=True
    )

    print("  🔄 Upload profiles...")
    r2 = subprocess.run(
        ["scp", str(profile_file),
         f"{SERVER_USER}@{SERVER_IP}:{REMOTE_DIR}/profiles/default/storage_state.json"],
        capture_output=True, text=True
    )

    if r1.returncode == 0 and r2.returncode == 0:
        print()
        print("  🎉 ═══════════════════════════════════════")
        print("  🎉  THÀNH CÔNG! Session đã được upload!")
        print("  🎉 ═══════════════════════════════════════")
        print()
        print("  Tiếp theo, restart backend trên server:")
        print(f"    ssh {SERVER_USER}@{SERVER_IP}")
        print(f"    cd /root/OfficeAI && docker compose restart backend")
    else:
        print()
        print("  ⚠️  Upload thất bại. Copy thủ công:")
        print(f"    scp {STORAGE_STATE_FILE} {SERVER_USER}@{SERVER_IP}:{REMOTE_DIR}/storage_state.json")
        if r1.returncode != 0:
            print(f"    Lỗi: {r1.stderr}")
        if r2.returncode != 0:
            print(f"    Lỗi: {r2.stderr}")

    print()


if __name__ == "__main__":
    main()
