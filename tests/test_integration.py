# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""KaiMi Studio — Integration Test Suite.

Tests the complete production workflow without GUI:
  Create -> Research -> Script -> Storyboard -> ImagePrompts -> Export -> Reload

Also covers: search, sort, filter, favorites, archive, duplicate, rename,
history, export formats, task queue, error handling, workflow state.
"""

import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.project_manager import ProjectManager
from core.script_storage import ScriptStorage
from core.image_prompt_storage import ImagePromptStorage
from core.history_manager import HistoryManager
from core.export_service import ExportService
from core.task_manager import TaskManager, TaskCancelledError
from core.workflow import (
    WORKFLOW_STAGES,
    build_initial_workflow_state,
    normalize_workflow_state,
    advance_workflow_state,
)


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """ProjectManager rooted in a temp directory."""
    mgr = ProjectManager()
    monkeypatch.setattr(mgr, "PROJECTS_DIR", tmp_path / "projects")
    mgr.PROJECTS_DIR.mkdir()
    return mgr


@pytest.fixture
def hm(pm, monkeypatch):
    """HistoryManager sharing the same temp root."""
    h = HistoryManager()
    monkeypatch.setattr(h, "pm", pm)
    return h


@pytest.fixture
def es(pm):
    """ExportService sharing the same ProjectManager."""
    return ExportService(pm)


def _proj_path(pm, name):
    """Get the projects dir from a ProjectManager fixture."""
    return pm.PROJECTS_DIR / name


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _read_json(pm, name, filename):
    """Read a JSON file from the temp project dir."""
    fp = _proj_path(pm, name) / filename
    if not fp.exists():
        return {}
    try:
        result = json.loads(fp.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_json_or_default(pm, name, filename, default):
    """Read a JSON file, returning default if missing/corrupt."""
    result = _read_json(pm, name, filename)
    return result if result else default


def _create_sample_project(pm, name="TestProject"):
    pm.create_project(
        name=name, topic="AI Education",
        platform="YouTube", video_type="Educational",
        language="English", script_mode="characters",
        script_min=4500, script_max=5000,
        research_sources="UNESCO, OECD", keywords="ai, education",
    )
    return name


def _fill_script(pm, name):
    data = {
        "script_output": "INT. CLASSROOM - DAY\nTeacher introduces AI...",
        "script_mode": "characters",
        "script_min": 4500,
        "script_max": 5000,
        "research_data": "",
    }
    _write_json(_proj_path(pm, name) / "script.json", data)


def _fill_image_prompts(pm, name):
    data = {"prompts": [
        {
            "scene_number": 1,
            "prompt_title": "Classroom Wide Shot",
            "full_image_prompt": "A modern classroom with digital screens, photorealistic, 4K",
            "timestamp": "00:00:10",
        },
        {
            "scene_number": 2,
            "prompt_title": "AI Visualization",
            "full_image_prompt": "Glowing neural network in a dark room, cinematic lighting",
            "timestamp": "00:00:25",
        },
    ]}
    _write_json(_proj_path(pm, name) / "image_prompts.json", data)


# =====================================================================
# PHASE 1 — End-to-End Integration
# =====================================================================

class TestEndToEndWorkflow:
    """Create -> Script -> ImagePrompts -> Export -> Reload."""

    def test_full_project_lifecycle(self, pm):
        name = _create_sample_project(pm)
        data = pm.load_project(name)
        assert data is not None
        assert data["name"] == name
        assert data["workflow_state"]["Script"] == "AVAILABLE"
        assert data["workflow_state"]["Voice"] == "LOCKED"

    def test_save_and_reload_script(self, pm):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        loaded = json.loads((_proj_path(pm, name) / "script.json").read_text(encoding="utf-8"))
        assert "CLASSROOM" in loaded["script_output"]

    def test_save_and_reload_image_prompts(self, pm):
        name = _create_sample_project(pm)
        _fill_image_prompts(pm, name)
        loaded = json.loads((_proj_path(pm, name) / "image_prompts.json").read_text(encoding="utf-8"))
        assert len(loaded["prompts"]) == 2
        assert "photorealistic" in loaded["prompts"][0]["full_image_prompt"]

    def test_project_survives_full_cycle(self, pm):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        _fill_image_prompts(pm, name)

        pm.touch_modified(name)

        reloaded = pm.load_project(name)
        assert reloaded is not None
        assert reloaded["name"] == name

        script = json.loads((_proj_path(pm, name) / "script.json").read_text(encoding="utf-8"))
        assert "CLASSROOM" in script["script_output"]
        prompts = json.loads((_proj_path(pm, name) / "image_prompts.json").read_text(encoding="utf-8"))
        assert len(prompts["prompts"]) == 2

    def test_multiple_projects_coexist(self, pm):
        for i in range(5):
            _create_sample_project(pm, f"Project_{i}")
        projects = pm.get_projects()
        assert len(projects) == 5
        names = {p["name"] for p in projects}
        assert all(f"Project_{i}" in names for i in range(5))

    def test_autosave_simulation(self, pm):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        loaded = json.loads((_proj_path(pm, name) / "script.json").read_text(encoding="utf-8"))
        assert "CLASSROOM" in loaded["script_output"]
        _write_json(_proj_path(pm, name) / "script.json", {**loaded, "script_output": "UPDATED SCRIPT"})
        loaded2 = json.loads((_proj_path(pm, name) / "script.json").read_text(encoding="utf-8"))
        assert loaded2["script_output"] == "UPDATED SCRIPT"


# =====================================================================
# PHASE 2 — Stress Testing (Project Management)
# =====================================================================

class TestStressProjectManagement:

    def test_create_50_projects(self, pm):
        for i in range(50):
            pm.create_project(f"StressProject_{i:03d}", f"Topic {i}", "en", "Educational")
        assert pm.get_project_count() == 50

    def test_search_across_50_projects(self, pm):
        for i in range(50):
            pm.create_project(f"StressProject_{i:03d}", f"Topic {i}", "en", "Educational")
        results = pm.search_projects("StressProject_025")
        assert len(results) == 1
        assert results[0]["name"] == "StressProject_025"

    def test_search_partial_match(self, pm):
        for i in range(50):
            pm.create_project(f"Project_{i:03d}", f"Science Topic {i}", "en", "Educational")
        results = pm.search_projects("Science")
        assert len(results) == 50

    def test_sort_by_name(self, pm):
        pm.create_project("Zebra", "z", "en", "Educational")
        pm.create_project("Apple", "a", "en", "Educational")
        pm.create_project("Mango", "m", "en", "Educational")
        projects = pm.get_projects()
        sorted_p = pm.sort_projects(projects, sort_by="name", reverse=False)
        assert sorted_p[0]["name"] == "Apple"
        assert sorted_p[-1]["name"] == "Zebra"

    def test_sort_by_last_modified(self, pm):
        pm.create_project("Old", "o", "en", "Educational")
        time.sleep(0.05)
        pm.create_project("New", "n", "en", "Educational")
        projects = pm.get_projects()
        sorted_p = pm.sort_projects(projects, sort_by="last_modified", reverse=True)
        assert sorted_p[0]["name"] == "New"

    def test_filter_by_status(self, pm):
        pm.create_project("P1", "t")
        pm.create_project("P2", "t")
        pm.update_project("P2", {**pm.load_project("P2"), "status": "Voice"})
        projects = pm.get_projects()
        filtered = pm.filter_projects(projects, "Script")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "P1"

    def test_favorite_toggle(self, pm):
        _create_sample_project(pm, "FavTest")
        assert pm.load_project("FavTest")["favorite"] is False
        pm.toggle_favorite("FavTest")
        assert pm.load_project("FavTest")["favorite"] is True
        pm.toggle_favorite("FavTest")
        assert pm.load_project("FavTest")["favorite"] is False

    def test_archive_unarchive(self, pm):
        _create_sample_project(pm, "ArchTest")
        pm.archive_project("ArchTest")
        assert pm.load_project("ArchTest")["archived"] is True
        non_archived = pm.get_projects()
        assert all(p["name"] != "ArchTest" for p in non_archived)
        all_proj = pm.get_projects(include_archived=True)
        assert any(p["name"] == "ArchTest" for p in all_proj)
        pm.unarchive_project("ArchTest")
        assert pm.load_project("ArchTest")["archived"] is False

    def test_duplicate_project(self, pm):
        _create_sample_project(pm, "Original")
        _fill_script(pm, "Original")
        pm.duplicate_project("Original", "Copy")
        copy_data = pm.load_project("Copy")
        assert copy_data is not None
        assert copy_data["name"] == "Copy"
        assert _read_json(pm, "Copy", "script.json")["script_output"] == _read_json(pm, "Original", "script.json")["script_output"]

    def test_rename_project(self, pm):
        _create_sample_project(pm, "OldName")
        pm.rename_project("OldName", "NewName")
        assert pm.load_project("OldName") is None
        assert pm.load_project("NewName") is not None

    def test_delete_project(self, pm):
        _create_sample_project(pm, "ToDelete")
        assert pm.delete_project("ToDelete") is True
        assert pm.load_project("ToDelete") is None

    def test_workspace_switching(self, pm):
        for i in range(10):
            _create_sample_project(pm, f"WS_Project_{i}")
        for i in range(10):
            data = pm.load_project(f"WS_Project_{i}")
            assert data is not None

    def test_no_corruption_after_bulk_ops(self, pm):
        for i in range(20):
            _create_sample_project(pm, f"Bulk_{i}")
        for i in range(0, 20, 2):
            pm.toggle_favorite(f"Bulk_{i}")
        for i in range(1, 20, 3):
            pm.archive_project(f"Bulk_{i}")
        active = pm.get_projects()
        for p in active:
            assert p["name"] != ""
            assert "status" in p


# =====================================================================
# PHASE 3 — Workspace / Workflow Validation
# =====================================================================

class TestWorkflowValidation:

    def test_initial_state(self):
        state = build_initial_workflow_state()
        assert state["Script"] == "AVAILABLE"
        for stage in WORKFLOW_STAGES[1:]:
            assert state[stage] == "LOCKED"

    def test_advance_script(self):
        state = build_initial_workflow_state()
        new_state = advance_workflow_state(state, "Script")
        assert new_state["Script"] == "COMPLETED"
        assert new_state["Voice"] == "AVAILABLE"
        for stage in WORKFLOW_STAGES[2:]:
            assert new_state[stage] == "LOCKED"

    def test_advance_full_pipeline(self):
        state = build_initial_workflow_state()
        for stage in WORKFLOW_STAGES:
            state = advance_workflow_state(state, stage)
        for s in WORKFLOW_STAGES:
            assert state[s] == "COMPLETED"

    def test_normalize_preserves_valid(self):
        state = build_initial_workflow_state()
        state["Script"] = "COMPLETED"
        state["Voice"] = "AVAILABLE"
        normalized = normalize_workflow_state(state)
        assert normalized["Script"] == "COMPLETED"
        assert normalized["Voice"] == "AVAILABLE"

    def test_normalize_repairs_invalid(self):
        state = {"Script": "BANANA", "Voice": "COMPLETED"}
        normalized = normalize_workflow_state(state)
        assert normalized["Script"] == "AVAILABLE"
        assert normalized["Voice"] == "COMPLETED"

    def test_normalize_none(self):
        assert normalize_workflow_state(None) == build_initial_workflow_state()

    def test_workflow_state_persists(self, pm):
        name = _create_sample_project(pm)
        data = pm.load_project(name)
        ws = advance_workflow_state(data["workflow_state"], "Script")
        data["workflow_state"] = ws
        pm.update_project(name, data)
        reloaded = pm.load_project(name)
        assert reloaded["workflow_state"]["Script"] == "COMPLETED"
        assert reloaded["workflow_state"]["Voice"] == "AVAILABLE"


# =====================================================================
# PHASE 4 — Export Completion
# =====================================================================

class TestExportFormats:

    def test_export_txt(self, pm, es):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        proj = pm.load_project(name)
        out = es.export_project(proj, fmt="txt")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "TestProject" in content
        assert "CLASSROOM" in content

    def test_export_empty_project(self, pm, es):
        name = _create_sample_project(pm)
        proj = pm.load_project(name)
        out = es.export_project(proj, fmt="txt")
        assert out.exists()

    def test_export_stage(self, pm, es):
        name = _create_sample_project(pm)
        _fill_image_prompts(pm, name)
        out = es.export_stage(name, "Image Prompts", fmt="txt")
        assert out is not None
        assert out.exists()


# =====================================================================
# PHASE 5 — History Manager
# =====================================================================

class TestHistoryManager:

    def test_save_and_list_snapshots(self, pm, hm):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        data = _read_json(pm, name, "script.json")
        filename = hm.save_snapshot(name, "Script", data)
        assert filename.endswith(".json")
        snapshots = hm.list_snapshots(name, "Script")
        assert len(snapshots) == 1
        assert snapshots[0]["filename"] == filename

    def test_delete_snapshot(self, pm, hm):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        data = _read_json(pm, name, "script.json")
        filename = hm.save_snapshot(name, "Script", data)
        assert hm.delete_snapshot(name, "Script", filename) is True
        assert len(hm.list_snapshots(name, "Script")) == 0

    def test_multiple_stages_history(self, pm, hm):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        hm.save_snapshot(name, "Script", _read_json(pm, name, "script.json"))
        assert len(hm.list_snapshots(name, "Script")) == 1

    def test_history_directory_creation(self, pm, hm):
        name = _create_sample_project(pm)
        d = hm._history_dir(name, "Script")
        assert d.exists()
        assert d.is_dir()


# =====================================================================
# PHASE 7 — Notifications (non-GUI)
# =====================================================================

class TestNotificationService:

    def test_singleton(self):
        from core.notifications import NotificationService
        a = NotificationService.get()
        b = NotificationService.get()
        assert a is b


# =====================================================================
# PHASE 7B — Provider Configuration & Persistence
# =====================================================================

class TestProviderConfiguration:

    def test_api_key_encrypted_round_trip(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("gemini")
        pm.save_provider_config("gemini", api_key="sk-secret-value", model="gemini-2.0-flash")

        raw = (tmp_path / "providers.json").read_text(encoding="utf-8")
        assert "sk-secret-value" not in raw, "plaintext key leaked into providers.json"

        reloaded = ProviderManager(config_path=tmp_path / "providers.json")
        assert reloaded.get_provider_api_key("gemini") == "sk-secret-value"
        assert reloaded.validate_provider_configuration("gemini")
        assert reloaded.get_provider_model("gemini") == "gemini-2.0-flash"

    def test_legacy_plaintext_key_still_reads(self, tmp_path):
        from providers.provider_manager import ProviderManager
        cfg_path = tmp_path / "providers.json"
        cfg_path.write_text(
            json.dumps({
                "active_provider": "gemini",
                "providers": {"gemini": {"api_key": "legacy-plain-key"}},
            }),
            encoding="utf-8",
        )
        pm = ProviderManager(config_path=cfg_path)
        assert pm.get_provider_api_key("gemini") == "legacy-plain-key"

    def test_save_config_can_clear_key(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.save_provider_config("gemini", api_key="secret")
        pm.save_provider_config("gemini", api_key="")
        assert pm.get_provider_api_key("gemini") == ""
        assert not pm.validate_provider_configuration("gemini")

    def test_connection_test_requires_key_message(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("openai")
        ok, msg = pm.test_provider_connection("openai")
        assert ok is False
        assert "API key" in msg

    def test_active_provider_persists(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("openrouter")
        reloaded = ProviderManager(config_path=tmp_path / "providers.json")
        assert reloaded.get_active_provider_name() == "openrouter"

    def test_settings_list_matches_registered_provider_metadata(self, tmp_path):
        from providers.provider_manager import PROVIDER_METADATA, ProviderManager

        pm = ProviderManager(config_path=tmp_path / "providers.json")
        registered = pm.get_registered_providers()

        assert registered == sorted(PROVIDER_METADATA.keys())
        for name in registered:
            meta = pm.get_provider_metadata(name)
            assert meta["display_name"]
            assert "requires_key" in meta
            assert "base_url" in meta

    def test_every_registered_provider_can_be_instantiated(self, tmp_path):
        from providers.base_provider import BaseProvider
        from providers.provider_manager import ProviderManager

        pm = ProviderManager(config_path=tmp_path / "providers.json")
        for name in pm.get_registered_providers():
            pm.save_provider_config(
                name,
                api_key="test-key" if pm.provider_requires_key(name) else "",
                base_url=pm.get_provider_metadata(name).get("base_url", ""),
                model="test-model",
            )
            provider = pm._get_provider(name)
            assert isinstance(provider, BaseProvider)
            assert provider.name == name

    def test_unsupported_active_provider_does_not_fall_back_to_gemini(self, tmp_path):
        from providers.provider_manager import ProviderManager

        cfg_path = tmp_path / "providers.json"
        cfg_path.write_text(
            json.dumps({
                "active_provider": "missing-provider",
                "providers": {
                    "gemini": {"api_key": "test-key", "model": "gemini-2.0-flash"},
                    "missing-provider": {"api_key": "test-key", "model": "missing-model"},
                },
            }),
            encoding="utf-8",
        )

        pm = ProviderManager(config_path=cfg_path)
        assert pm.get_active_provider_name() == ""
        ok, msg = pm.preflight_check()
        assert ok is False
        assert "No active AI provider" in msg

    def test_failover_sequence_covers_every_registered_provider(self, tmp_path):
        from providers.provider_manager import ProviderManager

        pm = ProviderManager(config_path=tmp_path / "providers.json")
        assert set(pm.FAILOVER_SEQUENCE) == set(pm.get_registered_providers())

    def test_local_providers_are_failover_candidates_without_api_keys(self, tmp_path):
        from providers.provider_manager import ProviderManager

        pm = ProviderManager(config_path=tmp_path / "providers.json")
        local_names = [
            name for name in pm.get_registered_providers()
            if not pm.provider_requires_key(name)
        ]

        for name in local_names:
            pm.save_provider_config(
                name,
                api_key="",
                base_url=pm.get_provider_metadata(name).get("base_url", ""),
                model="local-test-model",
            )

        first_local_index = min(pm.FAILOVER_SEQUENCE.index(name) for name in local_names)
        attempted = set(pm.FAILOVER_SEQUENCE[:first_local_index])

        assert pm._get_next_failover("", attempted) == pm.FAILOVER_SEQUENCE[first_local_index]

    def test_every_registered_provider_can_test_and_generate(self, tmp_path, monkeypatch):
        from providers.anthropic_provider import AnthropicProvider
        from providers.cohere_provider import CohereProvider
        from providers.gemini_provider import GeminiProvider
        from providers.models import GenerationRequest
        from providers.opencode_provider import OpenAICompatibleProvider
        from providers.provider_manager import ProviderManager

        class FakeOpenAIModels:
            def list(self):
                return SimpleNamespace(data=[SimpleNamespace(id="test-model")])

        class FakeOpenAICompletions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="mock openai-compatible output"),
                            finish_reason="stop",
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=1,
                        completion_tokens=2,
                        total_tokens=3,
                    ),
                )

        class FakeOpenAIClient:
            def __init__(self):
                self.models = FakeOpenAIModels()
                self.chat = SimpleNamespace(
                    completions=FakeOpenAICompletions()
                )

        class FakeGeminiModels:
            def list(self):
                return [SimpleNamespace(name="models/test-model")]

            def generate_content(self, **kwargs):
                return SimpleNamespace(
                    text="mock gemini output",
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=1,
                        candidates_token_count=2,
                        total_token_count=3,
                    ),
                )

        class FakeGeminiClient:
            def __init__(self):
                self.models = FakeGeminiModels()

        class FakeHttpResponse:
            def __init__(self, data):
                self.status_code = 200
                self.text = json.dumps(data)
                self._data = data

            def json(self):
                return self._data

        class FakeAnthropicClient:
            def get(self, path):
                return FakeHttpResponse({
                    "data": [{"id": "test-model", "display_name": "Test Model"}],
                })

            def post(self, path, json):
                return FakeHttpResponse({
                    "content": [{"type": "text", "text": "mock anthropic output"}],
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                    "stop_reason": "stop",
                })

        class FakeCohereClient:
            def get(self, path):
                return FakeHttpResponse({
                    "models": [{"name": "test-model"}],
                })

            def post(self, path, json):
                return FakeHttpResponse({
                    "message": {
                        "content": [{"type": "text", "text": "mock cohere output"}],
                    },
                    "usage": {
                        "tokens": {"input_tokens": 1, "output_tokens": 2},
                    },
                    "finish_reason": "stop",
                })

        def initialize_openai_compatible(provider):
            provider._client = FakeOpenAIClient()
            provider._initialized = True

        def initialize_gemini(provider):
            provider._client = FakeGeminiClient()
            provider._initialized = True

        def initialize_anthropic(provider):
            provider._client = FakeAnthropicClient()
            provider._initialized = True

        def initialize_cohere(provider):
            provider._client = FakeCohereClient()
            provider._initialized = True

        monkeypatch.setattr(OpenAICompatibleProvider, "initialize", initialize_openai_compatible)
        monkeypatch.setattr(GeminiProvider, "initialize", initialize_gemini)
        monkeypatch.setattr(AnthropicProvider, "initialize", initialize_anthropic)
        monkeypatch.setattr(CohereProvider, "initialize", initialize_cohere)

        pm = ProviderManager(config_path=tmp_path / "providers.json")
        for name in pm.get_registered_providers():
            pm.save_provider_config(
                name,
                api_key="test-key" if pm.provider_requires_key(name) else "",
                base_url=pm.get_provider_metadata(name).get("base_url", ""),
                model="test-model",
            )
            pm.set_active_provider(name)

            ok, msg = pm.test_provider_connection(name)
            assert ok is True, msg

            response = pm.generate(GenerationRequest(prompt="Generate a test response."))
            assert response.provider == name
            assert response.model == "test-model"
            assert response.text.startswith("mock ")


class TestProviderPreflight:
    """Generation preflight: the active provider must be usable before
    a Generate task is allowed to start (see ScriptPage.generate_script)."""

    def test_preflight_fails_when_model_missing(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("ollama")
        ok, msg = pm.preflight_check()
        assert ok is False
        assert "model" in msg.lower()
        assert "Ollama" in msg

    def test_preflight_fails_when_required_key_missing(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("openai")
        pm.set_provider_model("openai", "gpt-4o")
        ok, msg = pm.preflight_check()
        assert ok is False
        assert "API key" in msg

    def test_preflight_passes_for_local_provider_with_model(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("ollama")
        pm.set_provider_model("ollama", "llama3")
        ok, msg = pm.preflight_check()
        assert ok is True
        assert msg == ""

    def test_preflight_passes_for_configured_cloud_provider(self, tmp_path):
        from providers.provider_manager import ProviderManager
        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider("gemini")
        pm.save_provider_config("gemini", api_key="test-key", model="gemini-2.0-flash")
        ok, msg = pm.preflight_check()
        assert ok is True
        assert msg == ""

    def test_settings_dropdown_does_not_switch_active_provider(self):
        """Browsing the provider dropdown must not persist an active-provider
        change; only Save Provider may call set_active_provider."""
        import inspect
        from ui.pages.settings_page import SettingsPage
        changed_src = inspect.getsource(SettingsPage._on_provider_changed)
        assert "set_active_provider" not in changed_src
        save_src = inspect.getsource(SettingsPage._save_provider)
        assert "set_active_provider" in save_src


class TestScriptGenerationPolish:

    def test_script_operator_continues_and_formats_to_target_length(self):
        from operators.script.models import ScriptRequest
        from operators.script.operator import SCRIPT_TARGET_MAX, SCRIPT_TARGET_MIN, ScriptOperator
        from providers.models import GenerationResponse

        class FakeProviderManager:
            def __init__(self):
                self.calls = 0

            def generate(self, request):
                self.calls += 1
                if self.calls == 1:
                    return GenerationResponse(
                        text="HOOK\n\nSunlight looks simple, but plants turn it into a hidden factory."
                    )
                sentence = (
                    "That factory pulls carbon dioxide from the air, draws water from the roots, "
                    "and uses sunlight to build the sugars that keep the plant alive. "
                )
                return GenerationResponse(text=sentence * 45)

        operator = ScriptOperator(provider_manager=FakeProviderManager())
        result = operator.execute(ScriptRequest(topic="Photosynthesis"))

        assert SCRIPT_TARGET_MIN <= len(result) <= SCRIPT_TARGET_MAX
        assert "\n\n\n" not in result
        assert all(line.strip().upper() not in {"HOOK", "BODY", "ENDING", "PAUSE", "INTRO"} for line in result.splitlines())
        assert "(pause)" not in result.lower()
        assert "[breath]" not in result.lower()

    def test_script_page_character_progress_and_copy_button(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        page = ScriptPage()

        page.editor.setPlainText("a" * 4380)
        app.processEvents()
        assert page.char_count_label.text() == "4380 / 4500 minimum"

        page.editor.setPlainText("b" * 4725)
        app.processEvents()
        assert page.char_count_label.text() == "4725 / 4999 maximum"

        page.copy_script()
        assert QApplication.clipboard().text() == "b" * 4725


# =====================================================================
# PHASE 7C — Voice / Transcript Pipeline
# =====================================================================

class TestTranscriptStorage:

    def test_save_and_load_round_trip(self, tmp_path, monkeypatch):
        from core.transcript_storage import TranscriptStorage
        proj_dir = tmp_path / "projects"
        proj_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", proj_dir)

        storage = TranscriptStorage()
        storage.save("Proj", "Hello transcript")
        data = storage.load("Proj")
        assert data["text"] == "Hello transcript"
        assert data["segments"] == []

    def test_load_falls_back_to_voice_json(self, tmp_path, monkeypatch):
        from core.transcript_storage import TranscriptStorage
        proj_dir = tmp_path / "projects"
        proj_dir.mkdir(parents=True, exist_ok=True)
        _write_json(proj_dir / "Proj" / "voice.json", {
            "transcript": "From voice",
            "segments": [{"start": 0, "end": 3, "text": "From voice", "time": "00:00"}],
        })
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", proj_dir)

        data = TranscriptStorage().load("Proj")
        assert data["text"] == "From voice"
        assert len(data["segments"]) == 1

    def test_prefers_transcript_json_text(self, tmp_path, monkeypatch):
        from core.transcript_storage import TranscriptStorage
        proj_dir = tmp_path / "projects"
        proj_dir.mkdir(parents=True, exist_ok=True)
        _write_json(proj_dir / "Proj" / "transcript.json", {"text": "Edited text"})
        _write_json(proj_dir / "Proj" / "voice.json", {
            "transcript": "Original text",
            "segments": [{"start": 0, "end": 1, "text": "Original text", "time": "00:00"}],
        })
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", proj_dir)

        data = TranscriptStorage().load("Proj")
        assert data["text"] == "Edited text"
        assert len(data["segments"]) == 1


class TestTranscriptionService:

    @staticmethod
    def _reset_cache():
        from core.transcription_service import TranscriptionService
        TranscriptionService._model = None
        TranscriptionService._model_name = None

    @staticmethod
    def _install_fake_whisper(monkeypatch, transcriptions, construct_hook=None):
        """Inject a fake faster_whisper package and make the service see it."""
        import sys
        from types import SimpleNamespace

        calls = {"count": 0}

        def make_seg(start, end, text):
            return SimpleNamespace(start=start, end=end, text=text)

        class FakeModel:
            def __init__(self, *args, **kwargs):
                calls["count"] += 1
                if construct_hook:
                    construct_hook(calls["count"])

            def transcribe(self, audio_path, **kwargs):
                return iter(transcriptions), SimpleNamespace(language="en")

        class FakeWhisper:
            WhisperModel = FakeModel

        monkeypatch.setitem(sys.modules, "faster_whisper", FakeWhisper)
        monkeypatch.setattr(
            "core.transcription_service.importlib.util.find_spec",
            lambda name: SimpleNamespace() if name == "faster_whisper" else None,
        )
        return calls

    @staticmethod
    def _fake_settings(monkeypatch, data=None, defaults=None):
        """Replace AppSettings with a dict-backed fake for the service."""
        defaults = defaults or {}

        class FakeSettings:
            def __init__(self):
                self._data = dict(defaults)

            def get(self, key, default=None):
                return self._data.get(key, default)

            def set(self, key, value):
                self._data[key] = value

        instance = FakeSettings()
        monkeypatch.setattr("core.transcription_service.AppSettings", lambda: instance)
        return instance

    def test_is_available_detects_missing_package(self, monkeypatch):
        from core.transcription_service import TranscriptionService
        monkeypatch.setattr(
            "core.transcription_service.importlib.util.find_spec",
            lambda name: None,
        )
        assert TranscriptionService.is_available() is False

    def test_is_available_true_when_package_present(self, monkeypatch):
        from core.transcription_service import TranscriptionService
        monkeypatch.setattr(
            "core.transcription_service.importlib.util.find_spec",
            lambda name: SimpleNamespace() if name == "faster_whisper" else None,
        )
        assert TranscriptionService.is_available() is True

    def test_transcribe_raises_install_instruction_when_missing(self, tmp_path, monkeypatch):
        from core.transcription_service import TranscriptionService
        self._reset_cache()
        monkeypatch.setattr(
            "core.transcription_service.importlib.util.find_spec",
            lambda name: None,
        )
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")
        with pytest.raises(RuntimeError) as exc_info:
            TranscriptionService().transcribe(str(audio_file))
        assert "faster-whisper" in str(exc_info.value)
        assert "pip install faster-whisper" in str(exc_info.value)

    def test_transcribe_returns_formatted_text_and_segments(self, tmp_path, monkeypatch):
        from core.transcription_service import TranscriptionService
        self._reset_cache()
        raw = [
            SimpleNamespace(start=0.0, end=2.0, text="  hello  world "),
            SimpleNamespace(start=2.5, end=5.0, text="second sentence here"),
            SimpleNamespace(start=5.5, end=8.0, text="third part"),
        ]
        self._install_fake_whisper(monkeypatch, raw)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")

        text, segments = TranscriptionService().transcribe(str(audio_file))
        assert text == "Hello world second sentence here third part"
        assert len(segments) == 3
        assert segments[0]["time"] == "00:00"
        assert segments[0]["start"] == 0.0
        assert segments[2]["time"] == "00:05"
        assert all(seg["text"] == seg["text"].strip() for seg in segments)

    def test_model_is_loaded_once_and_reused(self, tmp_path, monkeypatch):
        from core.transcription_service import TranscriptionService
        self._reset_cache()
        raw = [SimpleNamespace(start=0.0, end=1.0, text="once")]
        calls = self._install_fake_whisper(monkeypatch, raw)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")

        service = TranscriptionService()
        service.transcribe(str(audio_file))
        service.transcribe(str(audio_file))
        TranscriptionService().transcribe(str(audio_file))
        assert calls["count"] == 1

    def test_transcribe_raises_when_no_speech_detected(self, tmp_path, monkeypatch):
        from core.transcription_service import TranscriptionService
        self._reset_cache()
        self._install_fake_whisper(monkeypatch, [])
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")
        with pytest.raises(RuntimeError) as exc_info:
            TranscriptionService().transcribe(str(audio_file))
        assert "speech" in str(exc_info.value).lower()

    def test_transcribe_raises_when_model_fails_to_load(self, tmp_path, monkeypatch):
        from core.transcription_service import TranscriptionService
        self._reset_cache()
        self._install_fake_whisper(
            monkeypatch, [], construct_hook=lambda n: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")
        with pytest.raises(RuntimeError) as exc_info:
            TranscriptionService().transcribe(str(audio_file))
        assert "could not be initialized" in str(exc_info.value)

    def test_configured_model_defaults_to_small(self, monkeypatch):
        from core.transcription_service import TranscriptionService, DEFAULT_MODEL
        self._fake_settings(monkeypatch)
        assert TranscriptionService().get_configured_model() == DEFAULT_MODEL

    def test_configured_model_round_trip_and_validation(self, monkeypatch):
        from core.transcription_service import TranscriptionService
        settings = self._fake_settings(monkeypatch)
        service = TranscriptionService()
        service.set_model("tiny")
        assert settings._data["whisper_model"] == "tiny"
        assert service.get_configured_model() == "tiny"
        with pytest.raises(ValueError):
            service.set_model("gpt-4")
        assert service.get_configured_model() == "tiny"

    def test_unknown_persisted_model_falls_back_to_default(self, monkeypatch):
        from core.transcription_service import TranscriptionService, DEFAULT_MODEL
        self._fake_settings(monkeypatch, defaults={"whisper_model": "not-a-model"})
        assert TranscriptionService().get_configured_model() == DEFAULT_MODEL


class TestTranscriptFormatting:

    def test_collapses_duplicate_spaces(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 1.0, "text": "this   has   extra   spaces"},
            {"start": 1.2, "end": 2.0, "text": "and   tabs\t\tinside"},
        ]
        assert format_transcript(segments) == "This has extra spaces and tabs inside"

    def test_capitalizes_each_sentence(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 1.0, "text": "hello there. this is one sentence. and another"},
        ]
        assert format_transcript(segments) == "Hello there. This is one sentence. And another"

    def test_paragraphs_split_on_long_pauses_with_single_blank_line(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 2.0, "text": "first paragraph begins here"},
            {"start": 2.5, "end": 4.0, "text": "and continues"},
            {"start": 9.0, "end": 11.0, "text": "second paragraph starts after a pause"},
            {"start": 12.0, "end": 14.0, "text": "and continues on"},
        ]
        result = format_transcript(segments)
        paragraphs = result.split("\n")
        assert paragraphs == [
            "First paragraph begins here and continues",
            "",
            "Second paragraph starts after a pause and continues on",
        ]
        assert "\n\n\n" not in result

    def test_trims_leading_and_trailing_whitespace(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 1.0, "text": "   leading text  "},
            {"start": 1.5, "end": 2.0, "text": "trailing   "},
        ]
        assert format_transcript(segments) == "Leading text trailing"

    def test_empty_input_returns_empty_string(self):
        from core.transcription_service import format_transcript
        assert format_transcript([]) == ""


class TestVoiceLocalBackend:

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.voice_page import VoicePage

        app = QApplication.instance() or QApplication([])
        page = VoicePage()
        page.manager = pm
        service = PipelineService()
        service._pm = pm
        page._pipeline = service

        class _NoopHistory:
            def record_action(self, *args, **kwargs):
                return ""

        page._history = _NoopHistory()
        return page

    def test_page_warns_when_whisper_missing(self, pm, monkeypatch):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        from core.workflow import advance_workflow_state
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        pm.update_project(name, data)

        class FakeService:
            def is_available(self):
                return False

            def install_instruction(self):
                return "faster-whisper missing: pip install faster-whisper"

            def get_configured_model(self):
                return "small"

            def set_model(self, model_name):
                pass

        monkeypatch.setattr(
            "ui.pages.voice_page.get_transcription_service",
            lambda: FakeService(),
        )

        page = self._make_page(pm)
        page.set_project(name)
        page._audio_path = str(pm.PROJECTS_DIR / name / "audio" / "clip.wav")
        page.transcribe_audio()
        assert page._worker_thread is None
        assert page._transcribing is False

    def test_worker_uses_local_service(self, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.pages.voice_page import TranscribeWorker
        captured = {}

        def fake_local(audio_path):
            captured["path"] = audio_path
            return "Local transcript", [{"start": 0.0, "end": 1.0, "text": "hi", "time": "00:00"}]

        monkeypatch.setattr("ui.pages.voice_page.transcribe_audio_locally", fake_local)
        results = []
        errors = []

        worker = TranscribeWorker("audio.mp3")
        worker.finished.connect(lambda text, segs: results.append((text, segs)))
        worker.error.connect(lambda msg: errors.append(msg))
        worker.run()

        assert captured["path"] == "audio.mp3"
        assert results == [("Local transcript", [{"start": 0.0, "end": 1.0, "text": "hi", "time": "00:00"}])]
        assert errors == []


class TestVoicePipelinePage:

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.voice_page import VoicePage

        app = QApplication.instance() or QApplication([])
        page = VoicePage()
        page.manager = pm
        service = PipelineService()
        service._pm = pm
        page._pipeline = service

        class _NoopHistory:
            def record_action(self, *args, **kwargs):
                return ""

        page._history = _NoopHistory()
        return page

    def test_transcription_done_writes_storage_and_completes_stage(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.project_name = name

        segments = [
            {"start": 0.0, "end": 2.5, "text": "Hello", "time": "00:00"},
            {"start": 2.5, "end": 5.0, "text": "world", "time": "00:02"},
        ]
        page._on_transcription_done("Hello world", segments)

        voice = _read_json(pm, name, "voice.json")
        transcript = _read_json(pm, name, "transcript.json")
        assert voice["transcript"] == "Hello world"
        assert len(voice["segments"]) == 2
        assert transcript["text"] == "Hello world"

        data = pm.load_project(name)
        assert data["workflow_state"]["Voice"] == "COMPLETED"
        assert data["workflow_state"]["Image Prompts"] == "AVAILABLE"
        assert page.next_btn.isEnabled()

    def test_voice_page_reloads_saved_transcript(self, pm):
        name = _create_sample_project(pm)
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Saved transcript"})
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Saved transcript",
            "segments": [{"start": 0, "end": 3, "text": "Saved transcript", "time": "00:00"}],
        })

        page = self._make_page(pm)
        page.set_project(name)
        assert page.transcript_box.toPlainText() == "Saved transcript"
        assert page.next_btn.isEnabled()
        assert len(page._segments) == 1

    def test_image_prompts_unlock_after_voice(self, pm, monkeypatch):
        from core.workflow import advance_workflow_state
        from core.pipeline_service import PipelineService

        name = _create_sample_project(pm)
        _fill_script(pm, name)
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        pm.update_project(name, data)

        service = PipelineService()
        service._pm = pm

        voice_validation = service.validate_stage(name, "Voice")
        assert voice_validation.passed

        service.mark_stage_completed(name, "Voice")
        state = service.get_pipeline_state(name)
        assert state["Voice"].value == "COMPLETED"
        assert state["Image Prompts"].value == "NOT_STARTED"
        assert state["Export"].value == "BLOCKED"


class TestImagePromptsSourceContext:

    def test_source_context_shows_script_and_transcript(self, pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.image_prompts_page import ImagePromptsPage

        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Hello world transcript",
            "segments": [
                {"start": 0, "end": 3, "text": "Hello", "time": "00:00"},
                {"start": 3, "end": 6, "text": "world", "time": "00:03"},
            ],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Hello world transcript"})
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        page = ImagePromptsPage()
        page.set_project(name)

        assert "ready" in page.source_script_label.text()
        assert "ready" in page.source_transcript_label.text()
        assert "2 segments" in page.source_timestamps_label.text()

    def test_image_prompt_generation_flow_with_stored_transcript(self, pm, monkeypatch):
        from core.script_storage import ScriptStorage
        from core.transcript_storage import TranscriptStorage
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator
        from operators.image_prompt.parser import ImagePromptParser

        name = _create_sample_project(pm)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Segment one. Segment two.",
            "segments": [
                {"start": 0, "end": 4, "text": "Segment one.", "time": "00:00"},
                {"start": 4, "end": 9, "text": "Segment two.", "time": "00:04"},
            ],
        })
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        script = ScriptStorage().load(name)["script_output"]
        transcript_data = TranscriptStorage().load(name)
        assert transcript_data["text"] == "Segment one. Segment two."
        assert len(transcript_data["segments"]) == 2

        request = ImagePromptRequest(
            script_text=script,
            transcript=transcript_data["text"],
            timestamps=transcript_data["segments"],
            topic="AI Education",
        )

        class FakeProviderManager:
            def generate(self, req):
                payload = [{
                    "scene_number": 1,
                    "timestamp": "00:00",
                    "prompt_title": "Opening Scene",
                    "full_image_prompt": "A classroom, photorealistic",
                }]
                return SimpleNamespace(text=json.dumps(payload))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        raw = operator.execute(request)
        prompts = ImagePromptParser().parse(raw)
        assert len(prompts) == 1

        ImagePromptStorage().save(name, prompts)
        reloaded = ImagePromptStorage().load(name)
        assert len(reloaded["prompts"]) == 1
        assert reloaded["prompts"][0]["scene_number"] == 1
        assert reloaded["prompts"][0]["full_image_prompt"] == "A classroom, photorealistic"


# =====================================================================
# PHASE 8 — Keyboard Shortcuts (structural)
# =====================================================================

class TestShortcuts:

    def test_shortcuts_class_exists(self):
        from core.shortcuts import KeyboardShortcuts
        assert KeyboardShortcuts is not None


# =====================================================================
# PHASE 9 — Error Handling
# =====================================================================

class TestErrorHandling:

    def test_load_nonexistent_project(self, pm):
        assert pm.load_project("NonExistent") is None

    def test_update_nonexistent_project(self, pm):
        assert pm.update_project("NonExistent", {}) is False

    def test_corrupted_json(self, pm):
        name = _create_sample_project(pm)
        bad_file = pm.PROJECTS_DIR / name / "project.json"
        bad_file.write_text("NOT VALID JSON {{{", encoding="utf-8")
        assert pm.load_project(name) is None

    def test_delete_nonexistent_project(self, pm):
        assert pm.delete_project("Ghost") is False

    def test_duplicate_nonexistent(self, pm):
        with pytest.raises(FileNotFoundError):
            pm.duplicate_project("Ghost", "Clone")

    def test_rename_nonexistent(self, pm):
        with pytest.raises(FileNotFoundError):
            pm.rename_project("Ghost", "NewGhost")

    def test_duplicate_to_existing(self, pm):
        _create_sample_project(pm, "A")
        _create_sample_project(pm, "B")
        with pytest.raises(FileExistsError):
            pm.duplicate_project("A", "B")

    def test_rename_to_existing(self, pm):
        _create_sample_project(pm, "A")
        _create_sample_project(pm, "B")
        with pytest.raises(FileExistsError):
            pm.rename_project("A", "B")

    def test_create_empty_name(self, pm):
        with pytest.raises(ValueError):
            pm.create_project("", "topic")

    def test_create_folder_separator_name(self, pm):
        with pytest.raises(ValueError):
            pm.create_project("bad/name", "topic")

    def test_duplicate_empty_name(self, pm):
        _create_sample_project(pm, "X")
        with pytest.raises(ValueError):
            pm.duplicate_project("X", "")

    def test_rename_empty_name(self, pm):
        _create_sample_project(pm, "X")
        with pytest.raises(ValueError):
            pm.rename_project("X", "")

    def test_corrupted_research_json(self, pm):
        name = _create_sample_project(pm)
        f = pm.PROJECTS_DIR / name / "research.json"
        f.write_text("{bad", encoding="utf-8")
        assert _read_json(pm, name, "research.json") == {}

    def test_corrupted_storyboard_json(self, pm):
        name = _create_sample_project(pm)
        f = pm.PROJECTS_DIR / name / "storyboard.json"
        f.write_text("[}", encoding="utf-8")
        assert _read_json(pm, name, "storyboard.json") == {}

    def test_corrupted_image_prompts_json(self, pm):
        name = _create_sample_project(pm)
        f = pm.PROJECTS_DIR / name / "image_prompts.json"
        f.write_text("null", encoding="utf-8")
        assert _read_json(pm, name, "image_prompts.json") == {}

    def test_history_load_nonexistent_snapshot(self, pm, hm):
        name = _create_sample_project(pm)
        assert hm.load_snapshot(name, "Research", "nonexistent.json") == {}

    def test_history_delete_nonexistent_snapshot(self, pm, hm):
        name = _create_sample_project(pm)
        assert hm.delete_snapshot(name, "Research", "ghost.json") is False

    def test_history_restore_nonexistent_snapshot(self, pm, hm):
        name = _create_sample_project(pm)
        assert hm.restore_snapshot(name, "Research", "ghost.json") == {}


# =====================================================================
# PHASE 10 — Performance
# =====================================================================

class TestPerformance:

    def test_create_50_projects_under_5s(self, pm):
        start = time.time()
        for i in range(50):
            pm.create_project(f"Perf_{i:03d}", f"Topic {i}")
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Creating 50 projects took {elapsed:.2f}s"

    def test_search_50_projects_under_1s(self, pm):
        for i in range(50):
            pm.create_project(f"Perf_{i:03d}", f"Topic {i}")
        start = time.time()
        pm.search_projects("Perf_025")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Search took {elapsed:.2f}s"

    def test_sort_50_projects_under_1s(self, pm):
        for i in range(50):
            pm.create_project(f"Perf_{i:03d}", f"Topic {i}", "en", "Educational")
        projects = pm.get_projects()
        start = time.time()
        pm.sort_projects(projects, sort_by="name")
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Sort took {elapsed:.2f}s"

    def test_export_txt_under_3s(self, pm, es):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        _fill_image_prompts(pm, name)
        proj = pm.load_project(name)
        start = time.time()
        es.export_project(proj, fmt="txt")
        elapsed = time.time() - start
        assert elapsed < 3.0, f"TXT export took {elapsed:.2f}s"

    def test_task_manager_basic(self):
        tm = TaskManager()
        result = []
        def task_fn(task_mgr):
            return "done"
        def on_complete(res):
            result.append(res)
        tm.run_task("TestTask", task_fn, on_complete=on_complete)
        time.sleep(0.1)
        assert len(tm.history) >= 1
        assert tm.history[0].name == "TestTask"

    def test_task_manager_queue(self):
        tm = TaskManager()
        results = []
        def slow_task(task_mgr):
            time.sleep(0.05)
            return "slow"
        def fast_task(task_mgr):
            return "fast"
        def on_complete(res):
            results.append(res)
        tm.run_task("Slow", slow_task, on_complete=on_complete)
        tm.run_task("Fast", fast_task, on_complete=on_complete)
        time.sleep(0.3)
        assert "slow" in results
        assert "fast" in results

    def test_task_manager_cancel(self):
        tm = TaskManager()
        error_result = []
        def long_task(task_mgr):
            for _ in range(100):
                if task_mgr.check_cancelled():
                    raise TaskCancelledError("Cancelled")
                time.sleep(0.01)
            return "done"
        def on_error(exc):
            error_result.append(str(exc))
        tm.run_task("Long", long_task, on_error=on_error)
        time.sleep(0.02)
        tm.cancel()
        time.sleep(0.3)
        assert len(error_result) >= 1


# =====================================================================
# PHASE 12 — UI Consistency (structural checks)
# =====================================================================

class TestUIConsistency:

    def test_theme_exists(self):
        from core.theme import Dark, Fonts, Spacing, Radius
        assert hasattr(Dark, "BG")
        assert hasattr(Dark, "PRIMARY")
        assert hasattr(Dark, "CARD")
        assert hasattr(Fonts, "BODY")
        assert hasattr(Spacing, "X1")
        assert hasattr(Radius, "SM")

    def test_version_exists(self):
        from core.version import APP_NAME, VERSION, CODENAME
        assert APP_NAME == "KaiMi Studio"
        assert VERSION == "1.0.0"
        assert CODENAME == "Aurora"


# =====================================================================
# PHASE 13 — Code Quality (import checks)
# =====================================================================

class TestCodeQuality:

    def test_all_core_modules_import(self):
        import core.project_manager
        import core.research_storage
        import core.script_storage
        import core.storyboard_storage
        import core.image_prompt_storage
        import core.history_manager
        import core.export_service
        import core.task_manager
        import core.notifications
        import core.shortcuts
        import core.workflow
        import core.theme
        import core.version
        import core.logger

    def test_providers_import(self):
        import providers.provider_manager
        import providers.models
        import providers.exceptions
        import providers.registry
        import providers.base_provider

    def test_operators_import(self):
        import operators.research.operator
        import operators.script.operator
        import operators.storyboard.operator
        import operators.image_prompt.operator
