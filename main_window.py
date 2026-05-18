from pathlib import Path
from typing import cast, TypedDict

import pandas as pd
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
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

from trace_logic import analyze_identifier_series, find_missing_ids, has_identifier_values
from zoho_integration import (
    fetch_company_id_lookup_dataframe,
    fetch_trace_id_lookup_dataframe,
)


class PipelineConfig(TypedDict):
    title: str
    prefix: str
    digits: int
    start_number: int
    exact_headers: tuple[str, ...]
    header_keywords: tuple[str, ...]
    column_placeholder: str
    expected_placeholder: str
    missing_column_name: str
    last_label: str
    panel_property: str
    fetch_button_text: str
    db_source_label: str


class PipelineRuntimeState(TypedDict):
    missing: list[str]
    enabled: bool
    valid: bool
    auto_selected: bool
    busy: bool
    dataframes: dict[str, pd.DataFrame | None]
    active_source: str | None


class PipelineWidgetGroup(TypedDict):
    section: QFrame
    include_btn: QPushButton
    state_label: QLabel
    source_label: QLabel
    inputs_container: QWidget
    column_box: QComboBox
    expected_input: QLineEdit


PIPELINES: dict[str, PipelineConfig] = {
    "trace": {
        "title": "Trace ID",
        "prefix": "TMGID",
        "digits": 6,
        "start_number": 1,
        "exact_headers": ("trace id", "traceid"),
        "header_keywords": (),
        "column_placeholder": "Select or type the Trace ID column",
        "expected_placeholder": "Expected total Trace ID count (optional)",
        "missing_column_name": "Missing Trace IDs",
        "last_label": "Last Trace ID",
        "panel_property": "trace",
        "fetch_button_text": "Fetch Trace IDs from DB",
        "db_source_label": "Zoho Leads",
    },
    "company": {
        "title": "Company ID",
        "prefix": "ACC",
        "digits": 6,
        "start_number": 0,
        "exact_headers": ("company id", "companyid", "company id1", "companyid1", "cid"),
        "header_keywords": ("cid",),
        "column_placeholder": "Select or type the Company ID column",
        "expected_placeholder": "Expected total Company ID count (optional)",
        "missing_column_name": "Missing Company IDs",
        "last_label": "Last Company ID",
        "panel_property": "company",
        "fetch_button_text": "Fetch Company IDs from DB",
        "db_source_label": "Zoho Company Registry",
    },
}


def normalize_column_name(value: object) -> str:
    text = str(value).strip().lower()
    return " ".join(text.replace("_", " ").replace("-", " ").split())


