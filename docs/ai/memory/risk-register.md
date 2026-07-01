# Risk Register

| ID | Risk | Area | Severity | Mitigation | Status |
|---|---|---|---|---|---|
| R01 | Tài liệu legacy mâu thuẫn source hiện tại | Documentation | Medium | Ưu tiên source code khi có conflict; ghi rõ conflict trong docs | Open |
| R02 | Secrets đang hiện diện trong repo và có thể bị lan sang docs mới | Security | High | Không sao chép secrets; lên kế hoạch tách secret khỏi repo ở bước riêng | Open |
| R03 | Một số AI tool hoặc thói quen cũ của team có thể vẫn tìm legacy docs thay vì docs ASEF mới | Tooling | Medium | Dùng root adapter mỏng và ghi rõ source of truth mới | Open |
| R04 | Manual runtime test phụ thuộc Windows + device thật nên khó xác nhận trên máy hiện tại | Testing | Medium | Ghi rõ testing gap, dùng evidence hiện có từ docs/source | Open |
