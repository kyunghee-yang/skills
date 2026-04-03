import glob
import os
import subprocess
import time
from typing import Optional


def capture_summary_sheet(xlsx_path: str, output_png_path: str) -> bool:
    """Excel에서 요약 시트를 열고 캡처하여 PNG로 저장."""
    abs_xlsx = os.path.abspath(xlsx_path)
    abs_png = os.path.abspath(output_png_path)

    open_script = f'''
    tell application "Microsoft Excel"
        activate
        open POSIX file "{abs_xlsx}"
        delay 2
        tell active workbook
            set active_sheet to sheet "요약"
            activate object active_sheet
        end tell
        delay 1
    end tell
    '''

    try:
        subprocess.run(["osascript", "-e", open_script], check=True, timeout=15)
        time.sleep(1)

        wid_script = '''
        tell application "System Events"
            tell process "Microsoft Excel"
                set wid to id of front window
            end tell
        end tell
        return wid
        '''
        result = subprocess.run(
            ["osascript", "-e", wid_script],
            capture_output=True, text=True, timeout=10,
        )
        window_id = result.stdout.strip()

        if window_id:
            subprocess.run(
                ["screencapture", "-l", window_id, abs_png],
                check=True, timeout=10,
            )
        else:
            subprocess.run(
                ["screencapture", "-w", abs_png],
                check=True, timeout=10,
            )

        close_script = '''
        tell application "Microsoft Excel"
            close active workbook saving no
        end tell
        '''
        subprocess.run(["osascript", "-e", close_script], timeout=10)

        return os.path.exists(abs_png)

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def find_xlsx_in_folder(folder_path: str) -> Optional[str]:
    pattern = os.path.join(folder_path, "*법인카드*양경희*.xlsx")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]
