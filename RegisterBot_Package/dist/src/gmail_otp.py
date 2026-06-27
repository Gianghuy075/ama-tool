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
        wait_seconds: int = 60,
        poll_interval: int = 5,
    ) -> str | None:
        """
        Poll Gmail inbox until OTP email arrives (max wait_seconds).
        Returns 6-digit OTP string or None on timeout.
        """
        deadline = time.time() + wait_seconds
        attempt = 0

        while time.time() < deadline:
            attempt += 1
            log.debug(f"OTP poll #{attempt} for {recipient_email}")
            try:
                otp = self._search_otp(recipient_email)
                if otp:
                    return otp
            except Exception as e:
                log.warning(f"IMAP error during poll: {e}")

            remaining = deadline - time.time()
            if remaining > 0:
                time.sleep(min(poll_interval, remaining))

        log.warning(f"OTP timeout ({wait_seconds}s) for {recipient_email}")
        return None

    def _search_otp(self, recipient_email: str) -> str | None:
        """Connect to IMAP and search recent unseen emails for OTP."""
        try:
            mail = self._connect()
            mail.select("INBOX")

            # Search unseen emails in last 2 minutes
            _, msg_ids = mail.search(None, "UNSEEN")
            ids = msg_ids[0].split()

            if not ids:
                mail.logout()
                return None

            # Check latest 10 emails (newest first)
            for msg_id in reversed(ids[-10:]):
                _, data = mail.fetch(msg_id, "(RFC822)")
                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                # Check destination (To field)
                to_field = msg.get("To", "")
                if recipient_email.lower() not in to_field.lower():
                    # Also check if it's a shared inbox – skip strict check if needed
                    pass

                body = self._extract_body(msg)
                otp = self._extract_6digit_otp(body)
                if otp:
                    # Mark as seen
                    mail.store(msg_id, "+FLAGS", "\\Seen")
                    mail.logout()
                    log.info(f"Found OTP {otp} in email to {to_field}")
                    return otp

            mail.logout()
        except imaplib.IMAP4.error as e:
            log.error(f"IMAP auth/connection error: {e}")
            raise
        return None

    def _extract_body(self, msg) -> str:
        """Extract plain text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
        return body

    def _extract_6digit_otp(self, text: str) -> str | None:
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

