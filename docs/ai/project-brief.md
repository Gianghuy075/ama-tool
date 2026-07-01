# Project Brief for AI

## Source

Tóm tắt từ `docs/project`.

## Project summary

AMA-Tool là hệ thống tự động đăng ký account Amazon JP bằng nhiều điện thoại Android thật qua ADB/Phone Farm API. AI agent cần ưu tiên hiểu rõ 2 component `android_phone_farm/` và `RegisterBot_Package/`, đồng thời phân biệt tài liệu chuẩn ASEF mới với legacy archive trong `docs/project/source/` và `docs/ai/source/`.

## Must-read docs

- `docs/project/00_project-overview.md`
- `docs/project/02_feature-catalog.md`
- `docs/project/04_business-rules.md`
- `docs/ai/standards/context-loading-policy.md`

## Current AI operating rule

Không đọc toàn bộ tài liệu nếu không cần. Luôn route context theo task, và ưu tiên source code khi tài liệu legacy mâu thuẫn.
