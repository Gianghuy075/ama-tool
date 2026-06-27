import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add search path for packages
curr_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(curr_dir, "..", "RegisterBot_Package"))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import PyQt6 components in headless/mock mode or just import MainWindow for testing
from PyQt6.QtWidgets import QApplication
# Create a dummy QApp if needed for signals
app = QApplication.instance() or QApplication([])

from ui.main_window import MainWindow

class TestDirectRegistrationFlow(unittest.TestCase):
    @patch('src.gmail_otp.GmailOTPReader')
    @patch('src.excel_handler.ExcelHandler')
    def test_registration_flow(self, mock_excel_class, mock_gmail_class):
        # 1. Setup mock Excel Handler
        mock_excel = MagicMock()
        mock_excel.read_rows.return_value = [
            {"name": "Test User", "email": "test+may03@gmail.com", "password": "Password123!"}
        ]
        mock_excel_class.return_value = mock_excel

        # 2. Setup mock Gmail OTP Reader
        mock_gmail = MagicMock()
        mock_gmail.fetch_otp.return_value = "741085"
        mock_gmail_class.return_value = mock_gmail

        # 3. Setup mock MainWindow & adb_handler
        window = MainWindow()
        window.log_signal = MagicMock() # Mock signal emit

        mock_device = MagicMock()
        mock_device.screencap.return_value = b"fake_screenshot_bytes"
        mock_device.shell.return_value = "success"

        # Mock adb_handler methods
        window.adb_handler = MagicMock()
        window.adb_handler.device_cache = {"mock_serial": mock_device}

        # 4. Run the direct flow
        row = {"name": "Test User", "email": "test+may03@gmail.com", "password": "Password123!"}
        
        # We patch time.sleep to run instantly during test
        with patch('time.sleep', return_value=None):
            result = window._execute_registration_flow_direct(mock_device, "mock_serial", row)

        # 5. Assertions
        print("\n--- Test Flow Execution Results ---")
        print(f"Status: {result['status']}")
        # Encode or skip print of unicode to avoid cp1252 errors on Windows console
        try:
            print(f"Note: {result['note'].encode('utf-8')}")
        except Exception:
            pass
        print("Logged steps count:", len(window.log_signal.emit.call_args_list))

        self.assertEqual(result["status"], "SUCCESS")

        self.assertEqual(result["note"], "Đăng ký thành công")

        # Verify correct shell commands were sent to the device
        # Step 1: clear cache & open app
        mock_device.shell.assert_any_call("pm clear org.mozilla.firefox")
        mock_device.shell.assert_any_call("monkey -p org.mozilla.firefox -c android.intent.category.LAUNCHER 1")
        mock_device.shell.assert_any_call("am force-stop org.mozilla.firefox")

        # Verify click coordinate calls
        self.assertTrue(window.adb_handler.tap.called)

if __name__ == '__main__':
    unittest.main()
