import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from main_window import MainWindow

APP_DISPLAY_NAME = "Missing Trace/Company ID Tool"
ICON_PATH = Path(__file__).with_name("missing_id_icon.ico")

app = QApplication(sys.argv)
app.setApplicationDisplayName(APP_DISPLAY_NAME)

if ICON_PATH.exists():
    app.setWindowIcon(QIcon(str(ICON_PATH)))

window = MainWindow()
if ICON_PATH.exists():
    window.setWindowIcon(QIcon(str(ICON_PATH)))
window.show()

sys.exit(app.exec())
