# Task History

## 2026-06-30 - XiaoWei Phase 1 official contract extraction

- Re-loaded mandatory repo context before continuing XiaoWei integration work.
- Reconnected `computer-use` and confirmed the vendor page `https://www.xiaowei.xin/help/70/234` is readable in local Chrome.
- Confirmed directly from the visible official page:
  - API WebSocket address: `ws://127.0.0.1:22222/`
  - common request shape: `action`, `devices`, `data`
  - common success code: `10000`
  - common failure code: `10001`
- Updated:
  - `docs/ai/plans/xiaowei-api-contract-notes.md`
  - `docs/ai/plans/xiaowei-direct-integration-plan.md`
- Current blocker:
  - `computer-use` can read the page but sidebar navigation/link clicking is unstable, so action-specific articles under `8.2` are not extracted yet.

## 2026-07-01 - XiaoWei Android handbook action mapping

- Extracted official Android handbook feature/action list from article `351` (`4.2 接口文档`).
- Confirmed canonical Android action names now include:
  - `list`
  - `adb`
  - `screen`
  - `pointerEvent`
  - `pushEvent`
  - `writeClipBoard`
  - `uploadFile`
  - `pullFile`
  - `apkList`
  - `installApk`
  - `uninstallApk`
  - `startApk`
  - `stopApk`
  - `imeList`
  - `installInputIme`
  - `selectIme`
  - `inputText`
- Extracted detailed Android action articles:
  - `401`: `list获取设备列表`
  - `403`: `screen 截图到相册`
  - `404`: `screenFile 截图到电脑`
  - `413`: `inputText 输入文字`
  - `422`: `pointerEvent 屏幕控制`
- Identified vendor-doc inconsistencies:
  - `startApp` article body says `stopApk`
  - `appList` article body says `pullFile`
  - `uploadFile` article body says `writeClipBoard`
- Conclusion:
  - feature-list article is more trustworthy for canonical action names
  - `adb` and `startApk` still need runtime verification before final code assumptions are locked

## 2026-07-01 - XiaoWei Phase 2 runtime defaults switched

- Updated runtime config file:
  - `RegisterBot_Package/data/config.json`
  - switched from `phone_farm` to `xiaowei`
  - `api_url = http://127.0.0.1:22222`
  - `devices = all`
- Updated code defaults/fallbacks:
  - `RegisterBot_Package/src/config.py`
  - `RegisterBot_Package/src/xiaowei_client.py`
  - `RegisterBot_Package/src/web_server.py`
- Verified:
  - `CONFIG['xiaowei']['api_type'] == 'xiaowei'`
  - `CONFIG['xiaowei']['api_url'] == 'http://127.0.0.1:22222'`
  - `CONFIG['xiaowei']['devices'] == 'all'`
- `py_compile` passed for:
  - `src/config.py`
  - `src/xiaowei_client.py`
  - `src/web_server.py`
  - `main.py`

## 2026-07-01 - XiaoWei Phase 3 CLI smoke-test preparation

- Installed Python dependencies from `RegisterBot_Package/requirements.txt` for local `python3`.
- Found local interpreter mismatch:
  - machine has `Python 3.9.6`
  - `main.py` used `str | None` annotation syntax that broke at runtime without postponed evaluation
- Fixed CLI startup compatibility by:
  - adding `from __future__ import annotations` to `RegisterBot_Package/main.py`
  - adding missing `import json` for `--diagnose-xiaowei` output path
- Re-ran:
  - `cd RegisterBot_Package && python3 main.py --diagnose-xiaowei`
- Result:
  - CLI now runs and emits diagnostics JSON
  - failure is now at the intended backend layer: connect refused to `ws://127.0.0.1:22222/`
  - this is expected on the current Mac dev machine without XiaoWei runtime listening locally

## 2026-07-01 - XiaoWei Windows JP diagnostics first pass

