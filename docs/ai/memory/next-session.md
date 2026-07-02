# Next Session

## XiaoWei Phase 1 status

- Phase 1 is no longer blocked on basic official contract discovery.
- Confirmed official common contract:
  - endpoint family uses WebSocket
  - Windows JP runtime assumption still `ws://127.0.0.1:22222/`
  - common codes: `10000=success`, `10001=request failed`
- Confirmed Android handbook action docs:
  - `401` list
  - `403` screen
  - `404` screenFile
  - `413` inputText
  - `422` pointerEvent
  - `351` feature-list article with canonical actions including `adb`, `pushEvent`, `startApk`, `stopApk`

## Important caution

- Vendor detail pages contain copy/paste mistakes.
- Do not trust single detail articles blindly when they conflict with feature-list article `351`.
- `adb` and `startApk` still need runtime verification on Windows JP machine.

## Recommended next step

1. Giữ đúng thứ tự của nhánh `feature/xiaowei-e2e-readiness`:
   - trước hết hoàn thành `XiaoWei direct integration baseline`
   - sau đó mới tiếp tục `Amazon flow hardening`
2. Re-run trên máy Windows Nhật nhưng đánh giá theo baseline trước:
   - mở đúng `Chrome`
   - mở đúng `product_url`
   - không bị app handoff / false-positive state
   - runtime action `tap/swipe/type/open_url/open_app` có evidence thật
3. Chỉ khi baseline trên ổn mới tiếp tục đánh giá:
   - `Request Invitation` CTA
   - sign-in / create-account / register-form
4. Nếu bot vẫn log state sai khác runtime thật:
   - dừng vá thêm heuristic
   - rebaseline hoặc rollback phần hardening gây lệch state

## Reset đã thực hiện

- Plan cải tiến CTA/sign-in cũ đã được đánh dấu là `fail ở observation/runtime verification`.
- `RegisterBot_Package/src/phone_bot.py` đã rollback về snapshot `65a9085`.
- Phần được giữ lại:
  - `Chrome loading/network recovery`
  - `open_url -> verify product page -> open CTA flow` baseline
- Phần đã bỏ:
  - `signin_entry/create_account_prompt/register_form/password_login` state machine
  - `Request invite` / `Available by invitation` heuristic mới
  - `short-sweep` / `first-fold CTA probe`
  - các false-positive guard được dựng trên observation layer không đáng tin

## Bắt đầu từ đâu?

1. Đọc `docs/ai/standards/context-loading-policy.md`
2. Đọc `docs/ai/memory/current-task.md`
3. Đọc `docs/ai/memory/known-issues.md`
4. Nếu làm việc với nghiệp vụ account flow, đọc thêm `docs/project/03_user-flows.md` và `docs/project/04_business-rules.md`

## Context cần đọc

- `docs/ai/standards/context-loading-policy.md`
- `docs/ai/memory/current-task.md`
- `docs/ai/memory/known-issues.md`
- `docs/project/08_roadmap.md`

## Việc còn lại

- Tiếp tục plan XiaoWei tại `docs/ai/plans/xiaowei-direct-integration-plan.md`
- Ưu tiên:
  - khóa lại baseline XiaoWei thật trên Windows JP
  - verify `startApk` / `open_app` / `open_url` / `tap` / `swipe` / `type_text`
  - chạy được 1 account thật với backend XiaoWei
  - sau đó mới quay lại `Request Invitation` + sign-in hardening

## Update 2026-07-02 Step 2 CTA

- Đã sửa lại `RegisterBot_Package/src/phone_bot.py` theo hướng:
  - bỏ `anchor fallback` click mù
  - bỏ `revealed bbox fallback` click quá thấp
  - giữ `micro-scroll` rất nhẹ cho first-fold CTA
  - nếu vẫn chỉ có CTA text nhưng geometry rác thì tap trong dải `first-fold viewport` hẹp ngay dưới block ảnh/giá
- Mục tiêu của patch này:
  - không click nhầm vào ảnh/info/help page nữa
  - không scroll sâu quá mất CTA
  - ưu tiên nhích xuống 10-20% chiều cao màn hình rồi tap trong vùng CTA thực tế
- Cần user test lại trên máy Windows JP để xác nhận:
  - log có `CTA micro-scroll step=1`
  - sau đó nếu geometry vẫn rác thì log có `first-fold viewport`
  - bot có vào đúng sign-in flow hay không

## Update 2026-07-02 Step 2 CTA - scroll verify

- Đã xác định lỗi mới:
  - bot có gửi `swipe` nhưng runtime thực tế không tạo thay đổi viewport đủ rõ
  - code cũ vẫn coi như scroll thành công rồi tiếp tục tap CTA
- Đã sửa tiếp:
  - `CTA micro-scroll` giờ dùng nấc mạnh hơn để lộ CTA web Chrome
  - sau mỗi swipe phải có `wait_for_ui_change`
  - chỉ khi viewport đổi thật mới cho phép dùng `first-fold viewport fallback`
  - nếu swipe không làm UI đổi, bot sẽ log rõ và thử nấc scroll mạnh hơn

## Update 2026-07-02 Step 2 CTA - anchor guided

- Từ ảnh runtime web Chrome:
  - sau scroll đầu tiên, `Available by invitation` đã hiện nhưng còn sát đáy màn
  - CTA thật vẫn nằm dưới fold
  - patch cũ vẫn tap luôn nên click trúng ảnh/product area
