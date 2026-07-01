# XiaoWei API Contract Notes

## Nguồn

- Public page: `https://www.xiaowei.xin/help/70/234`
- Actual article fetched from site API:
  - `https://www.xiaowei.xin/api/manual/article?id=234`

## Article identified

- `ID`: `234`
- `Title`: `8.1.1. 接口文档说明`

## Official details confirmed

### API address

```txt
ws://127.0.0.1:22222/
```

### Request/response format

- Request and response are JSON
- Unless specially noted, request parameters are string type

### Common request fields

| Field | Type | Required | Example | Meaning |
|---|---|---|---|---|
| `action` | string | Yes | `"pushEvent"` | Event/action type, case-insensitive |
| `devices` | string | Yes | `"all"` or `"xxx,xxx"` | Device serial(s); can also use `IP:port` when no serial |
| `data` | json | No | `{...}` | Action-specific payload |

### Common response fields

| Field | Type | Example | Meaning |
|---|---|---|---|
| `code` | int | `10000` | Return code |
| `message` | string | `"SUCCESS"` | Response message |
| `data` | json | `null` | JSON payload or null |

### Common response codes confirmed

| Code | Meaning |
|---|---|
| `10000` | Request succeeded |
| `10001` | Request failed |

### Example request from official doc

```json
{
  "action": "pushEvent",
  "devices": "all",
  "data": {
    "type": "2"
  }
}
```

### Example response from official doc

```json
{
  "code": 10000,
  "message": "SUCCESS",
  "data": null
}
```

## Mapping impact on repo

### Confirmed aligned with current code

- `xiaowei_client.py` already uses WebSocket
- default practical endpoint `127.0.0.1:22222` matches official doc
- `_is_success()` checking `code == 10000` and `message == "SUCCESS"` is correct
- request shape `action`, `devices`, `data` matches current client design

## Handbook frontend endpoints discovered

From the XiaoWei handbook frontend bundle, the documentation UI uses these site API endpoints:

- `/api/manual/handbook`
- `/api/manual/article`
- `/api/manual/getManualToken`
- `/api/manual/category`
- `/api/manual/articleTree`

### Bundle evidence

The handbook tree component in the Nuxt bundle calls:

- `$fetch("/api/manual/articleTree", { params: { manualId, categoryId }, headers: { Author: token } })`
- `$fetch("/api/manual/category", { params: { ParentID, HandbookID }, headers: { Author: token } })`

This means:

- action-specific docs should be reachable through handbook tree/category traversal
- the public article `234` is only the common API protocol page
- additional action pages likely exist under handbook `70`, category `106` (`8. API文档`)

### Still to verify in later articles or runtime

- `pushEvent` type mapping beyond `type:"2"`
- `pushEvent` type mapping
- exact `adb` payload shape in Android handbook
- exact `startApk` detailed payload article in Android handbook
- whether `screen` and `screenFile` are both supported by the Windows build in user environment
- exact semantics of `type` values used by `pointerEvent` and `pushEvent`

## Android handbook feature-list article confirmed

From article `351` (`4.2 接口文档`) in handbook `70`, the official Android API feature list currently exposes these action names:

| API | Action | Note |
|---|---|---|
| Get devices | `list` | Returns connected device list |
| Update device metadata | `updateDevices` | Rename / sort index |
| Execute adb command | `adb` | Run `adb shell` suffix only |
| Screenshot | `screen` | Saves current frame to PC by default |
| Screen control | `pointerEvent` | `0/1/2/4/5/6/7/8/9` described; article `422` also mentions `10=click` |
| Quick key action | `pushEvent` | `1=task manager`, `2=home`, `3=back` |
| Clipboard write | `writeClipBoard` | Send text to clipboard |
| Upload file | `uploadFile` | Upload file to device |
| Pull file | `pullFile` | Download file from device to PC |
| App list | `apkList` | Get installed apps |
| Install APK | `installApk` | Install app |
| Uninstall APK | `uninstallApk` | Uninstall app |
| Start app | `startApk` | Start app |
| Stop app | `stopApk` | Stop app |
| IME list | `imeList` | Get installed IMEs |
| Install XiaoWei IME | `installInputIme` | Usually auto-installed |
| Select IME | `selectIme` | Switch current IME |
| Input text | `inputText` | Requires active input page + XiaoWei IME |
| Get tags | `getTags` | All tags |
| Add tag | `addTag` | Create tag |
| Update tag | `updateTag` | Rename tag |
| Remove tag | `removeTag` | Delete tag |
| Add device to tag | `addtagdevice` | Note lowercase `t` in vendor doc |
| Remove device from tag | `removeTagDevice` | Remove from tag |

## Detailed action articles confirmed

### `list`

- Article `401`: `5.2.1 list获取设备列表`
- Request:
  - `action = "list"`
- Response `data` is an array and documents fields including:
  - `width`, `height`
  - `serial`
  - `sort`
  - `name`
  - `onlySerial`
  - `hide`
  - `connectTime`
  - `intranetIp`
  - `sourceWidth`, `sourceHeight`

### `pointerEvent`

- Article `422`: `5.2.19 pointerEvent 屏幕控制`
- Request:
  - `action = "pointerEvent"`
  - `data.type`
  - optional `data.x`, `data.y`
- Vendor type mapping currently documented:
  - `0=down`
  - `1=up`
  - `2=move`
  - `4=wheel up`
  - `5=wheel down`
  - `6=swipe up`
  - `7=swipe down`
  - `8=swipe left`
  - `9=swipe right`
  - `10=click`
- Vendor note:
  - sending only `0` behaves like long-press until `1` is sent

### `inputText`

- Article `413`: `5.2.10 inputText 输入文字`
- Request:
  - `action = "inputText"`
  - `data.content` required
- Constraint:
  - should only be used on an input-capable page

### `screen`

- Article `403`: `5.2.3 screen 截图到相册`
  - title says save to device gallery
  - request action shown as `"Screen"`
- Article `404`: `5.2.4 screenFile 截图到电脑`
  - request action shown as `"Screen"`
  - optional `data.savePath`
  - default path documented as `D:\\Pictures`

## Vendor-doc inconsistencies observed

The Android handbook contains internal contradictions. These must be runtime-verified before changing code assumptions:

- Article `410` title: `5.2.7 startApp 启动应用`
  - but body says `action = "stopApk"` and describes stopping an app
- Article `411` title: `5.2.8 stopApp 停止应用`
  - body also says `action = "stopApk"`
- Article `406` title: `5.2.6 appList 应用列表`
  - body says `action = "pullFile"`
- Article `412` title: `5.2.9 uploadFile 文件上传`
  - body says `action = "writeClipBoard"`

Inference:

- the feature-list article is likely more trustworthy for canonical action names
- the single-action detail pages appear to have copy/paste errors in multiple entries

## Remaining unknowns

- The page article `234` confirms only the common protocol and one `pushEvent` example
- The same page also confirms the common response-code table:
  - `10000`: success
  - `10001`: request failed
- We still need the detailed Android article for `adb` and the correct start/stop app request payload article or runtime confirmation
- Runtime validation on the Windows JP machine is still required
