from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout,
    QHBoxLayout, QLabel, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.notifications import NotificationService
from core.pipeline_events import get_pipeline_events
from core.pipeline_service import get_pipeline_service
from core.project_manager import ProjectManager
from core.theme import Fonts, Theme
from ui.theme_pyside import ThemeManager
from ui.widgets import (
    EmptyState, IconProvider, ModernButton, ModernCard, MutedLabel,
    PageTitle, SectionHeader, StatusBadge,
)
from ui.dialogs import NewProjectDialog

STAGE_LABELS = ["Script", "Voice", "Image Prompts", "Export"]


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val / (1024 * 1024):.1f} MB"


def _get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    if hour < 17:
        return "Good Afternoon"
    return "Good Evening"


class _ContinueProjectCard(ModernCard):
    def __init__(self, project, navigate_callback):
        super().__init__()
        self._project = project
        self._navigate_callback = navigate_callback
        self.setMinimumHeight(140)
        self.setCursor(Qt.PointingHandCursor)
        self._outer_layout.setContentsMargins(20, 16, 20, 16)
        self._build()

    def _build(self):
        c = ThemeManager.instance().colors()
        name = self._project.get("name", "Untitled")

        pipeline = get_pipeline_service()
        health = pipeline.get_project_health(name)
        action = pipeline.get_next_action(name)

        completed = pipeline.get_completed_stage_names(name)
        pct = int(len(completed) / len(STAGE_LABELS) * 100)

        active_stage = action.stage if action.stage else STAGE_LABELS[-1]
        badge_color = Theme.get_stage_color(c, active_stage) if active_stage else c.PRIMARY

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(20)

        progress_ring = QFrame()
        progress_ring.setFixedSize(80, 80)
        gradient = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.PRIMARY_LIGHT}, stop:1 {c.SURFACE})"
        progress_ring.setStyleSheet(
            f"background: {gradient}; border-radius: 40px; "
            f"border: 2px solid {c.PRIMARY};"
        )
        ring_layout = QVBoxLayout(progress_ring)
        ring_layout.setAlignment(Qt.AlignCenter)
        pct_label = QLabel(f"{pct}%")
        pct_label.setStyleSheet(f"{Fonts.css(22, 'bold', c.PRIMARY)} background: transparent;")
        ring_layout.addWidget(pct_label)
        pct_sub = QLabel("complete")
        pct_sub.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
        ring_layout.addWidget(pct_sub)
        h_layout.addWidget(progress_ring)

        col_content = QVBoxLayout()
        col_content.setSpacing(6)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"{Fonts.css(20, '700', c.TEXT)} background: transparent;")
        col_content.addWidget(name_lbl)

        meta_lbl = QLabel(health.overall.replace("_", " ").title() if health.overall else "")
        meta_lbl.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)} background: transparent;")
        col_content.addWidget(meta_lbl)

        progress_bar_bg = QFrame()
        progress_bar_bg.setFixedHeight(6)
        progress_bar_bg.setStyleSheet(f"background-color: {c.SURFACE}; border-radius: 3px;")
        progress_fill = QFrame()
        progress_fill.setStyleSheet(
            f"background-color: {c.PRIMARY}; border-radius: 3px; "
            f"min-width: {max(pct, 2)}%; max-width: {pct}%; min-height: 6px; max-height: 6px;"
        )
        bar_layout = QHBoxLayout(progress_bar_bg)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        bar_layout.addWidget(progress_fill)
        bar_layout.addStretch()
        col_content.addWidget(progress_bar_bg)

        if action.label:
            stage_badge = QFrame()
            stage_badge.setStyleSheet(
                f"background-color: {badge_color}; border-radius: 8px; "
                f"padding: 1px 10px; max-width: 200px;"
            )
            badge_layout = QHBoxLayout(stage_badge)
            badge_layout.setContentsMargins(6, 1, 6, 1)
            badge_lbl = QLabel(f"Next: {action.label}")
            badge_lbl.setStyleSheet(f"{Fonts.caption(c.TEXT_ON_PRIMARY)} background: transparent;")
            badge_layout.addWidget(badge_lbl)
            col_content.addWidget(stage_badge)

        col_content.addStretch()
        h_layout.addLayout(col_content, 1)

        actions = QVBoxLayout()
        actions.setAlignment(Qt.AlignCenter)

        resume_btn = ModernButton("Continue", primary=True)
        resume_btn.setFixedSize(140, 36)
        resume_btn.clicked.connect(lambda: self._navigate_callback(name))
        actions.addWidget(resume_btn)

        actions.addStretch()
        h_layout.addLayout(actions)

        self.content_layout.addLayout(h_layout)

    def mousePressEvent(self, event):
        self._navigate_callback(self._project.get("name", ""))


