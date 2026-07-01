# AI Knowledge — Security Boundary

## General rules

- Không expose secrets.
- Không log dữ liệu nhạy cảm đầy đủ nếu không cần.
- Không bypass auth/permission.
- Không thay đổi security flow nếu chưa có xác nhận.

## security-sensitive domain nếu có/thẻ/secure cơ chế bảo mật nếu có

- Không sao chép lại credential thật từ config legacy vào tài liệu mới.
- Không commit thêm secret, app password, token hoặc mailbox info vào docs.
- Không tự động thay đổi proxy/security/network behavior nếu chưa có plan được xác nhận.
- Không suy diễn rằng các credential đang nằm trong repo là hợp lệ để tiếp tục sử dụng.

## Project-specific risks

- `RegisterBot_Package/src/config.py` và một số doc legacy chứa dấu hiệu Gmail credential/app password thật.
- Một số tài liệu legacy có đường dẫn tuyệt đối máy cá nhân cũ.
- Hệ thống thao tác account automation trên dịch vụ bên ngoài; mọi thay đổi workflow cần cẩn trọng về compliance và review nội bộ.
