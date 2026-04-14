from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import pandas as pd
import re

from trace_logic import extract_numbers, find_missing


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Missing Trace ID Finder")
        self.resize(860, 560)
        self.setMinimumSize(760, 500)

        self.df = None
        self.missing = []
        self.loaded_file = ""

        self._build_ui()
        self._apply_styles()
        self._refresh_actions()

    def _build_ui(self):
        root = QWidget()
        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(28, 28, 28, 28)
        outer_layout.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        hero_layout.setSpacing(8)

        eyebrow = QLabel("TRACE COVERAGE CHECK")
        eyebrow.setObjectName("eyebrow")
        hero_layout.addWidget(eyebrow)

        title = QLabel("Missing Trace ID Finder")
        title.setObjectName("titleLabel")
        hero_layout.addWidget(title)

        subtitle = QLabel(
            "Load a CSV, detect the Trace ID column, and export any missing IDs in one pass."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(subtitle)

        self.status = QLabel("Import a CSV file to begin.")
        self.status.setObjectName("statusBanner")
        self.status.setWordWrap(True)
        hero_layout.addWidget(self.status)

        outer_layout.addWidget(hero_card)

        controls_card = QFrame()
        controls_card.setObjectName("panelCard")
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(24, 22, 24, 22)
        controls_layout.setSpacing(16)

        controls_header = QLabel("Data Source")
        controls_header.setObjectName("sectionTitle")
        controls_layout.addWidget(controls_header)

        file_row = QHBoxLayout()
        file_row.setSpacing(12)

        self.import_btn = QPushButton("Import CSV")
        self.import_btn.setObjectName("primaryButton")
        self.import_btn.clicked.connect(self.import_csv)
        file_row.addWidget(self.import_btn, 0)

        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("mutedLabel")
        self.file_label.setWordWrap(True)
        file_row.addWidget(self.file_label, 1)

        controls_layout.addLayout(file_row)

        selection_row = QHBoxLayout()
        selection_row.setSpacing(12)

        self.column_box = QComboBox()
        self.column_box.setEditable(True)
        self.column_box.lineEdit().setAlignment(Qt.AlignCenter)
        self.column_box.lineEdit().setPlaceholderText("Trace ID column")
        self.column_box.currentTextChanged.connect(self.column_changed)
        selection_row.addWidget(self.column_box, 3)

        self.expected_input = QLineEdit()
        self.expected_input.setPlaceholderText(
            "Expected total records (optional)"
        )
        self.expected_input.textChanged.connect(self.expected_changed)
        selection_row.addWidget(self.expected_input, 2)

        controls_layout.addLayout(selection_row)

        self.helper_label = QLabel(
            "Tip: enter the expected total only when you know the full record count."
        )
        self.helper_label.setObjectName("helperLabel")
        self.helper_label.setWordWrap(True)
        controls_layout.addWidget(self.helper_label)

        outer_layout.addWidget(controls_card)

        stats_card = QFrame()
        stats_card.setObjectName("panelCard")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(24, 22, 24, 22)
        stats_layout.setSpacing(16)

        stats_header = QLabel("Scan Summary")
        stats_header.setObjectName("sectionTitle")
        stats_layout.addWidget(stats_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        self.records_label = self._create_metric_card(
            "Rows Loaded", "Import a CSV to see the count."
        )
        self.last_label = self._create_metric_card(
            "Last Trace ID", "The highest detected ID will appear here."
        )
        self.missing_label = self._create_metric_card(
            "Missing IDs", "Missing Trace IDs will be counted here."
        )

        grid.addWidget(self.records_label.parentWidget(), 0, 0)
        grid.addWidget(self.last_label.parentWidget(), 0, 1)
        grid.addWidget(self.missing_label.parentWidget(), 1, 0, 1, 2)

        stats_layout.addLayout(grid)
        outer_layout.addWidget(stats_card)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)
        actions_row.addStretch(1)

        self.export_btn = QPushButton("Export Missing Trace IDs")
        self.export_btn.setObjectName("accentButton")
        self.export_btn.clicked.connect(self.export_missing)
        actions_row.addWidget(self.export_btn)

        outer_layout.addLayout(actions_row)
        outer_layout.addStretch(1)

        self.setCentralWidget(root)

    def _create_metric_card(self, title, value):
        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        heading = QLabel(title)
        heading.setObjectName("metricTitle")
        layout.addWidget(heading)

        label = QLabel(value)
        label.setObjectName("metricValue")
        label.setWordWrap(True)
        layout.addWidget(label)

        return label

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #07111f,
                    stop: 0.45 #0f2740,
                    stop: 1 #16385a
                );
            }
            QWidget {
                color: #f3f7fb;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(255, 255, 255, 0.13),
                    stop: 1 rgba(255, 255, 255, 0.06)
                );
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 24px;
            }
            QFrame#panelCard, QFrame#metricCard {
                background-color: rgba(6, 18, 31, 0.72);
                border: 1px solid rgba(165, 210, 255, 0.16);
                border-radius: 20px;
            }
            QLabel#eyebrow {
                color: #9fd0ff;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.8px;
            }
            QLabel#titleLabel {
                font-size: 30px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#subtitleLabel {
                color: #c9d8e7;
                font-size: 14px;
            }
            QLabel#statusBanner {
                background-color: rgba(82, 172, 255, 0.12);
                border: 1px solid rgba(124, 196, 255, 0.22);
                border-radius: 14px;
                padding: 12px 14px;
                color: #f4fbff;
                font-weight: 600;
            }
            QLabel#sectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#mutedLabel {
                color: #c1d0de;
                padding: 4px 0;
            }
            QLabel#helperLabel {
                color: #8fb8dc;
                font-size: 12px;
            }
            QLabel#metricTitle {
                color: #8ab6db;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }
            QLabel#metricValue {
                color: #ffffff;
                font-size: 19px;
                font-weight: 700;
            }
            QLineEdit, QComboBox {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(176, 215, 255, 0.18);
                border-radius: 14px;
                padding: 11px 14px;
                selection-background-color: #ff9f43;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #ffb660;
                background-color: rgba(255, 255, 255, 0.12);
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f2338;
                border: 1px solid rgba(176, 215, 255, 0.22);
                selection-background-color: #ff9f43;
                selection-color: #0d1117;
            }
            QPushButton {
                border: none;
                border-radius: 14px;
                padding: 12px 18px;
                font-weight: 700;
            }
            QPushButton#primaryButton {
                background-color: #ff9f43;
                color: #152031;
            }
            QPushButton#primaryButton:hover {
                background-color: #ffb45c;
            }
            QPushButton#primaryButton:pressed {
                background-color: #ea8e34;
            }
            QPushButton#accentButton {
                background-color: #3fc1a2;
                color: #082119;
            }
            QPushButton#accentButton:hover {
                background-color: #5ed2b5;
            }
            QPushButton#accentButton:pressed {
                background-color: #30a88a;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.14);
                color: rgba(255, 255, 255, 0.44);
            }
            """
        )

    def _refresh_actions(self):
        has_data = self.df is not None and not self.df.empty
        has_column = bool(self.column_box.currentText().strip())
        self.export_btn.setEnabled(has_data and has_column)

    def _set_status(self, message):
        self.status.setText(message)

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
                "border: 1px solid #ff7b7b; background-color: rgba(255, 123, 123, 0.08);"
            )
            return False

        self.expected_input.setStyleSheet("")
        return True

    def calculate_stats(self, column):
        if self.df is None or column not in self.df.columns:
            return False

        data = self.df[column].dropna().astype(str)

        if data.empty or not data.str.contains(r"TMGID\d+", regex=True).any():
            self.records_label.setText("No Trace IDs found in the selected column.")
            self.last_label.setText("Choose a different column to continue.")
            self.missing_label.setText("Missing IDs cannot be calculated yet.")
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

        self.records_label.setText(f"{len(self.df):,} rows scanned")
        self.last_label.setText(f"TMGID{last_id:06d}")
        self.missing_label.setText(f"{len(self.missing):,} missing IDs detected")
        self._refresh_actions()
        return True

    def column_changed(self):
        if self.df is None:
            self._refresh_actions()
            return

        column = self.column_box.currentText().strip()
        if not column:
            self._refresh_actions()
            return

        self.calculate_stats(column)

    def expected_changed(self):
        if self.df is None:
            return

        if not self.validate_expected():
            self._set_status("Expected total must be a positive whole number.")
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
        self.loaded_file = file_path
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
            self._set_status(
                f"Loaded {len(self.df):,} rows from the selected file. Trace ID column auto-detected."
            )
            self.calculate_stats(auto_col)
        else:
            self.records_label.setText(f"{len(self.df):,} rows loaded")
            self.last_label.setText("Select the Trace ID column.")
            self.missing_label.setText("Missing IDs will appear after column selection.")
            self._set_status(
                f"Loaded {len(self.df):,} rows. Select the column that contains Trace IDs."
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
                "Expected total must be a positive whole number.",
            )
            return

        column = self.column_box.currentText().strip()
        valid = self.calculate_stats(column)

        if not valid:
            QMessageBox.warning(
                self,
                "Invalid Column",
                "The selected column does not appear to contain Trace IDs.",
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