- User checked out branch `feature/xiaowei-e2e-readiness` on the Japan Windows machine and ran:
  - `cd RegisterBot_Package`
  - `python main.py --diagnose-xiaowei`
- Runtime evidence confirmed:
  - connected to local XiaoWei runtime at `http://127.0.0.1:22222`
  - discovered `10` devices
  - `adb wm size` works
  - `adb pm list packages com.android.chrome` works
  - `uiautomator dump` works
  - UI text probe works
- Remaining issue found:
  - diagnostics reported `overall_success=false` only because `screenshot` step returned success from XiaoWei but local file existence check failed immediately
- Fix implemented in repo:
  - `RegisterBot_Package/src/xiaowei_client.py`
  - `RegisterBot_Package/src/web_server.py`
  - client now prefers `screenFile` when `savePath` is provided, falls back to `screen`, and waits briefly for file materialization

## 2026-07-01 - XiaoWei Windows JP diagnostics pass

- Re-ran `python main.py --diagnose-xiaowei` on the Japan Windows machine after the non-blocking screenshot adjustment.
- Result:
  - `overall_success=true`
  - `get_devices`, `adb_wm_size`, `adb_pm_list_packages`, `uiautomator_dump`, `ui_text_probe` all passed
  - `screenshot` still did not materialize a local file and is now treated as a warning instead of a hard failure
- Practical conclusion:
  - Phase 3 core smoke test is good enough to proceed to runtime interaction checks and one real registration flow

## 2026-07-01 - Amazon product-page false-negative fix for XiaoWei flow

- Runtime test on the Japan Windows machine reached a real Amazon JP product page but the bot stopped at Step 1 with:
  - `Wrong page detected hoặc không xác nhận được product page Amazon`
- Evidence from the shared screenshot showed the phone was already on a valid Amazon product page:
  - Amazon search bar visible
  - product title visible
  - price marker `¥7,216`
  - Amazon benefit text such as `Amazon Mastercard`
- Root cause in repo:
  - `RegisterBot_Package/src/phone_bot.py`
  - `verify_expected_product_page()` still depended too heavily on first-fold CTA visibility
  - `screen_reader.find_best_element()` had a `preferred_region` bug comparing percent regions against pixel coordinates
- Fix implemented:
  - widened Amazon product-page fingerprint detection with host + price + cart/benefit/product markers
  - wrong-domain detection now ignores cases where XML already contains strong Amazon indicators
  - fixed `preferred_region` scoring to convert node coordinates into screen percentages before boosting
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py RegisterBot_Package/src/screen_reader.py`
  - pass

## 2026-07-01 - Runtime rebaseline: surface control is part of the core problem

- Further real-device tests on the Japan Windows machine changed the understanding of the CTA issue:
  - opening the same Amazon product URL could hand off into `Amazon Shopping app`
  - after removing that app from the phone, the same URL stayed in `Chrome mobile web` but the UI variant changed again
  - `Chrome first-run`, `Translate page` UI, mobile web layout, and CTA visibility all affect the flow before CTA targeting even starts
- Conclusion:
  - the improvement plan can no longer treat CTA-finding as an isolated problem
  - `surface control` must be considered a prerequisite layer:
    - correct foreground package
    - no app handoff
    - stable Chrome runtime state
    - CTA viewport readiness
- The XiaoWei improvement plan was rebaselined accordingly:
  - Wave 1 and Wave 2 remain useful but are no longer sufficient indicators of runtime readiness
  - a new `Wave S - Surface control` was added ahead of CTA hardening

## 2026-07-01 - Sign-in mobile web state-machine hardening

- After the product CTA started landing on the real Amazon mobile web sign-in screen, the next blocker moved from `product CTA` to `post-CTA account flow`.
- Real runtime evidence showed the previous Step 3/4 logic was still too generic:
  - email field detection only matched broad `Email` labels
  - `Continue` still depended on generic text search and could drift on mobile web
  - the bot could continue even if the surface had changed into `password login` instead of `create account`
- Fix implemented in `RegisterBot_Package/src/phone_bot.py`:
  - added explicit account-surface classification:
    - `signin_entry`
    - `create_account_prompt`
    - `register_form`
    - `password_login`
  - added dedicated finder for the sign-in field:
    - `Enter mobile number or email`
    - Japanese label variants
    - top-half EditText fallback
  - added dedicated `Continue` tap logic:
    - `field anchor -> primary button below anchor`
    - no scroll on the sign-in screen
    - only fallback to constrained scoring inside the sign-in viewport
  - hardened state transition checks:
    - fail fast if `Continue` lands on `password login`
    - skip Step 3/4 if runtime already lands directly on `register_form`
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py`
  - pass

