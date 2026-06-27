"""
captcha_helper.py
Inject mock reCAPTCHA token vào form khi chạy test (ENV != production).
"""

import os

TEST_BYPASS_KEY = os.getenv("CAPTCHA_TEST_KEY", "TEST_BYPASS_123")
ENV = os.getenv("APP_ENV", "development")


async def inject_mock_captcha(page):
    """
    Inject TEST_BYPASS_KEY vào hidden input g-recaptcha-response.
    Chỉ có tác dụng khi server đang chạy ở env test/development.
    """
    if ENV == "production":
        return  # không làm gì cả ở production

    await page.evaluate(f"""
        () => {{
            // Tìm hidden input của reCAPTCHA
            let el = document.querySelector('[name="g-recaptcha-response"]');

            // Nếu chưa có, tạo mới
            if (!el) {{
                el = document.createElement('textarea');
                el.name = 'g-recaptcha-response';
                el.style.display = 'none';
                document.querySelector('form').appendChild(el);
            }}
            el.value = '{TEST_BYPASS_KEY}';

            // Nếu dùng reCAPTCHA widget, ghi đè callback
            if (window.grecaptcha) {{
                window.grecaptcha.getResponse = () => '{TEST_BYPASS_KEY}';
            }}
        }}
    """)