class DataFetchWorker(QObject):
    status = Signal(str, str)
    finished = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, pipeline_key: str) -> None:
        super().__init__()
        self.pipeline_key = pipeline_key

    def run(self) -> None:
        try:
            callback = lambda message: self.status.emit(self.pipeline_key, message)
            if self.pipeline_key == "trace":
                dataframe = fetch_trace_id_lookup_dataframe(status_callback=callback)
            else:
                dataframe = fetch_company_id_lookup_dataframe(status_callback=callback)
        except Exception as exc:
            self.failed.emit(self.pipeline_key, str(exc))
            return

        self.finished.emit(self.pipeline_key, dataframe)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Missing Trace ID and Company ID Tool")
        self.resize(980, 620)
        self.setMinimumSize(900, 520)

        self.shared_df: pd.DataFrame | None = None
        self.imported_file_path: str | None = None
        self.pipeline_state: dict[str, PipelineRuntimeState] = {
            key: {
                "missing": [],
                "enabled": False,
                "valid": False,
                "auto_selected": False,
                "busy": False,
                "dataframes": {
                    "import": None,
                    "db": None,
                },
                "active_source": None,
            }
            for key in PIPELINES
        }
        self.pipeline_widgets: dict[str, PipelineWidgetGroup] = {}
        self.stats_labels: dict[tuple[str, str], QLabel] = {}
        self.fetch_threads: dict[str, QThread] = {}
        self.fetch_workers: dict[str, DataFetchWorker] = {}

        self._build_ui()
        self._apply_styles()
        self.status_message = "No data loaded yet."
        for pipeline_key in PIPELINES:
            self._set_pipeline_enabled(pipeline_key, False)
            self._update_source_label(pipeline_key)
        self._refresh_actions()

    def _build_ui(self) -> None:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)

        title = QLabel("Missing Trace ID and Company ID Tool")
        title.setObjectName("titleLabel")
        main_layout.addWidget(title)

        subtitle = QLabel(
            "Load IDs from a local file or fetch them from Zoho CRM."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        self.status = QLabel("No data loaded yet.")
        self.status.setObjectName("statusLabel")
        self.status.setWordWrap(True)
        main_layout.addWidget(self.status)

        file_panel = QFrame()
        file_panel.setObjectName("panel")
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(12, 10, 12, 10)
        file_layout.setSpacing(8)

        sources_row = QHBoxLayout()
        sources_row.setSpacing(8)

        local_panel = QFrame()
        local_panel.setObjectName("sourceGroupPanel")
        local_layout = QVBoxLayout(local_panel)
        local_layout.setContentsMargins(8, 8, 8, 8)
        local_layout.setSpacing(6)

        local_label = QLabel("From Local Computer")
        local_label.setObjectName("sourceGroupLabel")
        local_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        local_layout.addWidget(local_label)

        self.import_btn = QPushButton("Import Local File")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.import_csv)
        local_layout.addWidget(self.import_btn)

        sources_row.addWidget(local_panel, 1)

        online_panel = QFrame()
        online_panel.setObjectName("sourceGroupPanel")
        online_layout = QVBoxLayout(online_panel)
        online_layout.setContentsMargins(8, 8, 8, 8)
        online_layout.setSpacing(6)

        online_label = QLabel("Fetch from DB Online")
        online_label.setObjectName("sourceGroupLabel")
        online_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        online_layout.addWidget(online_label)

        fetch_buttons_row = QHBoxLayout()
        fetch_buttons_row.setSpacing(8)

        trace_fetch_btn = QPushButton(PIPELINES["trace"]["fetch_button_text"])
        trace_fetch_btn.setObjectName("topFetchTraceButton")
        trace_fetch_btn.clicked.connect(
            lambda _checked=False: self.fetch_pipeline_from_db("trace")
        )
        self.top_trace_fetch_btn = trace_fetch_btn
        fetch_buttons_row.addWidget(trace_fetch_btn, 1)

        company_fetch_btn = QPushButton(PIPELINES["company"]["fetch_button_text"])
        company_fetch_btn.setObjectName("topFetchCompanyButton")
        company_fetch_btn.clicked.connect(
            lambda _checked=False: self.fetch_pipeline_from_db("company")
        )
        self.top_company_fetch_btn = company_fetch_btn
        fetch_buttons_row.addWidget(company_fetch_btn, 1)

        online_layout.addLayout(fetch_buttons_row)
        sources_row.addWidget(online_panel, 2)

        file_layout.addLayout(sources_row)

        self.clear_btn = QPushButton("Clear All Files")
        self.clear_btn.setObjectName("clearButton")
        self.clear_btn.clicked.connect(self.clear_all_data)
        self.clear_btn.setMaximumWidth(140)

        clear_row = QHBoxLayout()
        clear_row.addStretch(1)
        clear_row.addWidget(self.clear_btn, 0)
        file_layout.addLayout(clear_row)

        pipeline_grid = QGridLayout()
        pipeline_grid.setHorizontalSpacing(12)
        pipeline_grid.setVerticalSpacing(6)

        trace_header = QLabel("Trace ID Pipeline")
        trace_header.setObjectName("sectionLabel")
        company_header = QLabel("Company ID Pipeline")
        company_header.setObjectName("sectionLabel")
        pipeline_grid.addWidget(trace_header, 0, 0)
        pipeline_grid.addWidget(company_header, 0, 1)

        for column_index, pipeline_key in enumerate(("trace", "company")):
            section = self._build_pipeline_section(pipeline_key)
            pipeline_grid.addWidget(section, 1, column_index)

        file_layout.addLayout(pipeline_grid)

        main_layout.addWidget(file_panel)

        stats_panel = QFrame()
        stats_panel.setObjectName("panel")
        stats_layout = QGridLayout(stats_panel)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setHorizontalSpacing(16)
        stats_layout.setVerticalSpacing(4)

        stats_layout.addWidget(self._make_stats_header(""), 0, 0)
        stats_layout.addWidget(self._make_stats_header("Trace ID"), 0, 1)
        stats_layout.addWidget(self._make_stats_header("Company ID"), 0, 2)

        row_titles = (
            ("records", "Records scanned:"),
            ("last", "Last detected ID:"),
            ("missing", "Missing IDs:"),
        )

        for row_index, (label_key, title_text) in enumerate(row_titles, start=1):
            label = QLabel(title_text)
            label.setObjectName("statsTitleLabel")
            stats_layout.addWidget(label, row_index, 0)

            for column_index, pipeline_key in enumerate(("trace", "company"), start=1):
                stats_value = QLabel("-")
                stats_value.setObjectName("statsValueLabel")
                stats_value.setWordWrap(True)
                stats_layout.addWidget(stats_value, row_index, column_index)
                self.stats_labels[(pipeline_key, label_key)] = stats_value

        main_layout.addWidget(stats_panel)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)

        self.export_btn = QPushButton("Export Missing IDs")
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_missing)
        actions_row.addWidget(self.export_btn)

        main_layout.addLayout(actions_row)
        main_layout.addStretch(1)

        scroll_area.setWidget(container)
        self.setCentralWidget(scroll_area)

    def _build_pipeline_section(self, pipeline_key: str) -> QFrame:
        config = PIPELINES[pipeline_key]

        section = QFrame()
        section.setObjectName("subPanel")
        section.setProperty("pipelineType", config["panel_property"])
        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        include_btn = QPushButton("Include")
        include_btn.setObjectName("includeButton")
        include_btn.setProperty("pipelineType", config["panel_property"])
        include_btn.setCheckable(True)
        include_btn.clicked.connect(
            lambda checked, key=pipeline_key: self.toggle_pipeline(key, checked)
        )
        top_row.addWidget(include_btn, 0)

        state_label = QLabel("Not included")
        state_label.setObjectName("pipelineStateLabel")
        top_row.addWidget(state_label, 0)

        top_row.addStretch(1)
        layout.addLayout(top_row)

        source_label = QLabel("Source: No data loaded")
        source_label.setObjectName("sourceLabel")
        source_label.setWordWrap(True)
        layout.addWidget(source_label)

        inputs_container = QWidget()
        inputs_layout = QVBoxLayout(inputs_container)
        inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_layout.setSpacing(6)

        column_box = QComboBox()
        column_box.setEditable(True)
        line_edit = column_box.lineEdit()
        assert line_edit is not None
        line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft)
        line_edit.setPlaceholderText(config["column_placeholder"])
        column_box.currentTextChanged.connect(
            lambda _text, key=pipeline_key: self.column_changed(key)
        )
        inputs_layout.addWidget(column_box)

        expected_input = QLineEdit()
        expected_input.setPlaceholderText(config["expected_placeholder"])
        expected_input.textChanged.connect(
            lambda _text, key=pipeline_key: self.expected_changed(key)
        )
        inputs_layout.addWidget(expected_input)

        layout.addWidget(inputs_container)

        self.pipeline_widgets[pipeline_key] = {
            "section": section,
            "include_btn": include_btn,
            "state_label": state_label,
            "source_label": source_label,
            "inputs_container": inputs_container,
            "column_box": column_box,
            "expected_input": expected_input,
        }

        return section

    def _make_stats_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("statsHeaderLabel")
        return label

    def _apply_styles(self) -> None:
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
                font-size: 22px;
                font-weight: 700;
                color: #1d3557;
            }
            QLabel#subtitleLabel {
                color: #4f6478;
                font-size: 12px;
            }
            QFrame#sourceGroupPanel {
                background-color: #fbfcfe;
                border: 1px solid #d7e1ec;
                border-radius: 10px;
            }
            QLabel#sourceGroupLabel {
                color: #30485f;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#statusLabel {
                background-color: #f4f7fb;
                border: 1px solid #d5dfeb;
                border-radius: 8px;
                padding: 7px 9px;
                color: #1f3b57;
                font-weight: 600;
            }
            QFrame#panel {
                background-color: #ffffff;
                border: 1px solid #d7e1ec;
                border-radius: 10px;
            }
            QFrame#subPanel[pipelineType="trace"] {
                background-color: #edf5ff;
                border: 1px solid #c8dcf5;
                border-radius: 10px;
            }
            QFrame#subPanel[pipelineType="company"] {
                background-color: #eef9f1;
                border: 1px solid #c7e6d0;
                border-radius: 10px;
            }
            QLabel#sectionLabel {
                color: #1d3557;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#pipelineStateLabel {
                color: #5f7488;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#sourceLabel {
                color: #46637e;
                font-size: 12px;
            }
            QLabel#statsHeaderLabel {
                color: #1d3557;
                font-size: 13px;
                font-weight: 700;
                padding-bottom: 2px;
            }
            QLabel#statsTitleLabel {
                color: #4f6478;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#statsValueLabel {
                color: #213547;
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #ffffff;
                border: 1px solid #c9d5e2;
                border-radius: 8px;
                padding: 6px 9px;
                min-height: 18px;
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
                padding: 6px 12px;
                font-weight: 600;
                min-height: 18px;
            }
            QPushButton#importButton {
                background-color: #e9eef5;
                color: #2f475d;
                border: 1px solid #cfd8e2;
            }
            QPushButton#importButton:hover {
                background-color: #dde5ee;
            }
            QPushButton#topFetchTraceButton {
                background-color: #d9e9ff;
                color: #174a95;
                border: 1px solid #b9d2f8;
            }
            QPushButton#topFetchTraceButton:hover {
                background-color: #cbe0ff;
            }
            QPushButton#topFetchCompanyButton {
                background-color: #dbf2e2;
                color: #1d6b3b;
                border: 1px solid #bee0c8;
            }
            QPushButton#topFetchCompanyButton:hover {
                background-color: #cdebd7;
            }
            QPushButton#clearButton {
                background-color: #fdeaea;
                color: #8b2e2e;
                border: 1px solid #f1bfc0;
            }
            QPushButton#clearButton:hover {
                background-color: #fbdcdc;
            }
            QPushButton#clearButton:disabled {
                background-color: #f5eeee;
                color: #c09a9a;
                border: 1px solid #ead8d8;
            }
            QPushButton#exportButton {
                background-color: #35a86b;
                color: white;
            }
            QPushButton#exportButton:hover {
                background-color: #2e975f;
            }
            QPushButton#includeButton[pipelineType="trace"] {
                background-color: #d8e7fb;
                color: #23496f;
                min-width: 72px;
                padding: 4px 9px;
            }
            QPushButton#includeButton[pipelineType="trace"]:checked {
                background-color: #2f6fdd;
                color: white;
            }
            QPushButton#includeButton[pipelineType="company"] {
                background-color: #dcefe2;
                color: #28563a;
                min-width: 72px;
                padding: 4px 9px;
            }
            QPushButton#includeButton[pipelineType="company"]:checked {
                background-color: #2f9d57;
                color: white;
            }
            QPushButton:disabled {
                background-color: #d8e0e8;
                color: #7a8795;
            }
            QPushButton#exportButton:disabled {
                background-color: #dce4dd;
                color: #7c8b7e;
            }
            """
        )

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self._update_info_bar()

    def _has_any_loaded_data(self) -> bool:
        if self.shared_df is not None:
            return True
        return any(self._pipeline_has_available_data(key) for key in PIPELINES)

    def _build_summary_message(self) -> str:
        imported_text = "Local file: none"
        if self.shared_df is not None:
            file_name = (
                Path(self.imported_file_path).name
                if self.imported_file_path
                else "Loaded import"
            )
            imported_text = (
                f"Local file: {file_name} ({len(self.shared_df):,} rows)"
            )

        pipeline_parts = []
        for pipeline_key, config in PIPELINES.items():
            dataframe = self._get_current_dataframe(pipeline_key)
            if dataframe is None:
                pipeline_parts.append(f"{config['title']}: none")
                continue

            source_text = (
                "DB"
                if self.pipeline_state[pipeline_key]["active_source"] == "db"
                else "Local"
            )
            pipeline_parts.append(
                f"{config['title']}: {source_text} ({len(dataframe):,})"
            )

        return "Loaded | " + " | ".join([imported_text] + pipeline_parts)

    def _update_info_bar(self) -> None:
        detail_line = self._build_summary_message()
        self.status.setText(f"{self.status_message}\n{detail_line}")

    def _confirm_replace_data(self, action_label: str, detail_text: str) -> bool:
        result = QMessageBox.question(
            self,
            "Replace Loaded Data?",
            f"{detail_text}\n\nDo you want to continue with {action_label}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _confirm_clear_all(self) -> bool:
        result = QMessageBox.question(
            self,
            "Clear All Files?",
            "Confirm deleting all files from memory? This will remove all imported and fetched datasets from the app until you load them again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _get_current_dataframe(self, pipeline_key: str) -> pd.DataFrame | None:
        source = self.pipeline_state[pipeline_key]["active_source"]
        if not source:
            return None
        return cast(
            pd.DataFrame | None,
            self.pipeline_state[pipeline_key]["dataframes"].get(source),
        )

    def _pipeline_has_available_data(self, pipeline_key: str) -> bool:
        state = self.pipeline_state[pipeline_key]
        return any(
            dataframe is not None and not dataframe.empty
            for dataframe in state["dataframes"].values()
        )

    def _update_source_label(self, pipeline_key: str) -> None:
        state = self.pipeline_state[pipeline_key]
        source = state["active_source"]
        widgets = self.pipeline_widgets[pipeline_key]
        dataframe = self._get_current_dataframe(pipeline_key)

        if source == "import" and dataframe is not None:
            file_name = (
                Path(self.imported_file_path).name if self.imported_file_path else "Imported file"
            )
            widgets["source_label"].setText(
                f"Source: Local file ({file_name}, {len(dataframe):,} rows)"
            )
            return

        if source == "db" and dataframe is not None:
            widgets["source_label"].setText(
                f"Source: {PIPELINES[pipeline_key]['db_source_label']} ({len(dataframe):,} rows)"
            )
            return

        widgets["source_label"].setText("Source: No data loaded")

    def _refresh_actions(self) -> None:
        has_enabled_pipeline = any(
            self.pipeline_state[key]["enabled"] and self._get_current_dataframe(key) is not None
            for key in PIPELINES
        )
        has_any_data = any(self._get_current_dataframe(key) is not None for key in PIPELINES)
        has_busy_pipeline = any(self.pipeline_state[key]["busy"] for key in PIPELINES)
        self.export_btn.setEnabled(has_enabled_pipeline and not has_busy_pipeline)
        self.import_btn.setEnabled(not has_busy_pipeline)
        self.clear_btn.setEnabled(has_any_data and not has_busy_pipeline)
        self.top_trace_fetch_btn.setEnabled(not self.pipeline_state["trace"]["busy"])
        self.top_company_fetch_btn.setEnabled(not self.pipeline_state["company"]["busy"])
        self._update_info_bar()

    def _reset_pipeline_stats(self, pipeline_key: str) -> None:
        self.pipeline_state[pipeline_key]["missing"] = []
        self.pipeline_state[pipeline_key]["valid"] = False
        self.stats_labels[(pipeline_key, "records")].setText("-")
        self.stats_labels[(pipeline_key, "last")].setText("-")
        self.stats_labels[(pipeline_key, "missing")].setText("-")

    def _update_pipeline_controls(self, pipeline_key: str) -> None:
        widgets = self.pipeline_widgets[pipeline_key]
        state = self.pipeline_state[pipeline_key]
        has_data = self._pipeline_has_available_data(pipeline_key)
        active_data = self._get_current_dataframe(pipeline_key) is not None

        widgets["include_btn"].setEnabled(has_data and not state["busy"])
        widgets["column_box"].setEnabled(state["enabled"] and active_data and not state["busy"])
        widgets["expected_input"].setEnabled(
            state["enabled"] and active_data and not state["busy"]
        )

        opacity_effect = widgets["inputs_container"].graphicsEffect()
        if opacity_effect is None:
            opacity_effect = QGraphicsOpacityEffect(widgets["inputs_container"])
            widgets["inputs_container"].setGraphicsEffect(opacity_effect)
        opacity_effect = cast(QGraphicsOpacityEffect, opacity_effect)
        opacity_effect.setOpacity(1.0 if state["enabled"] and active_data else 0.35)

    def _set_pipeline_enabled(self, pipeline_key: str, enabled: bool) -> None:
        state = self.pipeline_state[pipeline_key]
        widgets = self.pipeline_widgets[pipeline_key]
        if enabled and self._get_current_dataframe(pipeline_key) is None:
            enabled = False

        state["enabled"] = enabled
        widgets["include_btn"].blockSignals(True)
        widgets["include_btn"].setChecked(enabled)
        widgets["include_btn"].blockSignals(False)
        widgets["include_btn"].setText("Included" if enabled else "Include")
        widgets["state_label"].setText("Included" if enabled else "Not included")

        if not enabled:
            self._reset_pipeline_stats(pipeline_key)

        self._update_pipeline_controls(pipeline_key)
        self._refresh_actions()

    def _set_pipeline_busy(self, pipeline_key: str, busy: bool) -> None:
        self.pipeline_state[pipeline_key]["busy"] = busy
        if busy:
            self.pipeline_widgets[pipeline_key]["state_label"].setText("Fetching from DB...")
        else:
            enabled = self.pipeline_state[pipeline_key]["enabled"]
            self.pipeline_widgets[pipeline_key]["state_label"].setText(
                "Included" if enabled else "Not included"
            )
        self._update_pipeline_controls(pipeline_key)
        self._refresh_actions()

    def _populate_column_box(self, pipeline_key: str) -> None:
        dataframe = self._get_current_dataframe(pipeline_key)
        column_box = self.pipeline_widgets[pipeline_key]["column_box"]
        selected_text = column_box.currentText().strip()
        column_names = [str(column) for column in dataframe.columns] if dataframe is not None else []

        column_box.blockSignals(True)
        column_box.clear()
        column_box.addItems(column_names)
        if selected_text and selected_text in column_names:
            column_box.setCurrentText(selected_text)
        else:
            column_box.setCurrentText("")
        column_box.blockSignals(False)

    def _match_status_message(self) -> str:
        busy_pipelines = [
            PIPELINES[key]["title"]
            for key in PIPELINES
            if self.pipeline_state[key]["busy"]
        ]
        if busy_pipelines:
            return "Fetching " + ", ".join(busy_pipelines) + " from Zoho DB..."

        ready = []
        for pipeline_key, config in PIPELINES.items():
            state = self.pipeline_state[pipeline_key]
            if not state["enabled"] or not state["valid"]:
                continue
            source_text = "DB" if state["active_source"] == "db" else "Local"
            missing_count = len(state["missing"])
            ready.append(
                f"{config['title']}: {missing_count:,} missing ({source_text})"
            )

        if ready:
            return "Ready | " + " | ".join(ready)

        if self.shared_df is not None:
            return "Local file loaded. Review the pipeline columns."

        if any(self._pipeline_has_available_data(key) for key in PIPELINES):
            return "DB data loaded. Review the pipeline columns."

        return "No data loaded yet."

    def _read_input_file(self, file_path: str) -> pd.DataFrame:
        file_path_lower = file_path.lower()

        if file_path_lower.endswith(".csv"):
            return pd.read_csv(file_path)

        if file_path_lower.endswith(".tsv"):
            return pd.read_csv(file_path, sep="\t")

        if file_path_lower.endswith((".xlsx", ".xlsm")):
            return pd.read_excel(file_path)

        raise ValueError("Unsupported file type. Please choose CSV, TSV, XLSX, or XLSM.")

    def _build_output_frame(self, valid_pipelines: list[str]) -> pd.DataFrame:
        output = {}
        max_length = 0

        for pipeline_key in valid_pipelines:
            missing_ids = self.pipeline_state[pipeline_key]["missing"]
            output[PIPELINES[pipeline_key]["missing_column_name"]] = missing_ids
            max_length = max(max_length, len(missing_ids))

        for column_name, values in list(output.items()):
            output[column_name] = values + [""] * (max_length - len(values))

        return pd.DataFrame(output)

    def _write_output_file(self, output_df: pd.DataFrame, save_path: str) -> None:
        save_path_lower = save_path.lower()

        if save_path_lower.endswith(".csv"):
            output_df.to_csv(save_path, index=False)
            return

        if save_path_lower.endswith(".xlsx"):
            output_df.to_excel(save_path, index=False)
            return

        raise ValueError("Unsupported export type. Please save as CSV or XLSX.")

    def _resolve_export_path(self, save_path: str, selected_filter: str) -> str:
        path = Path(save_path)
        if path.suffix:
            return str(path)

        if "xlsx" in selected_filter.lower():
            return f"{save_path}.xlsx"
        return f"{save_path}.csv"

    def auto_detect_column(self, pipeline_key: str) -> str | None:
        config = PIPELINES[pipeline_key]
        dataframe = self._get_current_dataframe(pipeline_key)
        if dataframe is None:
            return None

        normalized_columns = [
            (str(column), normalize_column_name(column))
            for column in dataframe.columns
        ]

        for original, normalized in normalized_columns:
            if normalized in config["exact_headers"]:
                return original

        for original, normalized in normalized_columns:
            if any(keyword in normalized for keyword in config["header_keywords"]):
                return original

        for column in dataframe.columns:
            if has_identifier_values(
                dataframe[column],
                config["prefix"],
                config["digits"],
            ):
                return str(column)

        return None

    def validate_expected(self, pipeline_key: str) -> bool:
        expected_input = self.pipeline_widgets[pipeline_key]["expected_input"]
        value = expected_input.text().strip()

        if value == "":
            expected_input.setStyleSheet("")
            return True

        if not value.isdigit() or int(value) < 0:
            expected_input.setStyleSheet(
                "border: 1px solid #d9534f; background-color: #fff3f2;"
            )
            return False

        if pipeline_key == "trace" and int(value) == 0:
            expected_input.setStyleSheet(
                "border: 1px solid #d9534f; background-color: #fff3f2;"
            )
            return False

        expected_input.setStyleSheet("")
        return True

    def validate_selected_column(self, pipeline_key: str, show_error: bool = False) -> bool:
        config = PIPELINES[pipeline_key]
        dataframe = self._get_current_dataframe(pipeline_key)

        if not self.pipeline_state[pipeline_key]["enabled"]:
            self._reset_pipeline_stats(pipeline_key)
            self._refresh_actions()
            return False

        column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()

        if dataframe is None or column == "":
            self._reset_pipeline_stats(pipeline_key)
            self._refresh_actions()
            return False

        if column not in dataframe.columns:
            self._reset_pipeline_stats(pipeline_key)
            if show_error:
                QMessageBox.warning(
                    self,
                    "Invalid Column",
                    f"Selected column for {config['title']} was not found in the active data source.",
                )
            self._refresh_actions()
            return False

        analysis = analyze_identifier_series(
            dataframe[column],
            config["prefix"],
            config["digits"],
        )

        total_values = analysis["total_values"]
        match_count = analysis["match_count"]

        if total_values == 0 or match_count == 0 or (match_count / total_values) < 0.5:
            self._reset_pipeline_stats(pipeline_key)
            if show_error:
                QMessageBox.warning(
                    self,
                    "Invalid Column",
                    f"Selected column for {config['title']} does not mostly start "
                    f"with {config['prefix']}.",
                )
            self._refresh_actions()
            return False

        last_id = max(analysis["numbers"])
        expected_text = self.pipeline_widgets[pipeline_key]["expected_input"].text().strip()
        max_range = max(last_id, int(expected_text)) if expected_text.isdigit() else last_id

        self.pipeline_state[pipeline_key]["missing"] = find_missing_ids(
            analysis["numbers"],
            config["start_number"],
            max_range,
            config["prefix"],
            config["digits"],
        )
        self.pipeline_state[pipeline_key]["valid"] = True

        self.stats_labels[(pipeline_key, "records")].setText(f"{len(dataframe):,}")
        self.stats_labels[(pipeline_key, "last")].setText(
            f"{config['prefix']}{last_id:0{config['digits']}d}"
        )
        self.stats_labels[(pipeline_key, "missing")].setText(
            f"{len(self.pipeline_state[pipeline_key]['missing']):,}"
        )
        self._refresh_actions()
        return True

    def _activate_dataframe(self, pipeline_key: str, source: str, auto_enable: bool) -> bool:
        state = self.pipeline_state[pipeline_key]
        state["active_source"] = source
        state["valid"] = False
        state["auto_selected"] = False
        self._reset_pipeline_stats(pipeline_key)
        self._populate_column_box(pipeline_key)
        self._update_source_label(pipeline_key)

        auto_col = self.auto_detect_column(pipeline_key)
        column_box = self.pipeline_widgets[pipeline_key]["column_box"]

        if auto_col:
            state["auto_selected"] = True
            self._set_pipeline_enabled(pipeline_key, True)
            index = column_box.findText(auto_col)
            if index >= 0:
                column_box.setCurrentIndex(index)
            else:
                column_box.setCurrentText(auto_col)
            self.validate_selected_column(pipeline_key, show_error=False)
            return True

        column_box.setCurrentText("")
        self._set_pipeline_enabled(pipeline_key, auto_enable)
        return False

    def toggle_pipeline(self, pipeline_key: str, checked: bool) -> None:
        if self._get_current_dataframe(pipeline_key) is None:
            self.pipeline_widgets[pipeline_key]["include_btn"].blockSignals(True)
            self.pipeline_widgets[pipeline_key]["include_btn"].setChecked(False)
            self.pipeline_widgets[pipeline_key]["include_btn"].blockSignals(False)
            return

        self._set_pipeline_enabled(pipeline_key, checked)
        if checked:
            column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()
            if column:
                self.validate_selected_column(pipeline_key, show_error=False)
        self._set_status(self._match_status_message())

    def column_changed(self, pipeline_key: str) -> None:
        if self._get_current_dataframe(pipeline_key) is None:
            self._refresh_actions()
            return

        if not self.pipeline_state[pipeline_key]["enabled"]:
            self._refresh_actions()
            return

        column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()
        if column:
            self.validate_selected_column(pipeline_key, show_error=False)
        else:
            self._reset_pipeline_stats(pipeline_key)
        self._refresh_actions()

    def expected_changed(self, pipeline_key: str) -> None:
        if self._get_current_dataframe(pipeline_key) is None:
            return

        if not self.pipeline_state[pipeline_key]["enabled"]:
            return

        config = PIPELINES[pipeline_key]
        if not self.validate_expected(pipeline_key):
            self.pipeline_state[pipeline_key]["valid"] = False
            self._set_status(
                f"Expected {config['title']} count must be a valid whole number."
            )
            self._refresh_actions()
            return

        column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()
        if column:
            self.validate_selected_column(pipeline_key, show_error=False)
            self._set_status(self._match_status_message())

    def import_csv(self) -> None:
        if self._has_any_loaded_data():
            if not self._confirm_replace_data(
                "Import File",
                "There is already imported or fetched data loaded in memory. "
                "Importing a new file will replace the imported-file dataset for both pipelines.",
            ):
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Data File",
            "",
            "Supported Files (*.csv *.tsv *.xlsx *.xlsm);;CSV Files (*.csv);;TSV Files (*.tsv);;Excel Files (*.xlsx *.xlsm)",
        )

        if not file_path:
            return

        try:
            df = self._read_input_file(file_path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Unable to Open File",
                f"The selected file could not be loaded.\n\n{exc}",
            )
            return

        if df.empty or df.dropna(how="all").empty:
            QMessageBox.warning(
                self,
                "Empty File",
                "The selected file does not contain any usable rows.",
            )
            return

        if len(df.columns) == 0:
            QMessageBox.warning(
                self,
                "Invalid File",
                "The selected file does not contain any columns.",
            )
            return

        self.shared_df = df
        self.imported_file_path = file_path
        auto_detected_pipelines = []
        for pipeline_key in PIPELINES:
            self.pipeline_state[pipeline_key]["dataframes"]["import"] = df
            self.pipeline_widgets[pipeline_key]["expected_input"].clear()
            self.pipeline_widgets[pipeline_key]["expected_input"].setStyleSheet("")
            if self._activate_dataframe(pipeline_key, "import", auto_enable=False):
                auto_detected_pipelines.append(PIPELINES[pipeline_key]["title"])

        self._set_status(self._match_status_message())
        self._refresh_actions()
        if not auto_detected_pipelines:
            QMessageBox.information(
                self,
                "Manual Review Needed",
                "The file loaded successfully, but no Trace ID or Company ID column "
                "was auto-detected. Please review the column selectors manually.",
            )

    def fetch_pipeline_from_db(self, pipeline_key: str) -> None:
        if self.pipeline_state[pipeline_key]["busy"]:
            return

        if self._pipeline_has_available_data(pipeline_key):
            source_name = PIPELINES[pipeline_key]["title"]
            if not self._confirm_replace_data(
                PIPELINES[pipeline_key]["fetch_button_text"],
                f"{source_name} already has data loaded in memory. Fetching from DB will "
                "replace the active dataset for that pipeline only.",
            ):
                return

        worker = DataFetchWorker(pipeline_key)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.status.connect(self._handle_fetch_status)
        worker.finished.connect(self._handle_fetch_complete)
        worker.failed.connect(self._handle_fetch_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda key=pipeline_key: self._cleanup_fetch_thread(key))

        self.fetch_threads[pipeline_key] = thread
        self.fetch_workers[pipeline_key] = worker
        self._set_pipeline_busy(pipeline_key, True)
        self._set_status(f"Preparing {PIPELINES[pipeline_key]['title']} fetch from Zoho DB...")
        thread.start()

    def _handle_fetch_status(self, pipeline_key: str, message: str) -> None:
        self._set_status(f"{PIPELINES[pipeline_key]['title']}: {message}")

    def _handle_fetch_complete(self, pipeline_key: str, dataframe: object) -> None:
        if not isinstance(dataframe, pd.DataFrame):
            self._handle_fetch_failed(
                pipeline_key,
                "Unexpected data was returned from the background fetch.",
            )
            return

        self._set_pipeline_busy(pipeline_key, False)

        if dataframe is None or dataframe.empty:
            QMessageBox.warning(
                self,
                "No Records Returned",
                f"Zoho returned no rows for the {PIPELINES[pipeline_key]['title']} dataset.",
            )
            self._set_status(self._match_status_message())
            return

        self.pipeline_state[pipeline_key]["dataframes"]["db"] = dataframe
        auto_detected = self._activate_dataframe(pipeline_key, "db", auto_enable=True)
        if auto_detected:
            self._set_status(
                f"{PIPELINES[pipeline_key]['title']} loaded from DB."
            )
        else:
            self._set_status(
                f"{PIPELINES[pipeline_key]['title']} loaded from DB. Select the ID column."
            )
        self._refresh_actions()

    def _handle_fetch_failed(self, pipeline_key: str, message: str) -> None:
        self._set_pipeline_busy(pipeline_key, False)
        QMessageBox.warning(
            self,
            "Zoho Fetch Failed",
            message,
        )
        self._set_status(
            f"{PIPELINES[pipeline_key]['title']} DB fetch failed."
        )

    def _cleanup_fetch_thread(self, pipeline_key: str) -> None:
        self.fetch_threads.pop(pipeline_key, None)
        self.fetch_workers.pop(pipeline_key, None)
        self._refresh_actions()

    def closeEvent(self, event: QCloseEvent) -> None:
        busy_pipelines = [
            PIPELINES[key]["title"]
            for key in PIPELINES
            if self.pipeline_state[key]["busy"]
        ]
        if busy_pipelines:
            QMessageBox.warning(
                self,
                "Fetch In Progress",
                "Please wait for the current Zoho fetch to finish before closing the app.\n\n"
                + ", ".join(busy_pipelines)
                + " is still downloading.",
            )
            event.ignore()
            return

        super().closeEvent(event)

    def clear_all_data(self) -> None:
        if not self._has_any_loaded_data():
            return

        if not self._confirm_clear_all():
            return

        self.shared_df = None
        self.imported_file_path = None
        for pipeline_key in PIPELINES:
            state = self.pipeline_state[pipeline_key]
            state["missing"] = []
            state["enabled"] = False
            state["valid"] = False
            state["auto_selected"] = False
            state["dataframes"]["import"] = None
            state["dataframes"]["db"] = None
            state["active_source"] = None

            widgets = self.pipeline_widgets[pipeline_key]
            widgets["column_box"].blockSignals(True)
            widgets["column_box"].clear()
            widgets["column_box"].setCurrentText("")
            widgets["column_box"].blockSignals(False)
            widgets["expected_input"].clear()
            widgets["expected_input"].setStyleSheet("")

            self._reset_pipeline_stats(pipeline_key)
            self._set_pipeline_enabled(pipeline_key, False)
            self._update_source_label(pipeline_key)

        self._set_status("All files were cleared from memory.")
        self._refresh_actions()

    def _validate_active_pipelines(self) -> list[str] | None:
        enabled_pipelines = [
            key for key in PIPELINES if self.pipeline_state[key]["enabled"]
        ]

        if not enabled_pipelines:
            QMessageBox.warning(
                self,
                "No Pipeline Selected",
                "Please select a pipeline to continue.",
            )
            return None

        valid_pipelines = []

        for pipeline_key, config in PIPELINES.items():
            if not self.pipeline_state[pipeline_key]["enabled"]:
                continue

            dataframe = self._get_current_dataframe(pipeline_key)
            if dataframe is None:
                QMessageBox.warning(
                    self,
                    "No Data Source",
                    f"Load imported data or fetch Zoho data for {config['title']} first.",
                )
                return None

            column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()
            if not column:
                QMessageBox.warning(
                    self,
                    "Missing Column Selection",
                    f"Select a column for {config['title']} before exporting.",
                )
                return None

            if column not in dataframe.columns:
                QMessageBox.warning(
                    self,
                    "Invalid Column",
                    f"Selected column for {config['title']} was not found in the active data source.",
                )
                return None

            if not self.validate_selected_column(pipeline_key, show_error=True):
                return None

            if not self.pipeline_state[pipeline_key]["valid"]:
                continue

            if not self.validate_expected(pipeline_key):
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Expected {config['title']} count must be a valid whole number.",
                )
                return None

            valid_pipelines.append(pipeline_key)

        if valid_pipelines:
            return valid_pipelines

        QMessageBox.warning(
            self,
            "No Valid Pipelines",
            "Please select at least one valid enabled pipeline first.",
        )
        return None

    def export_missing(self) -> None:
        if not any(self._get_current_dataframe(key) is not None for key in PIPELINES):
            QMessageBox.warning(
                self,
                "No Data",
                "Import a file or fetch a Zoho dataset first.",
            )
            return

        valid_pipelines = self._validate_active_pipelines()
        if not valid_pipelines:
            return

        save_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Missing IDs",
            "missing_trace_and_company_ids.csv",
            "CSV Files (*.csv);;Excel Files (*.xlsx)",
        )

        if not save_path:
            return

        save_path = self._resolve_export_path(save_path, selected_filter)

        output_df = self._build_output_frame(valid_pipelines)

        try:
            self._write_output_file(output_df, save_path)
            exported_titles = ", ".join(PIPELINES[key]["title"] for key in valid_pipelines)
            self._set_status(f"Exported missing IDs for {exported_titles}.")
        except PermissionError:
            QMessageBox.warning(
                self,
                "File Locked",
                "Close the export file if it is open in another app, then try again.",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"The export file could not be saved.\n\n{exc}",
            )
