from PySide6.QtCore import Qt
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

import pandas as pd

from trace_logic import analyze_identifier_series, find_missing_ids, has_identifier_values


PIPELINES = {
    "trace": {
        "title": "Trace ID",
        "prefix": "TMGID",
        "digits": 6,
        "start_number": 1,
        "exact_headers": ("trace id",),
        "header_keywords": ("trace",),
        "column_placeholder": "Select or type the Trace ID column",
        "expected_placeholder": "Expected total Trace ID count (optional)",
        "missing_column_name": "Missing Trace IDs",
        "last_label": "Last Trace ID",
        "panel_property": "trace",
    },
    "company": {
        "title": "Company ID",
        "prefix": "ACC",
        "digits": 6,
        "start_number": 0,
        "exact_headers": ("company id", "cid"),
        "header_keywords": ("company", "cid"),
        "column_placeholder": "Select or type the Company ID column",
        "expected_placeholder": "Expected total Company ID count (optional)",
        "missing_column_name": "Missing Company IDs",
        "last_label": "Last Company ID",
        "panel_property": "company",
    },
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Missing Trace ID and Company ID Tool")
        self.resize(940, 620)
        self.setMinimumSize(860, 560)

        self.df = None
        self.pipeline_state = {
            key: {
                "missing": [],
                "enabled": False,
                "valid": False,
                "auto_selected": False,
            }
            for key in PIPELINES
        }
        self.pipeline_widgets = {}
        self.stats_labels = {}

        self._build_ui()
        self._apply_styles()
        for pipeline_key in PIPELINES:
            self._set_pipeline_enabled(pipeline_key, False)
        self._refresh_actions()

    def _build_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(12)

        title = QLabel("Missing Trace ID and Company ID Tool")
        title.setObjectName("titleLabel")
        main_layout.addWidget(title)

        subtitle = QLabel(
            "Import a CSV, TSV, or Excel file, select the Trace ID and/or "
            "Company ID column, and export missing IDs."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        self.status = QLabel("Import a CSV, TSV, or Excel file to begin.")
        self.status.setObjectName("statusLabel")
        self.status.setWordWrap(True)
        main_layout.addWidget(self.status)

        file_panel = QFrame()
        file_panel.setObjectName("panel")
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(14, 14, 14, 14)
        file_layout.setSpacing(12)

        import_row = QHBoxLayout()
        import_row.setSpacing(10)

        self.import_btn = QPushButton("Import File")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.import_csv)
        import_row.addWidget(self.import_btn, 0)

        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setWordWrap(True)
        import_row.addWidget(self.file_label, 1)

        file_layout.addLayout(import_row)

        pipeline_grid = QGridLayout()
        pipeline_grid.setHorizontalSpacing(14)
        pipeline_grid.setVerticalSpacing(10)

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

        helper = QLabel(
            "Only enter expected totals when you know the exact upper bound for "
            "that ID series."
        )
        helper.setObjectName("helperLabel")
        helper.setWordWrap(True)
        file_layout.addWidget(helper)

        main_layout.addWidget(file_panel)

        stats_panel = QFrame()
        stats_panel.setObjectName("panel")
        stats_layout = QGridLayout(stats_panel)
        stats_layout.setContentsMargins(14, 14, 14, 14)
        stats_layout.setHorizontalSpacing(18)
        stats_layout.setVerticalSpacing(8)

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

    def _build_pipeline_section(self, pipeline_key):
        config = PIPELINES[pipeline_key]

        section = QFrame()
        section.setObjectName("subPanel")
        section.setProperty("pipelineType", config["panel_property"])
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        include_btn = QPushButton("Include")
        include_btn.setObjectName("includeButton")
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

        inputs_container = QWidget()
        inputs_layout = QVBoxLayout(inputs_container)
        inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_layout.setSpacing(8)

        column_box = QComboBox()
        column_box.setEditable(True)
        column_box.lineEdit().setAlignment(Qt.AlignLeft)
        column_box.lineEdit().setPlaceholderText(config["column_placeholder"])
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
            "inputs_container": inputs_container,
            "column_box": column_box,
            "expected_input": expected_input,
        }

        return section

    def _make_stats_header(self, text):
        label = QLabel(text)
        label.setObjectName("statsHeaderLabel")
        return label

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
            QFrame#subPanel[pipelineType="trace"] {
                background-color: #eef6ff;
                border: 1px solid #cfe0f5;
                border-radius: 10px;
            }
            QFrame#subPanel[pipelineType="company"] {
                background-color: #eefaf2;
                border: 1px solid #cfe8d6;
                border-radius: 10px;
            }
            QLabel#fileLabel {
                color: #55697d;
            }
            QLabel#helperLabel {
                color: #6a7f94;
                font-size: 12px;
            }
            QLabel#sectionLabel {
                color: #1d3557;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#pipelineStateLabel {
                color: #5f7488;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#statsHeaderLabel {
                color: #1d3557;
                font-size: 14px;
                font-weight: 700;
                padding-bottom: 4px;
            }
            QLabel#statsTitleLabel {
                color: #4f6478;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#statsValueLabel {
                color: #213547;
                font-size: 14px;
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
            QPushButton#includeButton {
                background-color: #d4dee8;
                color: #284058;
                min-width: 74px;
                padding: 6px 10px;
            }
            QPushButton#includeButton:checked {
                background-color: #4c8bf5;
                color: white;
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
        has_enabled_pipeline = any(
            self.pipeline_state[key]["enabled"] for key in PIPELINES
        )
        self.export_btn.setEnabled(has_data and has_enabled_pipeline)

    def _reset_pipeline_stats(self, pipeline_key):
        self.pipeline_state[pipeline_key]["missing"] = []
        self.pipeline_state[pipeline_key]["valid"] = False
        self.stats_labels[(pipeline_key, "records")].setText("-")
        self.stats_labels[(pipeline_key, "last")].setText("-")
        self.stats_labels[(pipeline_key, "missing")].setText("-")

    def _set_pipeline_enabled(self, pipeline_key, enabled):
        widgets = self.pipeline_widgets[pipeline_key]
        self.pipeline_state[pipeline_key]["enabled"] = enabled
        widgets["include_btn"].blockSignals(True)
        widgets["include_btn"].setChecked(enabled)
        widgets["include_btn"].blockSignals(False)
        widgets["include_btn"].setText("Included" if enabled else "Include")
        widgets["state_label"].setText("Included" if enabled else "Not included")
        widgets["column_box"].setEnabled(enabled)
        widgets["expected_input"].setEnabled(enabled)

        opacity_effect = widgets["inputs_container"].graphicsEffect()
        if opacity_effect is None:
            opacity_effect = QGraphicsOpacityEffect(widgets["inputs_container"])
            widgets["inputs_container"].setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(1.0 if enabled else 0.35)

        if not enabled:
            self._reset_pipeline_stats(pipeline_key)
        self._refresh_actions()

    def _populate_column_boxes(self):
        column_names = [str(column) for column in self.df.columns]
        for pipeline_key in PIPELINES:
            column_box = self.pipeline_widgets[pipeline_key]["column_box"]
            column_box.blockSignals(True)
            column_box.clear()
            column_box.addItems(column_names)
            column_box.blockSignals(False)

    def _match_status_message(self):
        found = [
            PIPELINES[key]["title"]
            for key in PIPELINES
            if self.pipeline_state[key]["auto_selected"]
        ]
        enabled = [
            PIPELINES[key]["title"]
            for key in PIPELINES
            if self.pipeline_state[key]["enabled"]
        ]

        if len(found) == 2:
            return "Loaded file. Trace ID and Company ID columns auto-selected."
        if len(found) == 1:
            return f"Loaded file. {found[0]} column auto-selected."
        if enabled:
            return "Loaded file. Select the Trace ID and/or Company ID columns to continue."
        return "Loaded file. Enable a pipeline to manually choose a column."

    def _read_input_file(self, file_path):
        file_path_lower = file_path.lower()

        if file_path_lower.endswith(".csv"):
            return pd.read_csv(file_path)

        if file_path_lower.endswith(".tsv"):
            return pd.read_csv(file_path, sep="\t")

        if file_path_lower.endswith(".xlsx"):
            return pd.read_excel(file_path)

        raise ValueError("Unsupported file type. Please choose CSV, TSV, or XLSX.")

    def _build_output_frame(self, valid_pipelines):
        output = {}
        max_length = 0

        for pipeline_key in valid_pipelines:
            missing_ids = self.pipeline_state[pipeline_key]["missing"]
            output[PIPELINES[pipeline_key]["missing_column_name"]] = missing_ids
            max_length = max(max_length, len(missing_ids))

        for column_name, values in list(output.items()):
            output[column_name] = values + [""] * (max_length - len(values))

        return pd.DataFrame(output)

    def _write_output_file(self, output_df, save_path):
        save_path_lower = save_path.lower()

        if save_path_lower.endswith(".csv"):
            output_df.to_csv(save_path, index=False)
            return

        if save_path_lower.endswith(".xlsx"):
            output_df.to_excel(save_path, index=False)
            return

        raise ValueError("Unsupported export type. Please save as CSV or XLSX.")

    def auto_detect_column(self, pipeline_key):
        config = PIPELINES[pipeline_key]
        normalized_columns = [(str(column), str(column).strip().lower()) for column in self.df.columns]

        for original, normalized in normalized_columns:
            if normalized in config["exact_headers"]:
                return original

        for original, normalized in normalized_columns:
            if any(keyword in normalized for keyword in config["header_keywords"]):
                return original

        for column in self.df.columns:
            if has_identifier_values(
                self.df[column],
                config["prefix"],
                config["digits"],
            ):
                return str(column)

        return None

    def validate_expected(self, pipeline_key):
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

    def validate_selected_column(self, pipeline_key, show_error=False):
        config = PIPELINES[pipeline_key]

        if not self.pipeline_state[pipeline_key]["enabled"]:
            self._reset_pipeline_stats(pipeline_key)
            self._refresh_actions()
            return False

        column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()

        if self.df is None or column == "":
            self._reset_pipeline_stats(pipeline_key)
            self._refresh_actions()
            return False

        if column not in self.df.columns:
            self._reset_pipeline_stats(pipeline_key)
            if show_error:
                QMessageBox.warning(
                    self,
                    "Invalid Column",
                    f"Selected column for {config['title']} was not found in the CSV.",
                )
            self._refresh_actions()
            return False

        analysis = analyze_identifier_series(
            self.df[column],
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

        self.stats_labels[(pipeline_key, "records")].setText(f"{len(self.df):,}")
        self.stats_labels[(pipeline_key, "last")].setText(
            f"{config['prefix']}{last_id:0{config['digits']}d}"
        )
        self.stats_labels[(pipeline_key, "missing")].setText(
            f"{len(self.pipeline_state[pipeline_key]['missing']):,}"
        )
        self._refresh_actions()
        return True

    def toggle_pipeline(self, pipeline_key, checked):
        if self.df is None:
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

    def column_changed(self, pipeline_key):
        if self.df is None:
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

    def expected_changed(self, pipeline_key):
        if self.df is None:
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

    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Data File",
            "",
            "Supported Files (*.csv *.tsv *.xlsx);;CSV Files (*.csv);;TSV Files (*.tsv);;Excel Files (*.xlsx)",
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

        if df.empty:
            QMessageBox.warning(
                self,
                "Empty File",
                "The selected file does not contain any rows.",
            )
            return

        self.df = df
        self.file_label.setText(file_path)
        self._populate_column_boxes()

        for pipeline_key in PIPELINES:
            self.pipeline_state[pipeline_key]["missing"] = []
            self.pipeline_state[pipeline_key]["enabled"] = False
            self.pipeline_state[pipeline_key]["valid"] = False
            self.pipeline_state[pipeline_key]["auto_selected"] = False
            self.pipeline_widgets[pipeline_key]["column_box"].setCurrentText("")
            self.pipeline_widgets[pipeline_key]["expected_input"].clear()
            self.pipeline_widgets[pipeline_key]["expected_input"].setStyleSheet("")
            self._reset_pipeline_stats(pipeline_key)
            self._set_pipeline_enabled(pipeline_key, False)

        for pipeline_key in PIPELINES:
            auto_col = self.auto_detect_column(pipeline_key)
            column_box = self.pipeline_widgets[pipeline_key]["column_box"]
            if auto_col:
                self.pipeline_state[pipeline_key]["auto_selected"] = True
                self._set_pipeline_enabled(pipeline_key, True)
                index = column_box.findText(auto_col)
                column_box.setCurrentIndex(index)
                self.validate_selected_column(pipeline_key, show_error=False)

        self._set_status(self._match_status_message())
        self._refresh_actions()

    def _validate_active_pipelines(self):
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

            column = self.pipeline_widgets[pipeline_key]["column_box"].currentText().strip()
            if not column:
                QMessageBox.warning(
                    self,
                    "Missing Column Selection",
                    f"Select a column for {config['title']} before exporting.",
                )
                return None

            if column not in self.df.columns:
                QMessageBox.warning(
                    self,
                    "Invalid Column",
                    f"Selected column for {config['title']} was not found in the CSV.",
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

    def export_missing(self):
        if self.df is None:
            QMessageBox.warning(self, "No File", "Import a CSV file first.")
            return

        valid_pipelines = self._validate_active_pipelines()
        if not valid_pipelines:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Missing IDs",
            "missing_trace_and_company_ids.csv",
            "CSV Files (*.csv);;Excel Files (*.xlsx)",
        )

        if not save_path:
            return

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
