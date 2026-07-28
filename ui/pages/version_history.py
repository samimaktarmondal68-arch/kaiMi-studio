"""Version History page — view, preview, and restore project versions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QAbstractItemView, QMessageBox,
)

from core.history_manager import HistoryManager
from core.notifications import NotificationService
from core.theme import Fonts, Spacing, Radius, Theme
from ui.theme_pyside import ThemeManager
from ui.widgets import ModernButton, MutedLabel, PageTitle


class VersionHistoryDialog(QDialog):

    def __init__(self, project_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Version History \u2014 {project_name}")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        self.project_name = project_name
        self.history = HistoryManager()
        self._build()
        self._load_history()

        c = ThemeManager.instance().colors()
        self.setStyleSheet(f"background-color: {c.BG}; color: {c.TEXT};")

    def _build(self):
        c = ThemeManager.instance().colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header_row = QHBoxLayout()
        header_row.addWidget(PageTitle("Version History"))
        header_row.addStretch()

        self.count_label = MutedLabel("")
        header_row.addWidget(self.count_label)

        layout.addLayout(header_row)

        self.status_label = MutedLabel("")
        layout.addWidget(self.status_label)

        self.version_table = QTableWidget(0, 4)
        self.version_table.setHorizontalHeaderLabels(["Date/Time", "Action", "Description", "Stage"])
        self.version_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.version_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.version_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.version_table.verticalHeader().setVisible(False)
        self.version_table.setShowGrid(False)
        self.version_table.setFrameShape(QFrame.NoFrame)
        self.version_table.setAlternatingRowColors(False)
        self.version_table.setMinimumHeight(300)

        header = self.version_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        layout.addWidget(self.version_table, 1)
        self.version_table.itemSelectionChanged.connect(self._on_selection_changed)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.restore_btn = ModernButton("Restore Selected Version", primary=True)
        self.restore_btn.clicked.connect(self._restore_version)
        self.restore_btn.setEnabled(False)
        btn_row.addWidget(self.restore_btn)

        self.refresh_btn = ModernButton("Refresh", primary=False)
        self.refresh_btn.clicked.connect(self._load_history)
        btn_row.addWidget(self.refresh_btn)

        btn_row.addStretch()

        close_btn = ModernButton("Close", primary=False)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _load_history(self):
        self.version_table.setRowCount(0)
        actions = self.history.get_action_history(self.project_name)
        c = ThemeManager.instance().colors()

        if not actions:
            self.count_label.setText("No version history yet.")
            return

        for action in actions:
            row = self.version_table.rowCount()
            self.version_table.insertRow(row)

            date_item = QTableWidgetItem(action.get("datetime", ""))
            date_item.setForeground(c.TEXT)
            self.version_table.setItem(row, 0, date_item)

            action_text = action.get("action", "")
            action_item = QTableWidgetItem(action_text)
            action_item.setForeground(c.PRIMARY if "Restore" in action_text else c.TEXT)
            self.version_table.setItem(row, 1, action_item)

            desc = action.get("description", "")
            desc_item = QTableWidgetItem(desc)
            desc_item.setForeground(c.TEXT_SECONDARY)
            self.version_table.setItem(row, 2, desc_item)

            stage = "General"
            for s in ["Script", "Voice", "Image Prompts", "Export"]:
                if s in action_text or s in desc:
                    stage = s
                    break
            stage_item = QTableWidgetItem(stage)
            stage_color = Theme.get_stage_color(c, stage)
            stage_item.setForeground(stage_color)
            self.version_table.setItem(row, 3, stage_item)

            self.version_table.setRowHeight(row, 36)

        self.count_label.setText(f"{len(actions)} version{'s' if len(actions) != 1 else ''}")

    def _on_selection_changed(self):
        self.restore_btn.setEnabled(len(self.version_table.selectedItems()) > 0)

    def _restore_version(self):
        row = self.version_table.currentRow()
        if row < 0:
            return

        action_text = self.version_table.item(row, 1).text()
        desc_text = self.version_table.item(row, 2).text()

        reply = QMessageBox.question(
            self, "Restore Version",
            f"Restore '{action_text}'?\n\n{desc_text}\n\n"
            "This creates a new version entry. No data is deleted.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.history.record_action(
                self.project_name,
                "Restore",
                f"User restored state from: {action_text}",
            )
            NotificationService.get().success(f"Version restored: {action_text}")
            self._load_history()
