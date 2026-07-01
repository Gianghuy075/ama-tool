# AMA-Tool — Index tài liệu

Hệ thống tự động đăng ký tài khoản Amazon JP bằng cách điều khiển điện thoại Android qua USB.
**Windows only. Python 3.10+. 2 component: `android_phone_farm/` (GUI+API:5000) + `RegisterBot_Package/` (Bot+Dashboard:8000).**

## Tài liệu chi tiết — đọc đúng file, đúng lúc

| File | Đọc khi nào |
|------|------------|
| [01-overview.md](document-agent-root/01-overview.md) | Cần hiểu dự án làm gì, môi trường |
| [02-architecture.md](document-agent-root/02-architecture.md) | Làm việc với kiến trúc, thêm component, sửa giao tiếp |
| [03-input-output.md](document-agent-root/03-input-output.md) | Làm việc với Excel, config, database output |
| [04-registration-flow.md](document-agent-root/04-registration-flow.md) | Sửa logic đăng ký Amazon, thêm bước, fix bug flow |
| [05-api-reference.md](document-agent-root/05-api-reference.md) | Gọi API hoặc thêm endpoint mới |
| [06-database-schema.md](document-agent-root/06-database-schema.md) | Thay đổi schema, thêm bảng, query |
| [07-current-status.md](document-agent-root/07-current-status.md) | Hiểu hiện trạng, chọn việc tiếp theo |
| [08-session-history.md](document-agent-root/08-session-history.md) | **Bắt buộc đọc** khi bắt đầu. **Bắt buộc ghi** khi kết thúc session |
| [improvement-plan-accuracy.md](document-agent-root/improvement-plan-accuracy.md) | Plan cải tiến độ chính xác — 6 issues, thứ tự implement, log kết quả |

## Quy tắc bắt buộc

1. **Đầu session:** Đọc `08-session-history.md` để biết session trước đã làm gì
2. **Cuối session:** Append kết quả vào `08-session-history.md` trước khi thoát
3. **Không sửa API contract** giữa 2 component mà không cập nhật `05-api-reference.md`
4. **Windows only** — đừng test trên macOS, Win32 API sẽ crash
