from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QCheckBox, QLineEdit, QSpinBox, QMessageBox
)
import logging
import threading
from utils import db_manager as db
from adb_handler import ADBHandler

class ProxyManagerWindow(QDialog):
    # Signals for thread-safe GUI updates
    reload_signal = pyqtSignal()
    message_signal = pyqtSignal(str, str, str) # type, title, message

    def __init__(self, parent, adb_handler: ADBHandler):
        super().__init__(parent)
        self.parent = parent
        self.adb_handler = adb_handler
        
        self.setWindowTitle("Quản lý Proxy & Đo lường Data")
        self.resize(850, 600)
        self.setMinimumSize(750, 500)
        self.setModal(True)
        
        db.init_db()
        
        # Connect signals
        self.reload_signal.connect(self._on_reload_ui)
        self.message_signal.connect(self._on_show_message)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)
        
        # 1. Title Header
        self.title_label = QLabel("🔌 MODULE QUẢN LÝ PROXY & ĐO LƯỜNG DUNG LƯỢNG DATA")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0; padding: 10px; background-color: #18181c; border-radius: 4px;")
        self.main_layout.addWidget(self.title_label)
        
        # 2. Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2a2d36; background: #1e1e24; border-radius: 4px; }
            QTabBar::tab { background: #18181c; color: #a0a0a0; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #1a73e8; color: white; font-weight: bold; }
        """)
        self.main_layout.addWidget(self.tabs)
        
        # Build Tabs
        self.tab_pool = QWidget()
        self.tab_config = QWidget()
        self.tab_data = QWidget()
        
        self.tabs.addTab(self.tab_pool, "Proxy Pool")
        self.tabs.addTab(self.tab_config, "Cấu hình & Phân phối")
        self.tabs.addTab(self.tab_data, "Dung lượng Data")
        
        self._build_pool_tab()
        self._build_config_tab()
        self._build_data_tab()
        
        # Load initial data
        self.reload_proxy_list()
        self.load_config()
        self.reload_data_usage_list()

    # ==========================================
    # TAB 1: PROXY POOL
    # ==========================================
    def _build_pool_tab(self):
        layout = QHBoxLayout(self.tab_pool)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Left Panel (Input TextArea & Buttons)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.input_lbl = QLabel("Dán danh sách Proxy thô (Dòng: IP:Port:User:Pass):")
        self.input_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        left_layout.addWidget(self.input_lbl)
        
        self.textarea = QTextEdit()
        self.textarea.setStyleSheet("background-color: #0a0a0d; color: #2ecc71; font-family: 'Consolas'; font-size: 12px; border: 1px solid #2a2d36; border-radius: 4px;")
        left_layout.addWidget(self.textarea)
        
        btn_layout = QHBoxLayout()
        self.btn_import = QPushButton("Nhập Proxy vào Pool")
        self.btn_import.setStyleSheet("background-color: #1a73e8; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_import.clicked.connect(self.import_proxies)
        
        self.btn_clear_pool = QPushButton("Xóa sạch Pool")
        self.btn_clear_pool.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_clear_pool.clicked.connect(self.clear_proxy_pool)
        
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_clear_pool)
        left_layout.addLayout(btn_layout)
        
        # Right Panel (Proxy Table)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pool_lbl = QLabel("Danh sách Proxy hiện tại trong Pool:")
        self.pool_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        right_layout.addWidget(self.pool_lbl)
        
        self.proxy_table = QTableWidget()
        self.proxy_table.setColumnCount(3)
        self.proxy_table.setHorizontalHeaderLabels(["Proxy Address", "Trạng thái", "Máy chiếm giữ"])
        self.proxy_table.setStyleSheet("""
            QTableWidget { background-color: #0a0a0d; color: #e0e0e0; border: 1px solid #2a2d36; }
            QHeaderView::section { background-color: #18181c; color: #a0a0a0; padding: 5px; border: 1px solid #2a2d36; font-weight: bold; }
        """)
        self.proxy_table.horizontalHeader().setSectionResizeMode(QHeaderView.SectionResizeMode.Stretch)
        self.proxy_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self.proxy_table)
        
        layout.addWidget(left_panel, 2)
        layout.addWidget(right_panel, 3)

    def import_proxies(self):
        text = self.textarea.toPlainText()
        if text.strip():
            inserted, total = db.import_proxies(text)
            self.textarea.clear()
            self.reload_proxy_list()
            QMessageBox.information(self, "Thành công", f"Đã nhập thành công {inserted}/{total} proxy mới!")

    def clear_proxy_pool(self):
        reply = QMessageBox.question(
            self, "Xác nhận", 
            "Bạn có chắc chắn muốn xóa toàn bộ danh sách Proxy và giải phóng liên kết?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            active_serials = list(self.parent.grid_view.cards.keys())
            for s in active_serials:
                self.adb_handler.clear_system_proxy(s)
                
            db.clear_proxy_pool()
            self.reload_proxy_list()
            QMessageBox.information(self, "Hoàn tất", "Đã xóa sạch danh sách Proxy Pool.")

    def reload_proxy_list(self):
        self.proxy_table.setRowCount(0)
        proxies = db.get_all_proxies()
        
        for p in proxies:
            row = self.proxy_table.rowCount()
            self.proxy_table.insertRow(row)
            
            addr_item = QTableWidgetItem(f"{p['ip']}:{p['port']}")
            
            status_text = p['status'].upper()
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p['status'] == 'live':
                status_item.setForeground(Qt.GlobalColor.green)
            else:
                status_item.setForeground(Qt.GlobalColor.red)
                
            phone_text = p['assigned_phone_id'] if p['assigned_phone_id'] else "--- Rảnh ---"
            phone_item = QTableWidgetItem(phone_text)
            phone_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p['assigned_phone_id']:
                phone_item.setForeground(Qt.GlobalColor.cyan)
            else:
                phone_item.setForeground(Qt.GlobalColor.gray)
                
            self.proxy_table.setItem(row, 0, addr_item)
            self.proxy_table.setItem(row, 1, status_item)
            self.proxy_table.setItem(row, 2, phone_item)

    # ==========================================
    # TAB 2: CẤU HÌNH & PHÂN PHỐI
    # ==========================================
    def _build_config_tab(self):
        layout = QVBoxLayout(self.tab_config)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        cfg_panel = QWidget()
        cfg_panel.setStyleSheet("background-color: #1e1e24; border-radius: 8px; padding: 15px;")
        cfg_layout = QVBoxLayout(cfg_panel)
        
        # Chế độ phân bổ
        cfg_layout.addWidget(QLabel("<b>Chế độ phân bổ IP Proxy:</b>"))
        self.mode_group = QButtonGroup(self)
        self.radio_static = QRadioButton("Cố định tuần tự (Static Binding - Phone 1: Proxy 1, Phone 2: Proxy 2...)")
        self.radio_dynamic = QRadioButton("Ngẫu nhiên tự động (Dynamic Random Pooling - Bốc ngẫu nhiên khi chạy và nhả ra khi xong)")
        self.mode_group.addButton(self.radio_static, 0)
        self.mode_group.addButton(self.radio_dynamic, 1)
        cfg_layout.addWidget(self.radio_static)
        cfg_layout.addWidget(self.radio_dynamic)
        
        # Hẹn giờ xoay
        self.chk_rot = QCheckBox("Tự động hẹn giờ xoay/thay đổi IP định kỳ")
        cfg_layout.addWidget(self.chk_rot)
        
        rot_time_layout = QHBoxLayout()
        rot_time_layout.addWidget(QLabel("Thời gian xoay IP:"))
        self.sb_rot_time = QSpinBox()
        self.sb_rot_time.setRange(1, 1440)
        self.sb_rot_time.setValue(10)
        self.sb_rot_time.setStyleSheet("background-color: #0a0a0d; color: white;")
        rot_time_layout.addWidget(self.sb_rot_time)
        rot_time_layout.addWidget(QLabel("phút/lần"))
        rot_time_layout.addStretch()
        cfg_layout.addLayout(rot_time_layout)
        
        # API provider link
        cfg_layout.addWidget(QLabel("<b>Link API đổi IP nhà cung cấp proxy bên ngoài (nếu có):</b>"))
        self.entry_api = QLineEdit()
        self.entry_api.setPlaceholderText("http://api.proxyprovider.com/rotate?key=...")
        self.entry_api.setStyleSheet("background-color: #0a0a0d; color: white; padding: 5px; border-radius: 4px;")
        cfg_layout.addWidget(self.entry_api)
        
        # Data limit
        quota_layout = QHBoxLayout()
        quota_layout.addWidget(QLabel("<b>Hạn mức Data giới hạn của mỗi điện thoại:</b>"))
        self.sb_quota = QSpinBox()
        self.sb_quota.setRange(1, 102400)
        self.sb_quota.setValue(1024)
        self.sb_quota.setStyleSheet("background-color: #0a0a0d; color: white;")
        quota_layout.addWidget(self.sb_quota)
        quota_layout.addWidget(QLabel("MB/thiết bị/ngày"))
        quota_layout.addStretch()
        cfg_layout.addLayout(quota_layout)
        
        # Save Button
        self.btn_save_config = QPushButton("Lưu Cấu Hình Proxy & Áp Dụng")
        self.btn_save_config.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px; border-radius: 4px;")
        self.btn_save_config.clicked.connect(self.save_config)
        cfg_layout.addWidget(self.btn_save_config)
        
        layout.addWidget(cfg_panel)
        layout.addStretch()

    def load_config(self):
        mode = db.get_config("mode", "static")
        if mode == "static":
            self.radio_static.setChecked(True)
        else:
            self.radio_dynamic.setChecked(True)
            
        self.chk_rot.setChecked(db.get_config("rotation_enabled", "0") == "1")
        
        try:
            self.sb_rot_time.setValue(int(db.get_config("rotation_interval_mins", "10")))
        except ValueError:
            self.sb_rot_time.setValue(10)
            
        self.entry_api.setText(db.get_config("api_link", ""))
        
        try:
            self.sb_quota.setValue(int(db.get_config("quota_limit_mb", "1024")))
        except ValueError:
            self.sb_quota.setValue(1024)

    def save_config(self):
        mode = "static" if self.radio_static.isChecked() else "dynamic"
        db.set_config("mode", mode)
        db.set_config("rotation_enabled", "1" if self.chk_rot.isChecked() else "0")
        
        interval = self.sb_rot_time.value()
        db.set_config("rotation_interval_mins", interval)
        
        db.set_config("api_link", self.entry_api.text().strip())
        
        quota = self.sb_quota.value()
        db.set_config("quota_limit_mb", quota)
        
        # Apply config back to parent main window
        self.parent.is_proxy_rotation_enabled = self.chk_rot.isChecked()
        self.parent.proxy_rotation_interval = interval * 60
        self.parent.api_rotation_link = self.entry_api.text().strip()
        
        # Trigger proxy allocation
        active_serials = list(self.parent.grid_view.cards.keys())
        self.parent.allocate_proxies_to_devices(active_serials)
        
        self.reload_proxy_list()
        QMessageBox.information(self, "Thành công", "Đã lưu và áp dụng cấu hình Proxy thành công!")

    # ==========================================
    # TAB 3: DUNG LƯỢNG DATA
    # ==========================================
    def _build_data_tab(self):
        layout = QVBoxLayout(self.tab_data)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header Controls
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.data_lbl = QLabel("Bảng đo lường lưu lượng mạng tiêu thụ qua adb:")
        self.data_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        header_layout.addWidget(self.data_lbl)
        
        header_layout.addStretch()
        
        self.btn_refresh_data = QPushButton("Làm mới")
        self.btn_refresh_data.setStyleSheet("background-color: #1a73e8; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_refresh_data.clicked.connect(self.reload_data_usage_list)
        
        self.btn_reset_data = QPushButton("Reset Số Liệu Đo Lường")
        self.btn_reset_data.setStyleSheet("background-color: #c0392b; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_reset_data.clicked.connect(self.reset_data_usage)
        
        header_layout.addWidget(self.btn_refresh_data)
        header_layout.addWidget(self.btn_reset_data)
        
        layout.addWidget(header_widget)
        
        # Table of Data Usages
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(6)
        self.data_table.setHorizontalHeaderLabels([
            "Thiết bị (Serial)", "Đã dùng (Data Used)", "Hạn mức (Quota)",
            "IP Proxy Hiện Tại", "Trạng thái Mạng", "Thao tác"
        ])
        self.data_table.setStyleSheet("""
            QTableWidget { background-color: #0a0a0d; color: #e0e0e0; border: 1px solid #2a2d36; }
            QHeaderView::section { background-color: #18181c; color: #a0a0a0; padding: 5px; border: 1px solid #2a2d36; font-weight: bold; }
        """)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.SectionResizeMode.Stretch)
        self.data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.data_table)

    def reset_data_usage(self):
        reply = QMessageBox.question(
            self, "Xác nhận", 
            "Bạn có muốn reset số liệu dung lượng mạng đã tiêu thụ của toàn bộ các máy về 0?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.reset_data_usage()
            self.reload_data_usage_list()
            QMessageBox.information(self, "Hoàn thành", "Đã khởi tạo lại toàn bộ số liệu đo lường.")

    def reload_data_usage_list(self):
        self.data_table.setRowCount(0)
        data_usages = db.get_all_data_usages()
        active_serials = list(self.parent.grid_view.cards.keys())
        
        all_serials = list(set(active_serials + [d["phone_id"] for d in data_usages]))
        
        for idx, serial in enumerate(sorted(all_serials)):
            row = self.data_table.rowCount()
            self.data_table.insertRow(row)
            
            # Serial
            self.data_table.setItem(row, 0, QTableWidgetItem(serial))
            
            # Data records
            db_record = next((d for d in data_usages if d["phone_id"] == serial), None)
            total_bytes = db_record["total_bytes_used"] if db_record else 0
            is_blocked = db_record["is_blocked"] if db_record else 0
            
            mb_used = total_bytes / (1024 * 1024)
            data_str = f"{mb_used/1024:.2f} GB" if mb_used >= 1024 else f"{mb_used:.2f} MB"
            
            data_item = QTableWidgetItem(data_str)
            data_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if total_bytes > 0:
                data_item.setForeground(Qt.GlobalColor.green)
            self.data_table.setItem(row, 1, data_item)
            
            # Quota
            quota_mb = int(db.get_config("quota_limit_mb", "1024"))
            quota_str = f"{quota_mb} MB" if quota_mb < 1024 else f"{quota_mb/1024:.1f} GB"
            quota_item = QTableWidgetItem(quota_str)
            quota_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.data_table.setItem(row, 2, quota_item)
            
            # Proxy
            proxy = db.get_assigned_proxy(serial)
            proxy_str = f"{proxy['ip']}:{proxy['port']}" if proxy else "--- Trực tiếp ---"
            proxy_item = QTableWidgetItem(proxy_str)
            proxy_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if proxy:
                proxy_item.setForeground(Qt.GlobalColor.cyan)
            self.data_table.setItem(row, 3, proxy_item)
            
            # Network Status
            net_status = "BỊ KHÓA" if is_blocked == 1 else "Bình thường"
            status_item = QTableWidgetItem(net_status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_blocked == 1:
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status_item.setForeground(Qt.GlobalColor.green)
            self.data_table.setItem(row, 4, status_item)
            
            # Action Button
            if serial in active_serials:
                btn_rotate = QPushButton("Đổi IP")
                btn_rotate.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; max-width: 60px;")
                btn_rotate.clicked.connect(lambda checked, s=serial: self.force_rotate_device_ip(s))
                self.data_table.setCellWidget(row, 5, btn_rotate)
            else:
                self.data_table.setItem(row, 5, QTableWidgetItem("Offline"))

    def force_rotate_device_ip(self, serial: str):
        """Trigger proxy rotate asynchronously."""
        def run_rotate():
            success = self.parent.rotate_device_ip(serial, force_api_call=True)
            self.reload_signal.emit()
            if success:
                self.message_signal.emit("info", "Thành công", f"Đã hoàn thành xoay IP cho thiết bị {serial}!")
            else:
                self.message_signal.emit("warn", "Cảnh báo", f"Lỗi xoay IP hoặc không tìm thấy proxy rảnh cho {serial}!")
                
        threading.Thread(target=run_rotate, daemon=True).start()

    def _on_reload_ui(self):
        self.reload_proxy_list()
        self.reload_data_usage_list()

    def _on_show_message(self, msg_type: str, title: str, message: str):
        if msg_type == "info":
            QMessageBox.information(self, title, message)
        else:
            QMessageBox.warning(self, title, message)
