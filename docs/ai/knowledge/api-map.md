# AI Knowledge — API Map

| Method | Path/Action | Input | Output | File |
|---|---|---|---|---|
| GET | `/api/devices` | None | Danh sách thiết bị và trạng thái | `android_phone_farm/api_server.py` |
| POST | `/api/tap` | target + toạ độ | success message | `android_phone_farm/api_server.py` |
| POST | `/api/swipe` | target + toạ độ + duration | success message | `android_phone_farm/api_server.py` |
| POST | `/api/text` | target + text | success message | `android_phone_farm/api_server.py` |
| POST | `/api/keyevent` | target + keycode | success message | `android_phone_farm/api_server.py` |
| POST | `/api/screenshot` | `serial`, `savePath?` | ảnh hoặc path thành công | `android_phone_farm/api_server.py` |
| POST | `/api/adb` | target + shell command | output hoặc status | `android_phone_farm/api_server.py` |
| GET | `/api/proxy` | `serial` | proxy info | `android_phone_farm/api_server.py` |
| POST | `/api/proxy/rotate` | `serial` | success message | `android_phone_farm/api_server.py` |
| GET | `/api/data_usage` | None | usage/quota list | `android_phone_farm/api_server.py` |
| POST | `/device/clear-cache` | `serial`, `package` | success message | `android_phone_farm/api_server.py` |
| POST | `/device/open-app` | `serial`, `package` | success message | `android_phone_farm/api_server.py` |
| POST | `/device/type-char` | `serial`, `char` | success message | `android_phone_farm/api_server.py` |
| POST | `/device/click` | `serial`, `x`, `y` | success message | `android_phone_farm/api_server.py` |
| GET | `/` | None | Dashboard HTML | `RegisterBot_Package/src/web_server.py` |
| POST | `/api/start` | `group_name`, `product_url` | start status | `RegisterBot_Package/src/web_server.py` |
| POST | `/api/stop` | None | stop status | `RegisterBot_Package/src/web_server.py` |
| GET | `/api/status` | None | bot status | `RegisterBot_Package/src/web_server.py` |
| GET | `/api/results` | None | records list | `RegisterBot_Package/src/web_server.py` |
| POST | `/api/config` | runtime config | save/test result | `RegisterBot_Package/src/web_server.py` |
| GET | `/api/logs` | None | SSE log stream | `RegisterBot_Package/src/web_server.py` |
| GET | `/api/devices` | None | proxy sang Phone Farm API | `RegisterBot_Package/src/web_server.py` |
| GET | `/download/results` | None | file kết quả | `RegisterBot_Package/src/web_server.py` |
