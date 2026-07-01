"""
Phone Registration Bot — Đăng ký tài khoản Amazon JP trực tiếp trên điện thoại.
Sử dụng XiaoWei API để điều khiển Chrome trên điện thoại thật qua ADB.
"""

import asyncio
import os
import random
import logging
import re
import string
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from src.screen_reader import ScreenReader
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
        self.screen_reader = ScreenReader(xiaowei)

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

    def _extract_asin(self, product_url: str) -> str:
        """Lấy ASIN từ URL Amazon nếu có."""
        match = re.search(r"/dp/([A-Z0-9]{10})(?:[/?]|$)", product_url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return ""

    def _validate_product_url(self) -> tuple[bool, str, str, str]:
        """
        Validate product_url cho flow Amazon JP.
        Return: (is_valid, message, expected_host, expected_asin)
        """
        if not self.product_url or not self.product_url.strip():
            return False, "Chưa cung cấp link sản phẩm Amazon (product_url)", "", ""

        try:
            parsed = urlparse(self.product_url.strip())
        except Exception as e:
            return False, f"Không parse được product_url: {e}", "", ""

        host = (parsed.netloc or "").lower()
        asin = self._extract_asin(self.product_url)

        if parsed.scheme not in {"http", "https"}:
            return False, f"product_url có scheme không hợp lệ: {parsed.scheme}", host, asin
        if "amazon.co.jp" not in host:
            return False, f"product_url không thuộc amazon.co.jp: {host}", host, asin
        if not asin:
            return False, "product_url không chứa ASIN dạng /dp/<ASIN>", host, asin

        return True, "OK", host, asin

    def _detect_visible_wrong_domain(self, xml: str, expected_host: str) -> Optional[str]:
        """
        Tìm domain hiển thị trên UI XML. Nếu thấy domain khác expected_host thì coi là dấu hiệu vào sai trang.
        """
        if not xml:
            return None

        xml_lower = xml.lower()
        amazon_indicators = [
            "amazon.co.jp",
            "www.amazon.co.jp",
            "amazon",
            "ショッピングカート",
            "カートに入れる",
            "ほしい物リスト",
            "prime",
            "ポイント",
            "配送料無料",
            "amazon mastercard",
        ]
        domains = set(re.findall(r"[a-z0-9.-]+\.[a-z]{2,}", xml_lower))
        # Loại domain hệ thống/phổ biến không hữu ích
        ignored = {"amazon", "amazon.co.jp", "www.amazon.co.jp", "android", "google", "gstatic", "doubleclick.net"}
        candidates = [d for d in domains if not any(d == ig or d.endswith("." + ig) for ig in ignored)]

        if expected_host and expected_host in candidates:
            return None

        # Nếu XML đã mang fingerprint rất rõ của product page Amazon thì không đánh dấu wrong-domain nữa.
        if any(marker in xml_lower for marker in amazon_indicators) or "￥" in xml or "¥" in xml:
            return None

        for domain in candidates:
            if expected_host and expected_host not in domain:
                return domain
        return None

    async def _verify_expected_product_page(
        self,
        expected_host: str,
        expected_asin: str,
        timeout: float = 10.0,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Verify cơ bản rằng bot đang ở product page Amazon JP đúng hướng.
        Return: (success, reason, xml)
        """
        amazon_host_markers = [
            "amazon.co.jp",
            "www.amazon.co.jp",
            "amazon",
        ]
        strong_markers = [
            "招待をリクエストする",
            "招待をリクエスト",
            "Request Invitation",
            "Invitation",
        ]
        product_page_markers = [
            "カートに入れる",
            "ショッピングカート",
            "prime",
            "ポイント",
            "ほしい物リスト",
            "在庫",
            "配送料無料",
            "Amazon Mastercard",
            "商品の情報",
            "この商品について",
            "評価",
            "レビュー",
            "検索",
            "検索する",
        ]
        xml = await self._wait_for_state(
            strong_markers + amazon_host_markers + product_page_markers,
            timeout=timeout,
            step_name="step1_wait_product_page",
        )
        if not xml:
            xml = await self.screen_reader.dump_ui(self.device)

        wrong_domain = self._detect_visible_wrong_domain(xml or "", expected_host)
        if wrong_domain:
            return False, f"Phát hiện domain lạ trên UI: {wrong_domain}", xml

        if xml:
            xml_lower = xml.lower()
            if expected_host and expected_host in xml_lower:
                return True, f"Xác nhận host hiển thị đúng: {expected_host}", xml
            if any(marker in xml_lower for marker in amazon_host_markers):
                if any(marker.lower() in xml_lower for marker in product_page_markers):
                    return True, "Tìm thấy host/fingerprint Amazon product page", xml
                if "￥" in xml or "¥" in xml:
                    return True, "Tìm thấy host Amazon cùng marker giá sản phẩm", xml
            if any(marker.lower() in xml_lower for marker in strong_markers[:4]):
                reason = "Tìm thấy CTA/product marker của Amazon"
                if expected_asin:
                    reason += f" (ASIN kỳ vọng: {expected_asin})"
                return True, reason, xml
            if any(marker.lower() in xml_lower for marker in product_page_markers):
                return True, "Tìm thấy fingerprint product page Amazon (cart/price/benefit markers)", xml
            if "￥" in xml or "¥" in xml:
                return True, "Tìm thấy price marker trên product page", xml

        return False, "Không thấy fingerprint đáng tin của product page Amazon", xml

    def _is_chrome_first_run_screen(self, xml: str) -> bool:
        if not xml:
            return False
        xml_lower = xml.lower()
        markers = [
            "tùy chỉnh chrome theo cách của bạn",
            "chrome theo cách của bạn",
            "không đăng nhập",
            "tiếp tục bằng tài khoản",
            "customize chrome",
            "continue as",
            "sign in to chrome",
            "use without an account",
            "no thanks",
            "skip sign in",
        ]
        return any(marker in xml_lower for marker in markers)

    def _is_chrome_loading_screen(self, xml: str) -> bool:
        """
        Nhận diện trạng thái Chrome đang mở nhưng chưa render được product page.
        """
        if not xml:
            return False
        xml_lower = xml.lower()
        loading_markers = [
            "chrome",
            "đang tải",
            "loading",
            "reload",
            "làm mới",
            "refresh",
        ]
        product_markers = [
            "amazon.co.jp",
            "request invite",
            "招待をリクエスト",
            "￥",
            "¥",
            "pokemon card game",
            "available by invitation",
            "amazon mastercard",
        ]
        if any(marker in xml_lower for marker in product_markers):
            return False

        nodes = self.screen_reader._parse_nodes(xml)
        if not nodes:
            return True

        visible_texts = [
            ((node.get("text") or "").strip() or (node.get("content_desc") or "").strip()).lower()
            for node in nodes
        ]
        visible_texts = [text for text in visible_texts if text]

        if any(marker in " ".join(visible_texts) for marker in loading_markers):
            return True

        # Nếu rất ít text có nghĩa và toàn package Chrome thì coi là loading screen.
        chrome_nodes = [node for node in nodes if "chrome" in (node.get("package") or "").lower()]
        if chrome_nodes and len(visible_texts) <= 3:
            return True
        return False

    async def _recover_chrome_loading_if_needed(self, browser_package: str, target_url: str) -> bool:
        """
        Nếu Chrome bị kẹt ở splash/loading screen sau khi mở URL, chủ động reopen/reload URL.
        """
        if browser_package != "com.android.chrome":
            return False

        for attempt in range(2):
            xml = await self.screen_reader.dump_ui(self.device)
            if not self._is_chrome_loading_screen(xml or ""):
                return False

            log.warning(
                f"[Phone:{self.device}] Phát hiện Chrome loading/splash screen (attempt {attempt + 1}/2), "
                "thử reopen URL để ép reload"
            )
            reopen_ok = await self.xw.open_url(self.device, target_url, browser_package)
            log.info(f"[Phone:{self.device}] reopen_url during loading recovery: {'OK' if reopen_ok else 'FAIL'}")
            await self._delay(1.2, 1.8)

        return True

    async def _dismiss_chrome_first_run_if_needed(self, browser_package: str, target_url: str) -> bool:
        """
        Xử lý các màn hình first-run/onboarding của Chrome sau khi clear data.
        Nếu đã phải dismiss onboarding thì mở lại target_url sau đó.
        """
        if browser_package != "com.android.chrome":
            return False

        handled_any = False
        dismiss_text_sets = [
            ["Không đăng nhập", "Use without an account", "No thanks", "Skip", "Not now"],
            ["Chấp nhận và tiếp tục", "Accept & continue", "Continue", "Tiếp tục"],
            ["OK", "Đồng ý", "Got it"],
        ]

        for step in range(4):
            xml = await self.screen_reader.dump_ui(self.device)
            if not self._is_chrome_first_run_screen(xml or ""):
                break

            handled_any = True
            log.warning(f"[Phone:{self.device}] Phát hiện Chrome first-run/onboarding screen (step {step + 1})")

            tapped = False
            for texts in dismiss_text_sets:
                elem = self.screen_reader.find_best_element(
                    xml or "",
                    texts=texts,
                    clickable=True,
                    preferred_region=(5, 95, 55, 95),
                    partial=True,
                )
                if elem:
                    log.info(
                        f"[Phone:{self.device}] Dismiss Chrome onboarding bằng '{elem.get('text') or elem.get('content_desc')}' "
                        f"tại ({elem['cx']},{elem['cy']})"
                    )
                    await self.xw.device_click(self.device, elem["cx"], elem["cy"])
                    await self._delay(0.8, 1.3)
                    await self.screen_reader.wait_for_ui_change(self.device, xml, timeout=5.0, poll_interval=0.5)
                    tapped = True
                    break

            if not tapped:
                log.warning(f"[Phone:{self.device}] Không tìm được nút dismiss rõ ràng trên Chrome onboarding")
                break

        if handled_any:
            log.info(f"[Phone:{self.device}] Mở lại product URL sau khi dismiss Chrome onboarding")
            reopen_ok = await self.xw.open_url(self.device, target_url, browser_package)
            log.info(f"[Phone:{self.device}] reopen_url after onboarding: {'OK' if reopen_ok else 'FAIL'}")
            await self._delay(1.0, 1.6)

        return handled_any

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

    async def _screenshot_step(self, step_name: str):
        """
        Chụp màn hình tại một bước quan trọng và lưu vào thư mục screenshots/<device>/.
        Tên file: HHMMSS_<step_name>.png — dễ sort theo thời gian.
        Không raise exception nếu screenshot thất bại.
        """
        try:
            screenshot_dir = CONFIG.get("xiaowei", {}).get("screenshot_dir", "data/screenshots")
            device_dir = os.path.join(screenshot_dir, self.device)
            os.makedirs(device_dir, exist_ok=True)
            ts = datetime.now().strftime("%H%M%S")
            safe_name = step_name.replace(" ", "_").replace("/", "-")
            path = os.path.join(device_dir, f"{ts}_{safe_name}.png")
            await self.xw.screenshot(self.device, path)
            log.debug(f"[Phone:{self.device}] Screenshot → {path}")
        except Exception as e:
            log.warning(f"[Phone:{self.device}] Screenshot thất bại ({step_name}): {e}")

    async def _wait_for_state(self, expected_texts: list, timeout: float = 10.0, step_name: str = "") -> Optional[str]:
        """
        Đợi đến khi UI hiển thị bất kỳ text nào trong expected_texts.
        Non-blocking: nếu timeout thì chỉ log warning + chụp screenshot, bot KHÔNG dừng.
        Return: XML string nếu tìm thấy, None nếu timeout.
        """
        xml = await self.screen_reader.wait_for_text(
            self.device, expected_texts, timeout=timeout
        )
        if xml is None:
            label = step_name or str(expected_texts)
            log.warning(f"[Phone:{self.device}] State timeout — không thấy {expected_texts} sau {timeout}s ({label})")
            await self._screenshot_step(f"TIMEOUT_{label[:30]}")
        return xml

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

    async def _tap_element(self, search_texts: list, fallback_bbox: tuple, description: str = "") -> bool:
        """
        Issue #3: Tap element bằng cách tìm text thực từ uiautomator dump.
        Fallback về hardcoded bbox nếu không tìm thấy element.

        Args:
            search_texts: list text để tìm (OR logic)
            fallback_bbox: (x_min, x_max, y_min, y_max) tính theo %
            description: mô tả để log
        Return: True nếu tap bằng dynamic coord, False nếu dùng fallback.
        """
        # Thinking delay (giả lập người nhìn vào màn hình trước khi bấm)
        thinking = random.uniform(1.5, 3.0)
        log.info(f"[Phone:{self.device}] 💭 Thinking {thinking:.2f}s trước {description or 'tap'}...")
        await asyncio.sleep(thinking)

        # Thử tìm element trong UI tree
        xml = await self.screen_reader.dump_ui(self.device)
        if xml:
            elem = self.screen_reader.find_any_element(xml, search_texts)
            if elem:
                log.info(f"[Phone:{self.device}] Dynamic tap '{description}' tại ({elem['cx']},{elem['cy']})")
                await self.xw.device_click(self.device, elem["cx"], elem["cy"])
                await self._delay()
                return True

        # Fallback: dùng bbox hardcoded
        x_min, x_max, y_min, y_max = fallback_bbox
        log.info(f"[Phone:{self.device}] Fallback bbox tap '{description}' ({x_min}-{x_max}%, {y_min}-{y_max}%)")
        await self._tap_bbox_pct(x_min, x_max, y_min, y_max, description)
        return False

    async def _tap_element_with_scroll_search(
        self,
        search_texts: list,
        description: str = "",
        max_scrolls: int = 3,
    ) -> bool:
        """
        Tìm element theo text trên UI hiện tại, nếu chưa thấy thì cuộn từng nhịp ngắn rồi tìm lại.
        Fail-safe: không click bbox cứng nếu chưa tìm thấy text thật, để tránh click sai flow.
        """
        for attempt in range(max_scrolls + 1):
            xml = await self.screen_reader.dump_ui(self.device)
            if xml:
                elem = self.screen_reader.find_any_element(xml, search_texts)
                if elem:
                    log.info(
                        f"[Phone:{self.device}] Tìm thấy '{description or search_texts[0]}' sau {attempt} lần cuộn tại "
                        f"({elem['cx']},{elem['cy']})"
                    )
                    await self.xw.device_click(self.device, elem["cx"], elem["cy"])
                    await self._delay()
                    return True

            if attempt < max_scrolls:
                log.info(
                    f"[Phone:{self.device}] Chưa thấy '{description or search_texts[0]}', cuộn thêm 1 nhịp để tìm lại "
                    f"(attempt {attempt + 1}/{max_scrolls})"
                )
                await self._scroll_down(1)
                await self._delay(0.8, 1.5)

        log.error(f"[Phone:{self.device}] Không tìm thấy '{description or search_texts[0]}' sau {max_scrolls} lần cuộn")
        return False

    async def _tap_best_element_with_scroll_search(
        self,
        description: str = "",
        max_scrolls: int = 3,
        texts: list[str] = None,
        resource_ids: list[str] = None,
        classes: list[str] = None,
        clickable: Optional[bool] = True,
        focusable: Optional[bool] = None,
        preferred_region: tuple[float, float, float, float] = None,
        partial: bool = True,
    ) -> bool:
        """
        Tìm node tốt nhất bằng scoring, cuộn từng nhịp ngắn nếu chưa thấy.
        """
        for attempt in range(max_scrolls + 1):
            xml = await self.screen_reader.dump_ui(self.device)
            if xml:
                elem = self.screen_reader.find_best_element(
                    xml,
                    texts=texts,
                    resource_ids=resource_ids,
                    classes=classes,
                    clickable=clickable,
                    focusable=focusable,
                    preferred_region=preferred_region,
                    partial=partial,
                )
                if elem:
                    log.info(
                        f"[Phone:{self.device}] Tìm thấy '{description or (texts or ['element'])[0]}' theo scoring "
                        f"sau {attempt} lần cuộn tại ({elem['cx']},{elem['cy']}) score={elem.get('score')}"
                    )
                    await self.xw.device_click(self.device, elem["cx"], elem["cy"])
                    await self._delay()
                    return True

            if attempt < max_scrolls:
                log.info(
                    f"[Phone:{self.device}] Chưa thấy '{description or (texts or ['element'])[0]}', cuộn thêm 1 nhịp "
                    f"(attempt {attempt + 1}/{max_scrolls})"
                )
                await self._scroll_down(1)
                await self._delay(0.8, 1.5)

        log.error(f"[Phone:{self.device}] Không tìm thấy '{description or (texts or ['element'])[0]}' sau {max_scrolls} lần cuộn")
        return False

    async def _tap_request_invitation_cta(self) -> tuple[bool, str]:
        """
        Chỉ nhắm đúng CTA vàng `招待をリクエストする` trên product page.
        Tránh click nhầm vào link/info block có text gần giống.
        """
        for attempt in range(4):
            xml = await self.screen_reader.dump_ui(self.device)
            elem = self._find_request_invitation_candidate(xml or "")
            if elem:
                log.info(
                    f"[Phone:{self.device}] CTA candidate tốt nhất tại ({elem['cx']},{elem['cy']}) "
                    f"score={elem.get('score')} width_pct={elem.get('width_pct')} y_pct={elem.get('y_pct')} "
                    f"text='{elem.get('visible_text', '')[:40]}'"
                )
                await self.xw.device_click(self.device, elem["cx"], elem["cy"])
                await self._delay()
                return True, "text_candidate"

            anchor = self._find_invitation_anchor(xml or "")
            if anchor:
                anchor_button = self._find_cta_below_anchor(xml or "", anchor)
                if anchor_button:
                    log.info(
                        f"[Phone:{self.device}] CTA dưới anchor tại ({anchor_button['cx']},{anchor_button['cy']}) "
                        f"score={anchor_button.get('score')} y_pct={anchor_button.get('y_pct')} "
                        f"width_pct={anchor_button.get('width_pct')}"
                    )
                    await self.xw.device_click(self.device, anchor_button["cx"], anchor_button["cy"])
                    await self._delay()
                    return True, "anchor_button_candidate"

                log.warning(
                    f"[Phone:{self.device}] Đã thấy invitation anchor '{anchor.get('visible_text', '')[:40]}' "
                    "nhưng chưa có bounds CTA đáng tin; fallback tap theo anchor, không scroll tiếp"
                )
                await self._tap_request_invitation_from_anchor(anchor)
                return True, "anchor_fallback"

            if attempt < 3:
                log.info(
                    f"[Phone:{self.device}] Chưa tìm được CTA vàng hợp lệ, cuộn thêm 1 nhịp "
                    f"(attempt {attempt + 1}/3)"
                )
                await self._scroll_down(1)
                await self._delay(0.8, 1.5)

        log.error(f"[Phone:{self.device}] Không tìm được CTA vàng '招待をリクエストする' hợp lệ")
        return False, "not_found"

    async def _tap_request_invitation_from_anchor(self, anchor: dict) -> None:
        """
        Fallback có kiểm soát: tap vào vùng nút vàng nằm bên dưới invitation anchor.
        """
        screen_w, screen_h = await self.get_device_resolution()
        x_pct = 50.0
        # Nút vàng thường nằm ngay dưới đoạn mô tả invitation, dùng offset vừa phải theo anchor.
        target_y_px = min(screen_h - 80, anchor["y2"] + int(screen_h * 0.12))
        y_pct = (target_y_px / max(1, screen_h)) * 100.0
        log.info(
            f"[Phone:{self.device}] Fallback anchor-based CTA tap dưới anchor tại y_pct={y_pct:.2f} "
            f"(anchor_y2={anchor['y2']})"
        )
        await self._tap_bbox_pct(22, 78, max(0.0, y_pct - 3.5), min(100.0, y_pct + 3.5), "Fallback CTA theo anchor")

    def _find_invitation_anchor(self, xml: str) -> Optional[dict]:
        """
        Tìm anchor text của khối invitation tiếng Nhật ngay phía trên nút vàng.
        """
        nodes = self.screen_reader._parse_nodes(xml)
        if not nodes:
            return None
        screen_h = max(node["y2"] for node in nodes)

        anchors = []
        anchor_texts = [
            "招待された方のみご購入いただけます",
            "本商品は招待販売としており",
        ]
        for node in nodes:
            visible_text = ((node.get("text") or "").strip() or (node.get("content_desc") or "").strip())
            if not visible_text:
                continue
            if not any(anchor_text in visible_text for anchor_text in anchor_texts):
                continue

            y_pct = (node["cy"] / max(1, screen_h)) * 100.0
            score = 100.0
            if 35.0 <= y_pct <= 70.0:
                score += 25.0
            if node["width"] >= 400:
                score += 10.0
            anchors.append({
                **node,
                "visible_text": visible_text,
                "score": score,
            })

        if not anchors:
            return None
        anchors.sort(key=lambda item: item["score"], reverse=True)
        best = anchors[0]
        log.info(
            f"[Phone:{self.device}] Invitation anchor: ({best['cx']},{best['cy']}) "
            f"score={best['score']} text='{best['visible_text'][:40]}'"
        )
        return best

    def _find_cta_below_anchor(self, xml: str, anchor: dict) -> Optional[dict]:
        """
        Tìm node clickable lớn nhất nằm ngay dưới invitation anchor.
        Dùng khi text của nút vàng không lộ rõ trong XML nhưng bounds/button vẫn có.
        """
        nodes = self.screen_reader._parse_nodes(xml)
        if not nodes:
            return None
        screen_w = max(node["x2"] for node in nodes)
        screen_h = max(node["y2"] for node in nodes)

        candidates = []
        for node in nodes:
            if not node["enabled"] or not node["clickable"]:
                continue

            x_pct = (node["cx"] / max(1, screen_w)) * 100.0
            y_pct = (node["cy"] / max(1, screen_h)) * 100.0
            width_pct = (node["width"] / max(1, screen_w)) * 100.0
            height_pct = (node["height"] / max(1, screen_h)) * 100.0

            if node["y1"] <= anchor["y2"]:
                continue
            if node["y1"] - anchor["y2"] > int(screen_h * 0.22):
                continue
            if not (20.0 <= x_pct <= 80.0):
                continue
            if width_pct < 45.0:
                continue
            if not (2.0 <= height_pct <= 10.0):
                continue

            score = 100.0
            if 78.0 <= width_pct <= 96.0:
                score += 35.0
            elif width_pct >= 60.0:
                score += 20.0
            if 78.0 <= y_pct <= 92.0:
                score += 30.0
            elif 70.0 <= y_pct <= 95.0:
                score += 15.0
            distance = node["y1"] - anchor["y2"]
            score += max(0.0, 25.0 - (distance / max(1, screen_h)) * 100.0)
            if "button" in node["class"].lower():
                score += 20.0

            candidates.append({
                **node,
                "score": round(score, 2),
                "x_pct": round(x_pct, 2),
                "y_pct": round(y_pct, 2),
                "width_pct": round(width_pct, 2),
                "height_pct": round(height_pct, 2),
            })

        if not candidates:
            return None
        candidates.sort(key=lambda item: item["score"], reverse=True)
        preview = [
            f"({c['cx']},{c['cy']}) score={c['score']} y={c['y_pct']} width={c['width_pct']} class={c['class']}"
            for c in candidates[:3]
        ]
        log.info(f"[Phone:{self.device}] CTA dưới anchor candidates: {' | '.join(preview)}")
        best = candidates[0]
        return best if best["score"] >= 120.0 else None

    def _find_request_invitation_candidate(self, xml: str) -> Optional[dict]:
        """
        Chọn node giống nút vàng CTA nhất dựa trên text + hình học màn hình.
        Mục tiêu là loại các node text trùng nhưng nằm ở vùng info/footer.
        """
        nodes = self.screen_reader._parse_nodes(xml)
        if not nodes:
            return None

        screen_w = max(node["x2"] for node in nodes)
        screen_h = max(node["y2"] for node in nodes)
        targets = ["招待をリクエストする", "招待をリクエスト", "Request Invitation"]
        button_like_classes = {
            "android.widget.button",
            "android.widget.textview",
            "android.view.view",
        }

        candidates = []
        for node in nodes:
            primary_text = (node.get("text") or "").strip()
            secondary_text = (node.get("content_desc") or "").strip()
            visible_text = primary_text or secondary_text
            if not visible_text:
                continue

            visible_text_lower = visible_text.lower()
            # Nếu node đang hiện text riêng của nó là notice/help thì loại.
            if any(noise in visible_text_lower for noise in ["notice to customers", "help", "ヘルプ"]):
                continue
            # Chỉ dùng content-desc fallback khi text trống. Nếu text đang là thứ khác thì không tin content-desc.
            if primary_text:
                if not any(target.lower() in primary_text.lower() for target in targets):
                    continue
            else:
                if not any(target.lower() in secondary_text.lower() for target in targets):
                    continue

            x_pct = (node["cx"] / max(1, screen_w)) * 100.0
            y_pct = (node["cy"] / max(1, screen_h)) * 100.0
            width_pct = (node["width"] / max(1, screen_w)) * 100.0
            height_pct = (node["height"] / max(1, screen_h)) * 100.0

            score = 0.0
            if visible_text == "招待をリクエストする":
                score += 140.0
            elif visible_text == "招待をリクエスト":
                score += 110.0
            elif visible_text_lower == "request invitation":
                score += 100.0
            else:
                score += 75.0

            if node["clickable"]:
                score += 25.0
            if node["enabled"]:
                score += 10.0
            if node["class"].lower() in button_like_classes:
                score += 12.0

            if 55.0 <= y_pct <= 80.0:
                score += 35.0
            elif 50.0 <= y_pct <= 86.0:
                score += 10.0
            else:
                score -= 60.0

            if width_pct >= 65.0:
                score += 40.0
            elif width_pct >= 50.0:
                score += 25.0
            elif width_pct >= 35.0:
                score += 5.0
            else:
                score -= 35.0

            if 2.0 <= height_pct <= 8.0:
                score += 12.0
            elif height_pct > 12.0:
                score -= 10.0

            if 15.0 <= x_pct <= 85.0:
                score += 10.0

            candidate = {
                **node,
                "visible_text": visible_text,
                "score": round(score, 2),
                "x_pct": round(x_pct, 2),
                "y_pct": round(y_pct, 2),
                "width_pct": round(width_pct, 2),
                "height_pct": round(height_pct, 2),
            }
            candidates.append(candidate)

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["score"], reverse=True)
        top_preview = [
            f"({c['cx']},{c['cy']}) score={c['score']} y={c['y_pct']} width={c['width_pct']} text={c.get('visible_text','')[:30]}"
            for c in candidates[:3]
        ]
        log.info(f"[Phone:{self.device}] CTA candidates: {' | '.join(top_preview)}")
        best = candidates[0]
        return best if best["score"] >= 120.0 else None

    async def _type_into_labeled_field(
        self,
        text: str,
        label_texts: list[str],
        description: str = "",
        is_password: bool = False,
        fallback_bbox: tuple[float, float, float, float] = None,
    ) -> bool:
        """
        Tìm ô input gần label trong UI XML, focus và nhập text. Có fallback bbox nếu cần.
        """
        xml = await self.screen_reader.dump_ui(self.device)
        field = self.screen_reader.find_input_near_label(xml or "", label_texts) if xml else None
        if field:
            log.info(
                f"[Phone:{self.device}] Tìm thấy field '{description or label_texts[0]}' gần label "
                f"'{field.get('anchor_text', '')}' tại ({field['cx']},{field['cy']}) score={field.get('score')}"
            )
            x_pct, y_pct = await self._device_point_to_percent(field["cx"], field["cy"])
            return await self._type_and_verify(
                text,
                max(0.0, x_pct - 3.0), min(100.0, x_pct + 3.0),
                max(0.0, y_pct - 2.0), min(100.0, y_pct + 2.0),
                description=description or label_texts[0],
                is_password=is_password,
            )

        if fallback_bbox:
            log.warning(
                f"[Phone:{self.device}] Không tìm thấy field theo label '{description or label_texts[0]}', "
                "fallback sang bbox cũ"
            )
            return await self._type_and_verify(
                text,
                fallback_bbox[0], fallback_bbox[1], fallback_bbox[2], fallback_bbox[3],
                description=description or label_texts[0],
                is_password=is_password,
            )

        log.error(f"[Phone:{self.device}] Không tìm thấy field '{description or label_texts[0]}'")
        return False

    async def _verify_post_request_invitation_state(self) -> tuple[bool, str, Optional[str]]:
        """
        Sau khi click CTA, xác minh bot đã sang sign-in/create-account flow thật.
        """
        expected_markers = [
            "メールアドレス",
            "Email",
            "sign in",
            "サインイン",
            "アカウントを作成",
            "Create account",
            "パスワード",
            "Password",
        ]
        xml = await self._wait_for_state(
            expected_markers,
            timeout=6.0,
            step_name="step2_wait_post_cta_state",
        )
        if not xml:
            xml = await self.screen_reader.dump_ui(self.device)

        if xml:
            xml_lower = xml.lower()
            nodes = self.screen_reader._parse_nodes(xml)
            input_nodes = [node for node in nodes if "edittext" in node["class"].lower()]
            has_email_marker = any(marker.lower() in xml_lower for marker in ["メールアドレス", "email", "サインイン", "sign in"])
            has_account_create_marker = any(marker.lower() in xml_lower for marker in ["アカウントを作成", "create account"])
            has_password_marker = any(marker.lower() in xml_lower for marker in ["パスワード", "password"])

            if has_email_marker and input_nodes:
                return True, f"Đã chuyển sang sign-in flow với {len(input_nodes)} input field(s)", xml
            if has_account_create_marker and input_nodes:
                return True, f"Đã chuyển sang create-account flow với {len(input_nodes)} input field(s)", xml
            if has_password_marker and len(input_nodes) >= 2:
                return True, f"Đã chuyển sang password/account flow với {len(input_nodes)} input field(s)", xml

            if any(marker in xml_lower for marker in [
                "amazonポイント",
                "ポイント",
                "ヘルプ",
                "詳細はこちら",
                "マイポイント",
                "pokemon",
                "pikachu",
            ]):
                return False, "Sau click CTA bot đã sang trang info/help khác, không phải sign-in flow", xml

        return False, "Không xác nhận được form/account flow thật sau khi bấm CTA", xml

    async def _open_request_invitation_flow(self) -> tuple[bool, str, Optional[str]]:
        """
        Cố gắng mở sign-in/create-account flow từ CTA invitation.
        Nếu click nhầm thì back lại và thử lại chiến lược tiếp theo.
        """
        last_reason = "Không mở được request invitation flow"
        for attempt in range(3):
            before_xml = await self.screen_reader.dump_ui(self.device)
            tapped, tap_mode = await self._tap_request_invitation_cta()
            if not tapped:
                return False, "Không tìm thấy nút Request Invitation trên trang sản phẩm", before_xml

            verify_ok, verify_reason, verify_xml = await self._verify_post_request_invitation_state()
            log.info(
                f"[Phone:{self.device}] Post-CTA verify (attempt {attempt + 1}/3, mode={tap_mode}): {verify_reason}"
            )
            if verify_ok:
                return True, verify_reason, verify_xml

            last_reason = verify_reason
            await self._screenshot_step(f"step2_wrong_click_attempt_{attempt + 1}")
            log.warning(
                f"[Phone:{self.device}] Click CTA có thể sai nhánh (mode={tap_mode}), back lại product page để thử lại"
            )
            await self.xw.press_back(self.device)
            await self._delay(0.8, 1.3)
            await self.screen_reader.wait_for_ui_change(self.device, verify_xml or before_xml, timeout=5.0, poll_interval=0.5)

        return False, last_reason, None

    async def _device_point_to_percent(self, x: int, y: int) -> tuple[float, float]:
        """Chuyển tọa độ pixel thật thành % màn hình để tái dùng helper hiện có."""
        w, h = await self.get_device_resolution()
        if w <= 0 or h <= 0:
            return 50.0, 50.0
        return (x / w) * 100.0, (y / h) * 100.0

    async def _type_and_verify(
        self,
        text: str,
        x_min_pct: float, x_max_pct: float, y_min_pct: float, y_max_pct: float,
        description: str = "",
        is_password: bool = False,
        max_retry: int = 2,
    ) -> bool:
        """
        Issue #5: Gõ text vào field rồi verify nội dung qua uiautomator dump.
        Skip verify cho password field (uiautomator không đọc được password).

        Return: True nếu verify thành công (hoặc is_password=True), False nếu mismatch.
        """
        for attempt in range(max_retry):
            await self._type_into_field_human(text, x_min_pct, x_max_pct, y_min_pct, y_max_pct, description)

            if is_password:
                # Không verify được password field
                return True

            # Đọc lại nội dung field để so sánh
            await asyncio.sleep(0.5)
            xml = await self.screen_reader.dump_ui(self.device)
            if xml:
                current = self.screen_reader.get_focused_field_text(xml)
                if current is not None and text.lower() in current.lower():
                    log.info(f"[Phone:{self.device}] Verify '{description}' OK: '{current[:30]}'")
                    return True
                elif current is not None:
                    log.warning(f"[Phone:{self.device}] Verify '{description}' MISMATCH: expected '{text[:20]}' got '{current[:20]}' — retry {attempt+1}/{max_retry}")
                    await self._screenshot_step(f"verify_fail_{description[:20]}")
                    continue
                else:
                    log.warning(f"[Phone:{self.device}] Verify '{description}': không đọc được field text, skip verify")
                    return True
            else:
                log.warning(f"[Phone:{self.device}] dump_ui thất bại khi verify '{description}'")
                return True  # Không block nếu uiautomator fail

        log.error(f"[Phone:{self.device}] _type_and_verify '{description}' thất bại sau {max_retry} lần")
        return False

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
            log.warning(
                f"[Phone:{self.device}] no_proxy_experiment=True -> chuyển sang luồng thực nghiệm register_no_proxy(), "
                "không dùng luồng mở product_url Amazon chuẩn"
            )
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
            if "com.android.chrome" in installed:
                chosen_browser = "com.android.chrome"
                log.info(f"[Phone:{self.device}] Khóa browser ổn định cho flow Amazon: {chosen_browser}")
            elif installed:
                chosen_browser = installed[0]
                log.warning(
                    f"[Phone:{self.device}] Không có Chrome, fallback sang browser đầu tiên đã cài: {chosen_browser}"
                )
            else:
                log.warning(f"[Phone:{self.device}] Không tìm thấy trình duyệt nào hỗ trợ, dùng mặc định Chrome")
                chosen_browser = "com.android.chrome"

            # ── STEP 1: Xóa Sạch Dấu Vết (Clear Data) ──────────────────────────
            log.info(f"[Phone:{self.device}] Step 1 – Xóa sạch dữ liệu & Chuẩn bị trình duyệt...")
            await self.xw.clear_browser_data(self.device, chosen_browser)
            await asyncio.sleep(1.0)
            await self.xw.kill_browser(self.device, chosen_browser)
            await asyncio.sleep(1.0)

            is_valid_product_url, validate_msg, expected_host, expected_asin = self._validate_product_url()
            if not is_valid_product_url:
                result["note"] = validate_msg
                return result

            # Mở trình duyệt với URL sản phẩm Amazon, có verify + retry nếu phát hiện sai trang.
            log.info(f"[Phone:{self.device}] Product URL gốc: {self.product_url}")
            log.info(f"[Phone:{self.device}] Expected host: {expected_host}, expected ASIN: {expected_asin}")
            page_verified = False
            for open_attempt in range(2):
                unique_url = self._randomize_product_url(self.product_url)
                log.info(f"[Phone:{self.device}] URL sau randomize: {unique_url}")
                log.info(
                    f"[Phone:{self.device}] Mở trình duyệt {chosen_browser} (attempt {open_attempt + 1}/2) "
                    f"→ {unique_url[:120]}..."
                )
                open_ok = await self.xw.open_url(self.device, unique_url, chosen_browser)
                log.info(f"[Phone:{self.device}] open_url result: {'OK' if open_ok else 'FAIL'}")
                await self._dismiss_chrome_first_run_if_needed(chosen_browser, unique_url)
                await self._recover_chrome_loading_if_needed(chosen_browser, unique_url)

                page_verified, verify_reason, verify_xml = await self._verify_expected_product_page(
                    expected_host=expected_host,
                    expected_asin=expected_asin,
                    timeout=10.0,
                )
                log.info(f"[Phone:{self.device}] Product page verify: {verify_reason}")
                if page_verified:
                    break

                await self._screenshot_step(f"wrong_page_attempt_{open_attempt + 1}")
                if open_attempt == 0:
                    log.warning(f"[Phone:{self.device}] Sai trang hoặc fingerprint yếu, thử mở lại link gốc thêm 1 lần...")
                    await self.xw.kill_browser(self.device, chosen_browser)
                    await asyncio.sleep(1.0)

            if not page_verified:
                result["note"] = "Wrong page detected hoặc không xác nhận được product page Amazon"
                await self._screenshot_step("step1_FAILED_wrong_page_detected")
                return result

            await self._screenshot_step("step1_product_page")

            # ── STEP 2: Click nút Request Invitation ──────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 2 – Tìm đúng CTA vàng '招待をリクエストする' trên product page...")
            login_ok, login_reason, login_xml = await self._open_request_invitation_flow()
            if not login_ok:
                result["note"] = login_reason
                await self._screenshot_step("step2_FAILED_login_form_not_found")
                return result
            await self._screenshot_step("step2_after_request_invitation")

            # ── STEP 3: Form Login – Nhập Email ──────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 3 – Nhập email vào form đăng nhập...")
            await self._screenshot_step("step3a_login_form")
            email_ok = await self._type_into_labeled_field(
                row["email"],
                ["メールアドレス", "Email address", "Email", "メール"],
                description="Ô Email",
                fallback_bbox=(40, 60, 38, 42),
            )
            if not email_ok:
                result["note"] = "Không nhập được email vào form đăng nhập"
                await self._screenshot_step("step3_FAILED_email_input")
                return result

            continue_ok = await self._tap_best_element_with_scroll_search(
                texts=["続行", "Continue", "次へ", "サインイン"],
                description="Nút Continue",
                max_scrolls=1,
                clickable=True,
                preferred_region=(30, 70, 45, 80),
            )
            if not continue_ok:
                result["note"] = "Không tìm thấy nút Continue sau khi nhập email"
                await self._screenshot_step("step3_FAILED_continue_not_found")
                return result

            # Đợi màn hình tiếp theo (Create Account hoặc password form)
            post_continue_xml = await self._wait_for_state(
                ["アカウントを作成", "Create account", "パスワード", "Password"],
                timeout=8.0, step_name="step3_wait_after_continue"
            )
            if not post_continue_xml:
                result["note"] = "Không xác nhận được màn hình sau bước Continue"
                await self._screenshot_step("step3_FAILED_post_continue_state")
                return result
            await self._screenshot_step("step3b_after_continue")

            # ── STEP 4: Tạo tài khoản ──────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 4 – Click tạo tài khoản mới...")
            create_ok = await self._tap_best_element_with_scroll_search(
                texts=["アカウントを作成", "Create account", "新規登録"],
                description="Nút Create Account",
                max_scrolls=1,
                clickable=True,
                preferred_region=(25, 75, 35, 85),
            )
            if not create_ok:
                result["note"] = "Không tìm thấy nút Create Account"
                await self._screenshot_step("step4_FAILED_create_account_not_found")
                return result

            # Đợi form đăng ký (có ô Tên)
            register_form_xml = await self._wait_for_state(
                ["お名前", "氏名", "名前", "Your name", "First name"],
                timeout=8.0, step_name="step4_wait_register_form"
            )
            if not register_form_xml:
                result["note"] = "Không xác nhận được form đăng ký sau khi bấm Create Account"
                await self._screenshot_step("step4_FAILED_register_form_not_found")
                return result
            await self._screenshot_step("step4_create_account_form")

            # ── STEP 5: Điền form đăng ký ─────────────────────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] Step 5 – Điền form đăng ký tài khoản...")
            name_ok = await self._type_into_labeled_field(
                row["name"],
                ["お名前", "氏名", "名前", "Your name", "First name"],
                description="Ô Tên (氏名)",
                fallback_bbox=(40, 60, 30, 34),
            )
            if not name_ok:
                result["note"] = "Không nhập được tên vào form đăng ký"
                await self._screenshot_step("step5_FAILED_name_input")
                return result
            await self._delay(0.5, 1.0)

            password_ok = await self._type_into_labeled_field(
                row["password"],
                ["パスワード", "Password"],
                description="Ô Mật khẩu",
                is_password=True,
                fallback_bbox=(40, 60, 46, 50),
            )
            if not password_ok:
                result["note"] = "Không nhập được mật khẩu"
                await self._screenshot_step("step5_FAILED_password_input")
                return result
            await self._delay(0.5, 1.0)

            confirm_ok = await self._type_into_labeled_field(
                row["password"],
                ["パスワードを再入力", "Confirm password", "パスワード再入力", "Re-enter password"],
                description="Ô Xác nhận mật khẩu",
                is_password=True,
                fallback_bbox=(40, 60, 56, 60),
            )
            if not confirm_ok:
                result["note"] = "Không nhập được ô xác nhận mật khẩu"
                await self._screenshot_step("step5_FAILED_confirm_password_input")
                return result
            await self._delay(0.5, 1.0)
            await self._screenshot_step("step5_form_filled")

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

            # Đợi màn hình OTP xuất hiện
            otp_xml = await self._wait_for_state(
                ["認証コード", "verification code", "OTP", "コードを入力", "メール"],
                timeout=10.0, step_name="step6_wait_otp_screen"
            )
            if not otp_xml:
                result["note"] = "Không xác nhận được màn hình nhập OTP sau submit"
                await self._screenshot_step("step6_FAILED_otp_screen_not_found")
                return result
            await self._screenshot_step("step6_after_submit")

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
                await self._screenshot_step("step7_FAILED_no_otp")
                result["note"] = f"Không nhận được OTP (nguồn: {self.otp_source})"
                return result

            log.info(f"[Phone:{self.device}] OTP nhận được: {otp}")
            await self._screenshot_step("step7a_otp_form")

            # Điền OTP + verify
            otp_ok = await self._type_into_labeled_field(
                otp,
                ["認証コード", "verification code", "OTP", "コードを入力"],
                description="Ô OTP",
                is_password=False,
                fallback_bbox=(30, 70, 40, 44),
            )
            if not otp_ok:
                result["note"] = "Không nhập được OTP vào form xác minh"
                await self._screenshot_step("step7_FAILED_otp_input")
                return result
            await self._screenshot_step("step7b_otp_typed")

            # Dynamic tap nút Xác minh OTP (fallback: 40%-60%, 58%-62%)
            await self._tap_element(
                ["確認", "Verify", "Submit", "Continue", "次へ"],
                fallback_bbox=(40, 60, 58, 62),
                description="Nút Xác minh OTP",
            )

            # Đợi màn hình thành công (trang sản phẩm hoặc confirmation)
            await self._wait_for_state(
                ["ありがとう", "Thank you", "完了", "Complete", "確認", "アカウント"],
                timeout=12.0, step_name="step7c_wait_success"
            )

            # ── STEP 8: Kiểm tra kết quả ─────────────────────────────
            log.info(f"[Phone:{self.device}] Step 8 – Kiểm tra kết quả đăng ký...")
            await self._screenshot_step("step8_final_result")

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
            await self._screenshot_step("step1_browser_opened")

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

            # Đợi trang load — chờ text "アカウントを作成" (Create Account) xuất hiện
            # Fallback: sleep cứng 5s nếu uiautomator không thấy text
            page_xml = await self._wait_for_state(
                ["アカウントを作成", "Create account", "Register", "招待"],
                timeout=10.0, step_name="step2_wait_page"
            )
            if not page_xml:
                await asyncio.sleep(random.uniform(3.0, 4.5))
            await self._screenshot_step("step2_page_loaded")

            # ── STEP 3: Click tạo tài khoản & nhập Email ───────────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] (No Proxy) Step 3 – Click Create Account & Nhập Email...")

            # Dynamic tap Create Account (fallback: 37%-55%, 57%-62%)
            await self._tap_element(
                ["アカウントを作成", "Create account", "新規登録"],
                fallback_bbox=(37, 55, 57, 62),
                description="Nút Create Account",
            )

            # Đợi form email xuất hiện
            email_form_xml = await self._wait_for_state(
                ["メールアドレス", "Email address", "メール"],
                timeout=8.0, step_name="step3a_wait_email_form"
            )
            if not email_form_xml:
                await asyncio.sleep(2.0)
            await self._screenshot_step("step3a_after_create_account")

            # Nhập Email + verify
            await self._type_and_verify(row["email"], 40, 60, 38, 42, "Ô Email", is_password=False)
            await asyncio.sleep(1.0)
            await self._screenshot_step("step3b_email_typed")

            # Dynamic tap Verify Email (fallback: 44%-48%, 69%-71%)
            sent_otp_time = time.time()
            await self._tap_element(
                ["メールアドレスを確認", "Verify email", "メールを確認", "Continue"],
                fallback_bbox=(44, 48, 69, 71),
                description="Nút Verify Email (Gửi OTP)",
            )

            # Đợi màn hình OTP (có text "認証コード" hoặc "verification code")
            otp_screen_xml = await self._wait_for_state(
                ["認証コード", "verification code", "OTP", "コードを入力"],
                timeout=10.0, step_name="step3c_wait_otp_screen"
            )
            if not otp_screen_xml:
                await asyncio.sleep(3.0)
            await self._screenshot_step("step3c_after_verify_email")

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
                await self._screenshot_step("step4_FAILED_no_otp")
                result["note"] = "Không nhận được OTP từ Gmail"
                return result

            log.info(f"[Phone:{self.device}] Đã tìm thấy mã OTP: {otp}")

            # ── STEP 5: Độ trễ suy nghĩ & Nhập OTP hoàn tất ──────────
            if self.should_stop:
                result["note"] = "Stopped by user"
                return result

            log.info(f"[Phone:{self.device}] (No Proxy) Step 5 – Độ trễ suy nghĩ & nhập OTP...")
            await self._screenshot_step("step5a_otp_form")

            # Độ trễ suy nghĩ (Thinking Time): dừng từ 1.5 đến 3.0 giây
            thinking = random.uniform(1.5, 3.0)
            log.info(f"[Phone:{self.device}] Dừng suy nghĩ: {thinking:.2f}s")
            await asyncio.sleep(thinking)

            # Nhập OTP + verify (OTP là số → có thể check được)
            await self._type_and_verify(otp, 30, 70, 40, 44, "Ô OTP", is_password=False)

            # Đợi tiếp 1.0 đến 1.8 giây sau khi gõ xong số cuối cùng
            post_typing = random.uniform(1.0, 1.8)
            log.info(f"[Phone:{self.device}] Chờ sau gõ: {post_typing:.2f}s")
            await asyncio.sleep(post_typing)
            await self._screenshot_step("step5b_otp_typed")

            # Dynamic tap nút Xác nhận cuối (fallback: 44%-48%, 77%-79%)
            await self._tap_element(
                ["アカウントを作成", "Create account", "確認", "Confirm", "Continue"],
                fallback_bbox=(44, 48, 77, 79),
                description="Nút Xác nhận tài khoản cuối",
            )

            # Chờ trang hoàn tất tải và chụp màn hình kết quả
            await asyncio.sleep(5.0)
            await self._screenshot_step("step5c_final_result")

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
