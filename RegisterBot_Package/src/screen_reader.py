"""
ScreenReader — Đọc và phân tích UI hierarchy của thiết bị Android.

Dùng `adb shell uiautomator dump` để lấy XML cây UI đang hiển thị,
parse XML để tìm elements theo text/resource-id, verify state, và
đợi UI thay đổi thay vì sleep cứng.

Không cần thêm dependency — chỉ dùng stdlib (xml.etree, re, asyncio).
"""

import asyncio
import logging
import math
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

    def _parse_nodes(self, xml_str: str) -> list[dict]:
        """Parse tất cả node trong XML thành list dict có attrs + bounds."""
        if not xml_str:
            return []
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            log.warning(f"[ScreenReader] XML parse error in _parse_nodes: {e}")
            return []

        nodes = []
        for node in root.iter("node"):
            bounds = self.parse_bounds(node.get("bounds", ""))
            if not bounds:
                continue
            nodes.append({
                **bounds,
                "text": node.get("text", "") or "",
                "content_desc": node.get("content-desc", "") or "",
                "resource_id": node.get("resource-id", "") or "",
                "class": node.get("class", "") or "",
                "package": node.get("package", "") or "",
                "clickable": node.get("clickable") == "true",
                "enabled": node.get("enabled") != "false",
                "focusable": node.get("focusable") == "true",
                "focused": node.get("focused") == "true",
                "selected": node.get("selected") == "true",
                "password": node.get("password") == "true",
                "raw_bounds": node.get("bounds", ""),
            })
        return nodes

    def _text_match_score(self, value: str, patterns: list[str], partial: bool = True) -> float:
        value_l = (value or "").strip().lower()
        if not value_l or not patterns:
            return 0.0
        score = 0.0
        for pattern in patterns:
            p = pattern.strip().lower()
            if not p:
                continue
            if value_l == p:
                score = max(score, 100.0)
            elif partial and p in value_l:
                ratio = min(1.0, len(p) / max(1, len(value_l)))
                score = max(score, 70.0 + ratio * 20.0)
        return score

    def find_best_element(
        self,
        xml_str: str,
        texts: list[str] = None,
        resource_ids: list[str] = None,
        classes: list[str] = None,
        clickable: Optional[bool] = None,
        enabled: Optional[bool] = True,
        focusable: Optional[bool] = None,
        partial: bool = True,
        preferred_region: tuple[float, float, float, float] = None,
    ) -> Optional[dict]:
        """
        Tìm node tốt nhất theo scoring thay vì lấy node đầu tiên.
        preferred_region: (x1_pct, x2_pct, y1_pct, y2_pct) để boost ứng viên nằm đúng vùng.
        """
        nodes = self._parse_nodes(xml_str)
        if not nodes:
            return None
        screen_w = max(node["x2"] for node in nodes)
        screen_h = max(node["y2"] for node in nodes)

        best = None
        best_score = -1.0
        for node in nodes:
            if enabled is not None and node["enabled"] != enabled:
                continue
            if clickable is not None and node["clickable"] != clickable:
                continue
            if focusable is not None and node["focusable"] != focusable:
                continue

            score = 0.0
            score += self._text_match_score(node["text"], texts or [], partial=partial)
            score += self._text_match_score(node["content_desc"], texts or [], partial=partial) * 0.9

            if resource_ids:
                rid = node["resource_id"].lower()
                for pattern in resource_ids:
                    p = pattern.lower()
                    if rid == p:
                        score += 90.0
                    elif p in rid:
                        score += 60.0

            if classes:
                cls = node["class"].lower()
                for pattern in classes:
                    p = pattern.lower()
                    if cls == p:
                        score += 35.0
                    elif p in cls:
                        score += 20.0

            if node["clickable"]:
                score += 12.0
            if node["enabled"]:
                score += 8.0
            if node["focusable"]:
                score += 8.0
            if node["focused"]:
                score += 5.0

            # Penalty cho node quá nhỏ
            if node["width"] < 20 or node["height"] < 20:
                score -= 20.0

            if preferred_region:
                x1_pct, x2_pct, y1_pct, y2_pct = preferred_region
                x_pct = (node["cx"] / max(1, screen_w)) * 100.0
                y_pct = (node["cy"] / max(1, screen_h)) * 100.0
                if (
                    x1_pct <= x_pct <= x2_pct and
                    y1_pct <= y_pct <= y2_pct
                ):
                    score += 15.0

            if score > best_score:
                best_score = score
                best = {**node, "score": round(score, 2)}

        return best if best_score > 0 else None

    def find_input_near_label(
        self,
        xml_str: str,
        label_texts: list[str],
        max_distance: float = 500.0,
        preferred_region: tuple[float, float, float, float] = None,
        min_score: float = 0.0,
        prefer_password: bool = False,
    ) -> Optional[dict]:
        """
        Tìm EditText tốt nhất gần label. Dùng cho email/name/password fields.
        """
        nodes = self._parse_nodes(xml_str)
        if not nodes:
            return None

        label = self.find_best_element(
            xml_str,
            texts=label_texts,
            clickable=None,
            enabled=True,
            partial=True,
        )
        if not label:
            return None

        best = None
        best_score = -1.0
        for node in nodes:
            cls = node["class"].lower()
            if "edittext" not in cls:
                continue
            if not node["enabled"]:
                continue

            dy = node["cy"] - label["cy"]
            dx = abs(node["cx"] - label["cx"])
            distance = math.hypot(dx, max(0, dy))
            screen_w = max(node_["x2"] for node_ in nodes)
            screen_h = max(node_["y2"] for node_ in nodes)
            x_pct = (node["cx"] / max(1, screen_w)) * 100.0
            y_pct = (node["cy"] / max(1, screen_h)) * 100.0

            score = 0.0
            if dy >= -30:
                score += 40.0
            else:
                score -= 30.0
            score += max(0.0, 40.0 - min(distance, max_distance) / max_distance * 40.0)
            if node["focusable"]:
                score += 10.0
            if node["clickable"]:
                score += 8.0
            if dx < 150:
                score += 8.0
            if preferred_region:
                x1_pct, x2_pct, y1_pct, y2_pct = preferred_region
                if x1_pct <= x_pct <= x2_pct and y1_pct <= y_pct <= y2_pct:
                    score += 25.0
                else:
                    score -= 35.0
            if prefer_password:
                if node["password"]:
                    score += 35.0
                else:
                    score -= 15.0
                if y_pct < 20.0:
                    score -= 40.0

            if score > best_score:
                best_score = score
                best = {
                    **node,
                    "score": round(score, 2),
                    "anchor_text": label["text"] or label["content_desc"],
                    "x_pct": round(x_pct, 2),
                    "y_pct": round(y_pct, 2),
                }

        if best and best["score"] >= min_score:
            return best
        return None

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
        return self.find_best_element(xml_str, texts=texts, partial=True)

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
