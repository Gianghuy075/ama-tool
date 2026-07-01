# Known Issues

| ID | Area | Issue | Severity | Status | Evidence |
|---|---|---|---|---|---|
| KI01 | Documentation | Legacy flow doc vẫn mô tả hardcoded taps như điểm yếu chính, nhưng source hiện đã có `screen_reader`/`_tap_element` | Medium | Open | `docs/project/source/legacy-docs/04-registration-flow.legacy.md`, `RegisterBot_Package/src/screen_reader.py` |
| KI02 | Documentation | Legacy current-status note chưa phản ánh đầy đủ accuracy improvements đã implement | Medium | Open | `docs/project/source/raw-notes/07-current-status.legacy.md`, `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` |
| KI03 | Security | Repo chứa credential dấu hiệu thật trong config/doc legacy | High | Open | `RegisterBot_Package/src/config.py`, `docs/project/source/legacy-docs/03-input-output.legacy.md` |
| KI04 | Naming | Repo dùng nhiều tên project khác nhau (`AMA-Tool`, `GDP-tool-phone`, `RegisterBot`) | Medium | Open | `CLAUDE.md`, `api_server.py`, README files |
| KI05 | Runtime verification | Chưa có evidence chuẩn hóa trong docs ASEF rằng accuracy improvements đã được test trên Windows thật sau khi implement | Medium | Open | `docs/project/source/raw-notes/improvement-plan-accuracy.legacy.md` |
