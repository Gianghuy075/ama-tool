"""
Phone Registration Bot — Đăng ký tài khoản Amazon JP trực tiếp trên điện thoại.
Sử dụng XiaoWei API để điều khiển Chrome trên điện thoại thật qua ADB.
"""

import asyncio
import random
import logging
import re
import string
import time
from datetime import datetime
from typing import Optional

from src.xiaowei_client import XiaoWeiClient
from src.config import CONFIG

log = logging.getLogger(__name__)


class PhoneRegistrationBot:
    """
    Bot đăng ký Amazon JP trên điện thoại thật qua XiaoWei API.
    Mỗi instance xử lý 1 điện thoại.
    """

    # Class variable để luân phiên trình duyệt (round-robin) across threads
    _rotation_index = 0

    def __init__(self, xiaowei: XiaoWeiClient, device_serial: str, product_url: str = ""):
        self.xw = xiaowei
        self.device = device_serial
        self.product_url = product_url or CONFIG.get("product_url", "")
        self.should_stop = False

        # Cấu hình timing
        xw_config = CONFIG.get("xiaowei", {})
        self.tap_delay = xw_config.get("tap_delay", [0.5, 1.5])
        self.otp_source = xw_config.get("otp_source", "sms")
        
        # Danh sách các trình duyệt hỗ trợ để luân phiên (Browser Rotation)
        self.supported_browsers = xw_config.get("browsers", [
            "com.android.chrome",        # Chrome
            "org.mozilla.firefox",       # Firefox
            "com.kiwibrowser.browser",   # Kiwi Browser
            "com.brave.browser"          # Brave Browser
        ])

    # ── Helpers ───────────────────────────────────────────────────────

    async def get_device_resolution(self) -> tuple[int, int]:
        """Lấy độ phân giải của thiết bị."""
        res_str = await self.xw.run_adb_with_output(self.device, "wm size")
        if res_str:
            override_match = re.search(r"Override size:\s*(\d+)x(\d+)", res_str)
            if override_match:
                return int(override_match.group(1)), int(override_match.group(2))
            physical_match = re.search(r"Physical size:\s*(\d+)x(\d+)", res_str)
            if physical_match:
                return int(physical_match.group(1)), int(physical_match.group(2))
        return 1080, 1920

    async def get_installed_browsers(self) -> list:
        """Kiểm tra và trả về các trình duyệt trong supported_browsers thực tế được cài đặt trên thiết bị."""
        installed = []
        for pkg in self.supported_browsers:
            if await self.xw.is_package_installed(self.device, pkg):
                installed.append(pkg)
        return installed

    async def _delay(self, min_sec: float = None, max_sec: float = None):
        """Tạo delay ngẫu nhiên giống hành vi người thật."""
        if min_sec is None:
            min_sec = self.tap_delay[0]
        if max_sec is None:
            max_sec = self.tap_delay[1]
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def _generate_japanese_name(self) -> str:
        """Tạo tên tiếng Nhật ngẫu nhiên."""
        surnames = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
                     "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水"]
        first_names = ["翔", "蓮", "悠真", "湊", "大翔", "陽翔", "結菜", "咲良", "莉子", "芽依",
                       "結愛", "陽葵", "紬", "凛", "葵", "さくら", "大輔", "健太", "拓海", "直樹"]
        return f"{random.choice(surnames)} {random.choice(first_names)}"

    def _generate_random_token(self, length: int = 20) -> str:
        """Tạo token ngẫu nhiên."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    # ── Core: Tap and type helpers ────────────────────────────────────

    async def _tap_at(self, x: float, y: float, description: str = ""):
        """Tap vào vị trí % trên màn hình với delay."""
        if description:
            log.info(f"[Phone:{self.device}] Tap → {description} ({x}%, {y}%)")
        await self.xw.tap(self.device, x, y)
        await self._delay()

    async def _tap_button(self, x: float, y: float, description: str = ""):
        """
        Tap nút với thinking delay + tọa độ lệch tâm ngẫu nhiên.
        Giả lập: người dùng nhìn lại → di tay → bấm nút (không chính xác 100%).
        """
        # Thinking time: 0.8 – 1.8 giây nhìn lại trước khi bấm
        await self.xw.thinking_delay(description)
        # Tap với tọa độ lệch ngẫu nhiên ±1.5%
        if description:
            log.info(f"[Phone:{self.device}] Tap nút → {description} ({x}%, {y}%) [offset + thinking]")
        await self.xw.tap_with_offset(self.device, x, y)
        await self._delay()

    async def _type_into_field(self, text: str, field_x: float = 50, field_y: float = 50, description: str = ""):
        """
        Tap vào ô input, clear nội dung cũ, rồi nhập text (cách cũ — gọi type_text).
        """
        if description:
            log.info(f"[Phone:{self.device}] Nhập '{text[:20]}...' vào {description}")

        # Tap vào ô input để focus
        await self._tap_at(field_x, field_y, f"Focus {description}")
        await self._delay(0.3, 0.6)

        # Triple-tap để select all text hiện tại, rồi xóa
        await self.xw.tap(self.device, field_x, field_y)
        await asyncio.sleep(0.1)
        await self.xw.tap(self.device, field_x, field_y)
        await asyncio.sleep(0.1)
        await self.xw.tap(self.device, field_x, field_y)
        await asyncio.sleep(0.3)
        # Nhấn phím Delete để xóa text đã select
        await self.xw.press_delete(self.device)  # KEYCODE_DEL via /api/keyevent
        await asyncio.sleep(0.3)

        # Nhập text mới
        await self.xw.type_text(self.device, text, field_x, field_y)
        await self._delay(0.3, 0.8)

    async def _human_type_into_field(self, text: str, field_x: float = 50, field_y: float = 50, description: str = ""):
        """
        Tap vào ô input, clear nội dung cũ, rồi nhập text TỪNG KÝ TỰ (giả lập người thật).
        Sử dụng human_type() với typo simulation.
        """
        if description:
            log.info(f"[Phone:{self.device}] 🖐️ Human-type '{text[:20]}...' vào {description}")

        # Tap vào ô input để focus
        await self._tap_at(field_x, field_y, f"Focus {description}")
        await self._delay(0.3, 0.6)

        # Triple-tap để select all text hiện tại, rồi xóa
        await self.xw.tap(self.device, field_x, field_y)
        await asyncio.sleep(0.1)
        await self.xw.tap(self.device, field_x, field_y)
        await asyncio.sleep(0.1)
        await self.xw.tap(self.device, field_x, field_y)
        await asyncio.sleep(0.3)
        await self.xw.press_delete(self.device)  # KEYCODE_DEL via /api/keyevent
        await asyncio.sleep(0.3)

        # Nhập text từng ký tự với human_type (có typo simulation)
        await self.xw.human_type(self.device, text)
        await self._delay(0.3, 0.8)

    async def _scroll_down(self, count: int = 1):
        """Scroll xuống trên Chrome."""
        for _ in range(count):
            await self.xw.swipe(self.device, "up")  # swipe up = scroll down
            await self._delay(0.3, 0.6)

    async def _wait_page_load(self, seconds: float = 3.0):
        """Đợi trang load."""
        await asyncio.sleep(seconds)

    async def _press_enter(self):
        """Nhấn phím Enter."""
        await self.xw.press_enter(self.device)  # KEYCODE_ENTER via /api/keyevent

    async def _tap_bbox_pct(self, x_min_pct: float, x_max_pct: float, y_min_pct: float, y_max_pct: float, description: str = ""):
        """
        Tap vào vị trí ngẫu nhiên trong bounding box phần trăm để giả lập click lệch tâm.
        """
        # Thinking time: 1.5 – 3.0 giây để giả lập người đọc thông tin trước khi tương tác
        thinking = random.uniform(1.5, 3.0)
        log.info(f"[Phone:{self.device}] 💭 Thinking delay: {thinking:.2f}s trước khi {description or 'click'}...")
        await asyncio.sleep(thinking)

        w, h = await self.get_device_resolution()
        x_min = int(x_min_pct * w / 100.0)
        x_max = int(x_max_pct * w / 100.0)
        y_min = int(y_min_pct * h / 100.0)
        y_max = int(y_max_pct * h / 100.0)

        # Lấy tọa độ ngẫu nhiên bên trong bounding box
        click_x = random.randint(min(x_min, x_max), max(x_min, x_max))
        click_y = random.randint(min(y_min, y_max), max(y_min, y_max))

        if description:
            log.info(f"[Phone:{self.device}] Click lệch tâm {description} tại ({click_x}, {click_y})")
        await self.xw.device_click(self.device, click_x, click_y)
        await self._delay()

    async def _human_type_char_by_char(self, text: str, description: str = ""):
        """
        Tách chuỗi thành các ký tự đơn lẻ và gửi qua API /device/type-char với delay ngẫu nhiên 0.07s - 0.22s.
        """
        if description:
            log.info(f"[Phone:{self.device}] Gõ chậm {description}: '{text[:15]}...'")
        for char in text:
            await self.xw.type_char(self.device, char)
            # Tốc độ gõ chậm ngẫu nhiên 0.07s - 0.22s
            await asyncio.sleep(random.uniform(0.07, 0.22))

    async def _type_into_field_human(self, text: str, x_min_pct: float, x_max_pct: float, y_min_pct: float, y_max_pct: float, description: str = ""):
        """
        Click vào ô input lệch tâm, sau đó gõ phím chậm từng ký tự.
        """
        # Focus ô input bằng cách click lệch tâm
        await self._tap_bbox_pct(x_min_pct, x_max_pct, y_min_pct, y_max_pct, f"Focus {description}")
        
        # Thinking time sau khi click focus để người chuẩn bị gõ: 1.5 – 3.0 giây
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # Clear text cũ nếu có
        mid_x = (x_min_pct + x_max_pct)/2
        mid_y = (y_min_pct + y_max_pct)/2
        await self.xw.tap(self.device, mid_x, mid_y)
        await asyncio.sleep(0.1)
        await self.xw.tap(self.device, mid_x, mid_y)
        await asyncio.sleep(0.1)
        await self.xw.tap(self.device, mid_x, mid_y)
        await asyncio.sleep(0.3)
        await self.xw.press_delete(self.device)
        await asyncio.sleep(0.3)

        # Gõ chậm
        await self._human_type_char_by_char(text, description)

    # ── Main Registration Flow ────────────────────────────────────────

    def _randomize_product_url(self, base_url: str) -> str:
        """Tạo URL sản phẩm mới với tracking tokens ngẫu nhiên cho mỗi tài khoản."""
        from urllib.parse import urlparse, urlencode, urlunparse
        try:
            parsed = urlparse(base_url)
            new_token = self._generate_random_token(20)
            ref_prefix = "cm_sw_r_cp_ud_dp_"
            new_params = {
                'ref': f"{ref_prefix}{new_token}",
                'ref_': f"{ref_prefix}{new_token}",
                'social_share': f"{ref_prefix}{self._generate_random_token(20)}",
            }
            if random.random() < 0.4:
                fbclid = 'Iw' + self._generate_random_token(40) + self._generate_random_token(40)
                new_params['fbclid'] = fbclid
            new_query = urlencode(new_params)
            randomized = urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, parsed.fragment
            ))
            return randomized
        except Exception as e:
            log.warning(f"[Anti-detect] Không thể randomize URL, dùng URL gốc: {e}")
            return base_url

    async def register_one(self, row: dict) -> dict:
        """
        Luồng đăng ký Amazon JP hoàn chỉnh trên 1 điện thoại.
        """
        # Nếu đang chạy thực nghiệm Không Proxy
        xw_config = CONFIG.get("xiaowei", {})
        if xw_config.get("no_proxy_experiment", False):
            return await self.register_no_proxy(row)

        if not row.get("name") or not str(row["name"]).strip():
            row["name"] = self._generate_japanese_name()
            log.info(f"[Phone:{self.device}] Tên trống, sinh tên tự động: {row['name']}")

        result = {
            "name": row["name"],
            "email": row["email"],
            "password": row.get("password", ""),
            "proxy": row.get("proxy", ""),
            "device": self.device,
            "status": "FAILED",
            "note": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        chosen_browser = "com.android.chrome"
        try:
            # ── Browser Rotation ──────────────────────────────────
            installed = await self.get_installed_browsers()
            if not installed:
                log.warning(f"[Phone:{self.device}] Không tìm thấy trình duyệt nào hỗ trợ, dùng mặc định Chrome")
                chosen_browser = "com.android.chrome"
            else:
                # Luân phiên (round-robin) trình duyệt
                PhoneRegistrationBot._rotation_index = (PhoneRegistrationBot._rotation_index + 1) % len(installed)
                chosen_browser = installed[PhoneRegistrationBot._rotation_index]
                log.info(f"[Phone:{self.device}] Trình duyệt luân phiên được chọn: {chosen_browser}")

            # ── STEP 1: Xóa Sạch Dấu Vết (Clear Data) ──────────────────────────
            log.info(f"[Phone:{self.device}] Step 1 – Xóa sạch dữ liệu & Chuẩn bị trình duyệt...")
            await self.xw.clear_browser_data(self.device, chosen_browser)
            await asyncio.sleep(1.0)
            await self.xw.kill_browser(self.device, chosen_browser)
            await asyncio.sleep(1.0)

            # Mở trình duyệt với URL sản phẩm Amazon
            if not self.product_url:
                result["note"] = "Chưa cung cấp link sản phẩm Amazon (product_url)"
                return result

            # Randomize URL tracking tokens cho mỗi tài khoản (anti-detection)
            unique_url = self._randomize_product_url(self.product_url)
            log.info(f"[Phone:{self.device}] Mở trình duyệt {chosen_browser} → {unique_url[:60]}...")
            await self.xw.open_url(self.device, unique_url, chosen_browser)
            
            # Đợi trang tải xong + Độ trễ suy nghĩ (Thinking Time)
            await self._wait_page_load(5.0)

            # ── STEP 2: Click nút Request Invitation ──────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 2 – Cuộn trang tìm nút Request Invitation...")
            await self._scroll_down(3)
            await self._delay(1.0, 2.0)

            # Click Lệch Tâm Ngẫu Nhiên: Bounding Box (45%-55%, 53%-57%)
            await self._tap_bbox_pct(45, 55, 53, 57, "Nút Request Invitation")
            await self._wait_page_load(4.0)

            # ── STEP 3: Form Login – Nhập Email ──────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 3 – Nhập email vào form đăng nhập...")
            # Nhập Email chậm phím từng ký tự (0.07s - 0.22s) với click lệch tâm ô Email (40%-60%, 38%-42%)
            await self._type_into_field_human(row["email"], 40, 60, 38, 42, "Ô Email")

            # Click Lệch Tâm Ngẫu Nhiên nút Continue (45%-55%, 53%-57%)
            await self._tap_bbox_pct(45, 55, 53, 57, "Nút Continue")
            await self._wait_page_load(4.0)

            # ── STEP 4: Tạo tài khoản ──────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 4 – Click tạo tài khoản mới...")
            # Click Lệch Tâm Ngẫu Nhiên nút Create Account (40%-60%, 48%-52%)
            await self._tap_bbox_pct(40, 60, 48, 52, "Nút Create Account")
            await self._wait_page_load(3.0)

            # ── STEP 5: Điền form đăng ký ─────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 5 – Điền form đăng ký tài khoản...")
            # Điền Tên: Bounding Box (40%-60%, 30%-34%)
            await self._type_into_field_human(row["name"], 40, 60, 30, 34, "Ô Tên (氏名)")
            await self._delay(0.5, 1.0)

            # Điền Mật khẩu: Bounding Box (40%-60%, 46%-50%)
            await self._type_into_field_human(row["password"], 40, 60, 46, 50, "Ô Mật khẩu")
            await self._delay(0.5, 1.0)

            # Điền Xác nhận mật khẩu: Bounding Box (40%-60%, 56%-60%)
            await self._type_into_field_human(row["password"], 40, 60, 56, 60, "Ô Xác nhận mật khẩu")
            await self._delay(0.5, 1.0)

            # ── STEP 6: Submit form ───────────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 6 – Submit form đăng ký...")
            await self._scroll_down(1)
            await self._delay(0.5, 1.0)

            # Click Lệch Tâm Ngẫu Nhiên nút Submit đăng ký (40%-60%, 68%-72%)
            # Lưu thời điểm điện thoại bấm nút "Gửi OTP" để lọc email (Layer 2)
            sent_otp_time = time.time()
            await self._tap_bbox_pct(40, 60, 68, 72, "Nút Submit đăng ký")
            await self._wait_page_load(5.0)

            # ── STEP 7: Nhập OTP ──────────────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 7 – Chờ và nhập mã OTP...")
            otp = None

            if self.otp_source == "sms":
                log.info(f"[Phone:{self.device}] Đang chờ OTP qua SMS...")
                otp = await self.xw.read_latest_sms(
                    self.device,
                    sender_filter="Amazon",
                    timeout_sec=CONFIG.get("otp_wait_seconds", 90)
                )
            else:
                log.info(f"[Phone:{self.device}] Đang chờ OTP qua Gmail (3-layer filter)...")
                from src.gmail_otp import GmailOTPReader
                gmail = GmailOTPReader(
                    email=CONFIG["gmail_address"],
                    password=CONFIG["gmail_app_password"],
                    imap_server=CONFIG["imap_server"],
                )
                otp = await asyncio.to_thread(
                    gmail.fetch_otp,
                    row["email"],
                    wait_seconds=CONFIG["otp_wait_seconds"],
                    poll_interval=3,
                    sent_otp_time=sent_otp_time
                )

            if not otp:
                result["note"] = f"Không nhận được OTP (nguồn: {self.otp_source})"
                return result

            log.info(f"[Phone:{self.device}] OTP nhận được: {otp}")

            # Điền OTP: Bounding Box (30%-70%, 40%-44%), gõ chậm từng ký tự
            await self._type_into_field_human(otp, 30, 70, 40, 44, "Ô OTP")

            # Click Lệch Tâm Ngẫu Nhiên nút Xác minh OTP (40%-60%, 58%-62%)
            await self._tap_bbox_pct(40, 60, 58, 62, "Nút Xác minh OTP")
            await self._wait_page_load(5.0)

            # ── STEP 8: Kiểm tra kết quả ─────────────────────────────
            log.info(f"[Phone:{self.device}] Step 8 – Kiểm tra kết quả đăng ký...")
            screenshot_dir = CONFIG.get("xiaowei", {}).get("screenshot_dir", "data/screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            await self.xw.screenshot(self.device, screenshot_dir)

            result["status"] = "SUCCESS"
            result["note"] = "Đăng ký Amazon thành công (trên điện thoại)"
            log.info(f"[Phone:{self.device}] ✅ ĐĂNG KÝ THÀNH CÔNG: {row['email']}")

        except Exception as e:
            result["note"] = f"Lỗi: {str(e)}"
            log.error(f"[Phone:{self.device}] ❌ Lỗi đăng ký {row['email']}: {e}", exc_info=True)

        finally:
            try:
                await self.xw.kill_browser(self.device, chosen_browser)
            except Exception:
                pass

        return result

    async def register_no_proxy(self, row: dict) -> dict:
        """
        Luồng đăng ký thử nghiệm - KHÔNG PROXY XOAY.
        Sử dụng luân phiên các trình duyệt được cài đặt, xóa cache,
        gõ chậm, nghĩ lâu, click lệch tâm ngẫu nhiên và bốc tách OTP 3 lớp.
        """
        if not row.get("name") or not str(row["name"]).strip():
            row["name"] = self._generate_japanese_name()
            log.info(f"[Phone:{self.device}] Tên trống, sinh tên tự động: {row['name']}")

        result = {
            "name": row["name"],
            "email": row["email"],
            "password": row.get("password", ""),
            "proxy": "NO_PROXY",
            "device": self.device,
            "status": "FAILED",
            "note": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        chosen_browser = "org.mozilla.firefox"
        try:
            # ── Browser Rotation ──────────────────────────────────
            installed = await self.get_installed_browsers()
            if not installed:
                log.warning(f"[Phone:{self.device}] Không tìm thấy trình duyệt nào hỗ trợ, dùng mặc định Firefox")
                chosen_browser = "org.mozilla.firefox"
            else:
                # Luân phiên (round-robin) trình duyệt
                PhoneRegistrationBot._rotation_index = (PhoneRegistrationBot._rotation_index + 1) % len(installed)
                chosen_browser = installed[PhoneRegistrationBot._rotation_index]
                log.info(f"[Phone:{self.device}] (No Proxy) Trình duyệt luân phiên được chọn: {chosen_browser}")

            # ── STEP 1: Xóa Sạch Dấu Vết (Clear Data) ──────────────────────────
            log.info(f"[Phone:{self.device}] (No Proxy) Step 1 – Xóa sạch dữ liệu {chosen_browser} & Mở App...")
            await self.xw.clear_browser_data(self.device, chosen_browser)
            await asyncio.sleep(1.0)
            await self.xw.kill_browser(self.device, chosen_browser)
            await asyncio.sleep(1.0)

            # Mở trình duyệt
            await self.xw.open_app(self.device, chosen_browser)
            
            # Chờ ứng dụng tải xong
            wait_app = random.uniform(3.0, 4.5)
            log.info(f"[Phone:{self.device}] Chờ app tải xong: {wait_app:.2f}s")
            await asyncio.sleep(wait_app)

            # ── STEP 2: Điều hướng đến Website ─────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] (No Proxy) Step 2 – Điều hướng...")
            target_url = self.product_url or CONFIG.get("xiaowei", {}).get("default_experiment_url", "https://example.com/register")
            unique_url = self._randomize_product_url(target_url)
            url_to_type = f"{unique_url}\n"
            
            log.info(f"[Phone:{self.device}] Gõ URL: {unique_url}")
            await self._human_type_char_by_char(url_to_type, "URL")
                
            # Chờ tải trang + Độ trễ suy nghĩ (Thinking Time)
            wait_load = random.uniform(4.0, 5.5)
            log.info(f"[Phone:{self.device}] Chờ tải trang: {wait_load:.2f}s")
            await asyncio.sleep(wait_load)

            # ── STEP 3: Click tạo tài khoản & nhập Email ───────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] (No Proxy) Step 3 – Click Create Account & Nhập Email...")
            
            # Click Lệch Tâm Ngẫu Nhiên: Bounding Box (400-600, 1100-1200) -> X: 37%-55%, Y: 57%-62%
            await self._tap_bbox_pct(37, 55, 57, 62, "Nút Create Account")
            await asyncio.sleep(2.0)

            # Nhập Email chậm phím từng ký tự: click focus ô Email (40%-60%, 38%-42%)
            await self._type_into_field_human(row["email"], 40, 60, 38, 42, "Ô Email")
            await asyncio.sleep(1.0)
            
            # Click Lệch Tâm Ngẫu Nhiên nút Verify Email (Gửi OTP): Bounding Box (480-520, 1330-1370) -> X: 44%-48%, Y: 69%-71%
            # Lưu thời điểm điện thoại bấm nút "Gửi OTP" để lọc email (Layer 2)
            sent_otp_time = time.time()
            await self._tap_bbox_pct(44, 48, 69, 71, "Nút Verify Email (Gửi OTP)")
            await asyncio.sleep(3.0)

            # ── STEP 4: Chờ và Quét OTP từ Mail Master ─────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] (No Proxy) Step 4 – Chờ và quét OTP từ Gmail (3-layer filter)...")
            from src.gmail_otp import GmailOTPReader
            gmail = GmailOTPReader(
                email=CONFIG["gmail_address"],
                password=CONFIG["gmail_app_password"],
                imap_server=CONFIG["imap_server"],
            )
            
            otp = await asyncio.to_thread(
                gmail.fetch_otp,
                row["email"],
                wait_seconds=CONFIG["otp_wait_seconds"],
                poll_interval=3,
                sent_otp_time=sent_otp_time
            )

            if not otp:
                result["note"] = "Không nhận được OTP từ Gmail"
                return result

            log.info(f"[Phone:{self.device}] Đã tìm thấy mã OTP: {otp}")

            # ── STEP 5: Độ trễ suy nghĩ & Nhập OTP hoàn tất ──────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] (No Proxy) Step 5 – Độ trễ suy nghĩ & nhập OTP...")
            
            # Độ trễ suy nghĩ (Thinking Time): dừng từ 1.5 đến 3.0 giây
            thinking = random.uniform(1.5, 3.0)
            log.info(f"[Phone:{self.device}] Dừng suy nghĩ: {thinking:.2f}s")
            await asyncio.sleep(thinking)

            # Gõ chậm từng số vào ô nhập liệu: click focus ô OTP (30%-70%, 40%-44%)
            await self._type_into_field_human(otp, 30, 70, 40, 44, "Ô OTP")

            # Đợi tiếp 1.0 đến 1.8 giây sau khi gõ xong số cuối cùng
            post_typing = random.uniform(1.0, 1.8)
            log.info(f"[Phone:{self.device}] Chờ sau gõ: {post_typing:.2f}s")
            await asyncio.sleep(post_typing)

            # Click Lệch Tâm Ngẫu Nhiên nút Xác nhận cuối cùng: Bounding Box (480-520, 1480-1520) -> X: 44%-48%, Y: 77%-79%
            await self._tap_bbox_pct(44, 48, 77, 79, "Nút Xác nhận tài khoản cuối")

            # Chờ trang hoàn tất tải và chụp màn hình
            await asyncio.sleep(5.0)
            screenshot_dir = CONFIG.get("xiaowei", {}).get("screenshot_dir", "data/screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            await self.xw.screenshot(self.device, screenshot_dir)

            result["status"] = "SUCCESS"
            result["note"] = "Đăng ký thử nghiệm (Không Proxy) thành công"
            log.info(f"[Phone:{self.device}] ✅ ĐĂNG KÝ THÀNH CÔNG: {row['email']}")

        except Exception as e:
            result["note"] = f"Lỗi: {str(e)}"
            log.error(f"[Phone:{self.device}] ❌ Lỗi đăng ký thử nghiệm {row['email']}: {e}", exc_info=True)

        finally:
            try:
                await self.xw.kill_browser(self.device, chosen_browser)
            except Exception:
                pass

        return result



class PhoneRegistrationManager:
    """
    Quản lý đăng ký song song trên nhiều điện thoại.
    Phân phối tài khoản cho từng thiết bị online.
    """

    def __init__(self, product_url: str = ""):
        xw_config = CONFIG.get("xiaowei", {})
        self.xiaowei = XiaoWeiClient(
            api_url=xw_config.get("api_url", "http://localhost:22222"),
            api_type=xw_config.get("api_type", "xiaowei"),
            timeout=30
        )
        self.product_url = product_url or CONFIG.get("product_url", "")
        self.should_stop = False

    async def run_all(self, input_xlsx: str, output_xlsx: str, on_progress=None, group_name=""):
        """
        Chạy đăng ký song song trên tất cả điện thoại online.
        Tương thích interface với RegistrationBot.run_all()
        """
        from src.excel_handler import ExcelHandler

        excel = ExcelHandler(input_xlsx)
        rows = excel.read_rows()
        log.info(f"[PhoneManager] Loaded {len(rows)} accounts from {input_xlsx}")

        if not rows:
            log.warning("[PhoneManager] Không có tài khoản để đăng ký!")
            return

        # Lấy danh sách thiết bị online
        devices = await self.xiaowei.get_devices()
        if not devices:
            log.error("[PhoneManager] Không tìm thấy thiết bị nào kết nối!")
            return

        # Lọc thiết bị đang online
        online_devices = []
        xw_config = CONFIG.get("xiaowei", {})
        device_filter = xw_config.get("devices", "all")

        for d in devices:
            serial = d.get("serial") or d.get("Serial") or d.get("id") or str(d)
            if isinstance(serial, dict):
                serial = serial.get("serial", "")
            online_devices.append(str(serial))

        if device_filter != "all":
            # Lọc theo danh sách serial cụ thể
            filter_serials = [s.strip() for s in device_filter.split(",")]
            online_devices = [d for d in online_devices if d in filter_serials]

        if not online_devices:
            log.error("[PhoneManager] Không có thiết bị online phù hợp!")
            return

        log.info(f"[PhoneManager] Sử dụng {len(online_devices)} thiết bị: {online_devices}")

        # Phân phối accounts cho các điện thoại
        results = []
        account_queue = asyncio.Queue()
        for row in rows:
            await account_queue.put(row)

        async def device_worker(device_serial: str):
            """Worker xử lý accounts trên 1 thiết bị."""
            bot = PhoneRegistrationBot(self.xiaowei, device_serial, self.product_url)
            bot.should_stop = self.should_stop

            while not account_queue.empty() and not self.should_stop:
                try:
                    row = account_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                log.info(f"[PhoneManager] Device {device_serial} xử lý: {row['email']}")
                result = await bot.register_one(row)
                results.append(result)

                if on_progress:
                    try:
                        on_progress(result)
                    except Exception as ex:
                        log.error(f"[PhoneManager] Lỗi callback: {ex}")

                # Delay giữa các tài khoản
                delay = CONFIG.get("delay_between_accounts", 3)
                if delay > 0 and not self.should_stop:
                    await asyncio.sleep(delay)

        # Tạo workers song song cho tất cả thiết bị
        tasks = [device_worker(serial) for serial in online_devices]
        await asyncio.gather(*tasks)

        # Ghi kết quả
        excel.write_results(results, output_xlsx)
        log.info(f"\n✅ [PhoneManager] Done. Results saved to: {output_xlsx}")
        self._print_summary(results)

    def _print_summary(self, results):
        total = len(results)
        success = sum(1 for r in results if r["status"] == "SUCCESS")
        log.info(f"\n{'═' * 40}")
        log.info(f"SUMMARY (PHONE MODE): {success}/{total} succeeded")
        for r in results:
            icon = "✅" if r["status"] == "SUCCESS" else "❌"
            device = r.get("device", "?")
            log.info(f"  {icon} [{device}] {r['email']} – {r['note']}")
        log.info(f"{'═' * 40}")
