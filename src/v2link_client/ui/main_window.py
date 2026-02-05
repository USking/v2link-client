"""Main application window."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from v2link_client.ui.diagnostics_widget import DiagnosticsWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("v2link-client")
        self.resize(900, 640)

        central = QWidget(self)
        self.setCentralWidget(central)

        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("Paste vmess://, vless://, trojan://, or ss:// link")

        self.validate_button = QPushButton("Validate & Save")
        self.validate_button.clicked.connect(self._on_validate_clicked)

        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.setEnabled(False)

        self.status_label = QLabel("STOPPED")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        top_row = QHBoxLayout()
        top_row.addWidget(self.link_input, 1)
        top_row.addWidget(self.validate_button)

        control_row = QHBoxLayout()
        control_row.addWidget(self.start_stop_button)
        control_row.addWidget(QLabel("Status:"))
        control_row.addWidget(self.status_label, 1)

        self.diagnostics_widget = DiagnosticsWidget()

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addLayout(control_row)
        layout.addWidget(self.diagnostics_widget, 1)

        central.setLayout(layout)

    def _on_validate_clicked(self) -> None:
        # Placeholder until parsing and profile storage are implemented.
        self.status_label.setText("STOPPED")
        self.diagnostics_widget.set_hint("Validation not implemented yet.")
