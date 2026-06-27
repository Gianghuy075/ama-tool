"""
Excel Handler – đọc accounts từ input.xlsx, ghi kết quả ra output.xlsx
"""

import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

log = logging.getLogger(__name__)

# Màu sắc
COLOR_HEADER_BG  = "1E3A5F"   # Navy
COLOR_HEADER_FG  = "FFFFFF"
COLOR_SUCCESS_BG = "D6F4E1"   # Green tint
COLOR_FAILED_BG  = "FAD7D7"   # Red tint
COLOR_ALT_ROW    = "F5F8FF"   # Light blue alternating


class ExcelHandler:
    def __init__(self, input_path: str):
        self.input_path = Path(input_path)

    def read_rows(self) -> list[dict]:
        """Read accounts from Excel. Expects columns: name, email, password"""
        if not self.input_path.exists():
            log.warning(f"{self.input_path} not found – creating sample file...")
            self._create_sample_input()

        df = pd.read_excel(self.input_path, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]

        required = {"name", "email", "password"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Input Excel thiếu cột: {missing}")

        df = df.dropna(subset=["email"])
        
        # Đọc thêm cột proxy nếu tồn tại trong Excel
        cols = ["name", "email", "password"]
        if "proxy" in df.columns:
            cols.append("proxy")
            
        df = df.fillna("")
        rows = df[cols].to_dict("records")
        log.info(f"Đọc được {len(rows)} dòng từ {self.input_path}")
        return rows

    def write_results(self, results: list[dict], output_path: str):
        """Write results to a styled Excel file."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Results"

        headers = ["#", "Name", "Email", "Status", "Note", "Timestamp"]
        col_widths = [5, 20, 30, 12, 40, 22]

        # ── Header row ──────────────────────────────────────────────────
        for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True, color=COLOR_HEADER_FG, size=11, name="Arial")
            cell.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = self._border()
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.row_dimensions[1].height = 28
        ws.freeze_panes = "A2"

        # ── Data rows ────────────────────────────────────────────────────
        success_count = 0
        for i, r in enumerate(results, 1):
            row_num = i + 1
            is_success = r["status"] == "SUCCESS"
            if is_success:
                success_count += 1

            bg_color = COLOR_SUCCESS_BG if is_success else COLOR_FAILED_BG
            if not (is_success) and i % 2 == 0:
                bg_color = COLOR_ALT_ROW  # alternating for failed rows

            values = [i, r["name"], r["email"], r["status"], r["note"], r["timestamp"]]
            for col_idx, value in enumerate(values, 1):
                cell = ws.cell(row=row_num, column=col_idx, value=value)
                cell.fill = PatternFill("solid", fgColor=bg_color)
                cell.font = Font(size=10, name="Arial",
                                  bold=(col_idx == 4),
                                  color=("006400" if is_success else "8B0000") if col_idx == 4 else "000000")
                cell.alignment = Alignment(
                    horizontal="center" if col_idx in (1, 4) else "left",
                    vertical="center",
                    wrap_text=(col_idx == 5),
                )
                cell.border = self._border()
            ws.row_dimensions[row_num].height = 20

        # ── Summary section ──────────────────────────────────────────────
        total = len(results)
        summary_row = total + 3
        ws.cell(row=summary_row, column=1, value="SUMMARY").font = Font(bold=True, size=11, name="Arial")
        ws.cell(row=summary_row, column=2, value=f"Total: {total}")
        ws.cell(row=summary_row, column=3, value=f"Success: {success_count}").font = Font(color="006400", bold=True)
        ws.cell(row=summary_row, column=4, value=f"Failed: {total - success_count}").font = Font(color="8B0000", bold=True)
        ws.cell(row=summary_row, column=5, value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ws.cell(row=summary_row, column=6, value=f"Rate: {success_count/total*100:.1f}%" if total else "0%")

        # ── Auto-filter ──────────────────────────────────────────────────
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{total+1}"

        wb.save(output_path)
        log.info(f"📊 Đã lưu kết quả: {output_path} ({success_count}/{total} thành công)")

    def _border(self):
        thin = Side(style="thin", color="CCCCCC")
        return Border(left=thin, right=thin, top=thin, bottom=thin)

    def _create_sample_input(self):
        """Create a sample accounts.xlsx for first-time use."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Accounts"

        headers = ["name", "email", "password"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1E3A5F")

        sample_data = [
            ["Nguyen Van A", "testa@example.com", "Password123!"],
            ["Tran Thi B",   "testb@example.com", "Password456!"],
            ["Le Van C",     "testc@example.com", "Password789!"],
        ]
        for row in sample_data:
            ws.append(row)

        for col_idx, width in enumerate([20, 30, 20], 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        wb.save(self.input_path)
        log.info(f"📄 Tạo file mẫu: {self.input_path}")

    @staticmethod
    def parse_excel(file_path: str) -> list[dict]:
        """Parse Excel file and return list of dictionaries with normalized columns: name, email, password, proxy.
        Attempts smart mapping of column headers.
        """
        import pandas as pd
        df = pd.read_excel(file_path, dtype=str)
        df = df.fillna("") # Replace NaN with empty string
        
        # Normalize headers to string and strip
        df.columns = [str(c).strip() for c in df.columns]
        
        # Smart header mapping
        mapped_columns = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ["name", "tên", "tên hiển thị", "display name", "username", "họ tên", "ho ten", "fullname"]:
                mapped_columns[col] = "name"
            elif col_lower in ["email", "mail", "gmail", "tài khoản", "tai khoang", "address"]:
                mapped_columns[col] = "email"
            elif col_lower in ["password", "mật khẩu", "mat khau", "pass", "pwd"]:
                mapped_columns[col] = "password"
            elif col_lower in ["proxy", "ip", "socks5", "socks", "http"]:
                mapped_columns[col] = "proxy"
                
        # Rename identified columns
        df = df.rename(columns=mapped_columns)
        
        # Check standard columns, fill missing ones with empty string
        for std_col in ["name", "email", "password", "proxy"]:
            if std_col not in df.columns:
                df[std_col] = ""
                
        # Drop rows where name, email, and password are all empty
        df = df[
            (df["name"].str.strip() != "") |
            (df["email"].str.strip() != "") |
            (df["password"].str.strip() != "")
        ]
        
        # Ensure only standard columns are returned
        rows = df[["name", "email", "password", "proxy"]].to_dict("records")
        return rows

    def append_registered_accounts(self, new_records: list[dict]):
        """Append list of newly registered accounts to data/registered_accounts.xlsx."""
        import pandas as pd
        file_path = Path("data/registered_accounts.xlsx")
        
        # Ensure directories exist
        file_path.parent.mkdir(exist_ok=True)
        
        if file_path.exists():
            try:
                df_old = pd.read_excel(file_path, dtype=str)
            except Exception:
                df_old = pd.DataFrame()
        else:
            df_old = pd.DataFrame()
            
        df_new = pd.DataFrame(new_records)
        if df_new.empty:
            return
            
        # Merge old and new
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined = df_combined.fillna("")
        
        # Drop duplicates based on email (keep the latest status/note/timestamp)
        if not df_combined.empty and "email" in df_combined.columns:
            df_combined["email"] = df_combined["email"].str.strip()
            df_combined = df_combined.drop_duplicates(subset=["email"], keep="last")
            
        # Reorder columns
        cols = ["name", "email", "password", "proxy", "status", "note", "timestamp"]
        # Ensure all columns exist
        for col in cols:
            if col not in df_combined.columns:
                df_combined[col] = ""
        df_combined = df_combined[cols]
        
        df_combined.to_excel(file_path, index=False)
        log.info(f"Đã cập nhật {len(new_records)} tài khoản vào {file_path}")


