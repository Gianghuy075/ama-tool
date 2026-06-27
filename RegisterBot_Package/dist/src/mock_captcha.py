"""
Mock reCAPTCHA cho Test Environment
====================================
Chỉ dùng khi ENV=test hoặc ENV=development.
KHÔNG BAO GIỜ deploy cái này lên production.

Cách hoạt động:
  - Khi ENV=test: bỏ qua verify reCAPTCHA, luôn trả về True
  - Khi ENV=production: gọi Google API thật như bình thường
"""

import os
import httpx
from functools import wraps
from flask import request, jsonify  # hoặc đổi sang Django/FastAPI bên dưới

# ── Config ──────────────────────────────────────────────────────────────────
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET_KEY", "")
ENV              = os.getenv("APP_ENV", "development")   # "production" | "development" | "test"
TEST_BYPASS_KEY  = os.getenv("CAPTCHA_TEST_KEY", "TEST_BYPASS_123")  # key bí mật chỉ test biết


# ── Core verify function ─────────────────────────────────────────────────────
def verify_recaptcha(token: str) -> bool:
    """
    Verify reCAPTCHA token.
    - Môi trường test: bypass nếu token == TEST_BYPASS_KEY
    - Môi trường production: gọi Google API thật
    """
    # MOCK: chỉ hoạt động ngoài production
    if ENV != "production":
        if token == TEST_BYPASS_KEY:
            print(f"[CAPTCHA MOCK] Bypass accepted (env={ENV})")
            return True

    # REAL: gọi Google reCAPTCHA verify
    if not RECAPTCHA_SECRET:
        raise RuntimeError("RECAPTCHA_SECRET_KEY chưa được set")

    try:
        resp = httpx.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": RECAPTCHA_SECRET, "response": token},
            timeout=5,
        )
        data = resp.json()
        return data.get("success", False)
    except Exception as e:
        print(f"[CAPTCHA ERROR] {e}")
        return False


# ── Flask decorator ──────────────────────────────────────────────────────────
def require_captcha(f):
    """
    Dùng như decorator trên route Flask:

        @app.route("/huy/register", methods=["POST"])
        @require_captcha
        def register():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (
            request.form.get("g-recaptcha-response")
            or request.json.get("g-recaptcha-response", "") if request.is_json else ""
        )
        if not verify_recaptcha(token):
            return jsonify({"error": "CAPTCHA verification failed"}), 400
        return f(*args, **kwargs)
    return decorated


# ── Django helper ────────────────────────────────────────────────────────────
def django_verify_captcha(request_obj) -> bool:
    """
    Dùng trong Django view:

        def register(request):
            if not django_verify_captcha(request):
                return HttpResponseBadRequest("CAPTCHA failed")
            ...
    """
    token = request_obj.POST.get("g-recaptcha-response", "")
    return verify_recaptcha(token)
