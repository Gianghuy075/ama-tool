import os
import sys

# Fix Playwright browser path and external config importing when running inside PyInstaller
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)
        
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(local_app_data, "ms-playwright")
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

import asyncio
import time
import random
import string
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import pandas as pd

# Playwright imports are lazy — only loaded when browser mode is used
# This allows phone-only exe to run without Playwright installed
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    async_playwright = None
    PlaywrightTimeout = Exception  # Fallback

from src.gmail_otp import GmailOTPReader
from src.excel_handler import ExcelHandler
from src.config import CONFIG
from src.captcha_helper import inject_mock_captcha

# Reconfigure stdout/stderr to UTF-8 on Windows if needed to prevent UnicodeEncodeError
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass

# Setup logs directory
os.makedirs("logs", exist_ok=True)

# Configure logging to console and to logs/bot.log
log_handlers = [logging.FileHandler("logs/bot.log", encoding="utf-8")]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=log_handlers
)
log = logging.getLogger(__name__)



class RegistrationBot:
    def __init__(self, product_url: str = ""):
        self.base_url = CONFIG["base_url"]
        self.product_url = product_url or CONFIG.get("product_url", "")
        self.gmail = GmailOTPReader(
            email=CONFIG["gmail_address"],
            password=CONFIG["gmail_app_password"],
            imap_server=CONFIG["imap_server"],
        )
        self.should_stop = False

    # ── Anti-detection Helpers ─────────────────────────────────────────

    def _generate_japanese_name(self) -> str:
        """Tạo tên tiếng Nhật ngẫu nhiên (Họ + Tên)."""
        surnames = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水"]
        first_names = ["翔", "蓮", "悠真", "湊", "大翔", "陽翔", "結菜", "咲良", "莉子", "芽依", "結愛", "陽葵", "紬", "凛", "葵", "さくら", "大輔", "健太", "拓海", "直樹"]
        return f"{random.choice(surnames)} {random.choice(first_names)}"

    def _generate_random_token(self, length: int = 20) -> str:
        """Tạo token tracking ngẫu nhiên giống format Amazon: uppercase + digits."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))

    def _randomize_product_url(self, base_url: str) -> str:
        """
        Tạo URL sản phẩm mới với tracking tokens ngẫu nhiên cho mỗi tài khoản.
        Giúp mỗi session trông như đến từ nguồn khác nhau.
        """
        try:
            parsed = urlparse(base_url)
            # Chỉ giữ path (chứa ASIN), loại bỏ tất cả tracking params cũ
            # Tạo bộ params mới với token ngẫu nhiên
            new_token = self._generate_random_token(20)
            ref_prefix = "cm_sw_r_cp_ud_dp_"
            
            new_params = {
                'ref': f"{ref_prefix}{new_token}",
                'ref_': f"{ref_prefix}{new_token}",
                'social_share': f"{ref_prefix}{self._generate_random_token(20)}",
            }
            
            # Thỉnh thoảng thêm fbclid giả để giống traffic từ Facebook
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

    async def _human_delay(self, min_sec: float = 0.5, max_sec: float = 2.0):
        """Tạo delay ngẫu nhiên giống hành vi người thật."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def _human_type(self, page, selector_or_element, text: str):
        """
        Gõ từng ký tự với tốc độ ngẫu nhiên giống người thật.
        Hỗ trợ cả selector (str) và element handle.
        """
        if isinstance(selector_or_element, str):
            element = await page.query_selector(selector_or_element)
        else:
            element = selector_or_element
        
        if not element:
            return
        
        # Click vào ô input trước
        await element.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Clear nội dung cũ nếu có
        await element.fill('')
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Gõ từng ký tự
        for char in text:
            await element.type(char, delay=random.randint(30, 120))
            # Thỉnh thoảng dừng lâu hơn (giống người suy nghĩ)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.3, 0.8))

    async def _human_scroll(self, page, direction: str = 'down', amount: int = None):
        """Cuộn trang giống người thật trước khi tương tác."""
        if amount is None:
            amount = random.randint(100, 400)
        
        if direction == 'down':
            await page.evaluate(f'window.scrollBy(0, {amount})')
        else:
            await page.evaluate(f'window.scrollBy(0, -{amount})')
        
        await asyncio.sleep(random.uniform(0.3, 0.8))

    async def _random_mouse_move(self, page):
        """Di chuyển chuột ngẫu nhiên trên trang để giả lập hành vi thật."""
        try:
            x = random.randint(100, 800)
            y = random.randint(100, 500)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass

    async def register_one(self, page, row: dict) -> dict:
        """Run the Amazon JP registration flow for one user."""
        if not row.get("name") or not str(row["name"]).strip():
            row["name"] = self._generate_japanese_name()
            log.info(f"[{row['email']}] Tên trống, tự động sinh tên tiếng Nhật: {row['name']}")

        result = {
            "name": row["name"],
            "email": row["email"],
            "password": row.get("password", ""),
            "proxy": row.get("proxy", ""),
            "status": "FAILED",
            "note": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        try:
            # ── STEP 1: Mở trang sản phẩm Amazon JP ──────────────────
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 1 – Mở trang sản phẩm Amazon...")
            
            if not self.product_url:
                result["note"] = "Chưa cung cấp link sản phẩm Amazon (product_url)"
                return result

            # Randomize URL tracking tokens cho mỗi tài khoản (anti-detection)
            unique_url = self._randomize_product_url(self.product_url)
            log.info(f"[{row['email']}] URL đã randomize: {unique_url[:80]}...")

            await page.goto(unique_url, wait_until="domcontentloaded", timeout=30000)
            await self._human_delay(1.5, 3.0)
            
            # Giả lập hành vi người thật: cuộn trang, di chuột
            await self._random_mouse_move(page)
            await self._human_scroll(page, 'down')
            await self._human_delay(0.5, 1.5)
            
            log.info(f"[{row['email']}] Đã load trang sản phẩm: {page.url}")

            # ── STEP 2: Click nút "招待をリクエストする" (Request Invitation) ──
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 2 – Tìm và click nút Request Invitation...")

            # Tìm nút Request Invitation bằng nhiều selector khác nhau
            request_btn = None
            btn_selectors = [
                'input#buy-now-button',
                'input[name="submit.buy-now"]',
                '#invite-button',
                'a:has-text("招待をリクエストする")',
                'input[value*="招待"]',
                'span:has-text("招待をリクエストする")',
                'a:has-text("リクエスト")',
                '#sp-cc-accept',  # Cookie consent nếu có
            ]
            
            # Xử lý cookie consent popup trước nếu có
            try:
                cookie_btn = await page.query_selector('#sp-cc-accept')
                if cookie_btn:
                    await cookie_btn.click()
                    await asyncio.sleep(1)
                    log.info(f"[{row['email']}] Đã đóng cookie consent popup")
            except Exception:
                pass

            # Tìm nút Request Invitation
            for sel in btn_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        is_visible = await btn.is_visible()
                        if is_visible:
                            btn_text = await btn.inner_text() if not sel.startswith('input') else (await btn.get_attribute('value') or '')
                            if '招待' in btn_text or 'リクエスト' in btn_text or 'invite' in btn_text.lower():
                                request_btn = btn
                                log.info(f"[{row['email']}] Tìm thấy nút Request Invitation: {sel}")
                                break
                except Exception:
                    pass

            # Fallback: tìm bằng text content trên trang
            if not request_btn:
                try:
                    request_btn = await page.locator('text=招待をリクエストする').first.element_handle(timeout=5000)
                    log.info(f"[{row['email']}] Tìm thấy nút bằng text locator")
                except Exception:
                    pass
            
            # Fallback 2: tìm tất cả link/button có chữ 招待
            if not request_btn:
                try:
                    elements = await page.query_selector_all('a, button, input[type="submit"], span[role="button"]')
                    for el in elements:
                        try:
                            tag = await el.evaluate('el => el.tagName')
                            if tag == 'INPUT':
                                el_text = await el.get_attribute('value') or ''
                            else:
                                el_text = await el.inner_text()
                            if '招待' in el_text:
                                is_vis = await el.is_visible()
                                if is_vis:
                                    request_btn = el
                                    log.info(f"[{row['email']}] Tìm thấy nút bằng fullscan: '{el_text[:30]}'")
                                    break
                        except Exception:
                            pass
                except Exception:
                    pass

            if not request_btn:
                result["note"] = "Không tìm thấy nút 'Request Invitation' trên trang sản phẩm"
                return result

            await self._human_scroll(page, 'down', random.randint(200, 500))
            await self._human_delay(0.3, 0.8)
            await request_btn.click()
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await self._human_delay(1.5, 3.0)
            log.info(f"[{row['email']}] Đã click Request Invitation, URL hiện tại: {page.url}")

            # ── STEP 3: Trang Login Amazon – Nhập Email ───────────────
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 3 – Nhập email vào form đăng nhập Amazon...")

            # Chờ form login xuất hiện
            email_input = None
            email_selectors = [
                'input[name="email"]',
                'input[type="email"]',
                '#ap_email',
                'input[name="ap_email"]',
            ]
            for sel in email_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=8000)
                    email_input = await page.query_selector(sel)
                    if email_input:
                        log.info(f"[{row['email']}] Tìm thấy ô email: {sel}")
                        break
                except Exception:
                    pass

            if not email_input:
                result["note"] = "Không tìm thấy ô nhập email trên trang login Amazon"
                return result

            await self._human_delay(0.3, 0.8)
            await self._random_mouse_move(page)
            await self._human_type(page, email_input, row["email"])
            await self._human_delay(0.5, 1.2)

            # Click nút "次に進む" (Continue)
            continue_btn = None
            continue_selectors = [
                '#continue',
                'input#continue',
                'span#continue',
                'input[type="submit"]',
                'button[type="submit"]',
            ]
            for sel in continue_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        continue_btn = btn
                        log.info(f"[{row['email']}] Tìm thấy nút Continue: {sel}")
                        break
                except Exception:
                    pass

            if not continue_btn:
                result["note"] = "Không tìm thấy nút 'Continue' trên trang login"
                return result

            await self._human_delay(0.3, 0.6)
            await continue_btn.click()
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await self._human_delay(1.5, 3.0)
            log.info(f"[{row['email']}] Đã submit email, URL: {page.url}")

            # ── STEP 4: Kiểm tra – Email chưa đăng ký hay đã có tài khoản ──
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 4 – Kiểm tra trạng thái email...")

            page_content = await page.content()
            current_url = page.url

            # Trường hợp 1: Email chưa đăng ký – trang "Amazonを初めてご利用のようです"
            if 'claim' in current_url or '初めて' in page_content or 'claimType' in current_url:
                log.info(f"[{row['email']}] Email chưa đăng ký Amazon → Click tạo tài khoản mới")
                
                # Click nút "アカウントの作成に進む" (Proceed to create account)
                create_btn = None
                create_selectors = [
                    '#createAccountSubmit',
                    'a:has-text("アカウントの作成に進む")',
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'span:has-text("アカウントの作成")',
                ]
                for sel in create_selectors:
                    try:
                        btn = await page.query_selector(sel)
                        if btn and await btn.is_visible():
                            create_btn = btn
                            log.info(f"[{row['email']}] Tìm thấy nút Create Account: {sel}")
                            break
                    except Exception:
                        pass

                # Fallback: tìm bằng text
                if not create_btn:
                    try:
                        create_btn = await page.locator('text=アカウントの作成に進む').first.element_handle(timeout=5000)
                    except Exception:
                        pass

                if not create_btn:
                    # Thử click trực tiếp vào bất kỳ submit button nào
                    try:
                        create_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                    except Exception:
                        pass

                if create_btn:
                    await self._human_delay(0.5, 1.0)
                    await create_btn.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    await self._human_delay(1.5, 3.0)
                    log.info(f"[{row['email']}] Đã click tạo tài khoản, URL: {page.url}")
                else:
                    result["note"] = "Không tìm thấy nút 'Tạo tài khoản' trên trang xác nhận email mới"
                    return result

            # Trường hợp 2: Email đã có tài khoản – hiện form nhập password
            elif 'password' in current_url.lower() or await page.query_selector('#ap_password'):
                log.info(f"[{row['email']}] ⚠️ Email đã có tài khoản Amazon – đánh dấu FAILED")
                result["note"] = "Email đã có tài khoản Amazon (yêu cầu nhập mật khẩu)"
                return result

            # ── STEP 5: Điền form đăng ký tài khoản ──────────────────
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 5 – Điền thông tin đăng ký tài khoản...")

            await self._human_delay(1.0, 2.0)
            await self._random_mouse_move(page)

            # Điền Email (có thể đã được điền sẵn)
            try:
                reg_email = await page.query_selector('#ap_email, input[name="email"], input[type="email"]')
                if reg_email:
                    current_val = await reg_email.input_value()
                    if not current_val or current_val.strip() == '':
                        await self._human_type(page, reg_email, row["email"])
                        log.info(f"[{row['email']}] Đã điền email vào form đăng ký")
                    else:
                        log.info(f"[{row['email']}] Email đã được điền sẵn: {current_val}")
            except Exception as e:
                log.warning(f"[{row['email']}] Không thể điền email: {e}")

            await self._human_delay(0.3, 0.8)

            # Điền Tên (氏名)
            try:
                name_input = await page.query_selector('#ap_customer_name, input[name="customerName"], input[name="name"]')
                if name_input:
                    await self._human_type(page, name_input, row["name"])
                    log.info(f"[{row['email']}] Đã điền tên: {row['name']}")
                else:
                    log.warning(f"[{row['email']}] Không tìm thấy ô nhập tên")
            except Exception as e:
                log.warning(f"[{row['email']}] Không thể điền tên: {e}")

            await self._human_delay(0.3, 0.8)

            # Điền Mật khẩu
            try:
                pwd_input = await page.query_selector('#ap_password, input[name="password"]')
                if pwd_input:
                    await self._human_type(page, pwd_input, row["password"])
                    log.info(f"[{row['email']}] Đã điền mật khẩu")
                else:
                    log.warning(f"[{row['email']}] Không tìm thấy ô nhập mật khẩu")
            except Exception as e:
                log.warning(f"[{row['email']}] Không thể điền mật khẩu: {e}")

            await self._human_delay(0.3, 0.8)

            # Điền Xác nhận mật khẩu
            try:
                pwd_check = await page.query_selector('#ap_password_check, input[name="passwordCheck"]')
                if pwd_check:
                    await self._human_type(page, pwd_check, row["password"])
                    log.info(f"[{row['email']}] Đã điền xác nhận mật khẩu")
                else:
                    log.info(f"[{row['email']}] Không tìm thấy ô xác nhận mật khẩu (có thể không yêu cầu)")
            except Exception as e:
                log.warning(f"[{row['email']}] Không thể điền xác nhận mật khẩu: {e}")

            await self._human_delay(0.5, 1.2)

            # ── STEP 6: Submit form đăng ký ───────────────────────────
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 6 – Submit form đăng ký...")

            submit_btn = None
            submit_selectors = [
                '#continue',
                'input#continue',
                'input[type="submit"]',
                'button[type="submit"]',
                'span:has-text("次に進む")',
            ]
            for sel in submit_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        submit_btn = btn
                        log.info(f"[{row['email']}] Tìm thấy nút submit đăng ký: {sel}")
                        break
                except Exception:
                    pass

            if submit_btn:
                await self._human_delay(0.3, 0.8)
                await submit_btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                await self._human_delay(2.0, 4.0)
                log.info(f"[{row['email']}] Đã submit form đăng ký, URL: {page.url}")
            else:
                result["note"] = "Không tìm thấy nút Submit trên form đăng ký"
                return result

            # Kiểm tra lỗi trên trang sau khi submit
            error_msg = await self._check_page_error(page)
            if error_msg:
                result["note"] = f"Lỗi form đăng ký: {error_msg}"
                return result

            # ── STEP 7: Lấy OTP từ Gmail và nhập vào form xác minh ───
            if getattr(self, "should_stop", False):
                result["note"] = "Stopped by user"
                return result
            log.info(f"[{row['email']}] Step 7 – Chờ mã OTP từ Gmail...")

            # Kiểm tra xem có form OTP xuất hiện không
            otp_input = None
            otp_selectors = [
                'input[name="code"]',
                'input#cvf-input-code',
                'input[name="cvf-input-code"]',
                'input.cvf-widget-input',
                'input[name="otp"]',
                'input[maxlength="6"]',
            ]
            
            for sel in otp_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=8000)
                    otp_input = await page.query_selector(sel)
                    if otp_input:
                        log.info(f"[{row['email']}] Tìm thấy ô nhập OTP: {sel}")
                        break
                except Exception:
                    pass

            if not otp_input:
                # Có thể Amazon hiện trang khác, log URL để debug
                current_content = await page.content()
                if '確認' in current_content or 'verify' in page.url.lower():
                    log.warning(f"[{row['email']}] Trang xác minh xuất hiện nhưng không tìm thấy ô OTP")
                result["note"] = f"Không tìm thấy ô nhập OTP. URL hiện tại: {page.url}"
                return result

            # Đọc OTP từ Gmail
            otp = await asyncio.to_thread(
                self.gmail.fetch_otp,
                row["email"],
                wait_seconds=CONFIG["otp_wait_seconds"],
            )

            if not otp:
                result["note"] = "Không nhận được OTP từ Gmail (timeout)"
                return result

            log.info(f"[{row['email']}] OTP nhận được: {otp}")

            # Nhập OTP (giống người thật gõ từng số)
            await self._human_type(page, otp_input, otp)
            await self._human_delay(0.5, 1.0)

            # Click nút xác minh OTP
            verify_btn = None
            verify_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                '#cvf-submit-otp-button',
                'span:has-text("アカウントの作成")',
                'span:has-text("確認")',
            ]
            for sel in verify_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        verify_btn = btn
                        log.info(f"[{row['email']}] Tìm thấy nút xác minh OTP: {sel}")
                        break
                except Exception:
                    pass

            if verify_btn:
                await self._human_delay(0.3, 0.8)
                await verify_btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                await self._human_delay(2.0, 4.0)
                log.info(f"[{row['email']}] Đã submit OTP, URL: {page.url}")
            else:
                result["note"] = "Không tìm thấy nút xác minh OTP"
                return result

            # ── STEP 8: Kiểm tra kết quả đăng ký ─────────────────────
            success = await self._check_success(page)
            if success:
                result["status"] = "SUCCESS"
                result["note"] = "Đăng ký Amazon thành công"
                log.info(f"[{row['email']}] ✅ ĐĂNG KÝ THÀNH CÔNG!")
            else:
                # Kiểm tra thêm - có thể đã thành công nhưng chuyển trang khác
                page_text = await page.content()
                if 'amazon.co.jp' in page.url and 'signin' not in page.url.lower():
                    result["status"] = "SUCCESS"
                    result["note"] = "Đăng ký hoàn tất (đã chuyển về trang Amazon)"
                    log.info(f"[{row['email']}] ✅ ĐĂNG KÝ THÀNH CÔNG (redirect)")
                else:
                    result["note"] = f"OTP đã submit nhưng chưa xác nhận thành công. URL: {page.url}"

        except PlaywrightTimeout as e:
            result["note"] = f"Timeout: {e}"
            log.warning(f"[{row['email']}] Timeout – {e}")
        except Exception as e:
            result["note"] = str(e)
            log.error(f"[{row['email']}] Error – {e}", exc_info=True)

        return result

    async def _check_page_error(self, page) -> str | None:
        """Return visible error message text if found on Amazon pages."""
        error_selectors = [
            '#auth-error-message-box',
            '.a-alert-content',
            '#auth-warning-message-box',
            '.a-box-inner .a-alert-content',
            '#cvf-error-message',
            '.cvf-widget-alert',
            '.a-alert-inline-error',
        ]
        # Also check CONFIG-defined selectors
        error_selectors.extend(CONFIG.get("error_selectors", []))
        
        for sel in error_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                pass
        return None

    async def _check_success(self, page) -> bool:
        """Detect success by URL pattern or page content for Amazon registration."""
        url = page.url
        
        # Amazon-specific success patterns
        amazon_success_patterns = [
            '/dp/', '/gp/', '/hz/wishlist', '/ap/mfa',
            '/ref=', '/home', '/your-account',
        ]
        for pattern in amazon_success_patterns:
            if pattern in url and 'signin' not in url.lower() and 'register' not in url.lower():
                return True
        
        # Check page content for success indicators
        try:
            content = await page.content()
            success_texts = ['ようこそ', 'アカウントが作成されました', 'welcome', '成功']
            for text in success_texts:
                if text.lower() in content.lower():
                    return True
        except Exception:
            pass
        
        # Also check CONFIG success patterns
        for pattern in CONFIG.get("success_url_patterns", []):
            if pattern in url:
                return True
        for sel in CONFIG.get("success_selectors", []):
            try:
                el = await page.query_selector(sel)
                if el:
                    return True
            except Exception:
                pass
        return False

    async def _get_current_public_ip(self, proxy_server: str = None) -> str:
        """Lấy IP công cộng hiện tại thông qua HTTP proxy nếu bật."""
        import httpx
        url = "https://api.ipify.org?format=json"
        try:
            async with httpx.AsyncClient(proxy=proxy_server, timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json().get("ip", "Unknown")
        except Exception as e:
            log.warning(f"[Proxy] Lỗi khi lấy IP công cộng: {e}")
        return "Unknown"

    async def _rotate_ip(self, index: int, row: dict):
        """Gọi API đổi IP của Boxphone và đợi mạng ổn định."""
        proxy_conf = CONFIG.get("proxy", {})
        change_url = proxy_conf.get("change_ip_url")
        delay = proxy_conf.get("change_ip_delay", 15)
        verify = proxy_conf.get("verify_ip", False)
        proxy_server = proxy_conf.get("server") if proxy_conf.get("enable") else None

        if not change_url:
            log.info("[Proxy] Không cấu hình URL đổi IP, bỏ qua bước đổi IP.")
            return

        # Định dạng URL nếu có tham số index hoặc email
        try:
            formatted_url = change_url.format(index=index, email=row["email"])
        except Exception:
            formatted_url = change_url

        # Kiểm tra IP cũ
        old_ip = "Unknown"
        if verify:
            old_ip = await self._get_current_public_ip(proxy_server)
            log.info(f"[Proxy] IP hiện tại trước khi đổi: {old_ip}")

        log.info(f"[Proxy] Đang gọi API đổi IP Boxphone: {formatted_url}")
        try:
            if formatted_url.startswith("ws://") or formatted_url.startswith("wss://"):
                import ssl
                from urllib.parse import urlparse
                parsed = urlparse(formatted_url)
                host = parsed.hostname
                port = parsed.port or (443 if parsed.scheme == 'wss' else 80)
                
                # Mở kết nối TCP/SSL bằng asyncio
                use_ssl = parsed.scheme == 'wss'
                ssl_context = ssl.create_default_context() if use_ssl else None
                if use_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

                reader, writer = await asyncio.open_connection(
                    host, port, ssl=ssl_context
                )
                
                # Gửi bản tin bắt tay HTTP Upgrade lên WebSocket
                handshake = (
                    f"GET {parsed.path or '/'} HTTP/1.1\r\n"
                    f"Host: {parsed.netloc}\r\n"
                    f"Upgrade: websocket\r\n"
                    f"Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                    f"Sec-WebSocket-Version: 13\r\n\r\n"
                )
                writer.write(handshake.encode())
                await writer.drain()
                
                # Nhận phản hồi từ server
                response = await reader.read(1024)
                resp_text = response.decode(errors='ignore')
                if "101" in resp_text or "Switching Protocols" in resp_text:
                    log.info("[Proxy] Kết nối WebSocket thành công, đã kích hoạt đổi IP.")
                else:
                    log.warning(f"[Proxy] Phản hồi bắt tay WebSocket: {resp_text.strip()}")
                
                writer.close()
                await writer.wait_closed()
            else:
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(formatted_url)
                    log.info(f"[Proxy] Kết quả gọi API đổi IP: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            log.warning(f"[Proxy] Lỗi khi gọi API đổi IP: {e}")

        log.info(f"[Proxy] Đợi {delay} giây để IP được đổi...")
        await asyncio.sleep(delay)

        # Kiểm tra IP mới
        if verify:
            new_ip = await self._get_current_public_ip(proxy_server)
            log.info(f"[Proxy] IP hiện tại sau khi đổi: {new_ip}")
            if old_ip != "Unknown" and new_ip != "Unknown" and old_ip == new_ip:
                log.warning("[Proxy] ⚠️ IP không thay đổi sau khi reset!")

    async def _register_worker(self, browser, i: int, row: dict, sem: asyncio.Semaphore, results: list, on_progress=None):
        """Worker xử lý đăng ký từng tài khoản độc lập."""
        async with sem:
            if getattr(self, "should_stop", False):
                log.info(f"[Worker] Đã hủy đăng ký tài khoản #{i}: {row['email']} do yêu cầu dừng.")
                return
            log.info(f"[Worker] Bắt đầu đăng ký tài khoản #{i}: {row['email']}")

            # Đổi IP trước khi chạy nếu có cấu hình proxy và change_ip_url
            proxy_conf = CONFIG.get("proxy", {})
            if proxy_conf.get("enable"):
                # Cảnh báo nếu chạy song song đồng thời nhưng dùng chung 1 URL đổi IP mạng vật lý
                max_concurrent = CONFIG.get("max_concurrent_tasks", 1)
                if max_concurrent > 1 and proxy_conf.get("change_ip_url"):
                    log.warning(
                        f"[Proxy] ⚠️ Cảnh báo: Đang bật chạy song song ({max_concurrent} luồng) "
                        f"nhưng bật đổi IP mạng. Việc này có thể làm đứt kết nối của các luồng khác!"
                    )
                if getattr(self, "should_stop", False):
                    return
                await self._rotate_ip(i, row)

            # Thiết lập proxy cho browser context (ưu tiên proxy cấu hình riêng trong file Excel)
            proxy_config = None
            row_proxy = row.get("proxy")
            if row_proxy and isinstance(row_proxy, str) and row_proxy.strip():
                proxy_config = {"server": row_proxy.strip()}
                log.info(f"[Worker] Thiết lập proxy riêng cho {row['email']}: {proxy_config['server']}")
            elif proxy_conf.get("enable") and proxy_conf.get("server"):
                proxy_config = {"server": proxy_conf["server"]}
                log.info(f"[Worker] Thiết lập proxy hệ thống cho {row['email']}: {proxy_config['server']}")

            if getattr(self, "should_stop", False):
                return

            # Anti-fingerprint: random viewport cho mỗi tài khoản
            viewport_variants = [
                {"width": 1920, "height": 1080},
                {"width": 1366, "height": 768},
                {"width": 1440, "height": 900},
                {"width": 1536, "height": 864},
                {"width": 1600, "height": 900},
                {"width": 1280, "height": 720},
                {"width": 1680, "height": 1050},
            ]
            chosen_viewport = random.choice(viewport_variants)

            # Anti-fingerprint: random user agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ]
            chosen_ua = random.choice(user_agents)

            log.info(f"[Worker] Anti-detect: viewport={chosen_viewport['width']}x{chosen_viewport['height']}, UA={chosen_ua[:50]}...")

            # Tạo mới context riêng biệt cho từng tài khoản (clean cookies, localStorage)
            context = await browser.new_context(
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                proxy=proxy_config,
                viewport=chosen_viewport,
                user_agent=chosen_ua,
            )

            # Custom script to mask automation footprint
            await context.add_init_script("""
                // Xóa bỏ thuộc tính webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Giả lập plugins danh sách giống Chrome thật
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Khai báo ngôn ngữ ưu tiên khớp với locale cấu hình
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ja-JP', 'ja']
                });
            """)

            page = await context.new_page()
            try:
                result = await self.register_one(page, row)
            except Exception as e:
                log.error(f"[Worker] Lỗi xảy ra khi đăng ký tài khoản #{i} ({row['email']}): {e}", exc_info=True)
                result = {
                    "name": row["name"],
                    "email": row["email"],
                    "password": row.get("password", ""),
                    "proxy": row.get("proxy", ""),
                    "status": "FAILED",
                    "note": f"Lỗi hệ thống: {e}",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            finally:
                await page.close()
                await context.close()

            results.append(result)
            if on_progress:
                try:
                    on_progress(result)
                except Exception as ex:
                    log.error(f"[Worker] Lỗi gọi callback on_progress: {ex}")

            # Giãn cách giữa các lần chạy của cùng 1 luồng (nếu cần)
            delay = CONFIG.get("delay_between_accounts", 3)
            if delay > 0 and not getattr(self, "should_stop", False):
                await asyncio.sleep(delay)

    async def run_all(self, input_xlsx: str, output_xlsx: str, on_progress=None, group_name=""):
        if not HAS_PLAYWRIGHT:
            log.error("Playwright chưa được cài đặt! Vui lòng bật chế độ Phone (XiaoWei) hoặc cài playwright: pip install playwright")
            raise ImportError("Playwright is not installed. Use phone mode (XiaoWei) instead.")

        excel = ExcelHandler(input_xlsx)
        rows = excel.read_rows()
        log.info(f"Loaded {len(rows)} accounts from {input_xlsx}")

        results = []
        max_concurrent = CONFIG.get("max_concurrent_tasks", 1)
        sem = asyncio.Semaphore(max_concurrent)
        
        log.info(f"Bắt đầu chạy đăng ký song song (Tối đa {max_concurrent} trình duyệt đồng thời)...")

        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(
                    headless=CONFIG["headless"],
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    ignore_default_args=["--enable-automation"],
                )
            except Exception as e:
                err_msg = str(e)
                if "Executable doesn't exist" in err_msg or "playwright install" in err_msg:
                    log.info("Trình duyệt Chromium của Playwright chưa được cài đặt. Đang tự động tải xuống (khoảng 150MB)...")
                    import sys
                    from playwright.__main__ import main as playwright_main
                    try:
                        old_argv = sys.argv
                        sys.argv = ["playwright", "install", "chromium"]
                        await asyncio.to_thread(playwright_main)
                        sys.argv = old_argv
                        log.info("Đã cài đặt Chromium thành công! Đang khởi động trình duyệt...")
                    except SystemExit as se:
                        sys.argv = old_argv
                        if se.code != 0:
                            log.error(f"Tự động cài đặt Chromium thất bại với mã thoát: {se.code}")
                            raise e
                        log.info("Đã cài đặt Chromium thành công! Đang khởi động trình duyệt...")
                    except Exception as ex:
                        sys.argv = old_argv
                        log.error(f"Lỗi khi tự động cài đặt Chromium: {ex}")
                        raise e
                    
                    # Thử khởi chạy lại browser
                    browser = await pw.chromium.launch(
                        headless=CONFIG["headless"],
                        args=[
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-blink-features=AutomationControlled",
                        ],
                        ignore_default_args=["--enable-automation"],
                    )
                else:
                    raise e


            # Tạo danh sách các tác vụ chạy song song
            tasks = []
            for i, row in enumerate(rows, 1):
                tasks.append(self._register_worker(browser, i, row, sem, results, on_progress))

            # Thực thi đồng thời tất cả các task giới hạn bởi Semaphore
            await asyncio.gather(*tasks)

            await browser.close()

        excel.write_results(results, output_xlsx)
        log.info(f"\n✅ Done. Results saved to: {output_xlsx}")
        self._print_summary(results)

    def _print_summary(self, results):
        total = len(results)
        success = sum(1 for r in results if r["status"] == "SUCCESS")
        log.info(f"\n{'═'*40}")
        log.info(f"SUMMARY: {success}/{total} succeeded")
        for r in results:
            icon = "✅" if r["status"] == "SUCCESS" else "❌"
            log.info(f"  {icon} {r['email']} – {r['note']}")
        log.info(f"{'═'*40}")


if __name__ == "__main__":
    try:
        # Ensure directories exist
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        if "--cli" in sys.argv or "--phone" in sys.argv:
            # Kiểm tra chế độ: Phone (XiaoWei) hay Browser (Playwright)
            xiaowei_config = CONFIG.get("xiaowei", {})
            use_phone = xiaowei_config.get("enable", False) or "--phone" in sys.argv
            
            if use_phone:
                log.info("📱 Chế độ PHONE (XiaoWei) – đăng ký trên điện thoại thật")
                from src.phone_bot import PhoneRegistrationManager
                asyncio.run(
                    PhoneRegistrationManager().run_all(
                        input_xlsx="data/accounts.xlsx",
                        output_xlsx="data/results.xlsx",
                    )
                )
            else:
                log.info("🖥️ Chế độ BROWSER (Playwright) – đăng ký trên trình duyệt PC")
                asyncio.run(
                    RegistrationBot().run_all(
                        input_xlsx="data/accounts.xlsx",
                        output_xlsx="data/results.xlsx",
                    )
                )
        elif "--web-only" in sys.argv:
            from src.web_server import app
            port = 8000
            logging.info(f"Đang chạy máy chủ Flask (chỉ Web) tại: http://127.0.0.1:{port}")
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        else:
            from src.web_server import run_server
            run_server()
    except Exception as e:
        if sys.stdout is not None:
            print(f"\n[CRITICAL ERROR] {e}")
        log.critical(f"Critical error on startup: {e}", exc_info=True)

    finally:
        if sys.stdout is not None and "--cli" in sys.argv:
            print("\n" + "="*40)
            try:
                input("Nhấn Enter để thoát...")
            except Exception:
                pass


