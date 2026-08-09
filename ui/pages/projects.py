from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.notifications import NotificationService
from core.pipeline_events import get_pipeline_events
from core.pipeline_service import get_pipeline_service, StageStatus
from core.project_manager import ProjectManager
from core.theme import Fonts, Theme
from ui.theme_pyside import ThemeManager
from ui.widgets import (
    EmptyState,
    IconProvider,
    ModernButton,
    ModernCard,
    ModernProgressBar,
    MutedLabel,
    PageTitle,
    SearchInput,
    StatusBadge,
    clear_layout,
)
from ui.dialogs import NewProjectDialog
from ui.pages.version_history import VersionHistoryDialog

STAGE_LABELS = ["Script", "Voice", "Image Prompts", "Export"]
SORT_OPTIONS = ["Last Modified", "Name", "Status", "Created"]
FILTER_OPTIONS = ["All", "Script", "Voice", "Image Prompts", "Export"]
SORT_KEY_MAP = {
    "Last Modified": "last_modified",
    "Name": "name",
    "Status": "status",
    "Created": "created",
}


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


class _ProjectCard(ModernCard):
    """Selectable project card.

    Clicking the card body selects the project for the page-level actions
    (e.g. Delete Project, RC-7.2); the per-card action buttons (Resume,
    History, Generate Script) keep their own handlers and never trigger
    selection.
    """

    def __init__(self, project, navigate_callback, generate_script_callback=None,
                 select_callback=None):
        super().__init__()
        self._project = project
        self._navigate_callback = navigate_callback
        self._generate_script_callback = generate_script_callback
        self._select_callback = select_callback
        self._selected = False
        self._active = False
        # Tall enough for the badge plus up to three 36px action buttons and
        # the content column with comfortable bottom spacing (RC-7.2.1).
        self.setFixedHeight(196)
        self.setCursor(Qt.PointingHandCursor)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._build()

    def mouseReleaseEvent(self, event):
        """Select the project when the card body is clicked.

        Child widgets (buttons, badges) consume their own mouse events, so
        this fires only for clicks on the card background/text.
        """
        if event.button() == Qt.LeftButton and self._select_callback:
            self._select_callback(self._project.get("name", ""))
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool):
        """Apply/remove the SELECTED treatment (RC-7.2/7.2.1).

        A selected card gets a stronger outline plus a subtle tinted
        background. This is intentionally different from the ACTIVE
        indicator (a small green label next to the project name) so the two
        states never look the same.
        """
        self._selected = selected
        self._sync_selection_style()

    def set_active(self, active: bool):
        """Show/hide the ACTIVE-project indicator (RC-7.2.1).

        ``active`` reflects the project currently opened in the app, which
        is tracked independently from the SELECTED project.
        """
        self._active = active
        if self.active_label is not None:
            self.active_label.setVisible(active)

    def _sync_selection_style(self):
        """Keep the selection treatment visible across hover enter/leave."""
        c = ThemeManager.instance().colors()
        if self._selected:
            self.setStyleSheet(
                f"QFrame#card {{ border: 2px solid {c.PRIMARY}; "
                f"background-color: {c.PRIMARY_LIGHT}; }}"
            )
        else:
            self.setStyleSheet("")

    def enterEvent(self, event):
        super().enterEvent(event)
        self._sync_selection_style()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._sync_selection_style()

    def _build(self):
        name = self._project.get("name", "Untitled")
        topic = self._project.get("topic", "No topic")
        language = self._project.get("language", "English")
        platform = self._project.get("platform", "")
        template = self._project.get("template", "Custom")
        last_modified = self._project.get("last_modified", "")
        asset_count = self._project.get("asset_count", 0)
        storage_used = self._project.get("storage_used", 0)

        c = ThemeManager.instance().colors()
        pipeline = get_pipeline_service()
        pipeline_state = pipeline.get_pipeline_state(name)
        health = pipeline.get_project_health(name)
        action = pipeline.get_next_action(name)

        completed_count = sum(
            1 for s in STAGE_LABELS
            if pipeline_state.get(s) == StageStatus.COMPLETED
        )
        pct = int(completed_count / len(STAGE_LABELS) * 100) if STAGE_LABELS else 0

        active_stage = action.stage if action.stage and action.can_execute else "Export"
        badge_color = Theme.get_stage_color(c, active_stage) if active_stage else c.PRIMARY

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        thumbnail = QFrame()
        gradient = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.PRIMARY_LIGHT}, stop:1 {c.SURFACE})"
        thumbnail.setStyleSheet(
            f"background: {gradient}; "
            f"border-top-left-radius: 12px; border-bottom-left-radius: 12px; "
            f"min-width: 120px; max-width: 120px;"
        )
        thumb_layout = QVBoxLayout(thumbnail)
        thumb_layout.setAlignment(Qt.AlignCenter)

        pct_label = QLabel(f"{pct}%")
        pct_label.setStyleSheet(f"{Fonts.css(26, 'bold', c.PRIMARY)} background: transparent;")
        thumb_layout.addWidget(pct_label)

        pct_sub = QLabel("complete")
        pct_sub.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
        thumb_layout.addWidget(pct_sub)

        layout.addWidget(thumbnail)

        content = QVBoxLayout()
        content.setContentsMargins(16, 14, 16, 14)
        content.setSpacing(4)

        # Name row carries the ACTIVE-project indicator (green label) so the
        # active project is always identifiable independently of selection
        # (RC-7.2.1).
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_label = QLabel(name)
        name_label.setStyleSheet(f"{Fonts.css(16, '600', c.TEXT)}")
        name_row.addWidget(name_label)
        self.active_label = QLabel("\u25CF  Active")
        self.active_label.setStyleSheet(
            f"{Fonts.tiny(c.SUCCESS)} font-weight: 600; background: transparent;"
        )
        self.active_label.setVisible(False)
        name_row.addWidget(self.active_label)
        name_row.addStretch()
        content.addLayout(name_row)

        meta = QLabel(f"{topic}  \u00B7  {language}" + (f"  \u00B7  {platform}" if platform else ""))
        meta.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        content.addWidget(meta)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        for label_text, value in [("Template", template), ("Assets", str(asset_count)), ("Storage", _format_size(storage_used))]:
            col = QVBoxLayout()
            col.setSpacing(0)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
            col.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(f"{Fonts.caption(c.TEXT)} background: transparent; font-weight: 500;")
            col.addWidget(val)
            stats_row.addLayout(col)
        content.addLayout(stats_row)

        # FIX E: project cards use the shared modern animated bar.
        progress_bar = ModernProgressBar()
        progress_bar.setFixedHeight(4)
        progress_bar.setValue(pct)
        content.addWidget(progress_bar)

        step_labels = QHBoxLayout()
        step_labels.setSpacing(6)
        for stage in STAGE_LABELS:
            status = pipeline_state.get(stage, StageStatus.BLOCKED)
            if status == StageStatus.COMPLETED:
                icon_name = "check_circle"
                sc = c.SUCCESS
            elif status in (StageStatus.NOT_STARTED, StageStatus.IN_PROGRESS):
                icon_name = "circle"
                sc = Theme.get_stage_color(c, stage)
            else:
                icon_name = "circle_empty"
                sc = c.TEXT_MUTED
            icon_lbl = IconProvider.icon_label(icon_name, 12, sc)
            step_labels.addWidget(icon_lbl)
            text_lbl = QLabel(stage)
            text_lbl.setStyleSheet(f"{Fonts.tiny(sc)} background: transparent;")
            step_labels.addWidget(text_lbl)
        step_labels.addStretch()
        content.addLayout(step_labels)

        if last_modified:
            mod = QLabel(last_modified)
            mod.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
            content.addWidget(mod)

        layout.addLayout(content, 1)

        # Reserved-width action rail (RC-7.2.1): the column always keeps room
        # for the stage badge, the primary stage/action button, Resume and
        # History. The rail width is derived from the widest control (stage
        # badge or the action buttons) so nothing is ever squeezed or clipped
        # against the card boundary, regardless of font metrics.
        actions_container = QWidget()
        actions = QVBoxLayout(actions_container)
        actions.setContentsMargins(10, 10, 10, 10)
        actions.setSpacing(8)
        actions.setAlignment(Qt.AlignTop)

        badge = StatusBadge(action.label if action.label else active_stage,
                           color=c.TEXT_ON_PRIMARY, bg=badge_color)
        badge.setAlignment(Qt.AlignCenter)
        actions.addWidget(badge)

        rail_width = max(badge.sizeHint().width(), 150)
        badge.setFixedWidth(rail_width)
        actions_container.setFixedWidth(rail_width + 20)

        # A dedicated "Generate Script" action: opens the project, navigates
        # to the Script page, and starts generation automatically (Sprint 3.4C).
        script_status = pipeline_state.get("Script", StageStatus.BLOCKED)
        if (
            self._generate_script_callback
            and action.stage == "Script"
            and action.can_execute
            and script_status in (StageStatus.NOT_STARTED, StageStatus.FAILED)
        ):
            gen_btn = ModernButton(action.label, primary=True)
            gen_btn.setFixedSize(rail_width, 36)
            gen_btn.clicked.connect(
                lambda checked, n=name: self._generate_script_callback(n)
            )
            actions.addWidget(gen_btn)

        open_btn = ModernButton("Resume", primary=True)
        open_btn.setFixedSize(rail_width, 36)
        open_btn.clicked.connect(lambda checked, n=name: self._navigate_callback(n))
        actions.addWidget(open_btn)

        history_btn = ModernButton("History", primary=False)
        history_btn.setFixedSize(rail_width, 36)
        history_btn.clicked.connect(lambda checked, n=name: self._show_history(n))
        actions.addWidget(history_btn)

        layout.addWidget(actions_container)

        self.content_layout.addLayout(layout)

    def _show_history(self, project_name):
        dlg = VersionHistoryDialog(project_name)
        dlg.exec()


class ProjectsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self._pipeline = get_pipeline_service()
        self._events = get_pipeline_events()
        self._events.stage_completed.connect(self._on_pipeline_event)
        self._events.project_updated.connect(self._on_pipeline_event)
        self._events.project_created.connect(self._on_pipeline_event)
        self._events.project_deleted.connect(self._on_pipeline_event)
        self._events.health_changed.connect(self._on_pipeline_event)
        self._search_query = ""
        self._sort_by = "last_modified"
        self._sort_reverse = True
        self._filter_status = "All"
        #: RC-7.2: the currently selected project (None until a card is
        #: clicked). Page-level actions such as Delete Project operate only
        #: on this selection.
        self._selected_project = None
        self._selected_card = None
        self._cards: dict[str, _ProjectCard] = {}
        #: RC-7.2.1: the ACTIVE project (opened in the app). Tracked
        #: independently of the SELECTED project and fed by ``set_project``
        #: through the existing navigation context.
        self._active_project = None
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_pipeline_event(self, *args):
        self.refresh()

    def _on_theme_changed(self):
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(16)

        title = PageTitle("Projects")
        header.addWidget(title)
        header.addStretch()

        # Selected-project action area (RC-7.2): the destructive Delete
        # action lives here, only enabled once a project card is selected.
        self.selected_label = MutedLabel("")
        self.selected_label.setVisible(False)
        header.addWidget(self.selected_label)

        self.delete_btn = ModernButton("Delete Project", primary=False, danger=True)
        self.delete_btn.setFixedSize(150, 36)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        header.addWidget(self.delete_btn)

        new_btn = ModernButton("+ New Project", primary=True)
        new_btn.setFixedSize(140, 36)
        new_btn.clicked.connect(self._create_new)
        header.addWidget(new_btn)

        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = SearchInput(placeholder="Search projects...")
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_OPTIONS)
        self.sort_combo.setMinimumWidth(140)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(FILTER_OPTIONS)
        self.filter_combo.setMinimumWidth(130)
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        self.count_label = MutedLabel("")
        toolbar.addWidget(self.count_label)

        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)

        self.refresh()

    def _build_cards(self, projects):
        # FIX E: fully clear the container — widgets AND spacer items — so a
        # rebuild after deletion never leaves stale stretches above the
        # remaining cards (the old loop only removed widget items and leaked
        # every addStretch() spacer, pushing cards down after a delete).
        clear_layout(self.cards_layout)

        if not projects:
            empty = EmptyState(
                icon="projects",
                title="No Projects Found",
                description="Create a new project to get started.",
                action_callback=self._create_new,
                action_text="Create New Project",
            )
            self.cards_layout.addWidget(empty, 1)
            return

        for project in projects:
            name = project.get("name", "")
            card = _ProjectCard(
                project,
                lambda n=name: self._navigate("", n),
                lambda n=name: self._generate_script(n),
                select_callback=self._select_project,
            )
            card.set_active(name == self._effective_active_project())
            self._cards[name] = card
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def _navigate(self, page_label, project_name=None):
        parent = self.parent()
        while parent and not hasattr(parent, "navigate_to"):
            parent = parent.parent()
        if parent:
            action = self._pipeline.get_next_action(project_name)
            target = action.stage if action.stage else STAGE_LABELS[0]
            parent.set_project_context(project_name)
            parent.navigate_to(target, project_name)

    def _generate_script(self, project_name):
        """Open a project, navigate to the Script page, and start generation.

        Called by the card's "Generate Script" action so the button always
        produces visible feedback instead of appearing to do nothing.
        """
        parent = self.window()
        if not parent or not hasattr(parent, "navigate_to"):
            return
        parent.set_project_context(project_name)
        parent.navigate_to("Script", project_name)
        content = getattr(parent, "content", None)
        current = content.currentWidget() if content is not None else None
        if current is not None and hasattr(current, "generate_script"):
            current.generate_script()

    def _create_new(self):
        parent = self.window()
        dlg = NewProjectDialog(parent, on_project_created=self._on_project_created)
        dlg.exec()

    def _on_project_created(self, name):
        self.refresh()
        self._events.project_created.emit(name)
        NotificationService.get().success(f"Project '{name}' created.")
        parent = self.window()
        if parent and hasattr(parent, 'navigate_to'):
            action = self._pipeline.get_next_action(name)
            target = action.stage if action.stage else STAGE_LABELS[0]
            parent.set_project_context(name)
            parent.navigate_to(target, name)

    def _effective_active_project(self):
        """Return the project currently opened in the app (ACTIVE).

        Prefers the main window's current project so the indicator stays
        correct even when the active project changed through a path that did
        not call ``set_project`` (RC-7.2.1).
        """
        parent = self.window()
        if parent is not None:
            name = getattr(parent, "_project_name", None)
            if name:
                return name
        return self._active_project

    def refresh(self):
        projects = self.manager.search_projects(self._search_query)
        projects = self.manager.filter_projects(projects, self._filter_status)
        projects = self.manager.sort_projects(projects, self._sort_by, self._sort_reverse)

        favorites = [p for p in projects if p.get("favorite")]
        regular = [p for p in projects if not p.get("favorite")]
        display = favorites + regular

        count = len(display)
        label = f"{count} project{'s' if count != 1 else ''}"
        self.count_label.setText(label)

        self._cards = {}
        self._build_cards(display)
        self._reconcile_selection(display)

    # ------------------------------------------------------------------
    # RC-7.2 — Project selection & deletion
    # ------------------------------------------------------------------

    def _select_project(self, name):
        """Select a project card, highlighting it and enabling Delete."""
        card = self._cards.get(name)
        if card is None:
            return
        if self._selected_card is not None and self._selected_card is not card:
            self._selected_card.set_selected(False)
        self._selected_project = name
        self._selected_card = card
        card.set_selected(True)
        self._update_selection_ui()

    def _clear_selection(self):
        """Deselect the current project (if any) and disable Delete."""
        if self._selected_card is not None:
            self._selected_card.set_selected(False)
        self._selected_card = None
        self._selected_project = None
        self._update_selection_ui()

    def _reconcile_selection(self, display):
        """Keep the selection valid after a list rebuild (RC-7.2).

        Cards are recreated on every refresh, so the stored card reference
        must be re-linked; a selected project that no longer exists (e.g.
        deleted) is deselected.
        """
        names = {p.get("name") for p in display}
        if self._selected_project and self._selected_project not in names:
            self._selected_project = None
            self._selected_card = None
            self._update_selection_ui()
            return
        if self._selected_project:
            self._selected_card = self._cards.get(self._selected_project)
            if self._selected_card is not None:
                self._selected_card.set_selected(True)
        self._update_selection_ui()

    def _update_selection_ui(self):
        """Enable/disable Delete and show the selected project name."""
        if self._selected_project:
            self.delete_btn.setEnabled(True)
            self.selected_label.setText(f"Selected: {self._selected_project}")
            self.selected_label.setVisible(True)
        else:
            self.delete_btn.setEnabled(False)
            self.selected_label.setVisible(False)

    def _confirm_delete(self, name) -> bool:
        """Show the destructive confirmation dialog. Returns True on confirm."""
        box = QMessageBox(self)
        box.setWindowTitle("Delete Project")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "Delete Project?\n\n"
            f'You are about to permanently delete:\n"{name}"\n\n'
            "This will remove the project and its stored project data/assets. "
            "This action cannot be undone."
        )
        delete_btn = box.addButton(
            "Delete Project", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        # Make the destructive confirm button visually distinct from Cancel.
        c = ThemeManager.instance().colors()
        delete_btn.setStyleSheet(
            f"background-color: {c.ERROR}; color: {c.TEXT_ON_PRIMARY}; "
            f"border: none; border-radius: 6px; padding: 6px 16px; "
            f"font-weight: 600;"
        )
        box.exec()
        return box.clickedButton() is delete_btn

    def _delete_selected(self):
        """Delete the selected project after confirmation (RC-7.2).

        Reuses the existing ``ProjectManager.delete_project`` primitive which
        removes exactly the selected project's own storage directory (path
        validated against the projects root). Nothing is deleted before the
        user confirms. On failure the project is preserved and the list is
        left unchanged.
        """
        name = self._selected_project
        if not name:
            return
        if not self._confirm_delete(name):
            return
        if not self.manager.delete_project(name):
            NotificationService.get().error(
                f"Project deletion failed. '{name}' was not removed. "
                "Please check the project folder and try again."
            )
            self.refresh()
            return
        self._clear_selection()
        fallback = self._active_project_after_delete(name)
        # The project_deleted listener refreshes the project list.
        self._events.project_deleted.emit(name)
        if fallback:
            self._select_project(fallback)
        NotificationService.get().success("Project deleted successfully.")

    def _active_project_after_delete(self, deleted_name):
        """Reset stale active-project state after deleting the active project.

        Returns the fallback project name to auto-select, or None when no
        projects remain or the deleted project was not the active one. Uses
        the existing project-selection mechanisms (navigation controller,
        sidebar, per-page ``set_project``) instead of patching widgets.
        """
        parent = self.window()
        if parent is None or getattr(parent, "_project_name", None) != deleted_name:
            return None
        watcher = getattr(parent, "_file_watcher", None)
        if watcher is not None and hasattr(watcher, "unwatch_project"):
            watcher.unwatch_project(self.manager.PROJECTS_DIR / deleted_name)
        remaining = self.manager.get_projects()
        nav = getattr(parent, "nav", None)
        if remaining:
            fallback = remaining[0]["name"]
            if nav is not None and hasattr(nav, "set_project_context"):
                nav.set_project_context(fallback)
            else:
                parent.set_project_context(fallback)
        else:
            if nav is not None and hasattr(nav, "set_project_context"):
                nav.set_project_context(None)
            parent.set_project_context(None)
            sidebar = getattr(parent, "sidebar", None)
            if sidebar is not None and hasattr(sidebar, "set_project_context"):
                sidebar.set_project_context(None)
        # Refresh the currently visible page through its own set_project hook.
        content = getattr(parent, "content", None)
        current = content.currentWidget() if content is not None else None
        if current is not None and hasattr(current, "set_project"):
            current.set_project(remaining[0]["name"] if remaining else None)
        return remaining[0]["name"] if remaining else None

    def set_project(self, name=None):
        """Record the ACTIVE project context (RC-7.2.1).

        Called by the navigation controller with the current project; the
        active indicator on the cards reflects this value while the SELECTED
        project stays independent.
        """
        self._active_project = name
        self.refresh()

    def _on_search_changed(self, text):
        self._search_query = text.strip()
        self.refresh()

    def _on_sort_changed(self, value):
        self._sort_by = SORT_KEY_MAP.get(value, "last_modified")
        self.refresh()

    def _on_filter_changed(self, value):
        self._filter_status = value
        self.refresh()