## 2026-07-01 - CTA viewport search tightened for Amazon mobile web

- New runtime evidence showed the Step 2 CTA search still failed because the fallback path was effectively:
  - no trustworthy CTA node
  - no anchor
  - preset swipe down the page
  - retry
- That was too loose for the Amazon mobile web product page because one large swipe can jump past the yellow CTA right below the product block.
- Fix implemented in `RegisterBot_Package/src/phone_bot.py`:
  - added English CTA variants:
    - `Request invite`
    - `Available by invitation`
  - added English invitation anchors for the product page info block
  - replaced preset CTA-search scrolling with `short-sweep` custom swipes that preserve heavy viewport overlap
  - added `viewport signature` logging to detect repeated/unchanged scroll states
  - added `first-fold CTA probe` before allowing any downward scroll
- Practical intent:
  - scan the current viewport more aggressively first
  - only move the page in short, controlled steps
  - stop if the viewport does not actually change, instead of continuing blind scroll
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py`
  - pass

## 2026-07-01 - Runtime fix for bogus CTA/anchor nodes with zero bounds

- A later Japan-machine runtime log exposed a more concrete bug in the Step 2 CTA path:
  - `Request invite` and `Available by invitation` were detected from XML text
  - but the matching nodes had bounds equivalent to `0,0`
  - the bot then used `anchor_y2=0` for fallback CTA tapping, which shifted the tap near the top of the screen
- Another verification bug was found in the same run:
  - post-click state classification already detected `register_form`
  - but `_verify_post_request_invitation_state()` still returned failure because broad `info/help marker` checks overrode the classified state
- Fix implemented in `RegisterBot_Package/src/phone_bot.py`:
  - reject CTA candidate nodes with invalid geometry
  - reject invitation anchor nodes with invalid geometry
  - reject first-fold CTA probe nodes with invalid geometry
  - log invalid geometry matches explicitly for later runtime diagnosis
  - make post-click verification trust a classified account-flow state before applying broad negative text heuristics
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py`
  - pass

## 2026-07-01 - False-positive guard for Step 3 email typing

- Another runtime regression appeared after the CTA/state patches:
  - bot could remain on the product page
  - internal logic still advanced into Step 3
  - email typing then hit the product-page search box instead of a real sign-in form
- Root cause in repo:
  - account-surface classification was still too loose
  - Step 3 email input still allowed bbox fallback even when a real sign-in field was not confirmed
  - Step 3 continue-button logic could also proceed without a strongly confirmed `signin_entry`
- Fix implemented in `RegisterBot_Package/src/phone_bot.py`:
  - tightened account-surface classification:
    - `signin_entry` now requires a verified sign-in field, not just any `EditText`

## 2026-07-02 - Reset after CTA/sign-in improvement plan failed

- Real-device runtime on the Japan Windows machine invalidated the current CTA/sign-in hardening branch:
  - bot could stay on the product page or search/top-bar surface
  - internal logs still advanced as if CTA click and sign-in detection had succeeded
  - email could then be typed into the wrong field while internal state claimed account flow progress
- Decision taken on branch `feature/xiaowei-e2e-readiness`:
  - stop stacking more heuristics on the failed observation layer
  - rebaseline back to `XiaoWei direct integration baseline`
  - preserve stable `Chrome loading/network recovery`
  - remove the later CTA/sign-in state-machine logic from `90a951e` onward
