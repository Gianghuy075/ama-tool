"""
Gmail IMAP OTP Reader
Reads OTP from Gmail using IMAP (App Password required).
"""

import imaplib
import email
import re
import time
import logging
from email.header import decode_header
from email import utils as email_utils
from typing import Optional

log = logging.getLogger(__name__)


class GmailOTPReader:
    def __init__(self, email: str, password: str, imap_server: str = "imap.gmail.com"):
        self.email_addr = email
        self.password = password
        self.imap_server = imap_server

    def _connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.imap_server, 993)
        mail.login(self.email_addr, self.password)
        return mail

    def fetch_otp(
        self,
        recipient_email: str,
        wait_seconds: int = 90,
        poll_interval: int = 3,
        sent_otp_time: float = None,
    ) -> Optional[str]:
        """
        Poll Gmail inbox/all-mail until OTP email arrives (max wait_seconds).
        Returns 6-digit OTP string or None on timeout.
        """
        if sent_otp_time is None:
            sent_otp_time = time.time() - 30

        deadline = time.time() + wait_seconds
        attempt = 0

        while time.time() < deadline:
            attempt += 1
            log.info(f"OTP poll #{attempt} for {recipient_email} (sent_otp_time={sent_otp_time})")
            try:
                otp = self._search_otp(recipient_email, sent_otp_time)
                if otp:
                    return otp
            except Exception as e:
                log.warning(f"IMAP error during poll: {e}")

            remaining = deadline - time.time()
            if remaining > 0:
                time.sleep(min(poll_interval, remaining))

        log.warning(f"OTP timeout ({wait_seconds}s) for {recipient_email}")
        return None

    def _search_otp(self, recipient_email: str, sent_otp_time: float) -> Optional[str]:
        """Connect to IMAP and search recent emails for forwarded OTP using 3-layer filter."""
        try:
            mail = self._connect()
            
            # Lớp 1: Truy cập thẳng vào thư mục [Gmail]/All Mail để quét
            selected = False
            for folder in ['"[Gmail]/All Mail"', '[Gmail]/All Mail', '"[Gmail]/Tất cả Thư"', '[Gmail]/Tất cả Thư', 'INBOX']:
                try:
                    status, _ = mail.select(folder)
                    if status == 'OK':
                        selected = True
                        log.debug(f"Selected folder: {folder}")
                        break
                except Exception:
                    continue
            
            if not selected:
                mail.select("INBOX")
                log.debug("Selected fallback folder: INBOX")

            # Quét tất cả email gần đây (lấy 30 thư mới nhất)
            status, msg_ids = mail.search(None, "ALL")
            ids = msg_ids[0].split()

            if not ids:
                mail.logout()
                return None

            # Duyệt từ mới nhất về cũ nhất
            for msg_id in reversed(ids[-30:]):
                try:
                    _, data = mail.fetch(msg_id, "(RFC822)")
                    if not data or not data[0]:
                        continue
                    raw = data[0][1]
                    msg = email.message_from_bytes(raw)

                    # Lớp 2 (Lọc Người gửi & Thời gian)
                    from_field = msg.get("From", "")
                    if not from_field or not any(x in from_field.lower() for x in ["amazon.com", "amazon.co.jp", "amazon"]):
                        continue

                    date_str = msg.get("Date")
                    if date_str:
                        try:
                            mail_dt = email_utils.parsedate_to_datetime(date_str)
                            mail_ts = mail_dt.timestamp()
                        except Exception:
                            mail_ts = time.time()
                    else:
                        mail_ts = time.time()

                    # Cho phép lệch clock tối đa 60 giây trước thời điểm gửi
                    if mail_ts < (sent_otp_time - 60):
                        continue

                    # Lớp 3 (Quét trường ẩn để bắt khớp)
                    sub_email = recipient_email.lower().strip()
                    found_recipient = False

                    # Kiểm tra các headers phổ biến cho email chuyển tiếp hoặc trực tiếp
                    for header_name in ["X-Forwarded-To", "Delivered-To", "To", "Cc", "X-Original-To"]:
                        header_val = msg.get(header_name, "")
                        if header_val and sub_email in header_val.lower():
                            found_recipient = True
                            break

                    # Kiểm tra toàn bộ headers khác nếu chưa thấy
                    if not found_recipient:
                        for name, value in msg.items():
                            if sub_email in str(value).lower():
                                found_recipient = True
                                break

                    # Trích xuất body
                    body = self._extract_body(msg)

                    # Kiểm tra body nếu chưa thấy khớp ở headers
                    if not found_recipient:
                        if sub_email in body.lower():
                            found_recipient = True

                    if not found_recipient:
                        continue

                    # Bốc tách 6 số OTP bằng RegEx
                    otp = self._extract_6digit_otp(body)
                    if otp:
                        # Đánh dấu đã đọc thư này
                        mail.store(msg_id, "+FLAGS", "\\Seen")
                        mail.logout()
                        log.info(f"Found forwarded OTP {otp} in email to {recipient_email}")
                        return otp
                except Exception as ex:
                    log.warning(f"Error processing message ID {msg_id}: {ex}")
                    continue

            mail.logout()
        except Exception as e:
            log.error(f"IMAP search error: {e}")
        return None

    def _extract_body(self, msg) -> str:
        """Extract text content from email message, with HTML tag-stripping fallback."""
        body = ""
        if msg.is_multipart():
            # Bước 1: Quét tìm plain text
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="replace")
            
            # Bước 2: Nếu không có plain text, quét HTML và loại bỏ tag
            if not body.strip():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disposition = str(part.get("Content-Disposition", ""))
                    if ctype == "text/html" and "attachment" not in disposition:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html_content = payload.decode(charset, errors="replace")
                            body += re.sub(r'<[^>]+>', ' ', html_content)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                ctype = msg.get_content_type()
                text_content = payload.decode(charset, errors="replace")
                if ctype == "text/html":
                    body = re.sub(r'<[^>]+>', ' ', text_content)
                else:
                    body = text_content
        return body

    def _extract_6digit_otp(self, text: str) -> Optional[str]:
        """
        Extract 6-digit OTP from text body.
        Handles patterns like:
          - 'Your OTP is: 123456'
          - '認証コード: 123456'
          - A standalone 6-digit number
        """
        if not text:
            return None

        # Priority patterns (labeled OTPs)
        labeled_patterns = [
            r"(?:OTP|otp|code|CODE|認証コード|確認コード|verification code)[^\d]*(\d{6})",
            r"(\d{6})\s*(?:がOTP|がコード|is your|はあなたの)",
        ]
        for pattern in labeled_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)

        # Fallback: any standalone 6-digit number (not part of longer number)
        m = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
        if m:
            return m.group(1)

        return None


