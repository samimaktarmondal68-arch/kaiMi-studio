"""Asset Manager page — centralized file browser for project assets."""

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QAbstractItemView, QInputDialog,
)

from core.pipeline_events import get_pipeline_events
from core.project_manager import ProjectManager
from core.notifications import NotificationService
from core.theme import Fonts
from ui.theme_pyside import ThemeManager
from ui.widgets import (
    EmptyState, ModernButton, MutedLabel, PageTitle, SectionHeader,
)


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


def _format_date(timestamp: str) -> str:
    if len(timestamp) >= 16:
        return timestamp[:16]
    return timestamp


class AssetManagerPage(QWidget):

    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self.project_name = None
        self._assets: list[dict] = []
        self._events = get_pipeline_events()
        self._events.assets_changed.connect(self._on_assets_changed)
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        self._refresh_theme_static()
        if self.project_name:
            self._load_project_data()

    def _refresh_theme_static(self):
        """Re-apply theme tokens to the static empty states.

        Empty states are built once in ``_build`` and would keep the colors
        they were constructed with after a runtime theme switch (Light-theme
        contrast regression).
        """
        self.empty_state.refresh_theme()
        self.assets_empty.refresh_theme()

    def _on_assets_changed(self, project_name):
        if project_name == self.project_name:
            self._refresh_assets()

    def set_project(self, name):
        self.project_name = name
        has_project = name is not None
        self.empty_state.setVisible(not has_project)
        self._content_widget.setVisible(has_project)
        self._load_project_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.addWidget(PageTitle("Asset Manager"))
        header_row.addStretch()

        self.refresh_btn = ModernButton("Refresh", primary=False)
        self.refresh_btn.clicked.connect(self._refresh_assets)
        self.refresh_btn.setFixedWidth(100)
        header_row.addWidget(self.refresh_btn)

        layout.addLayout(header_row)

        self.empty_state = EmptyState(
            title="No Project Selected",
            description="Select a project to view assets.",
        )
        layout.addWidget(self.empty_state)

        self._content_widget = QWidget()
        self._content_widget.setVisible(False)
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        self.status_label = MutedLabel("")
        content_layout.addWidget(self.status_label)

        content = QHBoxLayout()
        content.setSpacing(16)

        self._build_folder_tree(content)
        self._build_asset_table(content)

        content_layout.addLayout(content, 1)

        self._build_action_bar(content_layout)

        layout.addWidget(self._content_widget, 1)

    def _build_folder_tree(self, parent):
        container = QWidget()
        container.setFixedWidth(240)
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        v.addWidget(SectionHeader("Folders"))

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setFrameShape(QFrame.NoFrame)
        self.folder_tree.setAnimated(True)
        self.folder_tree.setIndentation(16)
        self.folder_tree.setMinimumHeight(300)
        self.folder_tree.itemClicked.connect(self._on_folder_clicked)
        v.addWidget(self.folder_tree, 1)

        parent.addWidget(container)

    def _build_asset_table(self, parent):
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        v.addWidget(SectionHeader("Files"))

        # Table + empty state stacked: a project with no assets must show a
        # helpful message instead of a blank table (RC-5 consistency pass).
        self.assets_stack = QStackedWidget()
        self.asset_table = QTableWidget(0, 5)
        self.asset_table.setHorizontalHeaderLabels(["Name", "Type", "Modified", "Size", "Status"])
        self.asset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.asset_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.asset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.asset_table.setAlternatingRowColors(False)
        self.asset_table.verticalHeader().setVisible(False)
        self.asset_table.setShowGrid(False)
        self.asset_table.setFrameShape(QFrame.NoFrame)
        self.asset_table.setMinimumHeight(300)

        header = self.asset_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.asset_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.assets_stack.addWidget(self.asset_table)

        self.assets_empty = EmptyState(
            icon="assets",
            title="No Assets Imported",
            description="Import or generate files in the Script, Voice, and Export stages "
            "to see them here.",
        )
        self.assets_stack.addWidget(self.assets_empty)

        v.addWidget(self.assets_stack, 1)
        parent.addWidget(container, 1)

    def _build_action_bar(self, parent):
        bar = QHBoxLayout()
        bar.setSpacing(12)

        self.open_btn = ModernButton("Open", primary=True)
        self.open_btn.clicked.connect(self._open_asset)
        self.open_btn.setEnabled(False)
        bar.addWidget(self.open_btn)

        self.reveal_btn = ModernButton("Reveal in Explorer", primary=False)
        self.reveal_btn.clicked.connect(self._reveal_asset)
        self.reveal_btn.setEnabled(False)
        bar.addWidget(self.reveal_btn)

        self.rename_btn = ModernButton("Rename", primary=False)
        self.rename_btn.clicked.connect(self._rename_asset)
        self.rename_btn.setEnabled(False)
        bar.addWidget(self.rename_btn)

        self.delete_btn = ModernButton("Delete", primary=False, danger=True)
        self.delete_btn.clicked.connect(self._delete_asset)
        self.delete_btn.setEnabled(False)
        bar.addWidget(self.delete_btn)

        bar.addStretch()
        parent.addLayout(bar)

    def _load_project_data(self):
        if not self.project_name:
            return
        self.status_label.setText(f"Project: {self.project_name}")
        self._build_folder_tree_data()
        self._refresh_assets()

    def _build_folder_tree_data(self):
        self.folder_tree.clear()
        if not self.project_name:
            return

        c = ThemeManager.instance().colors()
        project_path = self.manager.PROJECTS_DIR / self.project_name

        root_item = QTreeWidgetItem([f"  {self.project_name}"])
        root_item.setData(0, Qt.UserRole, "root")
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)
        root_item.setForeground(0, QColor(c.TEXT))
        self.folder_tree.addTopLevelItem(root_item)

        folders = ["Script", "Voice", "Transcript", "Image Prompts", "Images", "Videos", "Exports", "Temp", "Logs"]
        for folder in folders:
            child = QTreeWidgetItem([f"  {folder}"])
            child.setData(0, Qt.UserRole, folder.lower())
            child.setForeground(0, QColor(c.TEXT_SECONDARY))
            root_item.addChild(child)

        root_item.setExpanded(True)

    def _refresh_assets(self):
        if not self.project_name:
            return
        self._assets = self.manager.scan_assets(self.project_name)
        self._populate_table()

    def _populate_table(self):
        self.asset_table.setRowCount(0)
        c = ThemeManager.instance().colors()

        for asset in self._assets:
            row = self.asset_table.rowCount()
            self.asset_table.insertRow(row)

            name_item = QTableWidgetItem(asset["name"])
            name_item.setData(Qt.UserRole, asset["path"])
            name_item.setForeground(QColor(c.TEXT))
            self.asset_table.setItem(row, 0, name_item)

            type_item = QTableWidgetItem(asset["type"].upper())
            type_item.setForeground(QColor(c.TEXT_SECONDARY))
            self.asset_table.setItem(row, 1, type_item)

            date_item = QTableWidgetItem(_format_date(asset["modified"]))
            date_item.setForeground(QColor(c.TEXT_SECONDARY))
            self.asset_table.setItem(row, 2, date_item)

            size_item = QTableWidgetItem(_format_size(asset["size"]))
            size_item.setForeground(QColor(c.TEXT_SECONDARY))
            self.asset_table.setItem(row, 3, size_item)

            status_item = QTableWidgetItem("Synced")
            status_item.setForeground(QColor(c.SUCCESS))
            self.asset_table.setItem(row, 4, status_item)

        self.status_label.setText(
            f"Project: {self.project_name}  |  {len(self._assets)} assets"
        )
        self.assets_stack.setCurrentIndex(0 if self._assets else 1)

    def _on_selection_changed(self):
        has_selection = len(self.asset_table.selectedItems()) > 0
        self.open_btn.setEnabled(has_selection)
        self.reveal_btn.setEnabled(has_selection)
        self.rename_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _on_folder_clicked(self, item, column):
        folder = item.data(0, Qt.UserRole)
        if folder == "root":
            self._refresh_assets()
            return
        filtered = [a for a in self._assets if a.get("folder", "").startswith(folder)]
        self._populate_filtered(filtered)

    def _populate_filtered(self, assets: list[dict]):
        self.asset_table.setRowCount(0)
        c = ThemeManager.instance().colors()
        for asset in assets:
            row = self.asset_table.rowCount()
            self.asset_table.insertRow(row)
            name_item = QTableWidgetItem(asset["name"])
            name_item.setData(Qt.UserRole, asset["path"])
            name_item.setForeground(QColor(c.TEXT))
            self.asset_table.setItem(row, 0, name_item)
            type_item = QTableWidgetItem(asset["type"].upper())
            type_item.setForeground(QColor(c.TEXT_SECONDARY))
            self.asset_table.setItem(row, 1, type_item)
            date_item = QTableWidgetItem(_format_date(asset["modified"]))
            date_item.setForeground(QColor(c.TEXT_SECONDARY))
            self.asset_table.setItem(row, 2, date_item)
            size_item = QTableWidgetItem(_format_size(asset["size"]))
            size_item.setForeground(QColor(c.TEXT_SECONDARY))
            self.asset_table.setItem(row, 3, size_item)
            status_item = QTableWidgetItem("Synced")
            status_item.setForeground(QColor(c.SUCCESS))
            self.asset_table.setItem(row, 4, status_item)

        self.assets_stack.setCurrentIndex(0 if assets else 1)

    def _open_asset(self):
        row = self.asset_table.currentRow()
        if row < 0:
            return
        path = self.asset_table.item(row, 0).data(Qt.UserRole)
        if path:
            import subprocess
            try:
                subprocess.Popen(["start", "", path], shell=True)
            except Exception:
                NotificationService.get().error("Could not open file.")

    def _reveal_asset(self):
        row = self.asset_table.currentRow()
        if row < 0:
            return
        path = self.asset_table.item(row, 0).data(Qt.UserRole)
        if path:
            import subprocess
            try:
                subprocess.Popen(["explorer", "/select,", path])
            except Exception:
                NotificationService.get().error("Could not open file location.")

    def _rename_asset(self):
        row = self.asset_table.currentRow()
        if row < 0:
            return
        old_path = self.asset_table.item(row, 0).data(Qt.UserRole)
        if not old_path:
            return
        p = Path(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=p.stem)
        if ok and new_name:
            new_path = p.parent / f"{new_name}{p.suffix}"
            try:
                p.rename(new_path)
                NotificationService.get().success(f"Renamed to {new_name}{p.suffix}")
                self._refresh_assets()
            except Exception as e:
                NotificationService.get().error(f"Rename failed: {e}")

    def _delete_asset(self):
        row = self.asset_table.currentRow()
        if row < 0:
            return
        path = self.asset_table.item(row, 0).data(Qt.UserRole)
        name = self.asset_table.item(row, 0).text()
        if not path:
            return

        reply = QMessageBox.question(
            self, "Delete File",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                Path(path).unlink()
                NotificationService.get().success(f"Deleted {name}")
                self._refresh_assets()
            except Exception as e:
                NotificationService.get().error(f"Delete failed: {e}")


