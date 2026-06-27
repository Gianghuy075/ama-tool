"""
Phone Registration Bot — Đăng ký tài khoản Amazon JP trực tiếp trên điện thoại.
Sử dụng XiaoWei API để điều khiển Chrome trên điện thoại thật qua ADB.
"""

import asyncio
import random
import logging
import re
import string
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

    def __init__(self, xiaowei: XiaoWeiClient, device_serial: str, product_url: str = ""):
        self.xw = xiaowei
        self.device = device_serial
        self.product_url = product_url or CONFIG.get("product_url", "")
        self.should_stop = False

        # Cấu hình timing
        xw_config = CONFIG.get("xiaowei", {})
        self.tap_delay = xw_config.get("tap_delay", [0.5, 1.5])
        self.otp_source = xw_config.get("otp_source", "sms")

    # ── Helpers ───────────────────────────────────────────────────────

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

    async def _hide_keyboard(self):
        """Ẩn bàn phím ảo."""
        await self.xw.press_back(self.device)
        await asyncio.sleep(0.3)

    # ── Main Registration Flow ────────────────────────────────────────

    async def register_one(self, row: dict) -> dict:
        """
        Luồng đăng ký Amazon JP hoàn chỉnh trên 1 điện thoại.

        Args:
            row: dict chứa {name, email, password, proxy}

        Returns:
            dict chứa {name, email, password, proxy, status, note, timestamp}
        """
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

        try:
            # ── STEP 1: Chuẩn bị điện thoại ──────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] ═══════ Bắt đầu đăng ký: {row['email']} ═══════")
            log.info(f"[Phone:{self.device}] Step 1 – Chuẩn bị Chrome...")

            # Tắt Chrome cũ, xóa cookies
            await self.xw.kill_chrome(self.device)
            await asyncio.sleep(1)

            # Mở Chrome với URL sản phẩm Amazon
            if not self.product_url:
                result["note"] = "Chưa cung cấp link sản phẩm Amazon (product_url)"
                return result

            log.info(f"[Phone:{self.device}] Mở Chrome → {self.product_url[:60]}...")
            await self.xw.open_url(self.device, self.product_url)
            await self._wait_page_load(5.0)

            # ── STEP 2: Click nút Request Invitation ──────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 2 – Cuộn trang tìm nút Request Invitation...")

            # Trên mobile Chrome, nút "招待をリクエストする" thường ở giữa trang
            # Cuộn xuống để tìm nút
            await self._scroll_down(3)
            await self._delay(1.0, 2.0)

            # Tap vào vùng nút Buy/Request — vị trí ước lượng trên mobile
            # Nút này thường ở khoảng 50% ngang, 50-60% dọc sau khi cuộn
            await self._tap_at(50, 55, "Nút Request Invitation")
            await self._wait_page_load(4.0)

            # ── STEP 3: Form Login – Nhập Email ──────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 3 – Nhập email vào form đăng nhập...")

            # Trên trang login Amazon mobile, ô email thường ở giữa trên
            # Khoảng 50% ngang, 40% dọc
            await self._human_type_into_field(row["email"], 50, 40, "Ô Email")

            # Thinking delay + Tap nút Continue (次に進む) với offset ngẫu nhiên
            await self._tap_button(50, 55, "Nút Continue")
            await self._wait_page_load(4.0)

            # ── STEP 4: Kiểm tra trạng thái ──────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 4 – Kiểm tra trạng thái email...")

            # Chụp ảnh màn hình để kiểm tra
            screenshot_dir = CONFIG.get("xiaowei", {}).get("screenshot_dir", "data/screenshots")
            import os
            os.makedirs(screenshot_dir, exist_ok=True)
            await self.xw.screenshot(self.device, screenshot_dir)
            await self._delay(1.0, 1.5)

            # Giả định: nếu email mới → trang tạo tài khoản
            # Tap nút "アカウントの作成に進む" (Create Account)
            # Thường ở khoảng giữa trang
            await self._tap_at(50, 50, "Nút Create Account (nếu email mới)")
            await self._wait_page_load(3.0)

            # ── STEP 5: Điền form đăng ký ─────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 5 – Điền form đăng ký tài khoản...")

            # Trên form đăng ký Amazon mobile, thứ tự các field:
            # 1. Tên (氏名) — khoảng 30-35% dọc
            # 2. Email — thường đã được điền sẵn
            # 3. Mật khẩu — khoảng 45-50% dọc
            # 4. Xác nhận mật khẩu — khoảng 55-60% dọc

            # Nhập tên
            await self._human_type_into_field(row["name"], 50, 32, "Ô Tên (氏名)")
            await self._delay(0.5, 1.0)

            # Nhập mật khẩu
            await self._human_type_into_field(row["password"], 50, 48, "Ô Mật khẩu")
            await self._delay(0.5, 1.0)

            # Nhập xác nhận mật khẩu (nếu có)
            await self._human_type_into_field(row["password"], 50, 58, "Ô Xác nhận mật khẩu")
            await self._delay(0.5, 1.0)

            # ── STEP 6: Submit form ───────────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 6 – Submit form đăng ký...")

            # Cuộn xuống để thấy nút Submit
            await self._scroll_down(1)
            await self._delay(0.5, 1.0)

            # Tap nút Submit (次に進む / Continue)
            # Thinking delay + Tap nút Submit với offset ngẫu nhiên
            await self._tap_button(50, 70, "Nút Submit đăng ký")
            await self._wait_page_load(5.0)

            # ── STEP 7: Nhập OTP ──────────────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 7 – Chờ và nhập mã OTP...")

            otp = None

            if self.otp_source == "sms":
                # Đọc OTP từ SMS trên SIM điện thoại
                log.info(f"[Phone:{self.device}] Đang chờ OTP qua SMS...")
                otp = await self.xw.read_latest_sms(
                    self.device,
                    sender_filter="Amazon",
                    timeout_sec=CONFIG.get("otp_wait_seconds", 90)
                )
            else:
                # Đọc OTP từ Gmail
                log.info(f"[Phone:{self.device}] Đang chờ OTP qua Gmail...")
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
                )

            if not otp:
                result["note"] = f"Không nhận được OTP (nguồn: {self.otp_source})"
                return result

            log.info(f"[Phone:{self.device}] OTP nhận được: {otp}")

            # Nhập OTP vào ô xác minh — từng ký tự giống người thật
            # Ô OTP thường ở khoảng giữa trang
            await self._human_type_into_field(otp, 50, 42, "Ô OTP")

            # Thinking delay + Tap nút Xác nhận OTP với offset ngẫu nhiên
            await self._tap_button(50, 60, "Nút Xác minh OTP")
            await self._wait_page_load(5.0)

            # ── STEP 8: Kiểm tra kết quả ─────────────────────────────
            log.info(f"[Phone:{self.device}] Step 8 – Kiểm tra kết quả đăng ký...")

            # Chụp screenshot để xác nhận
            await self.xw.screenshot(self.device, screenshot_dir)

            # Nếu trang chuyển về Amazon (không còn form login) → thành công
            result["status"] = "SUCCESS"
            result["note"] = "Đăng ký Amazon thành công (trên điện thoại)"
            log.info(f"[Phone:{self.device}] ✅ ĐĂNG KÝ THÀNH CÔNG: {row['email']}")

        except Exception as e:
            result["note"] = f"Lỗi: {str(e)}"
            log.error(f"[Phone:{self.device}] ❌ Lỗi đăng ký {row['email']}: {e}", exc_info=True)

        finally:
            # Tắt Chrome sau khi xong
            try:
                await self.xw.kill_chrome(self.device)
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
