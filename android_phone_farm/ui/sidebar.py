from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QSlider, QTextEdit, QFrame
)
from PyQt6.QtGui import QFont
from typing import List, Callable
import config

class Sidebar(QFrame):
    def __init__(
        self, 
        parent: QWidget, 
        on_scan_click: Callable[[], None],
        on_sync_toggle: Callable[[bool], None],
        on_size_changed: Callable[[int], None],
        on_proxy_click: Callable[[], None],
        on_proxy_rotation_toggle: Callable[[bool], None],
        initial_proxy_rotation: bool,
        on_register_click: Callable[[], None]
    ):
        super().__init__(parent)
        self.on_scan_click = on_scan_click
        self.on_sync_toggle = on_sync_toggle
        self.on_size_changed = on_size_changed
        self.on_proxy_click = on_proxy_click
        self.on_proxy_rotation_toggle = on_proxy_rotation_toggle
        self.on_register_click = on_register_click

        
        self.app_config = config.load_config()
        
        # Stylesheet for high-end dark sidebar
        self.setObjectName("Sidebar")
        self.setFixedWidth(280)
        self.setStyleSheet("""
            QFrame#Sidebar {
                background-color: #111216;
                border-left: 1px solid #1e2029;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
            }
            QCheckBox {
                color: #e0e0e0;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #4f5466;
                background-color: #1c1d24;
            }
            QCheckBox::indicator:checked {
                background-color: #2ecc71;
                border: 1px solid #2ecc71;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1c1d24;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1a73e8;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 25, 20, 20)
        layout.setSpacing(12)
        
        # 1. Title
        self.title_label = QLabel("⚡ GDP-TOOL-PHONE")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Divider Line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("background-color: #2a2d36; max-height: 1px;")
        layout.addWidget(sep)
        
        # 2. Control Header
        self.control_lbl = QLabel("HỆ THỐNG ĐIỀU KHIỂN")
        self.control_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.control_lbl.setStyleSheet("color: #8f94a6;")
        layout.addWidget(self.control_lbl)
        
        # Scan USB Devices Button
        self.scan_btn = QPushButton("🔄 Quét Thiết Bị USB")
        self.scan_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.scan_btn.setStyleSheet("background-color: #1a73e8; padding: 10px; border-radius: 8px;")
        self.scan_btn.clicked.connect(self.on_scan_click)
        layout.addWidget(self.scan_btn)
        
        # Proxy & Data Manager Button
        self.proxy_btn = QPushButton("🔌 Quản Lý Proxy & Data")
        self.proxy_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.proxy_btn.setStyleSheet("background-color: #8e44ad; padding: 10px; border-radius: 8px;")
        self.proxy_btn.clicked.connect(self.on_proxy_click)
        layout.addWidget(self.proxy_btn)
        
        # Register Bot Button
        self.register_btn = QPushButton("🚀 Bắt đầu Tạo tài khoản")
        self.register_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.register_btn.setStyleSheet("background-color: #27ae60; padding: 10px; border-radius: 8px;")
        self.register_btn.clicked.connect(self.on_register_click)
        layout.addWidget(self.register_btn)

        
        # 3. Switches
        self.proxy_rotation_switch = QCheckBox("Xoay Proxy Tự Động")
        self.proxy_rotation_switch.setChecked(initial_proxy_rotation)
        self.proxy_rotation_switch.toggled.connect(self._on_proxy_rotation_toggled)
        layout.addWidget(self.proxy_rotation_switch)
        
        self.sync_switch = QCheckBox("Bật Đồng Bộ (Sync)")
        self.sync_switch.setEnabled(False)
        self.sync_switch.toggled.connect(self._on_sync_toggled)
        layout.addWidget(self.sync_switch)
        
        # Divider Line 2
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #2a2d36; max-height: 1px;")
        layout.addWidget(sep2)
        
        # 4. Device Size Control
        self.size_lbl = QLabel("KÍCH THƯỚC ĐIỆN THOẠI")
        self.size_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.size_lbl.setStyleSheet("color: #8f94a6;")
        layout.addWidget(self.size_lbl)
        
        current_width = self.app_config.get("card_width", 200)
        self.size_val_lbl = QLabel(f"🔍 Chiều rộng: {current_width}px")
        self.size_val_lbl.setFont(QFont("Segoe UI", 10))
        self.size_val_lbl.setStyleSheet("color: #b0b3c0;")
        layout.addWidget(self.size_val_lbl)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(120, 350)
        self.size_slider.setValue(current_width)
        self.size_slider.valueChanged.connect(self._on_slider_value_changed)
        self.size_slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self.size_slider)
        
        # Divider Line 3
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("background-color: #2a2d36; max-height: 1px;")
        layout.addWidget(sep3)
        
        # 5. System Log Box
        self.info_lbl = QLabel("TRẠNG THÁI HỆ THỐNG")
        self.info_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.info_lbl.setStyleSheet("color: #8f94a6;")
        layout.addWidget(self.info_lbl)
        
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setFont(QFont("Consolas", 10))
        self.info_box.setStyleSheet("""
            background-color: #0c0d12;
            color: #57f287;
            border: 1px solid #1e2029;
            border-radius: 8px;
            padding: 5px;
        """)
        self.info_box.setText("Hệ thống: Sẵn sàng.\nHãy kết nối điện thoại qua cổng USB và bấm nút quét để bắt đầu.")
        layout.addWidget(self.info_box)
        
        # 6. Footer
        self.footer_lbl = QLabel("GDP-tool-phone")
        self.footer_lbl.setFont(QFont("Segoe UI", 8))
        self.footer_lbl.setStyleSheet("color: #4f5466;")
        self.footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.footer_lbl)

    def update_device_list(self, serials: List[str], active_streams: List[str]):
        """Update system metrics and enable/disable sync mode checkbox."""
        if not active_streams:
            self.sync_switch.setEnabled(False)
            self.sync_switch.setChecked(False)
        else:
            self.sync_switch.setEnabled(True)
            
        self.update_log_info(f"Tổng thiết bị USB: {len(serials)}\nĐang stream màn hình: {len(active_streams)}")

    def update_log_info(self, text: str):
        """Append or set system console logging message thread-safely."""
        self.info_box.setText(text)
        # Scroll to bottom
        self.info_box.verticalScrollBar().setValue(self.info_box.verticalScrollBar().maximum())

    def _on_sync_toggled(self, checked: bool):
        self.on_sync_toggle(checked)

    def _on_proxy_rotation_toggled(self, checked: bool):
        self.on_proxy_rotation_toggle(checked)

    def _on_slider_value_changed(self, value: int):
        self.size_val_lbl.setText(f"🔍 Chiều rộng: {value}px")

    def _on_slider_released(self):
        val = self.size_slider.value()
        self.app_config["card_width"] = val
        config.save_config(self.app_config)
        self.on_size_changed(val)
