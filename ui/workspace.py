# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
import os
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from core.project_manager import ProjectManager
from core.theme import Dark, Fonts, Radius, Spacing
from core.notifications import NotificationService
from core.history_manager import HistoryManager
from operators.research.operator import ResearchOperator
from operators.research.prompt_builder import ResearchRequest
from core.research_storage import ResearchStorage
from operators.script.operator import ScriptOperator
from operators.script.models import ScriptRequest
from core.script_storage import ScriptStorage
from core.storyboard_storage import StoryboardStorage
from operators.storyboard.operator import StoryboardOperator
from operators.storyboard.models import StoryboardRequest
from operators.storyboard.parser import StoryboardParser
from core.image_prompt_storage import ImagePromptStorage
from operators.image_prompt.operator import ImagePromptOperator
from operators.image_prompt.models import ImagePromptRequest
from operators.image_prompt.parser import ImagePromptParser
from core.export_service import ExportService
from core.logger import get_logger
from core.task_manager import TaskCancelledError, TaskManager
from core.workflow import WORKFLOW_STAGES, advance_workflow_state, build_initial_workflow_state, normalize_workflow_state


class WorkspacePage(ctk.CTkFrame):
    def __init__(self, master, initial_project_name: Optional[str] = None):
        super().__init__(master, fg_color=Dark.BG)
        self.manager = ProjectManager()
        self.selected_name: Optional[str] = None
        self.initial_project_name = initial_project_name
        self.stages = WORKFLOW_STAGES
        self.selected_stage = self.stages[0]
        self.workflow_state: dict[str, str] = {}
        self.stage_buttons: dict[str, ctk.CTkButton] = {}
        self.project_menu: Optional[ctk.CTkOptionMenu] = None
        self.project_name_label: Optional[ctk.CTkLabel] = None
        self.project_status_label: Optional[ctk.CTkLabel] = None
        self.progress_bar: Optional[ctk.CTkProgressBar] = None
        self.current_stage_title: Optional[ctk.CTkLabel] = None
        self.current_stage_description: Optional[ctk.CTkLabel] = None
        self.project_overview_frame: Optional[ctk.CTkFrame] = None
        self.project_overview_name_label: Optional[ctk.CTkLabel] = None
        self.project_overview_status_label: Optional[ctk.CTkLabel] = None
        self.project_overview_progress_label: Optional[ctk.CTkLabel] = None
        self.project_overview_completed_label: Optional[ctk.CTkLabel] = None
        self.project_overview_current_label: Optional[ctk.CTkLabel] = None
        self.project_overview_next_label: Optional[ctk.CTkLabel] = None
        self.project_overview_modified_label: Optional[ctk.CTkLabel] = None
        self.placeholder_frame: Optional[ctk.CTkFrame] = None
        self.placeholder_label: Optional[ctk.CTkLabel] = None
        self.research_frame: Optional[ctk.CTkScrollableFrame] = None
        self.research_content: Optional[ctk.CTkFrame] = None
        self.topic_entry: Optional[ctk.CTkEntry] = None
        self.keywords_box: Optional[ctk.CTkTextbox] = None
        self.goal_box: Optional[ctk.CTkTextbox] = None
        self.sources_box: Optional[ctk.CTkTextbox] = None
        self.research_output_box: Optional[ctk.CTkTextbox] = None
        self.research_operator = ResearchOperator()
        self.research_storage = ResearchStorage()
        self.script_operator = ScriptOperator()
        self.script_storage = ScriptStorage()
        self.storyboard_operator = StoryboardOperator()
        self.storyboard_parser = StoryboardParser()
        self.storyboard_storage = StoryboardStorage()
        self.image_prompt_operator = ImagePromptOperator()
        self.image_prompt_parser = ImagePromptParser()
        self.image_prompt_storage = ImagePromptStorage()
        self.export_service = ExportService()
        self.task_manager = TaskManager()
        self.logger = get_logger()
        self.script_frame: Optional[ctk.CTkFrame] = None
        self.export_frame: Optional[ctk.CTkFrame] = None
        self.storyboard_frame: Optional[ctk.CTkFrame] = None
        self.image_prompt_frame: Optional[ctk.CTkFrame] = None
        self.image_prompt_toolbar: Optional[ctk.CTkFrame] = None
        self.image_prompt_container: Optional[ctk.CTkFrame] = None
        self.image_prompts: list[dict] = []
        self.storyboard_toolbar: Optional[ctk.CTkFrame] = None
        self.storyboard_scene_container: Optional[ctk.CTkFrame] = None
        self.storyboard_scenes: list[dict] = []
        self.task_status_frame: Optional[ctk.CTkFrame] = None
        self.task_status_content: Optional[ctk.CTkFrame] = None
        self.task_status_label: Optional[ctk.CTkLabel] = None
        self.task_progress_bar: Optional[ctk.CTkProgressBar] = None
        self.task_cancel_button: Optional[ctk.CTkButton] = None
        self.generate_button: Optional[ctk.CTkButton] = None
        self.script_generate_button: Optional[ctk.CTkButton] = None
        self.storyboard_generate_button: Optional[ctk.CTkButton] = None
        self.image_prompt_generate_button: Optional[ctk.CTkButton] = None
        self.export_generate_button: Optional[ctk.CTkButton] = None
        self.script_style_menu: Optional[ctk.CTkOptionMenu] = None
        self.script_length_menu: Optional[ctk.CTkOptionMenu] = None
        self.script_tone_menu: Optional[ctk.CTkOptionMenu] = None
        self.script_output_box: Optional[ctk.CTkTextbox] = None
        self._has_unsaved = False
        self._save_indicator: Optional[ctk.CTkLabel] = None
        self._last_saved_label: Optional[ctk.CTkLabel] = None
        self._autosave_id: Optional[str] = None
        self._history_manager = HistoryManager()
        self._notifications = NotificationService.get()
        self.build()

    def build(self) -> None:
        self.build_top_bar()

        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.build_sidebar(main_content)
        self.build_content(main_content)

        names = [project["name"] for project in self.manager.get_projects()] or ["No projects available"]
        if self.initial_project_name and self.initial_project_name in names:
            if self.project_menu is not None:
                self.project_menu.set(self.initial_project_name)
            self.load_project(self.initial_project_name)
        else:
            self.load_project(names[0])

        self.select_stage(self.selected_stage)
        self._start_autosave()

    def get_project_workflow_state(self, project_name: Optional[str]) -> dict[str, str]:
        if not project_name:
            return build_initial_workflow_state()

        project_data = self.manager.load_project(project_name) or {}
        workflow_state = normalize_workflow_state(project_data.get("workflow_state"))

        research_data = self.research_storage.load(project_name)
        if research_data.get("generated_research"):
            workflow_state["Research"] = "COMPLETED"
            if workflow_state.get("Script") == "LOCKED":
                workflow_state["Script"] = "AVAILABLE"

        script_data = self.script_storage.load(project_name)
        if script_data.get("script_output"):
            workflow_state["Script"] = "COMPLETED"
            if workflow_state.get("Storyboard") == "LOCKED":
                workflow_state["Storyboard"] = "AVAILABLE"

        storyboard_data = self.storyboard_storage.load(project_name)
        if storyboard_data.get("scenes"):
            workflow_state["Storyboard"] = "COMPLETED"
            if workflow_state.get("Image Prompts") == "LOCKED":
                workflow_state["Image Prompts"] = "AVAILABLE"

        image_prompt_data = self.image_prompt_storage.load(project_name)
        if image_prompt_data.get("prompts"):
            workflow_state["Image Prompts"] = "COMPLETED"
            workflow_state["Export"] = "AVAILABLE"

        if project_data.get("workflow_state") != workflow_state:
            project_data["workflow_state"] = workflow_state
            self.manager.update_project(project_name, project_data)

        return workflow_state

    def save_workflow_state(self, project_name: Optional[str]) -> None:
        if not project_name:
            return

        project_data = self.manager.load_project(project_name) or {}
        project_data["workflow_state"] = self.workflow_state
        self.manager.update_project(project_name, project_data)

    def refresh_stage_buttons(self) -> None:
        for stage, button in self.stage_buttons.items():
            state = self.workflow_state.get(stage, "LOCKED")
            if state == "LOCKED":
                button.configure(state="disabled", fg_color=Dark.SURFACE, hover_color=Dark.SURFACE, text_color=Dark.TEXT_MUTED)
            elif state == "AVAILABLE":
                button.configure(state="normal", fg_color=Dark.CARD, hover_color=Dark.HOVER, text_color=Dark.PRIMARY)
            else:
                button.configure(state="normal", fg_color=Dark.CARD, hover_color=Dark.HOVER, text_color=Dark.SUCCESS)

        if self.progress_bar is not None:
            completed_count = sum(1 for state in self.workflow_state.values() if state == "COMPLETED")
            self.progress_bar.set(completed_count / len(self.stages))

        self.update_project_overview()

    def build_top_bar(self) -> None:
        top_bar = ctk.CTkFrame(self, fg_color=Dark.SURFACE, corner_radius=Radius.LG)
        top_bar.pack(fill="x", padx=24, pady=(24, 16))

        left_column = ctk.CTkFrame(top_bar, fg_color="transparent")
        left_column.pack(side="left", padx=20, pady=16, anchor="w")

        self.project_name_label = ctk.CTkLabel(
            left_column, text="Project Name",
            font=Fonts.SECTION, text_color=Dark.TEXT,
        )
        self.project_name_label.pack(anchor="w")

        status_row = ctk.CTkFrame(left_column, fg_color="transparent")
        status_row.pack(anchor="w", pady=(6, 14))

        self.project_status_label = ctk.CTkLabel(
            status_row, text="Status: Draft",
            font=Fonts.BODY, text_color=Dark.SUCCESS,
        )
        self.project_status_label.pack(side="left")

        self._save_indicator = ctk.CTkLabel(
            status_row, text="", font=Fonts.TINY, text_color=Dark.TEXT_MUTED,
        )
        self._save_indicator.pack(side="left", padx=(Spacing.X3, 0))

        prog_row = ctk.CTkFrame(left_column, fg_color="transparent")
        prog_row.pack(anchor="w")

        ctk.CTkLabel(
            prog_row, text="Progress",
            font=Fonts.SMALL_BOLD, text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(
            prog_row, width=220, height=10,
            fg_color=Dark.SURFACE, progress_color=Dark.PRIMARY,
        )
        self.progress_bar.pack(side="left", padx=(Spacing.X3, 0))
        self.progress_bar.set(0.35)

        right_column = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_column.pack(side="right", padx=20, pady=16, anchor="e")

        nav_row = ctk.CTkFrame(right_column, fg_color="transparent")
        nav_row.pack(anchor="e", pady=(0, 8))

        self._prev_btn = ctk.CTkButton(
            nav_row, text="\u25C0 Prev", width=80, height=30,
            fg_color=Dark.CARD, hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY, font=Fonts.SMALL,
            corner_radius=Radius.SM, command=self._prev_stage,
        )
        self._prev_btn.pack(side="left", padx=(0, Spacing.X2))

        self._next_btn = ctk.CTkButton(
            nav_row, text="Next \u25B6", width=80, height=30,
            fg_color=Dark.PRIMARY, hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT, font=Fonts.SMALL_BOLD,
            corner_radius=Radius.SM, command=self._next_stage,
        )
        self._next_btn.pack(side="left")

        names = [project["name"] for project in self.manager.get_projects()] or ["No projects available"]
        self.project_menu = ctk.CTkOptionMenu(
            right_column, values=names, command=self.load_project,
            width=300, fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY, button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD, dropdown_hover_color=Dark.HOVER,
            text_color=Dark.TEXT,
        )
        self.project_menu.pack(anchor="e")

        self._last_saved_label = ctk.CTkLabel(
            right_column, text="", font=Fonts.TINY, text_color=Dark.TEXT_MUTED,
        )
        self._last_saved_label.pack(anchor="e", pady=(4, 0))

    def build_sidebar(self, parent: ctk.CTkFrame) -> None:
        sidebar = ctk.CTkFrame(parent, fg_color=Dark.SURFACE, width=250, corner_radius=Radius.LG)
        sidebar.pack(side="left", fill="y", padx=(0, 16))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="Production Pipeline",
            font=Fonts.CARD_TITLE,
            text_color=Dark.TEXT,
        ).pack(anchor="w", padx=20, pady=(20, 16))

        for stage in self.stages:
            button = ctk.CTkButton(
                sidebar,
                text=stage,
                height=42,
                corner_radius=Radius.MD,
                fg_color=Dark.CARD,
                hover_color=Dark.HOVER,
                text_color=Dark.TEXT_SECONDARY,
                font=Fonts.BODY,
                anchor="w",
                command=lambda stage_name=stage: self.select_stage(stage_name),
            )
            button.pack(fill="x", padx=16, pady=6)
            self.stage_buttons[stage] = button

        ctk.CTkLabel(sidebar, text="", fg_color="transparent").pack(fill="x", expand=True)

        ctk.CTkButton(
            sidebar, text="Version History", height=38,
            corner_radius=Radius.MD, fg_color=Dark.CARD,
            hover_color=Dark.HOVER, text_color=Dark.TEXT_SECONDARY,
            font=Fonts.SMALL, anchor="w",
            command=self._open_history,
        ).pack(fill="x", padx=16, pady=(8, 20))

    def build_content(self, parent: ctk.CTkFrame) -> None:
        content_panel = ctk.CTkScrollableFrame(parent, fg_color=Dark.SURFACE, corner_radius=Radius.LG)
        content_panel.pack(side="left", fill="both", expand=True)

        header = ctk.CTkFrame(content_panel, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        self.current_stage_title = ctk.CTkLabel(
            header,
            text="Research",
            font=Fonts.SECTION,
            text_color=Dark.TEXT,
        )
        self.current_stage_title.pack(anchor="w")

        self.current_stage_description = ctk.CTkLabel(
            content_panel,
            text="No content has been created yet.",
            text_color=Dark.TEXT_SECONDARY,
            font=Fonts.BODY,
        )
        self.current_stage_description.pack(anchor="w", padx=20, pady=(0, 12))

        self.build_project_overview(content_panel)
        self.build_placeholder(content_panel)
        self.build_research_ui(content_panel)
        self.build_script_ui(content_panel)
        self.build_storyboard_ui(content_panel)
        self.build_image_prompt_ui(content_panel)
        self.build_export_ui(content_panel)
        self.build_task_status_ui(content_panel)

        ctk.CTkButton(
            content_panel,
            text="Start Stage",
            width=180,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
        ).pack(anchor="e", padx=20, pady=(0, 16))

    def build_project_overview(self, parent: ctk.CTkFrame) -> None:
        self.project_overview_frame = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        self.project_overview_frame.pack(fill="x", padx=20, pady=(0, 12))

        overview_content = ctk.CTkFrame(self.project_overview_frame, fg_color="transparent")
        overview_content.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(
            overview_content,
            text="Project Overview",
            font=Fonts.CARD_TITLE,
            text_color=Dark.TEXT,
        ).pack(anchor="w")

        label_style = {"font": Fonts.BODY, "text_color": Dark.TEXT_SECONDARY}

        self.project_overview_name_label = ctk.CTkLabel(overview_content, text="Project Name: -", **label_style)
        self.project_overview_name_label.pack(anchor="w", pady=(10, 3))

        self.project_overview_status_label = ctk.CTkLabel(overview_content, text="Status: -", **label_style)
        self.project_overview_status_label.pack(anchor="w", pady=3)

        self.project_overview_progress_label = ctk.CTkLabel(overview_content, text="Overall Progress: 0%", **label_style)
        self.project_overview_progress_label.pack(anchor="w", pady=3)

        self.project_overview_completed_label = ctk.CTkLabel(overview_content, text="Completed Stages: -", **label_style)
        self.project_overview_completed_label.pack(anchor="w", pady=3)

        self.project_overview_current_label = ctk.CTkLabel(overview_content, text="Current Stage: -", **label_style)
        self.project_overview_current_label.pack(anchor="w", pady=3)

        self.project_overview_next_label = ctk.CTkLabel(overview_content, text="Next Stage: -", **label_style)
        self.project_overview_next_label.pack(anchor="w", pady=3)

        self.project_overview_modified_label = ctk.CTkLabel(overview_content, text="Last Modified: -", **label_style)
        self.project_overview_modified_label.pack(anchor="w", pady=3)

    def update_project_overview(self) -> None:
        if self.project_overview_name_label is None:
            return

        project_name = self.selected_name or "No Project Selected"
        project_data = self.manager.load_project(project_name) if self.selected_name else {}
        workflow_state = self.workflow_state or self.get_project_workflow_state(self.selected_name)

        completed_stages = [stage for stage in self.stages if workflow_state.get(stage) == "COMPLETED"]
        current_stage = next((stage for stage in self.stages if workflow_state.get(stage) == "AVAILABLE"), None)
        if current_stage is None:
            current_stage = completed_stages[-1] if completed_stages else self.stages[0]

        next_stage = None
        if current_stage in self.stages:
            current_index = self.stages.index(current_stage)
            for stage in self.stages[current_index + 1:]:
                if workflow_state.get(stage) != "COMPLETED":
                    next_stage = stage
                    break
        if next_stage is None and completed_stages and len(completed_stages) >= len(self.stages):
            next_stage = "All stages complete"
        elif next_stage is None:
            next_stage = "-"

        progress_pct = int(round((len(completed_stages) / len(self.stages)) * 100)) if self.stages else 0
        completed_text = ", ".join(completed_stages) if completed_stages else "None"
        status = project_data.get("status", "Draft") if project_data else "Draft"
        last_modified = project_data.get("last_modified") or project_data.get("created") or "-"

        self.project_overview_name_label.configure(text=f"Project Name: {project_name}")
        self.project_overview_status_label.configure(text=f"Status: {status}")
        self.project_overview_progress_label.configure(text=f"Overall Progress: {progress_pct}%")
        self.project_overview_completed_label.configure(text=f"Completed Stages: {completed_text}")
        self.project_overview_current_label.configure(text=f"Current Stage: {current_stage}")
        self.project_overview_next_label.configure(text=f"Next Stage: {next_stage}")
        self.project_overview_modified_label.configure(text=f"Last Modified: {last_modified}")

    def build_placeholder(self, parent: ctk.CTkFrame) -> None:
        self.placeholder_frame = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        self.placeholder_frame.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        self.placeholder_label = ctk.CTkLabel(
            self.placeholder_frame,
            text="No content has been created yet.",
            text_color=Dark.TEXT_MUTED,
            font=Fonts.CARD_TITLE,
        )
        self.placeholder_label.pack(expand=True)

    def build_research_ui(self, parent: ctk.CTkFrame) -> None:
        self.research_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
        )
        self.research_frame.pack_forget()

        self.research_content = ctk.CTkFrame(self.research_frame, fg_color="transparent")
        self.research_content.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self.research_content,
            text="Topic",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w")

        self.topic_entry = ctk.CTkEntry(
            self.research_content,
            width=420,
            height=38,
            fg_color=Dark.INPUT_BG,
            border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT,
            font=Fonts.INPUT,
            corner_radius=Radius.SM,
        )
        self.topic_entry.pack(fill="x", pady=(6, 14))
        self.topic_entry.configure(state="readonly")

        ctk.CTkLabel(
            self.research_content,
            text="Keywords",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w")

        self.keywords_box = ctk.CTkTextbox(
            self.research_content,
            height=80,
            corner_radius=Radius.SM,
            fg_color=Dark.INPUT_BG,
            text_color=Dark.TEXT,
        )
        self.keywords_box.pack(fill="x", pady=(6, 14))
        self.keywords_box.bind("<KeyRelease>", self._mark_unsaved)

        ctk.CTkLabel(
            self.research_content,
            text="Research Goal",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w")

        self.goal_box = ctk.CTkTextbox(
            self.research_content,
            height=80,
            corner_radius=Radius.SM,
            fg_color=Dark.INPUT_BG,
            text_color=Dark.TEXT,
        )
        self.goal_box.pack(fill="x", pady=(6, 14))
        self.goal_box.bind("<KeyRelease>", self._mark_unsaved)

        ctk.CTkLabel(
            self.research_content,
            text="Sources",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w")

        self.sources_box = ctk.CTkTextbox(
            self.research_content,
            height=80,
            corner_radius=Radius.SM,
            fg_color=Dark.INPUT_BG,
            text_color=Dark.TEXT,
        )
        self.sources_box.pack(fill="x", pady=(6, 14))
        self.sources_box.bind("<KeyRelease>", self._mark_unsaved)

        research_actions = ctk.CTkFrame(self.research_content, fg_color="transparent")
        research_actions.pack(fill="x", pady=(4, 16))

        ctk.CTkButton(
            research_actions,
            text="Preview Prompt",
            width=160,
            height=42,
            corner_radius=Radius.MD,
            fg_color="transparent",
            hover_color=Dark.HOVER,
            text_color=Dark.SECONDARY,
            border_width=1,
            border_color=Dark.SECONDARY,
            font=Fonts.BUTTON,
            command=self.preview_research_prompt,
        ).pack(side="left")

        self.generate_button = ctk.CTkButton(
            research_actions,
            text="Generate Research",
            width=200,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            command=self.generate_research,
        )
        self.generate_button.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            research_actions,
            text="Save Research",
            width=150,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.CARD,
            hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY,
            border_width=1,
            border_color=Dark.BORDER,
            font=Fonts.BUTTON,
            command=self.save_research,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            self.research_content,
            text="Research Output",
            font=Fonts.CARD_TITLE,
            text_color=Dark.TEXT,
        ).pack(anchor="w")

        self.research_output_box = ctk.CTkTextbox(
            self.research_content,
            height=180,
            corner_radius=Radius.SM,
            fg_color=Dark.INPUT_BG,
            text_color=Dark.TEXT,
        )
        self.research_output_box.pack(fill="both", expand=True, pady=(8, 0))
        self.research_output_box.insert("0.0", "No research generated.")

    def build_script_ui(self, parent: ctk.CTkFrame) -> None:
        self.script_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.script_frame.pack_forget()

        script_content = ctk.CTkFrame(self.script_frame, fg_color="transparent")
        script_content.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        label_style = {"font": Fonts.SMALL_BOLD, "text_color": Dark.TEXT_SECONDARY}

        ctk.CTkLabel(script_content, text="Script Style", **label_style).pack(anchor="w")

        self.script_style_menu = ctk.CTkOptionMenu(
            script_content,
            values=["Educational", "Documentary", "Storytelling"],
            width=320,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BODY,
        )
        self.script_style_menu.pack(fill="x", pady=(6, 14))

        ctk.CTkLabel(script_content, text="Script Length", **label_style).pack(anchor="w")

        self.script_length_menu = ctk.CTkOptionMenu(
            script_content,
            values=["Short", "Medium", "Long"],
            width=320,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BODY,
        )
        self.script_length_menu.pack(fill="x", pady=(6, 14))

        ctk.CTkLabel(script_content, text="Tone", **label_style).pack(anchor="w")

        self.script_tone_menu = ctk.CTkOptionMenu(
            script_content,
            values=["Friendly", "Funny", "Serious", "Dramatic"],
            width=320,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BODY,
        )
        self.script_tone_menu.pack(fill="x", pady=(6, 14))

        script_actions = ctk.CTkFrame(script_content, fg_color="transparent")
        script_actions.pack(fill="x", pady=(4, 16))

        ctk.CTkButton(
            script_actions,
            text="Preview Prompt",
            width=160,
            height=42,
            corner_radius=Radius.MD,
            fg_color="transparent",
            hover_color=Dark.HOVER,
            text_color=Dark.SECONDARY,
            border_width=1,
            border_color=Dark.SECONDARY,
            font=Fonts.BUTTON,
            command=self.preview_script_prompt,
        ).pack(side="left")

        self.script_generate_button = ctk.CTkButton(
            script_actions,
            text="Generate Script",
            width=180,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            command=self.generate_script,
        )
        self.script_generate_button.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            script_actions,
            text="Save Script",
            width=140,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.CARD,
            hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY,
            border_width=1,
            border_color=Dark.BORDER,
            font=Fonts.BUTTON,
            command=self.save_script,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            script_content,
            text="Script Output",
            font=Fonts.CARD_TITLE,
            text_color=Dark.TEXT,
        ).pack(anchor="w")

        self.script_output_box = ctk.CTkTextbox(
            script_content,
            height=280,
            corner_radius=Radius.SM,
            fg_color=Dark.INPUT_BG,
            text_color=Dark.TEXT,
        )
        self.script_output_box.pack(fill="both", expand=True, pady=(8, 0))

    def build_storyboard_ui(self, parent: ctk.CTkFrame) -> None:
        self.storyboard_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.storyboard_frame.pack_forget()

        storyboard_content = ctk.CTkFrame(self.storyboard_frame, fg_color="transparent")
        storyboard_content.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self.storyboard_toolbar = ctk.CTkFrame(storyboard_content, fg_color="transparent")
        self.storyboard_toolbar.pack(fill="x", pady=(0, 12))

        self.storyboard_generate_button = ctk.CTkButton(
            self.storyboard_toolbar,
            text="Generate Storyboard",
            width=200,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            command=self.generate_storyboard,
        )
        self.storyboard_generate_button.pack(side="left")

        ctk.CTkButton(
            self.storyboard_toolbar,
            text="Save Storyboard",
            width=180,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.CARD,
            hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY,
            border_width=1,
            border_color=Dark.BORDER,
            font=Fonts.BUTTON,
            command=self.save_storyboard,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            self.storyboard_toolbar,
            text="+ Add Scene",
            width=140,
            height=42,
            corner_radius=Radius.MD,
            fg_color="transparent",
            hover_color=Dark.HOVER,
            text_color=Dark.PRIMARY,
            border_width=1,
            border_color=Dark.PRIMARY,
            font=Fonts.BUTTON,
            command=self.add_scene,
        ).pack(side="left", padx=(10, 0))

        self.storyboard_scene_container = ctk.CTkScrollableFrame(
            storyboard_content,
            fg_color="transparent",
        )
        self.storyboard_scene_container.pack(fill="both", expand=True)

    def build_image_prompt_ui(self, parent: ctk.CTkFrame) -> None:
        self.image_prompt_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.image_prompt_frame.pack_forget()

        prompt_content = ctk.CTkFrame(self.image_prompt_frame, fg_color="transparent")
        prompt_content.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self.image_prompt_toolbar = ctk.CTkFrame(prompt_content, fg_color="transparent")
        self.image_prompt_toolbar.pack(fill="x", pady=(0, 12))

        self.image_prompt_generate_button = ctk.CTkButton(
            self.image_prompt_toolbar,
            text="Generate Prompts",
            width=200,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            command=self.generate_image_prompts,
        )
        self.image_prompt_generate_button.pack(side="left")

        ctk.CTkButton(
            self.image_prompt_toolbar,
            text="Save",
            width=120,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.CARD,
            hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY,
            border_width=1,
            border_color=Dark.BORDER,
            font=Fonts.BUTTON,
            command=self.save_image_prompts,
        ).pack(side="left", padx=(10, 0))

        self.image_prompt_container = ctk.CTkScrollableFrame(
            prompt_content,
            fg_color="transparent",
        )
        self.image_prompt_container.pack(fill="both", expand=True)

    def build_task_status_ui(self, parent: ctk.CTkFrame) -> None:
        self.task_status_frame = ctk.CTkFrame(
            parent, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER,
        )
        self.task_status_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.task_status_content = ctk.CTkFrame(self.task_status_frame, fg_color="transparent")
        self.task_status_content.pack(fill="x", padx=18, pady=16)

        ctk.CTkLabel(self.task_status_content, text="Background Task", font=Fonts.CARD_TITLE, text_color=Dark.TEXT).pack(anchor="w")
        self.task_status_label = ctk.CTkLabel(self.task_status_content, text="Idle", font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY)
        self.task_status_label.pack(anchor="w", pady=(8, 6))

        self.task_progress_bar = ctk.CTkProgressBar(
            self.task_status_content, width=260, height=10,
            fg_color=Dark.SURFACE, progress_color=Dark.PRIMARY,
        )
        self.task_progress_bar.pack(anchor="w", pady=(4, 8))
        self.task_progress_bar.set(0.0)

        self.task_cancel_button = ctk.CTkButton(
            self.task_status_content,
            text="Cancel",
            width=140,
            height=36,
            corner_radius=Radius.SM,
            fg_color="#2A1215",
            hover_color="#3D1A1E",
            text_color=Dark.ERROR,
            font=Fonts.BUTTON,
            command=self.cancel_current_task,
            state="disabled",
        )
        self.task_cancel_button.pack(anchor="w")

    def build_export_ui(self, parent: ctk.CTkFrame) -> None:
        self.export_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.export_frame.pack_forget()

        export_content = ctk.CTkFrame(self.export_frame, fg_color="transparent")
        export_content.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self.export_generate_button = ctk.CTkButton(
            export_content,
            text="Export Project",
            width=220,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            command=self.export_project,
        )
        self.export_generate_button.pack(anchor="w")

        ctk.CTkButton(
            export_content,
            text="Open Export Folder",
            width=220,
            height=42,
            corner_radius=Radius.MD,
            fg_color=Dark.CARD,
            hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY,
            border_width=1,
            border_color=Dark.BORDER,
            font=Fonts.BUTTON,
            command=self.open_export_folder,
        ).pack(anchor="w", pady=(10, 0))

    def _pack_stage_frame(self, frame: Optional[ctk.CTkFrame]) -> None:
        if frame is None:
            return
        if self.task_status_frame is not None:
            frame.pack(fill="x", padx=20, pady=(0, 12), before=self.task_status_frame)
        else:
            frame.pack(fill="x", padx=20, pady=(0, 12))

    def _show_frame(self, target: ctk.CTkFrame | None) -> None:
        self._pack_stage_frame(target)
        for f in (self.placeholder_frame, self.research_frame, self.script_frame,
                  self.storyboard_frame, self.image_prompt_frame, self.export_frame):
            if f is not None and f is not target:
                f.pack_forget()

    def show_placeholder(self) -> None:
        self._show_frame(self.placeholder_frame)

    def show_research(self) -> None:
        self._show_frame(self.research_frame)

    def show_script(self) -> None:
        self._show_frame(self.script_frame)

    def show_storyboard(self) -> None:
        self._show_frame(self.storyboard_frame)

    def show_image_prompts(self) -> None:
        self._show_frame(self.image_prompt_frame)

    def show_export(self) -> None:
        self._show_frame(self.export_frame)

    def select_stage(self, stage_name: str) -> None:
        if self.workflow_state.get(stage_name, "LOCKED") == "LOCKED":
            return

        self.selected_stage = stage_name
        self.refresh_stage_buttons()
        self.update_content(stage_name)
        self._update_nav_buttons()

    def update_content(self, stage_name: str) -> None:
        if self.current_stage_title is not None:
            self.current_stage_title.configure(text=stage_name)

        stage_state = self.workflow_state.get(stage_name, "LOCKED")
        descriptions = {
            "Research": "Define your research inputs and generate content.",
            "Script": "Configure script parameters and generate a script.",
            "Storyboard": "Generate and edit storyboard scenes.",
            "Image Prompts": "Generate image prompts for each storyboard scene.",
            "Export": "Export the project to a local folder.",
        }
        if self.current_stage_description is not None:
            if stage_state == "COMPLETED":
                self.current_stage_description.configure(text=f"{stage_name} — Completed.")
            else:
                self.current_stage_description.configure(text=descriptions.get(stage_name, "No content has been created yet."))

        if self.placeholder_label is not None:
            self.placeholder_label.configure(text=f"{stage_name}\n\nNo content has been created yet.")

        stage_show = {
            "Research": self.show_research,
            "Script": self.show_script,
            "Storyboard": self.show_storyboard,
            "Image Prompts": self.show_image_prompts,
            "Export": self.show_export,
        }
        show_fn = stage_show.get(stage_name, self.show_placeholder)
        show_fn()

    def load_project(self, name: Optional[str]) -> None:
        self.selected_name = name if name not in (None, "No projects available") else None
        if self.selected_name:
            self.logger.info("Workspace", f"Project loaded: {self.selected_name}")
        self.workflow_state = self.get_project_workflow_state(self.selected_name)
        self.refresh_stage_buttons()

        if self.project_name_label is not None:
            if self.selected_name:
                self.project_name_label.configure(text=self.selected_name)
            else:
                self.project_name_label.configure(text="No Project Selected")

        if self.project_status_label is not None:
            if self.selected_name:
                data = self.manager.load_project(self.selected_name)
                status = data.get("status", "Draft") if data else "Draft"
                self.project_status_label.configure(text=f"Status: {status}")
            else:
                self.project_status_label.configure(text="Status: Draft")

        if self.progress_bar is not None:
            done_count = sum(1 for state in self.workflow_state.values() if state == "COMPLETED")
            self.progress_bar.set(done_count / len(self.stages))

        if self.selected_name and self.topic_entry is not None:
            project_data = self.manager.load_project(self.selected_name)
            topic = project_data.get("topic", "") if project_data else ""
            self.topic_entry.configure(state="normal")
            self.topic_entry.delete("0", "end")
            self.topic_entry.insert("0", topic or "No topic available")
            self.topic_entry.configure(state="readonly")
        elif self.topic_entry is not None:
            self.topic_entry.configure(state="normal")
            self.topic_entry.delete("0", "end")
            self.topic_entry.insert("0", "No topic available")
            self.topic_entry.configure(state="readonly")

        if self.selected_name is not None:
            data = self.research_storage.load(self.selected_name)
            if self.keywords_box is not None:
                self.keywords_box.delete("1.0", "end")
                self.keywords_box.insert("1.0", data.get("keywords", ""))
            if self.goal_box is not None:
                self.goal_box.delete("1.0", "end")
                self.goal_box.insert("1.0", data.get("goal", ""))
            if self.sources_box is not None:
                self.sources_box.delete("1.0", "end")
                self.sources_box.insert("1.0", data.get("sources", ""))
            if self.research_output_box is not None:
                self.research_output_box.delete("0.0", "end")
                self.research_output_box.insert(
                    "0.0",
                    data.get("generated_research") or data.get("prompt_preview", "No research generated."),
                )

            script_data = self.script_storage.load(self.selected_name)
            if self.script_style_menu is not None:
                self.script_style_menu.set(script_data.get("style", "Educational"))
            if self.script_length_menu is not None:
                self.script_length_menu.set(script_data.get("length", "Medium"))
            if self.script_tone_menu is not None:
                self.script_tone_menu.set(script_data.get("tone", "Friendly"))
            if self.script_output_box is not None:
                self.script_output_box.delete("0.0", "end")
                self.script_output_box.insert("0.0", script_data.get("script_output", ""))

            storyboard_data = self.storyboard_storage.load(self.selected_name)
            self.storyboard_scenes = storyboard_data.get("scenes", [])
            self.render_storyboard_scenes()

            prompt_data = self.image_prompt_storage.load(self.selected_name)
            self.image_prompts = prompt_data.get("prompts", [])
            self.render_image_prompts()

        if self.selected_name is not None:
            self.refresh_stage_buttons()
            if self.workflow_state.get(self.selected_stage, "LOCKED") == "LOCKED":
                self.select_stage("Research")
            else:
                self.select_stage(self.selected_stage)

        self._has_unsaved = False
        self._update_save_indicator("Loaded")
        self._update_nav_buttons()

    def collect_research_inputs(self) -> dict[str, str]:
        topic = ""
        keywords = ""
        goal = ""
        sources = ""

        if self.topic_entry is not None:
            topic = self.topic_entry.get().strip()
        if self.keywords_box is not None:
            keywords = self.keywords_box.get("1.0", "end").strip()
        if self.goal_box is not None:
            goal = self.goal_box.get("1.0", "end").strip()
        if self.sources_box is not None:
            sources = self.sources_box.get("1.0", "end").strip()

        return {
            "topic": topic,
            "keywords": keywords,
            "goal": goal,
            "sources": sources,
        }

    def preview_research_prompt(self) -> None:
        inputs = self.collect_research_inputs()
        is_valid = self.validate_research_inputs(inputs)
        if not is_valid:
            if self.research_output_box is not None:
                self.research_output_box.delete("1.0", "end")
                self.research_output_box.insert("1.0", "Topic must not be empty.")
            return

        prompt_preview = self.build_research_prompt(inputs)
        if self.research_output_box is not None:
            self.research_output_box.delete("1.0", "end")
            self.research_output_box.insert("1.0", prompt_preview)

    def save_research(self) -> None:
        if self.selected_name is None:
            return

        inputs = self.collect_research_inputs()
        is_valid = self.validate_research_inputs(inputs)
        if not is_valid:
            if self.research_output_box is not None:
                self.research_output_box.delete("0.0", "end")
                self.research_output_box.insert("0.0", "Topic must not be empty.")
            return

        prompt_preview = self.build_research_prompt(inputs)
        generated_research = ""
        if self.research_output_box is not None:
            generated_research = self.research_output_box.get("0.0", "end").strip()

        self.research_storage.save(
            project_name=self.selected_name,
            topic=inputs.get("topic", ""),
            keywords=inputs.get("keywords", ""),
            goal=inputs.get("goal", ""),
            sources=inputs.get("sources", ""),
            prompt_preview=prompt_preview,
            generated_research=generated_research,
        )

    def validate_research_inputs(self, inputs: dict[str, str]) -> bool:
        return bool(inputs.get("topic", ""))

    def build_research_prompt(self, inputs: dict[str, str]) -> str:
        request = ResearchRequest(
            topic=inputs.get("topic", ""),
            keywords=inputs.get("keywords", ""),
            goal=inputs.get("goal", ""),
            sources=inputs.get("sources", ""),
        )
        return self.research_operator.get_prompt_preview(request)

    def collect_script_inputs(self) -> dict[str, str]:
        return {
            "style": self.script_style_menu.get() if self.script_style_menu is not None else "Educational",
            "length": self.script_length_menu.get() if self.script_length_menu is not None else "Medium",
            "tone": self.script_tone_menu.get() if self.script_tone_menu is not None else "Friendly",
        }

    def build_script_prompt(self, inputs: dict[str, str]) -> str:
        if self.selected_name is None:
            return ""

        research_data = self.research_storage.load(self.selected_name)
        request = ScriptRequest(
            topic=research_data.get("topic", ""),
            style=inputs.get("style", "Educational"),
            length=inputs.get("length", "Medium"),
            tone=inputs.get("tone", "Friendly"),
            keywords=research_data.get("keywords", ""),
            goal=research_data.get("goal", ""),
        )
        return self.script_operator.get_prompt_preview(request)

    def preview_script_prompt(self) -> None:
        if self.selected_name is None:
            return

        inputs = self.collect_script_inputs()
        prompt_preview = self.build_script_prompt(inputs)
        if self.script_output_box is not None:
            self.script_output_box.delete("1.0", "end")
            self.script_output_box.insert("1.0", prompt_preview)

    def save_script(self) -> None:
        if self.selected_name is None:
            return

        inputs = self.collect_script_inputs()
        script_output = ""
        if self.script_output_box is not None:
            script_output = self.script_output_box.get("1.0", "end").strip()

        self.script_storage.save(
            project_name=self.selected_name,
            style=inputs.get("style", "Educational"),
            length=inputs.get("length", "Medium"),
            tone=inputs.get("tone", "Friendly"),
            script_output=script_output,
        )

    def toggle_task_controls(self, running: bool) -> None:
        active_button = None
        if self.selected_stage == "Research":
            active_button = self.generate_button
        elif self.selected_stage == "Script":
            active_button = self.script_generate_button
        elif self.selected_stage == "Storyboard":
            active_button = self.storyboard_generate_button
        elif self.selected_stage == "Image Prompts":
            active_button = self.image_prompt_generate_button
        elif self.selected_stage == "Export":
            active_button = self.export_generate_button

        if active_button is not None:
            active_button.configure(state="disabled" if running else "normal")
        if self.script_style_menu is not None and self.selected_stage == "Script":
            self.script_style_menu.configure(state="disabled" if running else "normal")
        if self.script_length_menu is not None and self.selected_stage == "Script":
            self.script_length_menu.configure(state="disabled" if running else "normal")
        if self.script_tone_menu is not None and self.selected_stage == "Script":
            self.script_tone_menu.configure(state="disabled" if running else "normal")
        if self.task_cancel_button is not None:
            self.task_cancel_button.configure(state="normal" if running else "disabled")
        if self.task_progress_bar is not None:
            self.task_progress_bar.set(0.0 if not running else self.task_manager.progress)

    def update_task_status(self, message: str, progress: float = 0.0) -> None:
        if self.task_status_label is not None:
            self.task_status_label.configure(text=message)
        if self.task_progress_bar is not None:
            self.task_progress_bar.set(progress)

    def schedule_ui_update(self, callback, *args, **kwargs) -> None:
        def _safe_call():
            if self.winfo_exists():
                callback(*args, **kwargs)
        self.after(0, _safe_call)

    def cancel_current_task(self) -> None:
        self.task_manager.cancel()
        self.update_task_status("Cancelling task...")

    def generate_research(self) -> None:
        inputs = self.collect_research_inputs()
        if not self.validate_research_inputs(inputs):
            if self.research_output_box is not None:
                self.research_output_box.delete("0.0", "end")
                self.research_output_box.insert("0.0", "Topic must not be empty.")
            return

        self.schedule_ui_update(self.toggle_task_controls, True)
        self.schedule_ui_update(self.update_task_status, "Generating research...", 0.1)

        def run_task(task_manager: TaskManager) -> tuple[str, str]:
            task_manager.update_progress(0.2, "Preparing research request...")
            request = ResearchRequest(
                topic=inputs.get("topic", ""),
                keywords=inputs.get("keywords", ""),
                goal=inputs.get("goal", ""),
                sources=inputs.get("sources", ""),
            )
            prompt = self.research_operator.get_prompt_preview(request)
            task_manager.update_progress(0.6, "Generating research content...")
            generated_research = self.research_operator.execute(request)
            if task_manager.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            task_manager.update_progress(0.95, "Saving research output...")
            return generated_research, prompt

        def on_complete(result: tuple[str, str]) -> None:
            generated_research, prompt = result

            if self.selected_name is not None:
                self.research_storage.save(
                    project_name=self.selected_name,
                    topic=inputs.get("topic", ""),
                    keywords=inputs.get("keywords", ""),
                    goal=inputs.get("goal", ""),
                    sources=inputs.get("sources", ""),
                    prompt_preview=prompt,
                    generated_research=generated_research,
                )
                self.logger.info("Workspace", f"Research generation completed for project: {self.selected_name}")
                self.workflow_state = advance_workflow_state(self.workflow_state, "Research")
                self.save_workflow_state(self.selected_name)

            def _update_ui() -> None:
                if self.research_output_box is not None:
                    self.research_output_box.delete("0.0", "end")
                    self.research_output_box.insert("0.0", generated_research)
                self.refresh_stage_buttons()
                self.update_content(self.selected_stage)
                self.toggle_task_controls(False)
                self.update_task_status("Research generation complete.", 1.0)

            self.schedule_ui_update(_update_ui)

        def on_error(exc: Exception) -> None:
            self.schedule_ui_update(self.toggle_task_controls, False)
            self.schedule_ui_update(self.update_task_status, f"Error: {exc}", 0.0)

        self.task_manager.run_task(
            task_name="Generate Research",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def generate_script(self) -> None:
        if self.selected_name is None:
            return

        script_inputs = self.collect_script_inputs()
        style = script_inputs.get("style", "Educational")
        length = script_inputs.get("length", "Medium")
        tone = script_inputs.get("tone", "Friendly")

        self.schedule_ui_update(self.toggle_task_controls, True)
        self.schedule_ui_update(self.update_task_status, "Generating script...", 0.1)

        def run_task(task_manager: TaskManager) -> str:
            task_manager.update_progress(0.15, "Loading research data...")
            research_data = self.research_storage.load(self.selected_name)
            task_manager.update_progress(0.25, "Preparing script request...")
            request = ScriptRequest(
                topic=research_data.get("topic", ""),
                style=style,
                length=length,
                tone=tone,
                keywords=research_data.get("keywords", ""),
                goal=research_data.get("goal", ""),
            )
            task_manager.update_progress(0.4, "Generating script...")
            generated_script = self.script_operator.execute(request)
            if task_manager.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            task_manager.update_progress(0.95, "Saving script output...")
            return generated_script

        def on_complete(generated_script: str) -> None:
            self.script_storage.save(
                project_name=self.selected_name,
                style=style,
                length=length,
                tone=tone,
                script_output=generated_script,
            )
            self.logger.info("Workspace", f"Script generation completed for project: {self.selected_name}")
            self.workflow_state = advance_workflow_state(self.workflow_state, "Script")
            self.save_workflow_state(self.selected_name)

            def _update_ui() -> None:
                if self.script_output_box is not None:
                    self.script_output_box.delete("0.0", "end")
                    self.script_output_box.insert("0.0", generated_script)
                self.refresh_stage_buttons()
                self.update_content(self.selected_stage)
                self.toggle_task_controls(False)
                self.update_task_status("Script generation complete.", 1.0)

            self.schedule_ui_update(_update_ui)

        def on_error(exc: Exception) -> None:
            self.schedule_ui_update(self.toggle_task_controls, False)
            self.schedule_ui_update(self.update_task_status, f"Error: {exc}", 0.0)

        self.task_manager.run_task(
            task_name="Generate Script",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def render_storyboard_scenes(self) -> None:
        if self.storyboard_scene_container is None:
            return

        for widget in self.storyboard_scene_container.winfo_children():
            widget.destroy()

        if not self.storyboard_scenes:
            ctk.CTkLabel(
                self.storyboard_scene_container,
                text="No storyboard scenes yet.",
                font=Fonts.BODY,
                text_color=Dark.TEXT_MUTED,
            ).pack(anchor="w")
            return

        for index, scene in enumerate(self.storyboard_scenes):
            scene_number = scene.get("scene_number", index + 1)
            scene["scene_number"] = scene_number
            card = ctk.CTkFrame(
                self.storyboard_scene_container, fg_color=Dark.CARD,
                corner_radius=Radius.LG, border_width=1, border_color=Dark.BORDER,
            )
            card.pack(fill="x", pady=(0, 12))

            card_content = ctk.CTkFrame(card, fg_color="transparent")
            card_content.pack(fill="x", padx=16, pady=16)

            ctk.CTkLabel(card_content, text=f"Scene #{scene_number}", font=Fonts.CARD_TITLE, text_color=Dark.TEXT).pack(anchor="w")
            ctk.CTkLabel(card_content, text=f"Timestamp: {scene.get('timestamp', '-')}", font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY).pack(anchor="w", pady=(6, 0))

            textboxes: dict[str, ctk.CTkTextbox] = {}
            for field_name, label in [
                ("narration", "Narration"),
                ("visual_description", "Visual Description"),
                ("camera_direction", "Camera Direction"),
                ("on_screen_text", "On-screen Text"),
            ]:
                ctk.CTkLabel(card_content, text=label, font=Fonts.SMALL_BOLD, text_color=Dark.TEXT_SECONDARY).pack(anchor="w", pady=(10, 2))
                textbox = ctk.CTkTextbox(
                    card_content, height=70, corner_radius=Radius.SM,
                    fg_color=Dark.INPUT_BG, text_color=Dark.TEXT,
                )
                textbox.pack(fill="x", pady=(0, 6))
                textbox.insert("0.0", scene.get(field_name, ""))
                textboxes[field_name] = textbox

            scene["_textboxes"] = textboxes

            actions = ctk.CTkFrame(card_content, fg_color="transparent")
            actions.pack(fill="x", pady=(8, 0))
            ctk.CTkButton(
                actions, text="Delete", width=100,
                fg_color="#2A1215", hover_color="#3D1A1E",
                text_color=Dark.ERROR, font=Fonts.BUTTON,
                corner_radius=Radius.SM,
                command=lambda scene_copy=scene: self.delete_scene(scene_copy),
            ).pack(side="left")
            ctk.CTkButton(
                actions, text="Move Up", width=100,
                fg_color=Dark.CARD, hover_color=Dark.HOVER,
                text_color=Dark.TEXT_SECONDARY, font=Fonts.BUTTON,
                corner_radius=Radius.SM,
                command=lambda scene_copy=scene: self.move_scene(scene_copy, -1),
            ).pack(side="left", padx=(8, 0))
            ctk.CTkButton(
                actions, text="Move Down", width=100,
                fg_color=Dark.CARD, hover_color=Dark.HOVER,
                text_color=Dark.TEXT_SECONDARY, font=Fonts.BUTTON,
                corner_radius=Radius.SM,
                command=lambda scene_copy=scene: self.move_scene(scene_copy, 1),
            ).pack(side="left", padx=(8, 0))

    def add_scene(self) -> None:
        next_number = len(self.storyboard_scenes) + 1
        self.storyboard_scenes.append(
            {
                "scene_number": next_number,
                "timestamp": f"{(next_number - 1) * 10:02d}:00",
                "narration": "New scene narration.",
                "visual_description": "New visual description.",
                "camera_direction": "New camera direction.",
                "on_screen_text": "New on-screen text.",
            }
        )
        self.render_storyboard_scenes()

    def delete_scene(self, scene: dict) -> None:
        self.storyboard_scenes = [item for item in self.storyboard_scenes if item is not scene]
        for index, item in enumerate(self.storyboard_scenes, start=1):
            item["scene_number"] = index
        self.render_storyboard_scenes()

    def move_scene(self, scene: dict, direction: int) -> None:
        index = next((idx for idx, item in enumerate(self.storyboard_scenes) if item is scene), None)
        if index is None:
            return
        new_index = index + direction
        if 0 <= new_index < len(self.storyboard_scenes):
            self.storyboard_scenes.insert(new_index, self.storyboard_scenes.pop(index))
            for idx, item in enumerate(self.storyboard_scenes, start=1):
                item["scene_number"] = idx
            self.render_storyboard_scenes()

    def generate_storyboard(self) -> None:
        if self.selected_name is None:
            return

        self.schedule_ui_update(self.toggle_task_controls, True)
        self.schedule_ui_update(self.update_task_status, "Generating storyboard...", 0.1)

        def run_task(task_manager: TaskManager) -> list[dict]:
            task_manager.update_progress(0.15, "Loading script data...")
            script_data = self.script_storage.load(self.selected_name)
            task_manager.update_progress(0.25, "Preparing storyboard request...")
            script_text = (script_data.get("script_output") or "").strip()
            topic = script_text.splitlines()[0].replace("Title:", "").strip() if script_text else ""
            length = (script_data.get("length") or "Medium").strip()
            request = StoryboardRequest(
                script_text=script_text,
                topic=topic,
                length=length,
            )
            task_manager.update_progress(0.4, "Generating storyboard...")
            raw_response = self.storyboard_operator.execute(request)
            if task_manager.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            task_manager.update_progress(0.85, "Parsing storyboard scenes...")
            scenes = self.storyboard_parser.parse(raw_response)
            task_manager.update_progress(0.95, "Saving storyboard scenes...")
            return scenes

        def on_complete(scenes: list[dict]) -> None:
            self.storyboard_scenes = scenes
            self.storyboard_storage.save(self.selected_name, scenes)
            self.logger.info("Workspace", f"Storyboard generation completed for project: {self.selected_name}")
            self.workflow_state = advance_workflow_state(self.workflow_state, "Storyboard")
            self.save_workflow_state(self.selected_name)

            def _update_ui() -> None:
                self.render_storyboard_scenes()
                self.refresh_stage_buttons()
                self.update_content(self.selected_stage)
                self.toggle_task_controls(False)
                self.update_task_status("Storyboard generation complete.", 1.0)

            self.schedule_ui_update(_update_ui)

        def on_error(exc: Exception) -> None:
            self.schedule_ui_update(self.toggle_task_controls, False)
            self.schedule_ui_update(self.update_task_status, f"Error: {exc}", 0.0)

        self.task_manager.run_task(
            task_name="Generate Storyboard",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def save_storyboard(self) -> None:
        if self.selected_name is None:
            return

        scenes = []
        for scene in self.storyboard_scenes:
            if not isinstance(scene, dict):
                continue

            textboxes = scene.get("_textboxes", {})
            narration = textboxes.get("narration")
            visual_description = textboxes.get("visual_description")
            camera_direction = textboxes.get("camera_direction")
            on_screen_text = textboxes.get("on_screen_text")

            scenes.append({
                "scene_number": scene.get("scene_number", 1),
                "timestamp": scene.get("timestamp", "00:00"),
                "narration": narration.get("1.0", "end").strip() if narration is not None else scene.get("narration", ""),
                "visual_description": visual_description.get("1.0", "end").strip() if visual_description is not None else scene.get("visual_description", ""),
                "camera_direction": camera_direction.get("1.0", "end").strip() if camera_direction is not None else scene.get("camera_direction", ""),
                "on_screen_text": on_screen_text.get("1.0", "end").strip() if on_screen_text is not None else scene.get("on_screen_text", ""),
            })

        self.storyboard_scenes = scenes
        self.storyboard_storage.save(self.selected_name, scenes)

    def render_image_prompts(self) -> None:
        if self.image_prompt_container is None:
            return

        for widget in self.image_prompt_container.winfo_children():
            widget.destroy()

        if not self.image_prompts:
            ctk.CTkLabel(
                self.image_prompt_container,
                text="No image prompts yet.",
                font=Fonts.BODY,
                text_color=Dark.TEXT_MUTED,
            ).pack(anchor="w")
            return

        for prompt in self.image_prompts:
            card = ctk.CTkFrame(
                self.image_prompt_container, fg_color=Dark.CARD,
                corner_radius=Radius.LG, border_width=1, border_color=Dark.BORDER,
            )
            card.pack(fill="x", pady=(0, 12))
            card_content = ctk.CTkFrame(card, fg_color="transparent")
            card_content.pack(fill="x", padx=16, pady=16)

            ctk.CTkLabel(card_content, text=f"Scene #{prompt.get('scene_number', 1)}", font=Fonts.CARD_TITLE, text_color=Dark.TEXT).pack(anchor="w")
            ctk.CTkLabel(card_content, text=f"Timestamp: {prompt.get('timestamp', '-')}", font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY).pack(anchor="w", pady=(6, 0))
            ctk.CTkLabel(card_content, text=prompt.get("prompt_title", "Prompt"), font=Fonts.SMALL_BOLD, text_color=Dark.TEXT_SECONDARY).pack(anchor="w", pady=(10, 2))
            textbox = ctk.CTkTextbox(
                card_content, height=140, corner_radius=Radius.SM,
                fg_color=Dark.INPUT_BG, text_color=Dark.TEXT,
            )
            textbox.pack(fill="x", pady=(0, 6))
            textbox.insert("0.0", prompt.get("full_image_prompt", ""))
            prompt["_textbox"] = textbox

            buttons = ctk.CTkFrame(card_content, fg_color="transparent")
            buttons.pack(fill="x", pady=(8, 0))
            ctk.CTkButton(
                buttons, text="Copy Prompt", width=120,
                fg_color=Dark.PRIMARY, hover_color=Dark.PRIMARY_HOVER,
                text_color=Dark.TEXT, font=Fonts.BUTTON,
                corner_radius=Radius.SM,
                command=lambda prompt_copy=prompt: self.copy_prompt(prompt_copy),
            ).pack(side="left")
            ctk.CTkButton(
                buttons, text="Copy All", width=120,
                fg_color=Dark.CARD, hover_color=Dark.HOVER,
                text_color=Dark.TEXT_SECONDARY, font=Fonts.BUTTON,
                corner_radius=Radius.SM,
                command=self.copy_all_prompts,
            ).pack(side="left", padx=(8, 0))
            ctk.CTkButton(
                buttons, text="Export TXT", width=120,
                fg_color=Dark.CARD, hover_color=Dark.HOVER,
                text_color=Dark.TEXT_SECONDARY, font=Fonts.BUTTON,
                corner_radius=Radius.SM,
                command=lambda prompt_copy=prompt: self.export_prompt(prompt_copy),
            ).pack(side="left", padx=(8, 0))

    def copy_prompt(self, prompt: dict) -> None:
        if prompt.get("_textbox") is not None:
            prompt["_textbox"].clipboard_clear()
            prompt["_textbox"].clipboard_append(prompt.get("full_image_prompt", ""))

    def copy_all_prompts(self) -> None:
        text = "\n\n".join(prompt.get("full_image_prompt", "") for prompt in self.image_prompts)
        if self.image_prompt_container is not None:
            self.image_prompt_container.clipboard_clear()
            self.image_prompt_container.clipboard_append(text)

    def export_prompt(self, prompt: dict) -> None:
        if self.selected_name is None:
            return
        export_path = self.manager.PROJECTS_DIR / self.selected_name / f"{prompt.get('prompt_title', 'prompt')}.txt"
        export_path.write_text(prompt.get("full_image_prompt", ""), encoding="utf-8")

    def generate_image_prompts(self) -> None:
        if self.selected_name is None:
            return

        self.schedule_ui_update(self.toggle_task_controls, True)
        self.schedule_ui_update(self.update_task_status, "Generating image prompts...", 0.1)

        def run_task(task_manager: TaskManager) -> list[dict]:
            task_manager.update_progress(0.15, "Loading storyboard data...")
            storyboard_data = self.storyboard_storage.load(self.selected_name)
            task_manager.update_progress(0.25, "Preparing prompt generation...")
            scenes = storyboard_data.get("scenes", []) if isinstance(storyboard_data, dict) else []
            storyboard_text = "\n\n".join(
                f"Scene {s.get('scene_number', i+1)}: {s.get('narration', '')}"
                for i, s in enumerate(scenes)
            )
            topic = scenes[0].get("narration", "") if scenes else ""
            request = ImagePromptRequest(
                storyboard_text=storyboard_text,
                topic=topic,
            )
            task_manager.update_progress(0.4, "Generating image prompts...")
            raw_response = self.image_prompt_operator.execute(request)
            if task_manager.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            task_manager.update_progress(0.85, "Parsing image prompts...")
            prompts = self.image_prompt_parser.parse(raw_response)
            task_manager.update_progress(0.95, "Saving prompts...")
            return prompts

        def on_complete(prompts: list[dict]) -> None:
            self.image_prompts = prompts
            self.image_prompt_storage.save(self.selected_name, prompts)
            self.logger.info("Workspace", f"Image prompts saved for project: {self.selected_name}")
            self.logger.info("Workspace", f"Image Prompt generation completed for project: {self.selected_name}")
            self.workflow_state = advance_workflow_state(self.workflow_state, "Image Prompts")
            self.workflow_state["Export"] = "AVAILABLE"
            self.save_workflow_state(self.selected_name)

            def _update_ui() -> None:
                self.render_image_prompts()
                self.refresh_stage_buttons()
                self.update_content(self.selected_stage)
                self.toggle_task_controls(False)
                self.update_task_status("Image prompts generation complete.", 1.0)

            self.schedule_ui_update(_update_ui)

        def on_error(exc: Exception) -> None:
            self.schedule_ui_update(self.toggle_task_controls, False)
            self.schedule_ui_update(self.update_task_status, f"Error: {exc}", 0.0)

        self.task_manager.run_task(
            task_name="Generate Image Prompts",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def save_image_prompts(self) -> None:
        if self.selected_name is None:
            return

        prompts = []
        for prompt in self.image_prompts:
            if not isinstance(prompt, dict):
                continue
            textbox = prompt.get("_textbox")
            prompts.append({
                "scene_number": prompt.get("scene_number", 1),
                "timestamp": prompt.get("timestamp", "00:00"),
                "prompt_title": prompt.get("prompt_title", "Prompt"),
                "full_image_prompt": textbox.get("1.0", "end").strip() if textbox is not None else prompt.get("full_image_prompt", ""),
            })

        self.image_prompts = prompts
        self.image_prompt_storage.save(self.selected_name, prompts)

    def export_project(self) -> None:
        if self.selected_name is None:
            return

        project_data = self.manager.load_project(self.selected_name)
        if not project_data:
            return

        if self.workflow_state.get("Image Prompts", "LOCKED") != "COMPLETED":
            return

        self.schedule_ui_update(self.toggle_task_controls, True)
        self.schedule_ui_update(self.update_task_status, "Exporting project...", 0.1)

        def run_task(task_manager: TaskManager) -> Path:
            task_manager.update_progress(0.4, "Preparing export package...")
            export_dir = self.export_service.export_project(project_data)
            if task_manager.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            task_manager.update_progress(0.95, "Finishing export...")
            return export_dir

        def on_complete(export_dir: Path) -> None:
            self.logger.info("Workspace", f"Export completed for project: {self.selected_name}")
            self.workflow_state = advance_workflow_state(self.workflow_state, "Export")
            self.save_workflow_state(self.selected_name)

            def _update_ui() -> None:
                self.refresh_stage_buttons()
                self.toggle_task_controls(False)
                self.update_task_status("Project export complete.", 1.0)
                if export_dir.exists() and self.current_stage_description is not None:
                    self.current_stage_description.configure(text=f"Export created at {export_dir}")

            self.schedule_ui_update(_update_ui)

        def on_error(exc: Exception) -> None:
            self.schedule_ui_update(self.toggle_task_controls, False)
            self.schedule_ui_update(self.update_task_status, f"Error: {exc}", 0.0)

        self.task_manager.run_task(
            task_name="Export Project",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def open_export_folder(self) -> None:
        if self.selected_name is None:
            return
        export_dir = self.manager.PROJECTS_DIR / self.selected_name / "exports" / self.selected_name
        export_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(export_dir))

    # ==========================================================
    # AUTOSAVE
    # ==========================================================

    def _start_autosave(self):
        self._schedule_autosave()

    def _schedule_autosave(self):
        if self._autosave_id is not None:
            self.after_cancel(self._autosave_id)
        self._autosave_id = self.after(30000, self._perform_autosave)

    def _perform_autosave(self):
        if self._has_unsaved and self.selected_name:
            self._save_all_data(show_indicator=False)
            self._has_unsaved = False
            self._update_save_indicator("Autosaved")
        self._schedule_autosave()

    def _mark_unsaved(self, *args):
        self._has_unsaved = True
        if self._save_indicator:
            self._save_indicator.configure(text="\u25CF Unsaved", text_color=Dark.WARNING)

    def _update_save_indicator(self, text=""):
        if self._save_indicator:
            self._save_indicator.configure(text=text, text_color=Dark.TEXT_MUTED)
        if self._last_saved_label and self.selected_name:
            ts = self.manager.get_last_modified(self.selected_name)
            self._last_saved_label.configure(text=f"Last saved: {ts}")

    def _save_all_data(self, show_indicator=True):
        if self.selected_name is None:
            return
        self.save_research()
        self.save_script()
        self.save_storyboard()
        self.save_image_prompts()
        self.manager.touch_modified(self.selected_name)
        if show_indicator:
            self._has_unsaved = False
            self._update_save_indicator("Saved")
            self._notifications.info("Project saved.")

    def save_current(self):
        self._save_all_data(show_indicator=True)

    # ==========================================================
    # STAGE NAVIGATION
    # ==========================================================

    def _prev_stage(self):
        if not self.selected_stage or not self.workflow_state:
            return
        stages = [s for s in ["Research", "Script", "Storyboard", "Image Prompts", "Export"]
                  if self.workflow_state.get(s) != "LOCKED"]
        try:
            idx = stages.index(self.selected_stage)
            if idx > 0:
                self.select_stage(stages[idx - 1])
        except ValueError:
            pass

    def _next_stage(self):
        if not self.selected_stage or not self.workflow_state:
            return
        stages = [s for s in ["Research", "Script", "Storyboard", "Image Prompts", "Export"]
                  if self.workflow_state.get(s) != "LOCKED"]
        try:
            idx = stages.index(self.selected_stage)
            if idx < len(stages) - 1:
                self.select_stage(stages[idx + 1])
        except ValueError:
            pass

    def _update_nav_buttons(self):
        stages = [s for s in ["Research", "Script", "Storyboard", "Image Prompts", "Export"]
                  if self.workflow_state.get(s) != "LOCKED"]
        try:
            idx = stages.index(self.selected_stage)
        except ValueError:
            idx = -1

        if self._prev_btn:
            if idx <= 0:
                self._prev_btn.configure(state="disabled")
            else:
                self._prev_btn.configure(state="normal")

        if self._next_btn:
            if idx >= len(stages) - 1 or idx < 0:
                self._next_btn.configure(state="disabled")
            else:
                self._next_btn.configure(state="normal")

    def _open_history(self):
        if not self.selected_name:
            from core.notifications import NotificationService
            NotificationService.get().warning("Select a project first.")
            return
        from ui.dialogs import VersionHistoryDialog
        VersionHistoryDialog(self, self.selected_name)