class _StatCard(ModernCard):
    def __init__(self, icon_name, label, value, accent_color=None):
        super().__init__()
        self.setFixedHeight(100)
        self.setMinimumWidth(160)

        c = ThemeManager.instance().colors()
        ac = accent_color or c.PRIMARY

        self.content_layout.setSpacing(2)

        icon_lbl = IconProvider.icon_label(icon_name, 22, ac)
        self.content_layout.addWidget(icon_lbl)

        val_lbl = QLabel(str(value))
        val_lbl.setStyleSheet(f"{Fonts.css(24, '700', ac)} background: transparent;")
        self.content_layout.addWidget(val_lbl)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
        self.content_layout.addWidget(lbl)


class _QuickActionCard(ModernCard):
    def __init__(self, icon_name, label, subtitle, accent_color, click_callback):
        super().__init__()
        self.setFixedHeight(88)
        self.setMinimumWidth(160)
        self.setCursor(Qt.PointingHandCursor)
        self._click_callback = click_callback

        c = ThemeManager.instance().colors()

        self.content_layout.setSpacing(2)

        icon_lbl = IconProvider.icon_label(icon_name, 20, accent_color)
        self.content_layout.addWidget(icon_lbl)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"{Fonts.css(14, '600', c.TEXT)} background: transparent;")
        self.content_layout.addWidget(lbl)

        sub = QLabel(subtitle)
        sub.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
        self.content_layout.addWidget(sub)

    def mousePressEvent(self, event):
        self._click_callback()


class _RecentProjectCard(ModernCard):
    def __init__(self, project, navigate_callback):
        super().__init__()
        self._project = project
        self._navigate_callback = navigate_callback
        self.setFixedHeight(110)
        self.setMinimumWidth(200)
        self.setCursor(Qt.PointingHandCursor)
        self._build()

    def _build(self):
        c = ThemeManager.instance().colors()
        name = self._project.get("name", "Untitled")

        pipeline = get_pipeline_service()
        health = pipeline.get_project_health(name)
        completed = pipeline.get_completed_stage_names(name)
        pct = int(len(completed) / len(STAGE_LABELS) * 100)

        self.content_layout.setSpacing(4)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"{Fonts.css(14, '600', c.TEXT)} background: transparent;")
        self.content_layout.addWidget(name_lbl)

        meta_lbl = QLabel(health.overall.replace("_", " ").title() if health.overall else "")
        meta_lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_SECONDARY)} background: transparent;")
        self.content_layout.addWidget(meta_lbl)

        self.content_layout.addStretch()

        progress_bg = QFrame()
        progress_bg.setFixedHeight(4)
        progress_bg.setStyleSheet(f"background-color: {c.SURFACE}; border-radius: 2px;")
        progress_fill = QFrame()
        progress_fill.setStyleSheet(
            f"background-color: {c.PRIMARY}; border-radius: 2px; "
            f"min-width: {max(pct, 2)}%; max-width: {pct}%; min-height: 4px; max-height: 4px;"
        )
        bar_layout = QHBoxLayout(progress_bg)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addWidget(progress_fill)
        bar_layout.addStretch()
        self.content_layout.addWidget(progress_bg)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setStyleSheet(f"{Fonts.caption(c.PRIMARY)} background: transparent; font-weight: 600;")
        bottom.addWidget(pct_lbl)

        modified = self._project.get("last_modified", "")
        if modified:
            date = modified[:10] if len(modified) > 10 else modified
            date_lbl = QLabel(date)
            date_lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
            bottom.addWidget(date_lbl)
        bottom.addStretch()
        self.content_layout.addLayout(bottom)

    def mousePressEvent(self, event):
        self._navigate_callback(self._project.get("name", ""))


