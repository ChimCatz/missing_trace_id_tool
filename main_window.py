from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import pandas as pd

from trace_logic import extract_numbers, find_missing


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Missing Trace ID Tool v2")
        self.resize(760, 500)
        self.setMinimumSize(700, 460)

        self.df = None
        self.missing = []

        self._build_ui()
        self._apply_styles()
        self._refresh_actions()

    def _build_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(10)

        title = QLabel("Missing Trace ID Finder")
        title.setObjectName("titleLabel")
        main_layout.addWidget(title)

        subtitle = QLabel(
            "Import a CSV file, select the Trace ID column, and export missing IDs."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        self.status = QLabel("Import CSV to begin.")
        self.status.setObjectName("statusLabel")
        self.status.setWordWrap(True)
        main_layout.addWidget(self.status)

        file_panel = QFrame()
        file_panel.setObjectName("panel")
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(14, 14, 14, 14)
        file_layout.setSpacing(8)

        import_row = QHBoxLayout()
        import_row.setSpacing(10)

        self.import_btn = QPushButton("Import CSV")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.import_csv)
        import_row.addWidget(self.import_btn, 0)

        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setWordWrap(True)
        import_row.addWidget(self.file_label, 1)

        file_layout.addLayout(import_row)

        self.column_box = QComboBox()
        self.column_box.setEditable(True)
        self.column_box.lineEdit().setAlignment(Qt.AlignLeft)
        self.column_box.lineEdit().setPlaceholderText("Select or type the Trace ID column")
        self.column_box.currentTextChanged.connect(self.column_changed)
        file_layout.addWidget(self.column_box)

        self.expected_input = QLineEdit()
        self.expected_input.setPlaceholderText(
            "Expected total record count (optional)"
        )
        self.expected_input.textChanged.connect(self.expected_changed)
        file_layout.addWidget(self.expected_input)

        helper = QLabel(
            "Only enter the expected total if you know the exact number of records."
        )
        helper.setObjectName("helperLabel")
        helper.setWordWrap(True)
        file_layout.addWidget(helper)

        main_layout.addWidget(file_panel)

        stats_panel = QFrame()
        stats_panel.setObjectName("panel")
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(14, 14, 14, 14)
        stats_layout.setSpacing(6)

        self.records_label = QLabel("Records scanned: -")
        self.last_label = QLabel("Last Trace ID: -")
        self.missing_label = QLabel("Missing IDs: -")

        for label in (self.records_label, self.last_label, self.missing_label):
            label.setObjectName("statsLabel")
            label.setWordWrap(True)
            stats_layout.addWidget(label)

        main_layout.addWidget(stats_panel)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)

        self.export_btn = QPushButton("Export Missing Trace IDs")
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_missing)
        actions_row.addWidget(self.export_btn)

        main_layout.addLayout(actions_row)
        main_layout.addStretch(1)

        scroll_area.setWidget(container)
        self.setCentralWidget(scroll_area)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f3f6fb;
            }
            QScrollArea {
                background-color: #f3f6fb;
                border: none;
            }
            QWidget {
                color: #213547;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 700;
                color: #1d3557;
            }
            QLabel#subtitleLabel {
                color: #4f6478;
                font-size: 13px;
            }
            QLabel#statusLabel {
                background-color: #e7f0fb;
                border: 1px solid #c8dbf1;
                border-radius: 8px;
                padding: 8px 10px;
                color: #27496d;
            }
            QFrame#panel {
                background-color: #ffffff;
                border: 1px solid #d7e1ec;
                border-radius: 10px;
            }
            QLabel#fileLabel {
                color: #55697d;
            }
            QLabel#helperLabel {
                color: #6a7f94;
                font-size: 12px;
            }
            QLabel#statsLabel {
                color: #213547;
                font-size: 14px;
                padding: 2px 0;
            }
            QLineEdit, QComboBox {
                background-color: #ffffff;
                border: 1px solid #c9d5e2;
                border-radius: 8px;
                padding: 8px 10px;
                min-height: 20px;
            }
            QComboBox QAbstractItemView {
                min-height: 120px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #5b8def;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton#importButton {
                background-color: #4c8bf5;
                color: white;
            }
            QPushButton#importButton:hover {
                background-color: #3d7ce7;
            }
            QPushButton#exportButton {
                background-color: #35a86b;
                color: white;
            }
            QPushButton#exportButton:hover {
                background-color: #2e975f;
            }
            QPushButton:disabled {
                background-color: #c7d2df;
                color: #6f7f91;
            }
            """
        )

    def _set_status(self, message):
        self.status.setText(message)

    def _refresh_actions(self):
        has_data = self.df is not None and not self.df.empty
        has_column = bool(self.column_box.currentText().strip())
        self.export_btn.setEnabled(has_data and has_column)

    def auto_detect_trace_column(self):
        for col in self.df.columns:
            if "trace" in col.lower():
                return col

        for col in self.df.columns:
            sample = self.df[col].dropna().astype(str).head(20)
            if sample.str.contains(r"TMGID\d+", regex=True).any():
                return col

        return None

    def validate_expected(self):
        value = self.expected_input.text().strip()

        if value == "":
            self.expected_input.setStyleSheet("")
            return True

        if not value.isdigit() or int(value) <= 0:
            self.expected_input.setStyleSheet(
                "border: 1px solid #d9534f; background-color: #fff3f2;"
            )
            return False

        self.expected_input.setStyleSheet("")
        return True

    def calculate_stats(self, column):
        if self.df is None or column not in self.df.columns:
            return False

        data = self.df[column].dropna().astype(str)

        if data.empty or not data.str.contains(r"TMGID\d+", regex=True).any():
            self.records_label.setText("Records scanned: -")
            self.last_label.setText("Last Trace ID: -")
            self.missing_label.setText("Missing IDs: -")
            self.missing = []
            self._refresh_actions()
            return False

        numbers = extract_numbers(self.df[column])
        if not numbers:
            return False

        last_id = max(numbers)
        expected = self.expected_input.text().strip()
        max_range = max(last_id, int(expected)) if expected.isdigit() else last_id

        self.missing = find_missing(numbers, max_range)

        self.records_label.setText(f"Records scanned: {len(self.df):,}")
        self.last_label.setText(f"Last Trace ID: TMGID{last_id:06d}")
        self.missing_label.setText(f"Missing IDs: {len(self.missing):,}")
        self._refresh_actions()
        return True

    def column_changed(self):
        if self.df is None:
            self._refresh_actions()
            return

        column = self.column_box.currentText().strip()
        if column:
            self.calculate_stats(column)
        self._refresh_actions()

    def expected_changed(self):
        if self.df is None:
            return

        if not self.validate_expected():
            self._set_status("Expected total record count must be a positive whole number.")
            self._refresh_actions()
            return

        column = self.column_box.currentText().strip()
        if column:
            self.calculate_stats(column)

    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV", "", "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            df = pd.read_csv(file_path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Unable to Open File",
                f"The CSV could not be loaded.\n\n{exc}",
            )
            return

        if df.empty:
            QMessageBox.warning(
                self,
                "Empty File",
                "The selected CSV does not contain any rows.",
            )
            return

        self.df = df
        self.missing = []
        self.file_label.setText(file_path)

        self.column_box.blockSignals(True)
        self.column_box.clear()
        self.column_box.addItems([str(column) for column in self.df.columns])
        self.column_box.blockSignals(False)

        auto_col = self.auto_detect_trace_column()

        if auto_col:
            index = self.column_box.findText(auto_col)
            self.column_box.setCurrentIndex(index)
            self._set_status(f"Loaded {len(self.df):,} rows. Trace ID column auto-detected.")
            self.calculate_stats(auto_col)
        else:
            self.records_label.setText(f"Records scanned: {len(self.df):,}")
            self.last_label.setText("Last Trace ID: -")
            self.missing_label.setText("Missing IDs: -")
            self._set_status(
                f"Loaded {len(self.df):,} rows. Please select the Trace ID column."
            )

        self._refresh_actions()

    def export_missing(self):
        if self.df is None:
            QMessageBox.warning(self, "No File", "Import a CSV file first.")
            return

        if not self.validate_expected():
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Expected total record count must be a positive whole number.",
            )
            return

        column = self.column_box.currentText().strip()
        valid = self.calculate_stats(column)

        if not valid:
            QMessageBox.warning(
                self,
                "Invalid Column",
                "Selected column does not contain Trace IDs.",
            )
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Missing Trace IDs",
            "missing_trace_ids.csv",
            "CSV Files (*.csv)",
        )

        if not save_path:
            return

        try:
            out = pd.DataFrame({"Missing Trace IDs": self.missing})
            out.to_csv(save_path, index=False)
            self._set_status(f"Exported {len(self.missing):,} missing Trace IDs.")
        except PermissionError:
            QMessageBox.warning(
                self,
                "File Locked",
                "Close the CSV file if it is open in Excel, then try again.",
            )