def get_amazon_otp(gmail_address, app_password, imap_server="imap.gmail.com", max_retries=10, delay=5):
    """
    Kết nối Gmail qua IMAP để tìm mã OTP mới nhất từ Amazon.
    Mỗi lần không thấy sẽ đợi `delay` giây, thử tối đa `max_retries` lần.
    """
    for attempt in range(max_retries):
        try:
            # Kết nối đến Server
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(gmail_address, app_password)
            mail.select("inbox")
            
            # Tìm các thư CHƯA ĐỌC từ Amazon (hoặc từ localhost test)
            # Bạn có thể đổi "FROM" tùy theo môi trường test hoặc thật
            status, data = mail.search(None, '(UNSEEN)')
            mail_ids = data[0].split()
            
            if mail_ids:
                # Lấy email mới nhất trong danh sách chưa đọc
                latest_id = mail_ids[-1]
                status, msg_data = mail.fetch(latest_id, '(RFC822)')
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = msg['subject']
                        
                        # Đọc nội dung Email
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()
                        
                        # Dùng Regex quét mã OTP 6 chữ số
                        otp_match = re.search(r'\b\d{6}\b', body)
                        if otp_match:
                            otp = otp_match.group(0)
                            # Đánh dấu đã đọc thư này để lần sau không quét trùng
                            mail.store(latest_id, '+FLAGS', '\\Seen')
                            mail.logout()
                            return otp
            
            mail.logout()
        except Exception as e:
            print(f"Lỗi khi đọc Gmail (Lần {attempt+1}): {e}")
            
        print(f"Chưa nhận được OTP, đang thử lại sau {delay} giây...")
        time.sleep(delay)
        
    return None