class _ActivityCard(ModernCard):
    def __init__(self, activities):
        super().__init__()
        self._build(activities)

    def _build(self, activities):
        c = ThemeManager.instance().colors()

        if not activities:
            empty = EmptyState(description="No recent activity. Start working on your projects.")
            self.content_layout.addWidget(empty)
            return

        self.content_layout.setSpacing(6)

        for activity in activities[:5]:
            row = QHBoxLayout()
            row.setSpacing(8)
            icon_name = activity.get("icon", "circle")
            icon_lbl = IconProvider.icon_label(icon_name, 12, c.PRIMARY)
            row.addWidget(icon_lbl)

            text = QLabel(activity.get("text", ""))
            text.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)} background: transparent;")
            text.setWordWrap(True)
            row.addWidget(text, 1)

            time_lbl = QLabel(activity.get("time", ""))
            time_lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
            row.addWidget(time_lbl)

            self.content_layout.addLayout(row)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.pm = ProjectManager()
        self._pipeline = get_pipeline_service()
        self._events = get_pipeline_events()
        self._events.stage_completed.connect(self._on_pipeline_event)
        self._events.project_updated.connect(self._on_pipeline_event)
        self._events.export_completed.connect(self._on_pipeline_event)
        self._events.health_changed.connect(self._on_pipeline_event)
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_pipeline_event(self, *args):
        if self.isVisible():
            self.set_project()

    def _on_theme_changed(self):
        self.set_project()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(20)

        self._build_greeting()
        self._build_continue_project()
        self._build_quick_actions()
        self._build_stats()
        self._build_recent_projects()
        self._build_recent_activity()

        scroll.setWidget(content)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

    def _build_greeting(self):
        c = ThemeManager.instance().colors()
        greeting = PageTitle(f"{_get_greeting()}, Creator")
        self._content_layout.addWidget(greeting)

        projects_count = self.pm.get_project_count()
        sub_text = f"You have {projects_count} project{'s' if projects_count != 1 else ''}." if projects_count else "Ready to start your creative workflow."
        sub = QLabel(sub_text)
        sub.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        sub.setContentsMargins(0, 0, 0, 4)
        self._content_layout.addWidget(sub)

    def _build_continue_project(self):
        recent = self.pm.get_recent_projects(1)
        if not recent:
            return

        self._content_layout.addWidget(SectionHeader("Continue Working"))

        card = _ContinueProjectCard(recent[0], lambda n: self._navigate("", n))
        self._content_layout.addWidget(card)

    def _build_quick_actions(self):
        self._content_layout.addWidget(SectionHeader("Quick Actions"))

        c = ThemeManager.instance().colors()
        grid = QGridLayout()
        grid.setSpacing(12)

        actions = [
            ("add", "New Project", "Create a new project", c.PRIMARY, self._create_new),
            ("projects", "Open Projects", "Browse all projects", c.SECONDARY, self._show_all_projects),
            ("assets", "Asset Manager", "Manage project files", c.WARNING, self._show_assets),
            ("settings", "Settings", "Configure preferences", c.TEXT_MUTED, self._show_settings),
        ]

        for i, (icon_name, label, subtitle, color, callback) in enumerate(actions):
            card = _QuickActionCard(icon_name, label, subtitle, color, callback)
            grid.addWidget(card, 0, i)

        for col in range(4):
            grid.setColumnStretch(col, 1)

        self._content_layout.addLayout(grid)

    def _build_stats(self):
        projects = self.pm.get_projects()
        if not projects:
            return

        total = len(projects)
        total_assets = sum(p.get("asset_count", 0) for p in projects)
        total_storage = sum(p.get("storage_used", 0) for p in projects)

        completed_all = sum(
            1 for p in projects
            if self._pipeline.get_completed_stage_names(p.get("name", ""))
               == STAGE_LABELS
        )
        completion_rate = int(completed_all / total * 100) if total else 0

        self._content_layout.addWidget(SectionHeader("Statistics"))

        c = ThemeManager.instance().colors()
        grid = QGridLayout()
        grid.setSpacing(12)

        stats_cards = [
            ("projects", "Projects", str(total), c.PRIMARY),
            ("document", "Assets", str(total_assets), c.SECONDARY),
            ("storage", "Storage", _format_size(total_storage), c.WARNING),
            ("check_circle", "Completion", f"{completion_rate}%", c.SUCCESS),
        ]
        for i, (icon_name, label, value, color) in enumerate(stats_cards):
            grid.addWidget(_StatCard(icon_name, label, value, color), 0, i)
            grid.setColumnStretch(i, 1)

        self._content_layout.addLayout(grid)

    def _build_recent_projects(self):
        projects = self.pm.get_recent_projects(6)
        if not projects:
            return

        self._content_layout.addWidget(SectionHeader("Recent Projects"))

        grid = QHBoxLayout()
        grid.setSpacing(12)

        for proj in projects:
            card = _RecentProjectCard(proj, lambda n: self._navigate("", n))
            grid.addWidget(card)

        grid.addStretch()
        self._content_layout.addLayout(grid)

    def _build_recent_activity(self):
        activities = self._get_recent_activities()

        self._content_layout.addWidget(SectionHeader("Recent Activity"))

        card = _ActivityCard(activities)
        self._content_layout.addWidget(card)

        self._content_layout.addStretch()

    def _get_recent_activities(self):
        activities = []
        for project in self.pm.get_recent_projects(5):
            name = project.get("name", "")
            completed = self._pipeline.get_completed_stage_names(name)
            modified = project.get("last_modified", "")
            modified_short = modified[-5:] if len(modified) > 5 else modified

            for stage in ["Export", "Image Prompts", "Voice", "Script"]:
                if stage in completed:
                    stage_icons = {"Script": "script", "Voice": "voice",
                                   "Image Prompts": "image", "Export": "export"}
                    activities.append({
                        "icon": stage_icons.get(stage, "circle"),
                        "text": f"{stage} generated for \"{name}\"",
                        "time": modified_short,
                    })
                    break
        return activities

    def _navigate(self, page_label, project_name=None):
        parent = self.parent()
        while parent and not hasattr(parent, "navigate_to"):
            parent = parent.parent()
        if parent:
            from core.pipeline_service import get_pipeline_service
            pipeline = get_pipeline_service()
            action = pipeline.get_next_action(project_name)
            target = action.stage if action.stage else STAGE_LABELS[0]
            parent.set_project_context(project_name)
            parent.navigate_to(target, project_name)

    def _show_all_projects(self):
        parent = self.parent()
        while parent and not hasattr(parent, "navigate_to"):
            parent = parent.parent()
        if parent:
            parent.navigate_to("Projects")

    def _show_assets(self):
        parent = self.parent()
        while parent and not hasattr(parent, "navigate_to"):
            parent = parent.parent()
        if parent:
            parent.navigate_to("Asset Manager")

    def _show_settings(self):
        parent = self.parent()
        while parent and not hasattr(parent, "navigate_to"):
            parent = parent.parent()
        if parent:
            parent.navigate_to("Settings")

    def _create_new(self):
        parent = self.window()
        dlg = NewProjectDialog(parent, on_project_created=self._on_project_created)
        dlg.exec()

    def _on_project_created(self, name):
        self.set_project()
        self._events.project_created.emit(name)
        NotificationService.get().success(f"Project '{name}' created.")

    def set_project(self, name=None):
        for i in reversed(range(self._content_layout.count())):
            item = self._content_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self._build()
