"""
STTNB Login Helper — Đăng nhập NotebookLM bằng Google Chrome hệ thống.

Cách dùng do Playwright bundled Chromium bị crash (SIGBUS) trên macOS ARM64.
Script này mở Google Chrome đã cài trên máy, cho bạn đăng nhập Google, 
rồi lưu session cookies vào file storage_state.json.

Usage:
    python login_helper.py
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# NotebookLM storage directory
NOTEBOOKLM_DIR = Path.home() / ".notebooklm"
STORAGE_STATE_FILE = NOTEBOOKLM_DIR / "storage_state.json"
PROFILES_DIR = NOTEBOOKLM_DIR / "profiles" / "default"


def find_chrome_path():
    """Find Google Chrome installation on macOS or Linux."""
    import shutil

    paths = [
        # Linux
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for p in paths:
        if os.path.exists(p):
            return p

    # Fallback: try PATH lookup
    for name in ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium"]:
        found = shutil.which(name)
        if found:
            return found

    return None


def _detect_display():
    """Auto-detect DISPLAY from running Xorg sessions (useful for XRDP/VNC)."""
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    try:
        out = subprocess.check_output(
            ["pgrep", "-a", "Xorg"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.strip().splitlines():
            for token in line.split():
                if token.startswith(":"):
                    return token
    except Exception:
        pass
    return None


async def login_with_system_chrome():
    """Launch system Chrome with remote debugging and capture cookies."""
    chrome_path = find_chrome_path()
    if not chrome_path:
        print("❌ Google Chrome không tìm thấy trên máy.")
        print("   Vui lòng cài Google Chrome từ: https://www.google.com/chrome/")
        sys.exit(1)

    print(f"✅ Tìm thấy Chrome: {chrome_path}")

    # Auto-detect DISPLAY for remote sessions (XRDP / VNC)
    display = _detect_display()
    if not display:
        print("❌ Không tìm thấy DISPLAY (X11 session).")
        print("   Hãy kết nối vào máy qua XRDP/VNC trước, rồi chạy lại script này.")
        print("   Hoặc set biến: export DISPLAY=:13")
        sys.exit(1)
    os.environ["DISPLAY"] = display
    print(f"🖥️  DISPLAY={display}")

    # Create user data dir for this session
    user_data_dir = str(NOTEBOOKLM_DIR / "chrome_login_profile")
    os.makedirs(user_data_dir, exist_ok=True)

    # Find a free port for remote debugging
    debug_port = 9222

    print(f"\n🌐 Đang mở Google Chrome để đăng nhập...")
    print(f"   Debug port: {debug_port}")
    print(f"   Profile: {user_data_dir}")

    # Launch Chrome with remote debugging
    chrome_args = [
        chrome_path,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
        "https://notebooklm.google.com",
    ]

    print(f"\n📋 Bước tiếp theo:")
    print(f"   1. Trình duyệt Chrome sẽ mở trang NotebookLM")
    print(f"   2. Đăng nhập tài khoản Google của bạn")
    print(f"   3. Sau khi thấy trang chính NotebookLM, quay lại đây")
    print(f"   4. Nhấn ENTER để lưu phiên đăng nhập\n")

    # Start Chrome
    chrome_process = subprocess.Popen(
        chrome_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for user to login
    input("⏳ Nhấn ENTER sau khi đã đăng nhập NotebookLM thành công... ")

    print("\n🔄 Đang lấy cookies từ Chrome...")

    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
            
            # Get the default context
            contexts = browser.contexts
            if not contexts:
                print("❌ Không tìm thấy browser context")
                return False
                
            context = contexts[0]
            
            # Save storage state (cookies + localStorage)
            NOTEBOOKLM_DIR.mkdir(parents=True, exist_ok=True)
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            
            storage_state = await context.storage_state()
            
            # Save to both locations that notebooklm-py checks
            with open(STORAGE_STATE_FILE, "w") as f:
                json.dump(storage_state, f, indent=2)
            
            profile_state_file = PROFILES_DIR / "storage_state.json"
            with open(profile_state_file, "w") as f:
                json.dump(storage_state, f, indent=2)
            
            print(f"\n✅ Cookies đã được lưu!")
            print(f"   📄 {STORAGE_STATE_FILE}")
            print(f"   📄 {profile_state_file}")
            
            # Check if we got NotebookLM-related cookies
            cookies = storage_state.get("cookies", [])
            google_cookies = [c for c in cookies if "google" in c.get("domain", "")]
            print(f"   🍪 Tổng cookies: {len(cookies)}")
            print(f"   🍪 Google cookies: {len(google_cookies)}")
            
            if google_cookies:
                print(f"\n🎉 Đăng nhập thành công! Bạn có thể chạy server.")
            else:
                print(f"\n⚠️  Không tìm thấy Google cookies. Hãy đảm bảo bạn đã đăng nhập.")
            
            await browser.close()
            
    except ImportError as e:
        print(f"❌ Thiếu thư viện: {e}")
        print("   Chạy: pip install playwright")
        return False
    except Exception as e:
        print(f"❌ Lỗi khi lấy cookies: {e}")
        print(f"   Chi tiết: {type(e).__name__}: {e}")
        return False
    finally:
        # Close Chrome
        print("\n🔄 Đang đóng Chrome...")
        chrome_process.terminate()
        try:
            chrome_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome_process.kill()
        print("✅ Hoàn tất!")

    return True


def main():
    print("=" * 50)
    print("  STTNB — Đăng nhập NotebookLM")
    print("  (Bypass Playwright Chromium crash)")
    print("=" * 50)
    
    result = asyncio.run(login_with_system_chrome())
    
    if result:
        print("\n" + "=" * 50)
        print("  Tiếp theo, chạy server:")
        print("  uvicorn app.main:app --reload --port 8000")
        print("=" * 50)
    else:
        print("\n❌ Đăng nhập thất bại. Thử lại hoặc liên hệ hỗ trợ.")


if __name__ == "__main__":
    main()
