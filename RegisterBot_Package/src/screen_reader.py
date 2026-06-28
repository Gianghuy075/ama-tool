"""
ScreenReader — Đọc và phân tích UI hierarchy của thiết bị Android.

Dùng `adb shell uiautomator dump` để lấy XML cây UI đang hiển thị,
parse XML để tìm elements theo text/resource-id, verify state, và
đợi UI thay đổi thay vì sleep cứng.

Không cần thêm dependency — chỉ dùng stdlib (xml.etree, re, asyncio).
"""

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional

log = logging.getLogger(__name__)


class ScreenReader:
    """
    Đọc UI hierarchy từ thiết bị Android qua uiautomator dump.

    Cách dùng:
        sr = ScreenReader(xiaowei_client)
        xml = await sr.dump_ui(device)
        elem = sr.find_element_by_text(xml, "招待をリクエストする")
        if elem:
            await xw.device_click(device, elem["cx"], elem["cy"])
    """

    def __init__(self, xiaowei_client):
        self.xw = xiaowei_client

    # ── Core: Dump UI từ thiết bị ────────────────────────────────────

    async def dump_ui(self, device: str) -> Optional[str]:
        """
        Dump UI hierarchy XML từ thiết bị qua uiautomator.
        Return: XML string hoặc None nếu fail.

        Gọi 2 lệnh ADB liên tiếp:
          1. uiautomator dump /sdcard/ui.xml   → tạo file XML
          2. cat /sdcard/ui.xml               → đọc nội dung
        """
        try:
            # Dump UI tree vào file tạm
            await self.xw.run_adb(device, "uiautomator dump /sdcard/ui.xml")
            await asyncio.sleep(0.3)  # Cho uiautomator kịp ghi file

            # Đọc nội dung file
            xml_str = await self.xw.run_adb_with_output(device, "cat /sdcard/ui.xml")
            if not xml_str:
                log.warning(f"[ScreenReader:{device}] dump_ui: empty response")
                return None

            # Validate XML tối thiểu
            if "<?xml" not in xml_str and "<hierarchy" not in xml_str:
                log.warning(f"[ScreenReader:{device}] dump_ui: invalid XML (len={len(xml_str)})")
                return None

            log.debug(f"[ScreenReader:{device}] dump_ui OK ({len(xml_str)} chars)")
            return xml_str

        except Exception as e:
            log.warning(f"[ScreenReader:{device}] dump_ui error: {e}")
            return None

    # ── Parse: Tìm elements trong XML ────────────────────────────────

    def parse_bounds(self, bounds_str: str) -> Optional[dict]:
        """
        Parse chuỗi bounds "[x1,y1][x2,y2]" → dict tọa độ + center.
        Return: {x1, y1, x2, y2, cx, cy, width, height} hoặc None.
        """
        match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
        if not match:
            return None
        x1 = int(match.group(1))
        y1 = int(match.group(2))
        x2 = int(match.group(3))
        y2 = int(match.group(4))
        return {
            "x1": x1, "y1": y1,
            "x2": x2, "y2": y2,
            "cx": (x1 + x2) // 2,
            "cy": (y1 + y2) // 2,
            "width": x2 - x1,
            "height": y2 - y1,
        }

    def find_element_by_text(self, xml_str: str, text: str, partial: bool = True) -> Optional[dict]:
        """
        Tìm element đầu tiên có text hoặc content-desc matching.

        Args:
            xml_str: XML string từ dump_ui()
            text: text cần tìm
            partial: True = tìm chuỗi con (case-insensitive), False = exact match

        Return: dict bounds+center hoặc None.
        """
        if not xml_str:
            return None
        try:
            root = ET.fromstring(xml_str)
            target = text.lower()
            for node in root.iter("node"):
                node_text = node.get("text", "").lower()
                content_desc = node.get("content-desc", "").lower()
                if partial:
                    match = target in node_text or target in content_desc
                else:
                    match = node_text == target or content_desc == target

                if match:
                    bounds = node.get("bounds", "")
                    result = self.parse_bounds(bounds)
                    if result:
                        log.debug(f"[ScreenReader] Found '{text}' → bounds={bounds} center=({result['cx']},{result['cy']})")
                        return result
        except ET.ParseError as e:
            log.warning(f"[ScreenReader] XML parse error in find_element_by_text: {e}")
        return None

    def find_element_by_resource_id(self, xml_str: str, resource_id: str) -> Optional[dict]:
        """
        Tìm element theo resource-id (stable hơn text — không đổi theo ngôn ngữ).
        """
        if not xml_str:
            return None
        try:
            root = ET.fromstring(xml_str)
            for node in root.iter("node"):
                rid = node.get("resource-id", "")
                if resource_id in rid:
                    bounds = node.get("bounds", "")
                    result = self.parse_bounds(bounds)
                    if result:
                        log.debug(f"[ScreenReader] Found resource-id='{resource_id}' at ({result['cx']},{result['cy']})")
                        return result
        except ET.ParseError as e:
            log.warning(f"[ScreenReader] XML parse error in find_element_by_resource_id: {e}")
        return None

    def find_any_element(self, xml_str: str, texts: list) -> Optional[dict]:
        """
        Tìm element đầu tiên matching bất kỳ text nào trong list.
        Trả về element đầu tiên tìm được.
        """
        for text in texts:
            elem = self.find_element_by_text(xml_str, text)
            if elem:
                log.debug(f"[ScreenReader] find_any_element: matched '{text}'")
                return elem
        return None

    def get_focused_field_text(self, xml_str: str) -> Optional[str]:
        """
        Lấy text của EditText đang có focus (ô input vừa được tap vào).

        Return:
            - String nội dung field nếu lấy được
            - None nếu không tìm thấy focused field
            - "" (empty string) nếu field đang trống
        """
        if not xml_str:
            return None
        try:
            root = ET.fromstring(xml_str)

            # Ưu tiên 1: node đang focused
            for node in root.iter("node"):
                if node.get("focused") == "true":
                    return node.get("text", "")

            # Ưu tiên 2: EditText bất kỳ (lấy cái đầu tiên có text)
            for node in root.iter("node"):
                cls = node.get("class", "")
                if "EditText" in cls:
                    text = node.get("text", "")
                    if text:
                        return text

        except ET.ParseError as e:
            log.warning(f"[ScreenReader] XML parse error in get_focused_field_text: {e}")
        return None

    def has_any_text(self, xml_str: str, texts: list) -> Optional[str]:
        """
        Kiểm tra nhanh xem có text nào trong list đang hiển thị không.
        Return: text đầu tiên tìm thấy, hoặc None.
        Dùng simple string search thay vì parse XML — nhanh hơn cho poll loop.
        """
        if not xml_str:
            return None
        xml_lower = xml_str.lower()
        for text in texts:
            if text.lower() in xml_lower:
                return text
        return None

    # ── Wait: Poll cho đến khi UI thay đổi ──────────────────────────

    async def wait_for_text(
        self,
        device: str,
        texts: list,
        timeout: float = 10.0,
        poll_interval: float = 0.8,
    ) -> Optional[str]:
        """
        Poll UI dump đến khi thấy bất kỳ text nào trong list.

        Args:
            device: serial thiết bị
            texts: list text cần chờ (OR logic — đủ 1 cái là pass)
            timeout: thời gian tối đa (giây)
            poll_interval: khoảng cách giữa mỗi lần poll

        Return: XML string khi tìm thấy text, None nếu timeout.
        """
        start = time.time()
        log.info(f"[ScreenReader:{device}] Waiting for: {texts} (timeout={timeout}s)")

        while time.time() - start < timeout:
            xml = await self.dump_ui(device)
            if xml:
                found = self.has_any_text(xml, texts)
                if found:
                    elapsed = time.time() - start
                    log.info(f"[ScreenReader:{device}] Found '{found}' after {elapsed:.1f}s")
                    return xml
            await asyncio.sleep(poll_interval)

        elapsed = time.time() - start
        log.warning(f"[ScreenReader:{device}] Timeout {elapsed:.1f}s waiting for {texts}")
        return None

    async def wait_for_ui_change(
        self,
        device: str,
        prev_xml: Optional[str],
        timeout: float = 8.0,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """
        Poll đến khi UI thay đổi so với prev_xml.
        Dùng khi không biết text kỳ vọng — chỉ cần biết "có gì đó đã thay đổi".

        Return: XML mới khi UI đã đổi, None nếu timeout hoặc prev_xml là None.
        """
        if not prev_xml:
            # Không có baseline → dump và return ngay
            return await self.dump_ui(device)

        start = time.time()
        while time.time() - start < timeout:
            new_xml = await self.dump_ui(device)
            if new_xml and new_xml != prev_xml:
                elapsed = time.time() - start
                log.debug(f"[ScreenReader:{device}] UI changed after {elapsed:.1f}s")
                return new_xml
            await asyncio.sleep(poll_interval)

        log.warning(f"[ScreenReader:{device}] Timeout {timeout}s — UI did not change")
        return None