- Repo changes made:
  - `docs/ai/plans/xiaowei-direct-integration-plan.md`
    - marked the current improvement plan as failed at `observation/runtime verification`
    - clarified that the branch priority is still `XiaoWei direct integration baseline` first
  - `RegisterBot_Package/src/phone_bot.py`
    - rolled back to snapshot `65a9085`
    - removed later runtime heuristics such as:
      - `signin_entry/create_account_prompt/register_form/password_login` state classification
      - `short-sweep` CTA scanning
      - `first-fold CTA probe`
      - `Request invite` / `Available by invitation` expansion
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py`
  - pass
    - removed overly generic `name` marker from `register_form`
  - email typing now hard-fails unless current surface is confirmed as `signin_entry`
  - removed blind bbox fallback for sign-in email input
  - continue-button tap now hard-fails unless current surface is confirmed as `signin_entry`
- Design intent:
  - fail early on surface ambiguity
  - never type into the product-page search box again
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py`
  - pass

## Mục tiêu

Ghi lại lịch sử task/session quan trọng đã thực hiện bởi user hoặc AI Agent.

| Date/Period | Task | Agent/Tool | Files/Modules | Result | Evidence |
|---|---|---|---|---|---|
| 2026-06-28 | Phân tích codebase và tạo bộ legacy context ban đầu | Orchestrator AI (legacy) | legacy docs, legacy adapter | Completed | `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` |
| 2026-06-28 | Implement 6 accuracy improvements cho phone bot | Orchestrator AI (legacy) | `RegisterBot_Package/src/phone_bot.py`, `src/screen_reader.py`, `src/xiaowei_client.py` | Completed, pending runtime verification | `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` |
| 2026-06-30 | Audit, migrate và dọn triệt để context architecture sang ASEF Pro | Codex | `docs/project/*`, `docs/ai/*`, root adapters | Completed | File tree hiện tại, `docs/ai/source/legacy-agent-context/legacy-context-inventory.md` |
| 2026-06-30 | Chuẩn bị migration sang `RegisterBot -> XiaoWei API`, thêm runbook/config mẫu/diagnostics tích hợp | Codex | `RegisterBot_Package/src/xiaowei_client.py`, `src/web_server.py`, `src/web/*`, `main.py`, `docs/ai/plans/*` | In progress, ready for Windows runtime test | `docs/ai/plans/xiaowei-direct-integration-plan.md`, `docs/ai/plans/xiaowei-windows-jp-runbook.md` |
| 2026-06-30 | Truy xuất contract API XiaoWei official từ site API nội bộ | Codex | `docs/ai/plans/xiaowei-api-contract-notes.md`, `docs/ai/plans/xiaowei-direct-integration-plan.md` | Partial contract confirmed | `https://www.xiaowei.xin/api/manual/article?id=234` |
| 2026-07-02 | Sửa lại Step 2 CTA cho XiaoWei sau regression geometry/XML: bỏ click mù theo anchor/bbox thấp, chuyển sang micro-scroll nhẹ + first-fold viewport tap hẹp | Codex | `RegisterBot_Package/src/phone_bot.py`, `docs/ai/memory/next-session.md` | Completed in code, pending Windows JP runtime verification | `python3 -m py_compile RegisterBot_Package/src/phone_bot.py` |
| 2026-07-02 | Sửa tiếp Step 2 CTA: scroll phải được xác nhận bằng `wait_for_ui_change`, nếu viewport không đổi thì không được coi như scroll thành công | Codex | `RegisterBot_Package/src/phone_bot.py`, `docs/ai/memory/next-session.md` | Completed in code, pending Windows JP runtime verification | `python3 -m py_compile RegisterBot_Package/src/phone_bot.py` |

## Ghi chú

Không dùng file này thay cho `current-task.md`.  
`current-task.md` chỉ chứa trạng thái hiện tại.