- Đã sửa tiếp:
  - nếu `Invitation anchor` còn sát đáy màn (`bottom_pct >= 82`) thì bot phải scroll tiếp, không được tap
  - nếu anchor đã lên vùng giữa dưới màn (`y_pct ~55-78`) thì mới cho phép tap tương đối ở dưới anchor
  - `first-fold viewport fallback` chỉ còn dùng khi không có anchor hợp lệ

## Update 2026-07-02 Step 4/5/6 - create-account variant

- Runtime mới nhất trên máy Windows Nhật đã xác nhận:
  - Step 2: pass, click đúng CTA `Request invite`
  - Step 3: pass, nhập đúng email vào `Enter mobile number or email`
  - blocker cũ đã chuyển sang biến thể account-creation sau `Continue`
- Biến thể Amazon thực tế hiện đang gặp:
  - màn trung gian có text:
    - `Looks like you're new to Amazon`
    - `Let's create an account using your email`
    - nút vàng `Proceed to create an account`
  - form kế tiếp có:
    - `First and last name`
    - `Password`
    - `Verify email`
  - không thể tiếp tục dùng assumption cũ:
    - chỉ tìm `Create account`
    - chỉ chờ `Your name/First name`
    - luôn bắt buộc `Confirm password`
    - scroll xuống bbox cứng để bấm submit
- Patch mới đã áp vào `RegisterBot_Package/src/phone_bot.py`:
  - Step 3 wait nhận thêm marker của màn trung gian và form mới
  - Step 4 ưu tiên click `Proceed to create an account`
  - Step 4 bỏ qua click trung gian nếu form đã hiện sẵn
  - Step 5 hỗ trợ label `First and last name`
  - Step 5 bỏ qua `Confirm password` nếu flow hiện tại không có field đó
  - Step 6 ưu tiên bấm `Verify email` theo text, chỉ fallback bbox khi bất khả kháng

## Việc user cần làm ở lượt test tiếp theo

1. Trên máy Windows Nhật:
   - `git pull origin feature/xiaowei-e2e-readiness`
2. Chạy lại `python main.py` trong `RegisterBot_Package`
3. Test 1 account thật và chụp lại nếu fail
4. Khi xem log, tập trung vào 3 điểm:
   - Step 4 có log `Proceed to create an account` / `Form tạo tài khoản đã hiện ngay sau Continue`
   - Step 5 có log `First and last name`
   - Step 6 có log `Nút Verify Email (Gửi OTP)`

## Mục tiêu xác nhận ở lượt test tới

- bot bấm qua được màn `Proceed to create an account`
- bot điền được:
  - `First and last name`
  - `Password`
- bot bấm được `Verify email`
- bot vào được màn OTP thật

## Update 2026-07-02 Password field false-positive

- Runtime mới nhất xác nhận:
  - Step 2 pass
  - Step 3 pass
  - Step 4 pass
  - Step 5 phần `First and last name` pass
  - blocker mới là `Password field`
- Failure thực tế:
  - bot log tìm thấy `Ô Mật khẩu` gần label `Show password`
  - candidate có score rất thấp nhưng vẫn bị dùng
  - click rơi vào top bar của Chrome (`omnibox/search/url bar`)
  - sau đó password bị gõ nhầm vào Chrome UI thay vì web form
- Patch mới đã áp:
  - thêm `min_score` cho field detection
  - thêm `preferred_region` cho email/name/password/otp
  - password flow ưu tiên node `password=true`
  - password flow phạt nặng candidate ở top màn hình
  - nếu candidate không đủ tin cậy thì bỏ qua và fallback vào bbox của form

## Việc user cần làm ở lượt test kế tiếp

1. Trên máy Windows Nhật:
   - `git pull origin feature/xiaowei-e2e-readiness`
2. Chạy lại `python main.py` trong `RegisterBot_Package`
3. Test lại 1 account thật
4. Khi xem log, tập trung đặc biệt vào password step:
   - nếu đúng, log phải không còn tọa độ kiểu `y~176`
   - nếu fallback chạy, log sẽ có:
     - `Không tìm thấy field đủ tin cậy ... fallback sang bbox cũ`
   - nếu vẫn sai, gửi lại ảnh + đoạn log từ `Step 5 – Điền form đăng ký` đến lúc gõ password

## Update 2026-07-02 OTP blocker moved to Gmail reader

- Runtime tốt nhất hiện tại đã đi qua được:
  - Step 2 `Request invite`
  - Step 3 email sign-in
  - Step 4 create-account variant
  - Step 5 name + password
  - Step 6 `Verify email`
- Blocker hiện tại:
  - Step 7 timeout khi lấy OTP Gmail
  - nguyên nhân nghi ngờ mạnh nhất là `gmail_otp.py` lọc quá cứng theo `recipient_email`, nên mail Amazon dạng forward/runtime variant bị bỏ qua
- Đã sửa trong repo:
  - decode MIME `Subject`/`From`
  - tìm OTP trong cả `subject + body`
  - recipient match chỉ còn là `boost`, không còn là điều kiện bắt buộc
  - thêm log:
    - `OTP search found no usable candidate ... Rejected preview: ...`
    - `OTP candidates for ...`
    - `Found OTP ... recipient_hint=... score=...`

## Việc user cần làm ở lượt test kế tiếp

1. Trên máy Windows Nhật:
   - `git pull origin feature/xiaowei-e2e-readiness`
2. Chạy lại `python main.py`
3. Test 1 account thật tới màn OTP
4. Nếu vẫn fail ở OTP:
   - gửi lại đoạn log từ `Step 7 – Chờ và nhập mã OTP...` tới `OTP timeout`
   - đặc biệt giữ lại các dòng mới:
     - `OTP search found no usable candidate`
     - `Rejected preview`
     - `OTP candidates for`
