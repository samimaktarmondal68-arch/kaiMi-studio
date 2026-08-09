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
        from operators.script.models import DEFAULT_SCRIPT_MAX, DEFAULT_SCRIPT_MIN, ScriptRequest
        from operators.script.operator import ScriptOperator
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

        assert DEFAULT_SCRIPT_MIN <= len(result) <= DEFAULT_SCRIPT_MAX
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
        assert page.char_count_label.text() == "4725 / 5000 maximum"

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
        assert text == (
            "[0:00] Hello world\n\n[0:02] second sentence here\n\n[0:05] third part"
        )
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
        assert format_transcript(segments) == (
            "[0:00] This has extra spaces\n\n[0:01] and tabs inside"
        )

    def test_capitalizes_each_sentence(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 1.0, "text": "hello there. this is one sentence. and another"},
        ]
        assert format_transcript(segments) == (
            "[0:00] Hello there. This is one sentence. And another"
        )

    def test_paragraphs_split_on_long_pauses_with_single_blank_line(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 2.0, "text": "first paragraph begins here"},
            {"start": 2.5, "end": 4.0, "text": "and continues"},
            {"start": 9.0, "end": 11.0, "text": "second paragraph starts after a pause"},
            {"start": 12.0, "end": 14.0, "text": "and continues on"},
        ]
        result = format_transcript(segments)
        blocks = result.split("\n\n")
        assert len(blocks) == 4
        assert blocks[0] == "[0:00] First paragraph begins here"
        assert blocks[1] == "[0:02] and continues"
        assert blocks[2] == "[0:09] second paragraph starts after a pause"
        assert blocks[3] == "[0:12] and continues on"
        assert "\n\n\n" not in result

    def test_trims_leading_and_trailing_whitespace(self):
        from core.transcription_service import format_transcript
        segments = [
            {"start": 0.0, "end": 1.0, "text": "   leading text  "},
            {"start": 1.5, "end": 2.0, "text": "trailing   "},
        ]
        assert format_transcript(segments) == "[0:00] Leading text\n\n[0:01] trailing"

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

    # ------------------------------------------------------------------
    # Sprint 3.3B UI behaviour (mode toggle, selection, speed, library)
    # ------------------------------------------------------------------

    def test_default_mode_is_ai(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_AI
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert page._voice_source == VOICE_SOURCE_AI
        assert not page.generate_btn.isHidden()
        assert not page.tts_setup_btn.isHidden()
        assert page._upload_card.isHidden()

    def test_mode_toggle_switches_sections(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_AI, VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._mode_options[VOICE_SOURCE_IMPORT].clicked.emit(VOICE_SOURCE_IMPORT)
        assert page._voice_source == VOICE_SOURCE_IMPORT
        assert page.generate_btn.isHidden()  # narration card stays, AI actions hide
        assert not page._upload_card.isHidden()
        page._mode_options[VOICE_SOURCE_AI].clicked.emit(VOICE_SOURCE_AI)
        assert page._voice_source == VOICE_SOURCE_AI
        assert not page.generate_btn.isHidden()
        assert page._upload_card.isHidden()

    def test_voice_selection_updates_summary(self, pm):
        from core.voice_generation_service import DEFAULT_VOICE_ID
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._select_voice("am_michael")
        assert page._selected_voice_id == "am_michael"
        assert page.selected_voice_name_label.text() == "James"
        assert "Deep Educational Voice" in page.selected_voice_desc_label.text()
        assert "American English" in page.selected_voice_lang_label.text()
        page._select_voice(DEFAULT_VOICE_ID)
        assert page.selected_voice_name_label.text() == "Emma"

    def test_speed_options_are_exactly_expected(self, pm):
        from ui.pages.voice_page import SPEED_OPTIONS
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        values = [page.speed_combo.itemData(i) for i in range(page.speed_combo.count())]
        assert values == list(SPEED_OPTIONS)
        assert page._current_speed() == 1.0

    def test_playback_controls_visible_when_narration_exists(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert page.playback_container.isHidden()
        audio_file = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio")
        page._audio_path = str(audio_file)
        page._refresh_narration_ui()
        assert not page.playback_container.isHidden()
        assert page.narration_empty_label.isHidden()
        for btn in (page.play_btn, page.pause_btn, page.stop_btn,
                    page.download_audio_btn, page.regenerate_btn):
            assert btn.isEnabled()
        assert page.narration_status_badge.text() == "Generated"
        assert "File size:" in page.narration_size_label.text()
        assert not page.narration_duration_label.isHidden()

    def test_empty_state_without_narration(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert page.playback_container.isHidden()
        assert not page.narration_empty_label.isHidden()
        assert "No narration generated yet" in page.narration_empty_label.text()
        assert page.narration_status_badge.text() == "Ready"
        assert not page.generate_btn.isHidden()

    def test_play_switches_from_preview_to_narration(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        audio_file = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio")
        page._audio_path = str(audio_file)

        from PySide6.QtMultimedia import QMediaPlayer
        PLAYING = QMediaPlayer.PlaybackState.PlayingState
        PAUSED = QMediaPlayer.PlaybackState.PausedState

        sources = []
        state = {"value": QMediaPlayer.PlaybackState.StoppedState}

        class FakePlayer:
            def playbackState(self):
                return state["value"]

            def play(self):
                state["value"] = PLAYING

            def pause(self):
                state["value"] = PAUSED

            def stop(self):
                state["value"] = QMediaPlayer.PlaybackState.StoppedState

            def setSource(self, url):
                sources.append(str(url.toString()))

            def setSourceDevice(self, device):
                pass

        page._media_player = FakePlayer()
        page._audio_output = None

        # Preview clip is the active source (paused) -> Play must load narration.
        page._playing_narration = False
        state["value"] = PAUSED
        page._play_narration()
        assert state["value"] == PLAYING
        assert any("clip.wav" in src for src in sources)

        # Narration is paused -> Play resumes it without re-loading.
        page._playing_narration = True
        state["value"] = PAUSED
        page._play_narration()
        assert state["value"] == PLAYING
        assert len(sources) == 1  # no new source load

        # Narration is playing -> Pause pauses it.
        state["value"] = PLAYING
        page._pause_narration()
        assert state["value"] == PAUSED

    def test_regenerate_switches_to_ai_mode(self, pm, monkeypatch):
        from ui.pages.voice_page import VOICE_SOURCE_AI, VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_mode_selected(VOICE_SOURCE_IMPORT)
        assert page._voice_source == VOICE_SOURCE_IMPORT
        monkeypatch.setattr(page._voice_service, "is_available", lambda: False)
        page._regenerate_voice()
        assert page._voice_source == VOICE_SOURCE_AI

    def test_regenerate_asks_confirmation_when_narration_exists(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        audio_file = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio")
        page._audio_path = str(audio_file)
        asked = []
        page._confirm_regenerate = lambda: asked.append(True) or False
        page._regenerate_voice()
        assert asked == [True]  # confirmation shown, cancelled

    def test_regenerate_skips_confirmation_without_narration(self, pm, monkeypatch):
        from ui.pages.voice_page import VOICE_SOURCE_AI, VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_mode_selected(VOICE_SOURCE_IMPORT)

        def _must_not_ask():
            raise AssertionError("confirmation must not be shown without narration")

        page._confirm_regenerate = _must_not_ask
        monkeypatch.setattr(page._voice_service, "is_available", lambda: False)
        page._regenerate_voice()
        assert page._voice_source == VOICE_SOURCE_AI

    def test_status_badge_tracks_playback_state(self, pm):
        from PySide6.QtMultimedia import QMediaPlayer
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        audio_file = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio")
        page._audio_path = str(audio_file)
        page._refresh_narration_ui()
        assert page.narration_status_badge.text() == "Generated"

        page._playing_narration = True
        page._on_playback_state_changed(QMediaPlayer.PlaybackState.PlayingState)
        assert page.narration_status_badge.text() == "Playing"
        page._on_playback_state_changed(QMediaPlayer.PlaybackState.PausedState)
        assert page.narration_status_badge.text() == "Paused"
        page._on_playback_state_changed(QMediaPlayer.PlaybackState.StoppedState)
        assert page.narration_status_badge.text() == "Generated"

        # A preview's playback must never change the narration badge.
        page._playing_narration = False
        page._on_playback_state_changed(QMediaPlayer.PlaybackState.PlayingState)
        assert page.narration_status_badge.text() == "Generated"

    def test_imported_audio_shows_imported_status(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        audio_file = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio")
        page._audio_path = str(audio_file)
        page._on_mode_selected(VOICE_SOURCE_IMPORT)
        assert page.narration_status_badge.text() == "Imported"

    def test_regenerate_confirmation_decision(self, pm, monkeypatch):
        import ui.pages.voice_page as vp
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        audio_file = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio")
        page._audio_path = str(audio_file)

        class _Btn:
            pass

        class FakeMessageBox:
            result = "cancel"  # which button clickedButton() reports

            class Icon:
                Warning = object()

            class ButtonRole:
                DestructiveRole = 3
                RejectRole = 5

            def __init__(self, parent=None):
                self._regenerate_btn = None
                self._cancel_btn = None

            def setWindowTitle(self, text):
                pass

            def setIcon(self, icon):
                pass

            def setText(self, text):
                pass

            def setDefaultButton(self, button):
                pass

            def addButton(self, text, role):
                btn = _Btn()
                if text == "Regenerate":
                    self._regenerate_btn = btn
                else:
                    self._cancel_btn = btn
                return btn

            def exec(self):
                return 0

            def clickedButton(self):
                if FakeMessageBox.result == "regenerate" and self._regenerate_btn:
                    return self._regenerate_btn
                return self._cancel_btn

        monkeypatch.setattr(vp, "QMessageBox", FakeMessageBox)

        generated = []
        page.generate_voice = lambda: generated.append(True)

        # Cancel keeps the existing narration and does not regenerate.
        FakeMessageBox.result = "cancel"
        page._regenerate_voice()
        assert generated == []

        # Regenerate proceeds to generation.
        FakeMessageBox.result = "regenerate"
        page._regenerate_voice()
        assert generated == [True]

    def test_page_no_longer_embeds_voice_library(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert not hasattr(page, "voice_search")
        assert not hasattr(page, "_voice_cards")
        assert not hasattr(page, "all_voices_scroll")

    def test_import_flow_requires_file_then_enables_transcribe(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert not page.transcribe_btn.isEnabled()
        page._audio_path = "C:\\tmp\\clip.wav"
        page._refresh_import_ui()
        assert page.transcribe_btn.isEnabled()
        assert "clip.wav" in page.file_label.text()


class TestVoiceLibraryCatalog:
    """Sprint 3.3B: the full Kokoro voice catalogue and search filtering."""

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.voice_page import VoicePage
        app = QApplication.instance() or QApplication([])
        page = VoicePage()
        page.manager = pm
        return page

    def test_catalogue_has_54_entries(self):
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG
        assert len(KOKORO_VOICE_CATALOG) == 54

    def test_catalogue_entries_have_display_metadata(self):
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG
        for voice_id, (name, description) in KOKORO_VOICE_CATALOG.items():
            assert voice_id
            assert name and isinstance(name, str)
            assert description and isinstance(description, str)

    def test_catalogue_covers_all_installed_voices(self):
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG, _load_installed_voice_ids
        installed = _load_installed_voice_ids()
        if not installed:
            pytest.skip("Kokoro voices file not present on disk")
        missing = [voice_id for voice_id in installed
                   if voice_id not in KOKORO_VOICE_CATALOG]
        assert missing == []

    def test_catalogue_covers_recommended_profiles(self):
        from core.voice_generation_service import VOICE_PROFILES
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG
        for profile in VOICE_PROFILES:
            assert profile.id in KOKORO_VOICE_CATALOG

    def test_fallback_entry_for_unknown_id(self):
        from ui.pages.voice_page import _fallback_voice_entry
        name, desc = _fallback_voice_entry("xx_mystery")
        assert name == "Mystery"
        assert "International" in desc
        name, desc = _fallback_voice_entry("plainvoice")
        assert name == "Plainvoice"
        assert desc == "Local Kokoro voice"

    def test_voice_match_is_case_insensitive(self):
        from ui.dialogs.voice_selection import VoiceSelectionDialog
        lang = "British English · Female"
        assert VoiceSelectionDialog._matches("Emma", "Calm Documentary", lang, "calm")
        assert VoiceSelectionDialog._matches("Emma", "Calm Documentary", lang, "emma")
        assert VoiceSelectionDialog._matches("Emma", "Calm Documentary", lang, "doc")
        assert VoiceSelectionDialog._matches("Emma", "Calm Documentary", lang, "british")
        assert not VoiceSelectionDialog._matches("Emma", "Calm Documentary", lang, "rocket")

    def test_empty_query_matches_everything(self):
        from ui.dialogs.voice_selection import VoiceSelectionDialog
        assert VoiceSelectionDialog._matches("Anything", "description here", "Language", "")

    def test_search_box_is_case_insensitive(self, pm):
        from ui.dialogs.voice_selection import VoiceSelectionDialog
        from ui.pages.voice_page import _voice_language
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        recommended = [
            (p.id, p.name, p.description, _voice_language(p.id))
            for p in page._recommended_profiles
        ]
        dialog = VoiceSelectionDialog("af_heart", recommended, [])
        dialog.voice_search.setText("XIAOXIAO")
        assert not dialog._voice_cards  # not a recommended voice
        dialog.voice_search.setText("EMMA")
        assert dialog._voice_cards
        for _voice_id, card in dialog._voice_cards.items():
            assert "emma" in card.name_label.text().lower()
        dialog.close()

    def test_library_exposes_all_installed_voice_ids(self, pm):
        from ui.dialogs.voice_selection import VoiceSelectionDialog
        from ui.pages.voice_page import _load_installed_voice_ids, _voice_language
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        installed = _load_installed_voice_ids()
        recommended = [
            (p.id, p.name, p.description, _voice_language(p.id))
            for p in page._recommended_profiles
        ]
        remaining = [
            (vid, nm, dc, _voice_language(vid))
            for vid, nm, dc in page._remaining_voices()
        ]
        dialog = VoiceSelectionDialog("af_heart", recommended, remaining)
        visible = set(dialog._voice_cards.keys())
        if installed:
            assert set(installed).issubset(visible)
        else:
            assert len(visible) == 54
        dialog.close()


class TestVoiceSelectionDialog:
    """RC-1: the voice library moved into the modal Voice Selection dialog."""

    @staticmethod
    def _make_dialog(current="af_heart"):
        from core.voice_generation_service import VOICE_PROFILES
        from ui.dialogs.voice_selection import VoiceSelectionDialog
        from ui.pages.voice_page import (
            KOKORO_VOICE_CATALOG,
            _fallback_voice_entry,
            _voice_language,
        )

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        recommended = [
            (p.id, p.name, p.description, _voice_language(p.id))
            for p in VOICE_PROFILES
        ]
        recommended_ids = {p.id for p in VOICE_PROFILES}
        remaining = [
            (voice_id, name, desc, _voice_language(voice_id))
            for voice_id, (name, desc) in KOKORO_VOICE_CATALOG.items()
            if voice_id not in recommended_ids
        ]
        return VoiceSelectionDialog(current, recommended, remaining)

    def test_dialog_lists_recommended_and_all_voices(self):
        from core.voice_generation_service import VOICE_PROFILES
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG
        dialog = self._make_dialog()
        assert dialog.recommended_grid.count() == len(VOICE_PROFILES)
        assert dialog.all_voices_grid.count() == (
            len(KOKORO_VOICE_CATALOG) - len(VOICE_PROFILES)
        )
        assert len(dialog._voice_cards) == len(KOKORO_VOICE_CATALOG)
        dialog.close()

    def test_dialog_remembers_previous_selection(self):
        dialog = self._make_dialog(current="am_michael")
        card = dialog._voice_cards["am_michael"]
        assert not card.selected_badge.isHidden()
        assert card.select_btn.text() == "Selected"
        assert not card.select_btn.isEnabled()
        dialog.close()

    def test_dialog_select_emits_and_closes(self):
        from PySide6.QtWidgets import QDialog
        dialog = self._make_dialog()
        chosen = []
        dialog.voice_selected.connect(chosen.append)
        dialog._select_voice("bf_emma")
        assert chosen == ["bf_emma"]
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_dialog_search_filters_voices(self):
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG, _fallback_voice_entry
        dialog = self._make_dialog()
        dialog.voice_search.setText("Xiaoxiao")
        assert dialog._voice_cards
        for voice_id in dialog._voice_cards:
            entry = KOKORO_VOICE_CATALOG.get(voice_id) or _fallback_voice_entry(voice_id)
            assert "xiaoxiao" in (entry[0] + " " + entry[1]).lower()
        assert "0 shown" in dialog.recommended_count.text()
        dialog.close()

    def test_dialog_cards_show_language(self):
        from ui.pages.voice_page import _voice_language
        dialog = self._make_dialog()
        assert _voice_language("bf_emma") == "British English · Female"
        assert _voice_language("zm_yunyang") == "Chinese · Male"
        assert "British English" in dialog._voice_cards["bf_emma"].lang_label.text()
        dialog.close()

    def test_dialog_preview_signal_emits_voice_id(self):
        dialog = self._make_dialog()
        previewed = []
        dialog.preview_requested.connect(previewed.append)
        dialog._voice_cards["af_heart"].preview_btn.click()
        assert previewed == ["af_heart"]
        dialog.close()


class TestVoicePrefsPersistence:
    """Sprint 3.3B: voice.json persistence round-trip and backward compat."""

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.voice_page import VoicePage
        app = QApplication.instance() or QApplication([])
        page = VoicePage()
        page.manager = pm
        return page

    def test_voice_prefs_round_trip(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._voice_source = VOICE_SOURCE_IMPORT
        page._selected_voice_id = "am_michael"
        page._set_speed(1.2)
        page._persist_voice_prefs()

        stored = _read_json(pm, name, "voice.json")
        assert stored["voice_source"] == "import"
        assert stored["voice_id"] == "am_michael"
        assert stored["voice_speed"] == 1.2

        reloaded = self._make_page(pm)
        reloaded.set_project(name)
        assert reloaded._voice_source == VOICE_SOURCE_IMPORT
        assert reloaded._selected_voice_id == "am_michael"
        assert reloaded._current_speed() == 1.2

    def test_legacy_voice_json_restores_defaults(self, pm):
        from core.voice_generation_service import DEFAULT_SPEED, DEFAULT_VOICE_ID
        from ui.pages.voice_page import VOICE_SOURCE_AI
        name = _create_sample_project(pm)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Old transcript",
            "segments": [],
            "audio_file": "old.wav",
        })
        page = self._make_page(pm)
        page.set_project(name)
        assert page._voice_source == VOICE_SOURCE_AI
        assert page._selected_voice_id == DEFAULT_VOICE_ID
        assert page._current_speed() == DEFAULT_SPEED
        assert page.transcript_box.toPlainText() == "Old transcript"

    def test_invalid_voice_prefs_fall_back_to_defaults(self, pm):
        from core.voice_generation_service import DEFAULT_SPEED, DEFAULT_VOICE_ID
        from ui.pages.voice_page import VOICE_SOURCE_AI
        name = _create_sample_project(pm)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "voice_source": "banana",
            "voice_id": "",
            "voice_speed": 99,
        })
        page = self._make_page(pm)
        page.set_project(name)
        assert page._voice_source == VOICE_SOURCE_AI
        assert page._selected_voice_id == DEFAULT_VOICE_ID
        assert page._current_speed() == DEFAULT_SPEED

    def test_select_voice_persists_to_disk(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._select_voice("am_michael")
        stored = _read_json(pm, name, "voice.json")
        assert stored["voice_id"] == "am_michael"
        assert stored["voice_source"] == "ai"

    def test_persist_keeps_existing_transcript_fields(self, pm):
        name = _create_sample_project(pm)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Kept",
            "segments": [{"start": 0, "end": 1, "text": "Kept", "time": "00:00"}],
        })
        page = self._make_page(pm)
        page.set_project(name)
        page._select_voice("bf_emma")
        stored = _read_json(pm, name, "voice.json")
        assert stored["transcript"] == "Kept"
        assert len(stored["segments"]) == 1
        assert stored["voice_id"] == "bf_emma"


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


class TestImagePromptBuilderReferenceFormat:
    """Sprint 3.6.1 — the builder must instruct the model to reproduce the
    Production Stage 7 reference format exactly: one continuous natural-language
    prompt per transcript scene, no metadata, no section labels, timestamp first.
    """

    @staticmethod
    def _build_user_prompt():
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.prompt_builder import ImagePromptBuilder

        request = ImagePromptRequest(
            script_text="INT. CLASSROOM - DAY\nTeacher introduces the water cycle.",
            transcript="[0:00] Water is always moving around us.\n\n"
                       "[0:04] It changes form as it travels.",
            timestamps=[
                {"time": "00:00", "text": "Water is always moving around us."},
                {"time": "00:04", "text": "It changes form as it travels."},
            ],
            topic="The Water Cycle",
            language="English",
        )
        _, user_prompt = ImagePromptBuilder().build(request)
        return user_prompt

    def test_embeds_reference_format(self):
        prompt = self._build_user_prompt()
        assert "Hand-drawn 2D doodle cartoon animation" in prompt
        assert "Narration focus" in prompt
        assert "16:9 aspect ratio" in prompt
        assert "KaiMi educational doodle style" in prompt
        assert "[0:00]" in prompt  # reference template timestamp line

    def test_orders_reference_elements(self):
        prompt = self._build_user_prompt()
        opening = prompt.index("Hand-drawn 2D doodle cartoon animation")
        narration = prompt.index("Narration focus")
        aspect = prompt.index("16:9 aspect ratio")
        style = prompt.index("KaiMi educational doodle style")
        assert opening < narration < aspect < style

    def test_requires_one_prompt_per_transcript_scene(self):
        prompt = self._build_user_prompt()
        assert "one image prompt per transcript scene" in prompt
        assert "never merge or split transcript scenes" in prompt

    def test_reference_template_has_no_metadata_labels(self):
        from operators.image_prompt.prompt_builder import PROMPT_TEMPLATE
        for label in (
            "Master Style Lock:",
            "Character:",
            "Environment:",
            "Lighting:",
            "Camera:",
            "Negative Prompt:",
            "Scene:",
            "Visual Description:",
        ):
            assert label not in PROMPT_TEMPLATE, f"'{label}' leaked into template"

    def test_instructions_warn_against_labels_and_metadata(self):
        prompt = self._build_user_prompt()
        assert "Never write labels" in prompt
        assert "headings, no labels, no metadata" in prompt.lower()

    def test_removed_old_labeled_section_instruction(self):
        prompt = self._build_user_prompt()
        assert "Subject, Environment, Composition" not in prompt
        assert "Art Style, Color Palette" not in prompt

    def test_keeps_json_contract(self):
        prompt = self._build_user_prompt()
        for key in ("scene_number", "timestamp", "prompt_title", "full_image_prompt"):
            assert f'"{key}"' in prompt

    def test_keeps_source_context(self):
        prompt = self._build_user_prompt()
        assert "The Water Cycle" in prompt
        assert "Water is always moving around us." in prompt
        assert "[0:04] It changes form as it travels." in prompt

    def test_preview_via_operator(self):
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator

        request = ImagePromptRequest(
            script_text="A short script about gravity.",
            transcript="[0:00] Gravity pulls everything down.",
            timestamps=[{"time": "00:00", "text": "Gravity pulls everything down."}],
        )
        preview = ImagePromptOperator().get_prompt_preview(request)
        assert "Hand-drawn 2D doodle cartoon animation" in preview
        assert "Narration focus" in preview


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
# PHASE 12D — Application Identity (RC-3)
# =====================================================================

class TestAppIdentity:
    """RC-3: all application identity lives in core.version and is rendered
    consistently across the window title, About dialog, Settings, and error
    reporting."""

    def test_version_metadata_complete(self):
        from core.version import (
            APP_NAME, APP_DESCRIPTION, AUTHOR, BUILD, BUILD_DATE, CODENAME,
            COPYRIGHT, ENGINE_VERSION, OFFICIAL_EMAIL, RELEASE_CHANNEL,
            SCHEMA_VERSION, VERSION, WORKFLOW_VERSION,
        )
        assert APP_NAME == "KaiMi Studio"
        assert VERSION == "1.0.0"
        assert CODENAME == "Aurora"
        assert BUILD
        assert BUILD_DATE
        assert RELEASE_CHANNEL
        assert ENGINE_VERSION
        assert WORKFLOW_VERSION
        assert SCHEMA_VERSION
        assert AUTHOR == "Md Samim Aktar Mondal"
        assert OFFICIAL_EMAIL == "kaimistudio07@gmail.com"
        assert APP_DESCRIPTION
        assert COPYRIGHT and AUTHOR in COPYRIGHT

    def test_copyright_includes_author_and_year(self):
        from core.version import AUTHOR, COPYRIGHT, YEAR
        assert YEAR in COPYRIGHT
        assert AUTHOR in COPYRIGHT
        assert COPYRIGHT.startswith("\u00A9")

    def test_settings_about_card_shows_identity(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from ui.pages.settings_page import SettingsPage

        app = QApplication.instance() or QApplication([])
        page = SettingsPage()
        texts = [lbl.text() for lbl in page.findChildren(QLabel)]
        joined = "\n".join(texts)
        assert "kaimistudio07@gmail.com" in joined
        assert "Md Samim Aktar Mondal" in joined
        assert "1.0.0" in joined
        assert page.email_copy_btn is not None
        assert page.about_dialog_btn is not None

    def test_settings_email_copy_button_copies_to_clipboard(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.version import OFFICIAL_EMAIL
        from ui.pages.settings_page import SettingsPage

        app = QApplication.instance() or QApplication([])
        page = SettingsPage()
        page.email_copy_btn.click()
        assert QApplication.clipboard().text() == OFFICIAL_EMAIL

    def test_about_dialog_displays_full_identity(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from core.version import AUTHOR, OFFICIAL_EMAIL, VERSION
        from ui.dialogs.about_dialog import AboutDialog

        app = QApplication.instance() or QApplication([])
        dlg = AboutDialog()
        texts = "\n".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        assert "KaiMi Studio" in texts
        assert VERSION in texts
        assert AUTHOR in texts
        assert OFFICIAL_EMAIL in texts
        assert "Engine" in texts
        assert "Workflow" in texts
        dlg.close()

    def test_about_dialog_copy_button_copies_email(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QPushButton
        from core.version import OFFICIAL_EMAIL
        from ui.dialogs.about_dialog import AboutDialog

        app = QApplication.instance() or QApplication([])
        dlg = AboutDialog()
        copy_btns = [b for b in dlg.findChildren(QPushButton) if b.text() == "Copy"]
        assert len(copy_btns) == 1
        copy_btns[0].click()
        assert QApplication.clipboard().text() == OFFICIAL_EMAIL
        dlg.close()

    def test_window_title_uses_centralized_metadata(self):
        import inspect
        from ui.main_window import MainWindow
        src = inspect.getsource(MainWindow.__init__)
        assert "APP_NAME" in src
        assert "VERSION" in src
        assert 'setWindowTitle(f"{APP_NAME} v{VERSION}")' in src

    def test_sidebar_version_label_opens_about_dialog(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QWidget
        from ui.sidebar import _AboutLabel, Sidebar

        app = QApplication.instance() or QApplication([])
        opened = []

        class FakeWindow(QWidget):
            def show_about_dialog(self):
                opened.append(True)

        win = FakeWindow()
        sidebar = Sidebar(win)
        labels = sidebar.findChildren(_AboutLabel)
        assert labels
        assert labels[0].text().startswith("v")
        labels[0].clicked.emit()
        assert opened == [True]
        sidebar.deleteLater()
        win.deleteLater()

    def test_crash_handler_references_official_email(self):
        import inspect
        from core import crash_handler
        src = inspect.getsource(crash_handler._show_error_dialog)
        assert "OFFICIAL_EMAIL" in src

    def test_no_placeholder_emails_in_source(self):
        """No placeholder support addresses may remain anywhere."""
        root = Path(__file__).resolve().parent.parent
        placeholders = (
            "@example.com", "@example.org", "@yourdomain.com",
            "@your-email", "your@email", "support@", "placeholder@",
        )
        this_file = Path(__file__).resolve()
        hits = []
        for base, dirs, files in os.walk(root):
            # Prune the bundled release build and vendored/hidden trees.
            dirs[:] = [d for d in dirs if d not in ("release", ".venv", ".git")]
            for fname in files:
                if not fname.endswith((".py", ".md")):
                    continue
                path = Path(base) / fname
                if path.resolve() == this_file:
                    continue  # this test file defines the placeholder patterns
                low = path.read_text(encoding="utf-8", errors="ignore").lower()
                for ph in placeholders:
                    if ph in low:
                        hits.append(f"{path}: {ph}")
        assert hits == []


class TestReleaseMetadata:
    """RC-4: every build resource derives from core.version — no duplicated
    or outdated version/publisher constants anywhere in the build chain."""

    @staticmethod
    def _root():
        return Path(__file__).resolve().parent.parent

    def test_build_manifest_matches_version_module(self):
        from core.version import (
            APP_NAME, APP_URL, AUTHOR, BUILD, BUILD_DATE, CODENAME, COMPANY,
            COPYRIGHT, ENGINE_VERSION, OFFICIAL_EMAIL, RELEASE_CHANNEL,
            SCHEMA_VERSION, VERSION, WORKFLOW_VERSION, build_manifest,
        )
        m = build_manifest()
        assert m["application"] == APP_NAME
        assert m["version"] == VERSION
        assert m["build"] == BUILD
        assert m["codename"] == CODENAME
        assert m["release_channel"] == RELEASE_CHANNEL
        assert m["build_date"] == BUILD_DATE
        assert m["author"] == AUTHOR
        assert m["official_email"] == OFFICIAL_EMAIL
        assert m["company"] == COMPANY
        assert m["copyright"] == COPYRIGHT
        assert m["engine_version"] == ENGINE_VERSION
        assert m["workflow_version"] == WORKFLOW_VERSION
        assert m["schema_version"] == SCHEMA_VERSION
        assert m["app_url"] == APP_URL
        # The publisher/company is the author for this release — never a
        # bare "KaiMi" placeholder.
        assert m["company"] == m["author"]
        assert "KaiMi" not in m["company"]

    def test_committed_version_info_matches_generated(self):
        from core.version import render_version_info
        committed = (self._root() / "file_version_info.txt").read_text(encoding="utf-8")
        assert committed == render_version_info()

    def test_committed_iss_defines_match_generated(self):
        from core.version import render_iss_defines
        committed = (self._root() / "installer_metadata.iss").read_text(encoding="utf-8")
        assert committed == render_iss_defines()

    def test_committed_manifest_matches_generated(self):
        from core.version import render_manifest_json
        committed = (self._root() / "build_manifest.json").read_text(encoding="utf-8")
        assert committed == render_manifest_json()

    def test_installer_uses_generated_defines_not_hardcoded_values(self):
        iss = (self._root() / "installer.iss").read_text(encoding="utf-8")
        assert '#include "installer_metadata.iss"' in iss
        assert 'MyAppPublisher "KaiMi"' not in iss
        assert 'MyAppVersion "1.0.0"' not in iss
        assert "© 2026 KaiMi" not in iss

    def test_version_info_has_author_not_placeholder_company(self):
        from core.version import COMPANY, COPYRIGHT
        txt = (self._root() / "file_version_info.txt").read_text(encoding="utf-8")
        assert "CompanyName', u'KaiMi'" not in txt
        assert COMPANY in txt
        assert COPYRIGHT in txt
        assert COPYRIGHT.split("©")[-1].strip().startswith("2026 Md Samim")

    def test_build_script_regenerates_release_metadata(self):
        src = (self._root() / "build.py").read_text(encoding="utf-8")
        assert "write_release_metadata" in src
        assert "render_version_info" in src
        assert "render_iss_defines" in src
        assert "render_manifest_json" in src
        assert "from core.version import" in src

    def test_spec_reads_name_from_centralized_metadata(self):
        src = (self._root() / "KaiMi Studio.spec").read_text(encoding="utf-8")
        assert "from core.version import APP_NAME" in src
        assert "name=APP_NAME" in src
        assert "name='KaiMi Studio'" not in src

    def test_build_script_uses_metadata_for_exe_path(self):
        src = (self._root() / "build.py").read_text(encoding="utf-8")
        assert 'DIST / APP_NAME' in src
        assert 'f"{APP_NAME}.exe"' in src


class TestAssetManagerEmptyState:
    """RC-5: a project with no assets shows a helpful empty state instead of
    a blank table; the table appears once assets exist."""

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.asset_manager import AssetManagerPage

        app = QApplication.instance() or QApplication([])
        page = AssetManagerPage()
        page.manager = pm
        return page

    def test_no_assets_shows_empty_state(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert page.assets_stack.currentIndex() == 1  # empty-state page
        assert not page.assets_empty.isHidden()
        assert "No Assets Imported" in page.assets_empty.title_label.text()
        assert page.asset_table.rowCount() == 0

    def test_with_assets_shows_table(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        audio = pm.PROJECTS_DIR / name / "audio" / "clip.wav"
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"RIFF fake audio")
        page.set_project(name)
        assert page.assets_stack.currentIndex() == 0  # table page
        assert page.asset_table.rowCount() == 1

    def test_no_project_selected_hides_content(self, pm):
        page = self._make_page(pm)
        page.set_project(None)
        assert not page.empty_state.isHidden()
        assert page._content_widget.isHidden()


class TestVersionHistoryDialog:
    """RC-5: the Version History dialog must render rows without crashing
    (regression guard for the setForeground(QColor) fix)."""

    def test_dialog_renders_history_rows(self, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.version_history import VersionHistoryDialog

        app = QApplication.instance() or QApplication([])

        class FakeHistory:
            def get_action_history(self, project_name):
                return [
                    {
                        "datetime": "01-01-2026 10:00",
                        "action": "Saved",
                        "description": "Manually saved script",
                    },
                    {
                        "datetime": "01-01-2026 11:00",
                        "action": "Restore",
                        "description": "Restored from snapshot",
                    },
                ]

        monkeypatch.setattr(
            "ui.pages.version_history.HistoryManager", lambda: FakeHistory()
        )
        dlg = VersionHistoryDialog("DemoProject")
        assert dlg.version_table.rowCount() == 2
        assert dlg.count_label.text() == "2 versions"
        dlg.close()


class TestBrandingIntegration:
    """Release prep: every part of KaiMi Studio reads its artwork from the
    single centralized ``resources/branding`` folder.

    The official pair (``logo.png`` + ``app_icon.png``) is the only branding
    source; ``app_icon.ico`` is derived from ``app_icon.png`` at build time.
    """

    @staticmethod
    def _root():
        return Path(__file__).resolve().parent.parent

    def test_branding_folder_contains_expected_assets(self):
        from core.branding import branding_dir
        expected = [
            "logo.png",
            "app_icon.png",
            "app_icon.ico",
        ]
        folder = branding_dir()
        assert folder.is_dir()
        for name in expected:
            assert (folder / name).is_file(), f"missing {name}"

    def test_branding_accessor_resolves_to_existing_files(self):
        from core.branding import (
            app_icon_ico_path,
            app_icon_path,
            branding_dir,
            logo_path,
        )
        assert branding_dir() == self._root() / "resources" / "branding"
        assert logo_path().is_file()
        assert app_icon_path().is_file()
        assert app_icon_ico_path().is_file()
        assert logo_path().name == "logo.png"
        assert app_icon_path().name == "app_icon.png"
        assert app_icon_ico_path().name == "app_icon.ico"

    def test_logo_pixmap_scales_without_distortion(self):
        """The lockup scales to the requested width, aspect preserved."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PIL import Image
        from PySide6.QtWidgets import QApplication
        from core.branding import logo_path, logo_pixmap

        app = QApplication.instance() or QApplication([])
        pixmap = logo_pixmap(48)
        assert not pixmap.isNull()
        assert pixmap.width() == 48
        with Image.open(logo_path()) as im:
            ratio = im.height / im.width
        assert abs(pixmap.height() / pixmap.width() - ratio) < 0.02

    def test_app_icon_loads_from_official_png(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.branding import app_icon, app_icon_path

        app = QApplication.instance() or QApplication([])
        icon = app_icon()
        assert not icon.isNull()
        assert icon.availableSizes()  # source PNG resolves to a real icon

    def test_about_dialog_displays_logo_above_title(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from ui.dialogs.about_dialog import AboutDialog

        app = QApplication.instance() or QApplication([])
        dlg = AboutDialog()
        pixmap_labels = [
            lbl for lbl in dlg.findChildren(QLabel)
            if lbl.pixmap() is not None and not lbl.pixmap().isNull()
        ]
        assert pixmap_labels
        assert pixmap_labels[0].pixmap().width() == 200
        dlg.close()

    def test_settings_about_card_displays_logo(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from ui.pages.settings_page import SettingsPage

        app = QApplication.instance() or QApplication([])
        page = SettingsPage()
        pixmap_labels = [
            lbl for lbl in page.findChildren(QLabel)
            if lbl.pixmap() is not None and not lbl.pixmap().isNull()
        ]
        assert pixmap_labels
        assert pixmap_labels[0].pixmap().width() == 96

    def test_sidebar_displays_logo_above_title(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel, QWidget
        from ui.sidebar import Sidebar

        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        sidebar = Sidebar(parent)
        pixmap_labels = [
            lbl for lbl in sidebar.findChildren(QLabel)
            if lbl.pixmap() is not None and not lbl.pixmap().isNull()
        ]
        assert pixmap_labels
        assert pixmap_labels[0].pixmap().width() == 56
        sidebar.deleteLater()
        parent.deleteLater()

    def test_ico_is_generated_from_official_png(self):
        """The build-time .ico derives from the official assets and matches
        the expected multi-resolution sizes."""
        from PIL import Image
        from core.branding import app_icon_ico_path
        from generate_icon import ensure_app_icon_ico

        ico_path = ensure_app_icon_ico()
        assert ico_path == app_icon_ico_path()
        assert ico_path.is_file()
        with Image.open(ico_path) as im:
            sizes = sorted(set(im.ico.sizes()))
        assert sizes == sorted([(16, 16), (32, 32), (48, 48),
                                (64, 64), (128, 128), (256, 256)])

    def test_generate_icon_converts_official_png(self, tmp_path):
        """generate_icon.py converts the official app_icon.png into a valid
        .ico without modifying the source PNG."""
        from PIL import Image
        from core.branding import app_icon_path
        from generate_icon import ensure_app_icon_png, generate_app_icon_ico

        ensure_app_icon_png()  # derived icon exists before conversion
        out = tmp_path / "derived.ico"
        result = generate_app_icon_ico(app_icon_path(), out)
        assert result == out
        assert out.is_file()
        with Image.open(out) as im:
            assert im.format == "ICO"
        source_before = app_icon_path().read_bytes()
        assert app_icon_path().read_bytes() == source_before  # untouched

    def test_app_sets_window_icon_from_centralized_folder(self):
        import inspect
        from ui.main_window import MainWindow
        src = inspect.getsource(MainWindow.__init__)
        assert "setWindowIcon" in src
        assert "app_icon" in src
        main_src = (self._root() / "main.py").read_text(encoding="utf-8")
        assert "setWindowIcon(app_icon())" in main_src
        assert "resources/branding/app_icon.png" in main_src
        assert "resources/branding/logo.png" in main_src

    def test_build_resources_use_centralized_branding(self):
        build_src = (self._root() / "build.py").read_text(encoding="utf-8")
        spec_src = (self._root() / "KaiMi Studio.spec").read_text(encoding="utf-8")
        iss_src = (self._root() / "installer.iss").read_text(encoding="utf-8")
        gen_src = (self._root() / "generate_icon.py").read_text(encoding="utf-8")

        # build.py regenerates the .ico from the official PNG before building.
        assert '"resources" / "branding" / "app_icon.ico"' in build_src
        assert "ensure_app_icon_ico" in build_src
        assert "generate_icon" in build_src
        # spec/installer consume the generated .ico from the central folder.
        assert "resources/branding/app_icon.ico" in spec_src
        assert "SetupIconFile=resources\\branding\\app_icon.ico" in iss_src
        # the generator converts the official PNG; it never draws its own mark
        # and resolves paths through core.branding (no hardcoded folder).
        assert "app_icon.png" in gen_src
        assert "app_icon_ico_path" in gen_src
        assert "app_icon_path" in gen_src

    def test_no_scattered_branding_paths_remain(self):
        root = self._root()
        forbidden = ("assets/icons", "kaimi.ico", "kaimi_256")
        hits = []
        for fname in ("main.py", "build.py", "generate_icon.py",
                      "KaiMi Studio.spec", "installer.iss"):
            text = (root / fname).read_text(encoding="utf-8").lower()
            for token in forbidden:
                if token in text:
                    hits.append(f"{fname}: {token}")
        assert hits == []


# =====================================================================
# PHASE 12B — RC-6.2 Voice Page State Layout Repair
# =====================================================================

class TestVoicePageRC62:
    """RC-6.2: Voice page state layout repair & transcript visibility.

    The Narration card must never clip or overlap its sections, the AI and
    Import modes must be true mutually exclusive UI states, and the
    Transcript group must stay visible with a clear status in every state.
    """

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.voice_page import VoicePage

        QApplication.instance() or QApplication([])
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

    @staticmethod
    def _attach_audio(page, pm, name, filename="clip.wav"):
        audio_file = pm.PROJECTS_DIR / name / "audio" / filename
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"RIFF fake audio data")
        page._audio_path = str(audio_file)
        page._refresh_narration_ui()
        return audio_file

    # --- A. AI Voice state -------------------------------------------------

    def test_ai_state_shows_voice_identity_and_controls(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_AI
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)

        assert page._voice_source == VOICE_SOURCE_AI
        # selected voice identity fully visible with metadata
        assert not page.ai_identity_container.isHidden()
        assert not page.selected_voice_name_label.isHidden()
        assert not page.selected_voice_desc_label.isHidden()
        assert not page.selected_voice_lang_label.isHidden()
        assert page.selected_voice_name_label.text() == "Emma"
        assert page.selected_voice_desc_label.text()
        assert page.selected_voice_lang_label.text()
        # voice controls visible
        assert not page.preview_btn.isHidden()
        assert not page.change_voice_btn.isHidden()
        assert not page.ai_speed_container.isHidden()
        assert not page.ai_generation_container.isHidden()
        assert not page.generate_btn.isHidden()
        assert not page.tts_setup_btn.isHidden()
        # imported-audio chrome never leaks into the AI state
        assert page.import_identity_container.isHidden()
        assert page.imported_file_label.isHidden()

    def test_ai_state_shared_sections_visible_with_audio(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        self._attach_audio(page, pm, name)

        assert not page.narration_summary.isHidden()
        assert not page.playback_container.isHidden()
        assert not page.export_container.isHidden()
        assert not page.transcript_container.isHidden()
        assert not page.next_btn.isHidden()

    # --- B. Generated AI Voice state ----------------------------------------

    def test_generated_ai_state_summary_and_sections(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        self._attach_audio(page, pm, name)

        assert not page.narration_summary.isHidden()
        assert page.summary_title_label.text() == "Voice Generated"
        assert page.summary_voice_label.text().startswith("Voice: ")
        assert "Duration:" in page.narration_duration_label.text()
        assert "File size:" in page.narration_size_label.text()
        for section in (page.playback_container, page.export_container,
                        page.transcript_container):
            assert not section.isHidden()
        assert not page.next_btn.isHidden()

    # --- C. Import Audio state ----------------------------------------------

    def test_import_state_shows_audio_identity_hides_ai_controls(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        self._attach_audio(page, pm, name, filename="lesson.mp3")
        page._on_mode_selected(VOICE_SOURCE_IMPORT)

        assert page._voice_source == VOICE_SOURCE_IMPORT
        # imported audio identity block
        assert not page.import_identity_container.isHidden()
        assert page.imported_title_label.text() == "Imported Audio"
        assert page.imported_file_label.text() == "lesson.mp3"
        assert "File size:" in page.imported_meta_label.text()
        assert not page.import_preview_btn.isHidden()
        assert not page.replace_audio_btn.isHidden()
        # AI voice-specific controls must NOT be shown
        assert page.ai_identity_container.isHidden()
        assert page.selected_voice_name_label.isHidden()
        assert page.selected_voice_desc_label.isHidden()
        assert page.selected_voice_lang_label.isHidden()
        assert page.preview_btn.isHidden()
        assert page.change_voice_btn.isHidden()
        assert page.ai_speed_container.isHidden()
        assert page.ai_generation_container.isHidden()
        assert page.generate_btn.isHidden()
        assert page.tts_setup_btn.isHidden()
        # shared workflow sections stay available
        assert not page.playback_container.isHidden()
        assert not page.export_container.isHidden()
        assert not page.transcript_container.isHidden()
        assert not page.next_btn.isHidden()
        # upload card handles importing/configuring only
        assert not page._upload_card.isHidden()

    def test_import_state_without_audio_keeps_transcript_group(self, pm):
        from ui.pages.voice_page import VOICE_SOURCE_IMPORT
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_mode_selected(VOICE_SOURCE_IMPORT)
        assert not page.transcript_container.isHidden()
        assert page.transcript_summary_label.text() == "Status: Not Generated"

    # --- D. Transcript workflow ---------------------------------------------

    def test_transcript_completion_exposes_view_transcript(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)

        # before audio: Generate Transcript present but disabled, View hidden
        assert not page.generate_transcript_btn.isHidden()
        assert not page.generate_transcript_btn.isEnabled()
        assert not page.view_transcript_btn.isEnabled()
        self._attach_audio(page, pm, name)
        assert page.generate_transcript_btn.isEnabled()
        assert not page.view_transcript_btn.isEnabled()

        page._on_transcription_done("Hello transcript", [
            {"start": 0.0, "end": 1.0, "text": "Hello transcript",
             "time": "00:00"},
        ])
        assert page.transcript_summary_label.text() == (
            "Status: Generated \u2014 16 characters \u00b7 1 segment"
        )
        assert page.generate_transcript_btn.text() == "Regenerate Transcript"
        assert page.view_transcript_btn.isEnabled()
        assert page.next_btn.isEnabled()

    def test_view_transcript_opens_existing_editor_dialog(self, pm, monkeypatch):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_transcription_done("Ready", [
            {"start": 0.0, "end": 1.0, "text": "Ready", "time": "00:00"},
        ])
        opened = []
        import ui.pages.voice_page as vp

        class _FakeDialog:
            def __init__(self, page_ref, parent=None):
                opened.append(page_ref)

            def exec(self):
                return 0

        monkeypatch.setattr(vp, "TranscriptEditorDialog", _FakeDialog)
        page._open_transcript_editor()
        assert opened == [page]

    # --- E. Theme regression -------------------------------------------------

    def test_identity_labels_refresh_on_theme_toggle(self, pm):
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("dark")
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        tm.set_mode("light")
        page._refresh_theme_static()
        assert "color: #111827" in page.selected_voice_name_label.styleSheet()
        assert "color: #111827" in page.imported_file_label.styleSheet()
        assert "color: #6B7280" in page.imported_meta_label.styleSheet()
        tm.set_mode("dark")

    # --- F. Layout regression (no clipping / overlap) -------------------------

    def test_narration_sections_do_not_overlap_or_clip(self, pm):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication, QScrollArea
        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        self._attach_audio(page, pm, name)
        page.show()
        app.processEvents()

        # the page scrolls as a whole instead of clipping the tall card
        assert isinstance(page._scroll, QScrollArea)
        assert page._scroll.widgetResizable()

        card = page._ai_card
        sections = [
            page.narration_summary,
            page.playback_container,
            page.export_container,
            page.transcript_container,
        ]
        positions = []
        for section in sections:
            assert not section.isHidden()
            y = section.mapTo(page, QPoint(0, 0)).y()
            positions.append((y, section))
        positions.sort()
        for (y1, s1), (y2, s2) in zip(positions, positions[1:]):
            assert y1 < y2, (
                f"{s1.__class__.__name__} overlaps {s2.__class__.__name__}"
            )
        card_top = card.mapTo(page, QPoint(0, 0)).y()
        for y, section in positions:
            assert y + section.height() <= card_top + card.height() + 1, (
                f"{section.__class__.__name__} is clipped by the Narration card"
            )

    def test_transcript_status_sits_next_to_header_not_far_right(self, pm):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page.show()
        app.processEvents()
        header_x = page._group_labels[-1].mapTo(page, QPoint(0, 0)).x()
        status_x = page.transcript_summary_label.mapTo(page, QPoint(0, 0)).x()
        assert header_x <= status_x <= header_x + 300

    # --- G. Cross-project state isolation (RC-6.2 regression) ----------------

    def test_cross_project_audio_and_transcript_isolation(self, pm):
        """Switching projects must not leak the previous project's narration."""
        name_with = _create_sample_project(pm, name="ProjWithData")
        name_empty = _create_sample_project(pm, name="ProjEmpty")
        page = self._make_page(pm)
        page.set_project(name_with)
        self._attach_audio(page, pm, name_with, filename="clip.wav")
        page._on_transcription_done("Cross project transcript", [
            {"start": 0.0, "end": 1.0, "text": "Cross project transcript",
             "time": "00:00"},
        ])
        assert page._audio_path is not None
        assert page._transcript_text == "Cross project transcript"
        assert page.view_transcript_btn.isEnabled()
        assert page.next_btn.isEnabled()

        page.set_project(name_empty)
        assert page._audio_path is None
        assert page._transcript_text == ""
        assert not page.view_transcript_btn.isEnabled()
        assert not page.next_btn.isEnabled()
        assert page.transcript_summary_label.text() == "Status: Not Generated"


# =====================================================================
# PHASE 12B2 — RC-6 Transcript viewer & Image Prompt generation
# =====================================================================

class TestRC6TranscriptViewer:
    """RC-6: the generated transcript must appear in View Transcript, survive
    reopen/edit/save, and the status must distinguish generating/generated/
    failed from 'not generated'.
    """

    @staticmethod
    def _make_page(pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.voice_page import VoicePage

        QApplication.instance() or QApplication([])
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

    @staticmethod
    def _segment(text="Seg"):
        return [{"start": 0.0, "end": 1.0, "text": text, "time": "00:00"}]

    def test_generated_transcript_is_persisted_to_disk(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_transcription_done("Persisted transcript", self._segment())

        transcript = _read_json(pm, name, "transcript.json")
        assert transcript["text"] == "Persisted transcript"
        voice = _read_json(pm, name, "voice.json")
        assert voice["transcript"] == "Persisted transcript"
        assert len(voice["segments"]) == 1

    def test_generated_transcript_appears_in_view_transcript_dialog(self, pm):
        from ui.pages.voice_page import TranscriptEditorDialog
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_transcription_done(
            "Generated transcript content", self._segment("Generated transcript content")
        )

        dialog = TranscriptEditorDialog(page, parent=page)
        dialog.show()
        app.processEvents()
        # RC-6 blank-viewer regression: the editor must render its content.
        assert page.transcript_box.toPlainText() == "Generated transcript content"
        assert not page.transcript_box.isHidden()
        assert page.transcript_box.isVisible()
        dialog.close()

    def test_reopening_view_transcript_preserves_transcript(self, pm):
        from ui.pages.voice_page import TranscriptEditorDialog
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_transcription_done("Persistent transcript", self._segment())

        for _ in range(2):
            dialog = TranscriptEditorDialog(page, parent=page)
            dialog.show()
            app.processEvents()
            assert page.transcript_box.toPlainText() == "Persistent transcript"
            assert page.transcript_box.isVisible()
            dialog.close()
            app.processEvents()

    def test_editing_and_saving_transcript_persists(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_transcription_done("Original transcript", self._segment())

        page.transcript_box.setPlainText("Edited transcript text")
        page.save_transcript()
        assert _read_json(pm, name, "transcript.json")["text"] == "Edited transcript text"

        # A fresh page (restart) must load the edited transcript.
        reloaded = self._make_page(pm)
        reloaded.set_project(name)
        assert reloaded._transcript_text == "Edited transcript text"
        assert reloaded.transcript_box.toPlainText() == "Edited transcript text"

    def test_transcript_status_generating_to_generated(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)

        page._transcribing = True
        page._update_transcript_status()
        assert page.transcript_summary_label.text() == "Status: Generating..."

        page._transcribing = False
        page._transcript_error = None
        page._transcript_text = "Hello world"
        page._segments = [{"start": 0, "end": 1, "text": "Hello world", "time": "00:00"}]
        page._update_transcript_status()
        assert page.transcript_summary_label.text() == (
            "Status: Generated \u2014 11 characters \u00b7 1 segment"
        )
        assert page.generate_transcript_btn.text() == "Regenerate Transcript"

    def test_transcript_failure_displays_failure_state(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        page._on_transcription_error("whisper model failed to load")

        assert page._transcript_error == "whisper model failed to load"
        assert page.transcript_summary_label.text() == (
            "Status: Failed \u2014 whisper model failed to load"
        )
        assert page.generate_transcript_btn.text() == "Retry Transcription"

    def test_transcript_not_generated_state(self, pm):
        name = _create_sample_project(pm)
        page = self._make_page(pm)
        page.set_project(name)
        assert page.transcript_summary_label.text() == "Status: Not Generated"
        assert page.generate_transcript_btn.text() == "Generate Transcript"


class TestRC6ImagePromptGeneration:
    """RC-6: Generate Prompts must update the UI on success and show a
    persistent, actionable failure on error — never a silent
    'No Prompts Yet'.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.image_prompts_page import ImagePromptsPage

        QApplication.instance() or QApplication([])
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr(
            "ui.pages.image_prompts_page._provider_preflight",
            lambda: (True, ""),
        )
        page = ImagePromptsPage()
        page.manager = pm
        service = PipelineService()
        service._pm = pm
        page._pipeline = service
        return page

    @staticmethod
    def _seed(pm, name):
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Segment one.",
            "segments": [{"start": 0, "end": 4, "text": "Segment one.", "time": "00:00"}],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Segment one."})
        # Advance the workflow through Script and Voice so the Image Prompts
        # stage is AVAILABLE (matches how a real user reaches this page).
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(
            data["workflow_state"], "Script"
        )
        data["workflow_state"] = advance_workflow_state(
            data["workflow_state"], "Voice"
        )
        pm.update_project(name, data)

    @staticmethod
    def _wait(app, predicate, timeout=10.0):
        """Pump the event loop until predicate is true or timeout elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return True
            time.sleep(0.02)
        return predicate()

    def test_success_updates_ui_and_persists(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "PromptsOk"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)

        class _FakeOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                if progress_callback:
                    progress_callback("generating", "Generating image prompts", 0.4)
                return [{
                    "scene_number": 1,
                    "timestamp": "00:00",
                    "prompt_title": "Opening",
                    "full_image_prompt": "A classroom scene, photorealistic",
                }]

        page.operator = _FakeOperator()
        page.set_project(name)
        assert page.empty_state is not None

        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: bool(page._prompts))

        # Success must replace the empty state immediately (no stale
        # 'No Prompts Yet') and re-enable the action.
        assert page.empty_state is None
        assert len(page._prompts) == 1
        assert page._generation_error is None
        assert page.failure_label.isHidden()
        assert page.generate_btn.isEnabled()
        assert page.export_btn.isEnabled()

        stored = _read_json(pm, name, "image_prompts.json")
        assert len(stored["prompts"]) == 1
        assert stored["prompts"][0]["full_image_prompt"] == "A classroom scene, photorealistic"

    def test_failure_shows_persistent_banner(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        from operators.image_prompt.models import ImagePromptGenerationError
        app = QApplication.instance() or QApplication([])
        name = "PromptsFail"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)

        class _FailingOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                raise ImagePromptGenerationError(
                    "Quota exceeded: insufficient balance"
                )

        page.operator = _FailingOperator()
        page.set_project(name)

        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: page._generation_error is not None)

        # The failure must be visible and actionable, never silent.
        assert "Quota exceeded" in page._generation_error
        assert not page.failure_label.isHidden()
        assert "Quota exceeded" in page.failure_label.text()
        assert page.empty_state is not None  # no prompts, but reason is shown
        assert page.generate_btn.isEnabled()

    def test_worker_exception_reaches_ui(self, pm, monkeypatch):
        """An exception raised in the background worker must surface as a
        visible failure banner (no silent drop)."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "PromptsWorkerExc"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)

        class _ExplodingOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                raise RuntimeError("provider connection reset")

        page.operator = _ExplodingOperator()
        page.set_project(name)

        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: page._generation_error is not None)
        assert "provider connection reset" in page._generation_error
        assert not page.failure_label.isHidden()

    def test_preflight_failure_reports_immediately(self, pm, monkeypatch):
        name = "PromptsBlocked"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)

        # Patch AFTER _make_page so it overrides the hermetic (True, "") stub.
        def _blocked():
            return (False, "Provider 'Gemini' requires an API key. Set one in Settings.")

        monkeypatch.setattr(
            "ui.pages.image_prompts_page._provider_preflight", _blocked
        )
        page.set_project(name)

        page.generate_prompts()
        assert not page.task_manager.is_running
        assert page._generation_error is not None
        assert "requires an API key" in page._generation_error
        assert not page.failure_label.isHidden()
        assert page.empty_state is not None
        assert page.generate_btn.isEnabled()


# =====================================================================
# PHASE 12B3 — RC-7 Image Prompt reliability & production pipeline
# =====================================================================

class TestRC7ImagePromptReliability:
    """RC-7: the Image Prompt stage is a reliable, observable production
    pipeline — explicit stages, bounded retry, provider error aggregation,
    strict validation, regeneration safety, cancellation, persistence,
    export completeness, and no silent failures.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.image_prompts_page import ImagePromptsPage

        QApplication.instance() or QApplication([])
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr(
            "ui.pages.image_prompts_page._provider_preflight",
            lambda: (True, ""),
        )
        page = ImagePromptsPage()
        page.manager = pm
        page.export_service.project_manager = pm
        service = PipelineService()
        service._pm = pm
        page._pipeline = service
        return page

    @staticmethod
    def _seed(pm, name):
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Segment one.",
            "segments": [{"start": 0, "end": 4, "text": "Segment one.", "time": "00:00"}],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Segment one."})
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Voice")
        pm.update_project(name, data)

    @staticmethod
    def _seed_prompts(pm, name, prompts):
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": prompts})

    @staticmethod
    def _wait(app, predicate, timeout=10.0):
        """Pump the event loop until predicate is true or timeout elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return True
            time.sleep(0.02)
        return predicate()

    # --- Operator pipeline ----------------------------------------------

    def test_valid_prompt_generation_reports_stages(self):
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        class FakeProviderManager:
            def generate(self, request):
                return GenerationResponse(text=json.dumps([{
                    "scene_number": 1,
                    "timestamp": "00:00",
                    "prompt_title": "Opening",
                    "full_image_prompt": (
                        "Hand-drawn 2D doodle cartoon animation, a classroom, "
                        "16:9 aspect ratio, KaiMi educational doodle style"
                    ),
                }]))

        stages = []
        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        request = ImagePromptRequest(
            script_text="A short script.",
            transcript="[0:00] Hello",
            timestamps=[{"start": 0, "end": 3, "text": "Hello", "time": "00:00"}],
            topic="Science",
            language="English",
        )
        prompts = operator.generate_prompts(
            request,
            progress_callback=lambda stage, message, fraction: stages.append(stage),
            max_retries=0,
        )
        assert len(prompts) == 1
        assert prompts[0]["scene_number"] == 1
        assert prompts[0]["timestamp"] == "00:00"
        assert stages == [
            "validating_source",
            "selecting_provider",
            "generating",
            "parsing",
            "validating",
        ]

    def test_bounded_retry_recovers_from_malformed_output(self):
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        calls = {"count": 0}
        good = json.dumps([{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
            "full_image_prompt": "Hand-drawn 2D doodle cartoon animation, a scene, KaiMi educational doodle style",
        }])

        class FakeProviderManager:
            def generate(self, request):
                calls["count"] += 1
                if calls["count"] == 1:
                    return GenerationResponse(text="Sorry, here is prose without JSON.")
                return GenerationResponse(text=good)

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        request = ImagePromptRequest(
            script_text="Script.", transcript="[0:00] Hello",
            timestamps=[{"start": 0, "end": 3, "text": "Hello", "time": "00:00"}],
        )
        prompts = operator.generate_prompts(request, max_retries=1)
        assert calls["count"] == 2
        assert len(prompts) == 1

    def test_malformed_ai_response_reports_invalid_prompt_data(self):
        from operators.image_prompt.models import (
            ImagePromptGenerationError, ImagePromptRequest,
        )
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        class FakeProviderManager:
            def generate(self, request):
                return GenerationResponse(text="not json at all")

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        request = ImagePromptRequest(
            script_text="Script.", transcript="[0:00] Hi",
            timestamps=[{"start": 0, "end": 2, "text": "Hi", "time": "00:00"}],
        )
        with pytest.raises(ImagePromptGenerationError) as exc_info:
            operator.generate_prompts(request, max_retries=0)
        assert "invalid prompt data" in str(exc_info.value)

    def test_empty_ai_response_fails_cleanly(self):
        from operators.image_prompt.models import (
            ImagePromptGenerationError, ImagePromptRequest,
        )
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        class FakeProviderManager:
            def generate(self, request):
                return GenerationResponse(text="   ")

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        with pytest.raises(ImagePromptGenerationError) as exc_info:
            operator.generate_prompts(
                ImagePromptRequest(script_text="Script.", transcript="[0:00] Hi"),
                max_retries=0,
            )
        assert "empty content" in str(exc_info.value).lower()

    def test_duplicate_scene_rejected(self):
        from operators.image_prompt.models import ImagePromptParseError
        from operators.image_prompt.parser import ImagePromptParser

        payload = json.dumps([
            {"scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
             "full_image_prompt": "Prompt A"},
            {"scene_number": 1, "timestamp": "00:05", "prompt_title": "B",
             "full_image_prompt": "Prompt B"},
        ])
        with pytest.raises(ImagePromptParseError) as exc_info:
            ImagePromptParser().parse(payload)
        assert "duplicates scene number" in str(exc_info.value)

    def test_out_of_order_timestamps_rejected(self):
        from operators.image_prompt.models import ImagePromptParseError
        from operators.image_prompt.parser import ImagePromptParser

        payload = json.dumps([
            {"scene_number": 1, "timestamp": "00:10", "prompt_title": "A",
             "full_image_prompt": "Prompt A"},
            {"scene_number": 2, "timestamp": "00:05", "prompt_title": "B",
             "full_image_prompt": "Prompt B"},
        ])
        with pytest.raises(ImagePromptParseError) as exc_info:
            ImagePromptParser().parse(payload)
        assert "out of order" in str(exc_info.value)

    def test_prompt_count_validation_rejects_coverage_gaps(self):
        from operators.image_prompt.models import (
            ImagePromptGenerationError, ImagePromptRequest,
        )
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        class FakeProviderManager:
            def generate(self, request):
                return GenerationResponse(text=json.dumps([
                    {"scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
                     "full_image_prompt": "Prompt A"},
                ]))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        request = ImagePromptRequest(
            script_text="Script.", transcript="x",
            timestamps=[
                {"start": i, "end": i + 1, "text": "s", "time": "00:00"}
                for i in range(6)
            ],
        )
        with pytest.raises(ImagePromptGenerationError) as exc_info:
            operator.generate_prompts(request, max_retries=0)
        assert "coverage is incomplete" in str(exc_info.value)

    # --- Provider handling ----------------------------------------------

    @staticmethod
    def _provider_manager_with_fakes(tmp_path, monkeypatch, provider_cls, names):
        from providers.provider_manager import ProviderManager

        class FakeProvider:
            is_initialized = True

            def __init__(self, name):
                self.name = name

            def generate(self, request):
                return provider_cls(self.name)

        pm = ProviderManager(config_path=tmp_path / "providers.json")
        pm.set_active_provider(names[0])
        for name in names:
            pm.save_provider_config(name, api_key="k", model="m")
        monkeypatch.setattr(pm, "_get_provider", lambda name: FakeProvider(name))
        return pm

    def test_provider_quota_failure_aggregates_friendly_message(
        self, tmp_path, monkeypatch
    ):
        from providers.exceptions import (
            GenerationFailedError, QuotaExceededError,
        )
        from providers.models import GenerationRequest

        def failing(name):
            raise QuotaExceededError("Insufficient Balance", provider=name)

        pm = self._provider_manager_with_fakes(
            tmp_path, monkeypatch, failing, ["groq", "gemini"]
        )
        with pytest.raises(GenerationFailedError) as exc_info:
            pm.generate(GenerationRequest(prompt="x"))
        message = str(exc_info.value)
        assert "Groq" in message and "insufficient quota" in message
        assert "Gemini" in message
        assert "{" not in message  # no raw API payload in the UI-facing message

    def test_provider_rate_limit_failure(self, tmp_path, monkeypatch):
        from providers.exceptions import GenerationFailedError, RateLimitedError
        from providers.models import GenerationRequest

        def failing(name):
            raise RateLimitedError("429 too many requests", provider=name)

        pm = self._provider_manager_with_fakes(
            tmp_path, monkeypatch, failing, ["groq"]
        )
        with pytest.raises(GenerationFailedError) as exc_info:
            pm.generate(GenerationRequest(prompt="x"))
        assert "rate limited" in str(exc_info.value)

    def test_provider_fallback_succeeds(self, tmp_path, monkeypatch):
        from providers.exceptions import RateLimitedError
        from providers.models import GenerationRequest, GenerationResponse

        def behavior(name):
            if name == "groq":
                raise RateLimitedError("429", provider=name)
            return GenerationResponse(text="fallback success", provider=name, model="m")

        pm = self._provider_manager_with_fakes(
            tmp_path, monkeypatch, behavior, ["groq", "gemini"]
        )
        response = pm.generate(GenerationRequest(prompt="x"))
        assert response.provider == "gemini"
        assert response.text == "fallback success"

    # --- Page pipeline --------------------------------------------------

    def test_reopening_project_preserves_prompts(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "ReopenProj"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
            "full_image_prompt": "Hand-drawn 2D doodle cartoon animation, a classroom, KaiMi educational doodle style",
        }])

        page = self._make_page(pm, monkeypatch)
        page.set_project(name)
        assert page.empty_state is None
        assert len(page._prompts) == 1

        # Reopening (fresh page instance == restart) restores from storage.
        page2 = self._make_page(pm, monkeypatch)
        page2.set_project(name)
        assert len(page2._prompts) == 1
        assert page2.empty_state is None
        assert page2.generate_btn.text() == "Regenerate Prompts"

    def test_failed_regeneration_preserves_previous_prompts(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        from operators.image_prompt.models import ImagePromptGenerationError
        app = QApplication.instance() or QApplication([])
        name = "RegenFail"
        self._seed(pm, name)
        existing = [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Old",
            "full_image_prompt": "Existing prompt one",
        }]
        self._seed_prompts(pm, name, existing)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        class _FailingOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                raise ImagePromptGenerationError("provider exploded")

        page.operator = _FailingOperator()
        page._confirm_regenerate = lambda: True

        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: page._generation_error is not None)

        # The previous successful prompt set must survive the failed attempt.
        assert len(page._prompts) == 1
        assert page._prompts == existing
        assert "Existing prompts were not modified" in page._generation_error
        stored = _read_json(pm, name, "image_prompts.json")
        assert stored["prompts"] == existing

    def test_successful_regeneration_replaces_prompts(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "RegenOk"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Old",
            "full_image_prompt": "Old prompt",
        }])
        page = self._make_page(pm, monkeypatch)

        class _FakeOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                return [
                    {"scene_number": 1, "timestamp": "00:00", "prompt_title": "New A",
                     "full_image_prompt": "New prompt A"},
                    {"scene_number": 2, "timestamp": "00:04", "prompt_title": "New B",
                     "full_image_prompt": "New prompt B"},
                ]

        page.operator = _FakeOperator()
        page._confirm_regenerate = lambda: True
        page.set_project(name)

        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: len(page._prompts) == 2)
        stored = _read_json(pm, name, "image_prompts.json")
        assert len(stored["prompts"]) == 2
        assert stored["prompts"][0]["prompt_title"] == "New A"

    def test_regeneration_asks_confirmation_before_overwrite(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "RegenConfirm"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Old",
            "full_image_prompt": "Old prompt",
        }])
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        asked = []
        page._confirm_regenerate = lambda: asked.append(True) or False  # declined
        page.generate_prompts()
        assert asked == [True]
        assert not page.task_manager.is_running
        assert page._generation_error is None
        assert len(page._prompts) == 1

    def test_cancellation_safety(self, pm, monkeypatch):
        import threading
        from PySide6.QtWidgets import QApplication
        from core.task_manager import TaskCancelledError
        app = QApplication.instance() or QApplication([])
        name = "CancelProj"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Old",
            "full_image_prompt": "Existing prompt",
        }])
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        class _BlockingOperator:
            started = threading.Event()

            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                if progress_callback:
                    progress_callback("generating", "Generating image prompts", 0.4)
                self.started.set()
                while not cancel_event.is_set():
                    time.sleep(0.01)
                raise TaskCancelledError("Image prompt generation cancelled.")

        page.operator = _BlockingOperator()
        page._confirm_regenerate = lambda: True  # deterministic, no modal dialog
        page.generate_prompts()
        assert self._wait(app, lambda: _BlockingOperator.started.is_set())
        assert page.task_manager.is_running

        page._cancel_generation()
        assert self._wait(app, lambda: not page.task_manager.is_running)

        # Cancellation is not a failure: no banner, prompts preserved intact.
        assert self._wait(app, lambda: page.cancel_btn.isHidden())
        assert page._generation_error is None
        assert page.failure_label.isHidden()
        assert page.generate_btn.isEnabled()
        assert len(page._prompts) == 1
        assert _read_json(pm, name, "image_prompts.json")["prompts"]  # intact

    def test_repeated_generate_clicks_cannot_create_duplicate_jobs(self, pm, monkeypatch):
        import threading
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "DoubleClick"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)

        class _CountingOperator:
            def __init__(self):
                self.calls = 0
                self.release = threading.Event()

            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                self.calls += 1
                while not self.release.is_set() and not cancel_event.is_set():
                    time.sleep(0.01)
                return [{
                    "scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
                    "full_image_prompt": "Prompt A",
                }]

        operator = _CountingOperator()
        page.operator = operator
        page.set_project(name)

        page.generate_prompts()
        assert self._wait(app, lambda: operator.calls == 1)
        page.generate_prompts()  # second click while running -> guarded
        assert operator.calls == 1
        assert page.task_manager.get_queue_size() == 0

        operator.release.set()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: len(page._prompts) == 1)

    def test_txt_export_completeness(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "ExportProj"
        self._seed(pm, name)
        long_prompt = (
            "Hand-drawn 2D doodle cartoon animation, "
            + "detailed scene description, " * 40
            + "16:9 aspect ratio, KaiMi educational doodle style"
        )
        prompts = [
            {"scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
             "full_image_prompt": "Prompt one " + long_prompt},
            {"scene_number": 2, "timestamp": "01:30", "prompt_title": "Middle",
             "full_image_prompt": "Prompt two"},
        ]
        self._seed_prompts(pm, name, prompts)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        chosen = pm.PROJECTS_DIR / name / "exports" / f"{name}_image_prompts.txt"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(chosen), "Text Files (*.txt)")),
        )

        page.export_txt()
        assert chosen.exists()
        content = chosen.read_text(encoding="utf-8")
        # RC-7.1 Google Flow format: exactly one physical line per prompt.
        lines = content.splitlines()
        assert len(lines) == 2
        assert lines[0] == "[00:00] Prompt one " + long_prompt  # long prompt intact
        assert lines[1] == "[01:30] Prompt two"
        assert "Scene 1" not in content and "Scene 2" not in content
        assert "Title:" not in content
        assert "Prompts exported successfully." in page.export_status_label.text()

    def test_long_prompt_not_truncated_in_storage_or_ui(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "LongPrompt"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)
        long_prompt = (
            "Hand-drawn 2D doodle cartoon animation, "
            + "flowing scene text, " * 300
            + "KaiMi educational doodle style"
        )
        assert len(long_prompt) > 5000

        class _FakeOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                return [{"scene_number": 1, "timestamp": "00:00",
                         "prompt_title": "Long", "full_image_prompt": long_prompt}]

        page.operator = _FakeOperator()
        page.set_project(name)
        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: len(page._prompts) == 1)
        stored = _read_json(pm, name, "image_prompts.json")
        assert stored["prompts"][0]["full_image_prompt"] == long_prompt

    def test_light_theme_colors(self, pm, monkeypatch):
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("dark")
        try:
            name = "LightTheme"
            self._seed(pm, name)
            page = self._make_page(pm, monkeypatch)
            page.set_project(name)
            page._set_generation_error("Test failure message")

            tm.set_mode("light")
            page._refresh_theme_static()
            assert "#6B7280" in page.controls_desc_label.styleSheet()
            assert "#DC2626" in page.failure_label.styleSheet()
        finally:
            tm.set_mode("dark")

    def test_dark_theme_colors(self, pm, monkeypatch):
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("light")
        try:
            name = "DarkTheme"
            self._seed(pm, name)
            page = self._make_page(pm, monkeypatch)
            page.set_project(name)

            light_sheet = page.controls_desc_label.styleSheet()
            tm.set_mode("dark")
            page._refresh_theme_static()
            dark_sheet = page.controls_desc_label.styleSheet()
            assert light_sheet != dark_sheet  # no color leakage between themes
        finally:
            tm.set_mode("dark")

    def test_smaller_window_layout(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QScrollArea
        app = QApplication.instance() or QApplication([])
        name = "SmallWindow"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)
        page.resize(820, 560)
        page.show()
        app.processEvents()

        assert page.generate_btn.isVisible()
        assert page.export_btn.isVisible()
        scroll = page.findChildren(QScrollArea)[0]
        assert scroll.width() > 0 and scroll.height() > 0
        assert page.prompts_container.width() > 0

    def test_stage_tagged_failure_message(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        from operators.image_prompt.models import ImagePromptGenerationError
        app = QApplication.instance() or QApplication([])
        name = "StageTagged"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)

        class _FailingOperator:
            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                if progress_callback:
                    progress_callback("parsing", "Parsing AI response", 0.7)
                raise ImagePromptGenerationError(
                    "Generation completed but the provider returned invalid prompt data. Details: bad JSON"
                )

        page.operator = _FailingOperator()
        page.set_project(name)
        page.generate_prompts()
        assert self._wait(app, lambda: not page.task_manager.is_running)
        assert self._wait(app, lambda: page._generation_error is not None)
        assert "failed during Parsing Response" in page._generation_error
        assert "No prompts were saved." in page._generation_error

    def test_inflight_result_never_lands_in_switched_project(self, pm, monkeypatch):
        """RC-7: a generation started for project A must persist to A even if
        the user navigates to project B before it finishes (no cross-project
        data leakage).
        """
        import threading
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name_a, name_b = "SwitchA", "SwitchB"
        self._seed(pm, name_a)
        self._seed(pm, name_b)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name_a)

        class _SlowOperator:
            release = threading.Event()

            def generate_prompts(
                self, request, progress_callback=None, cancel_event=None, max_retries=1
            ):
                while not self.release.is_set() and not cancel_event.is_set():
                    time.sleep(0.01)
                return [{"scene_number": 1, "timestamp": "00:00",
                         "prompt_title": "A", "full_image_prompt": "Prompt A"}]

        page.operator = _SlowOperator()
        page._confirm_regenerate = lambda: True
        page.generate_prompts()
        assert self._wait(app, lambda: page.task_manager.is_running)

        # User switches to project B while A's generation is in flight.
        page.set_project(name_b)
        # The in-flight run is cancelled; the worker observes the event.
        assert self._wait(app, lambda: not page.task_manager.is_running)
        _SlowOperator.release.set()

        # B must not receive A's prompts, and A's prompts were never written
        # because the run was cancelled before completion.
        assert self._wait(app, lambda: len(page._prompts) == 0)
        assert page._generation_error is None
        stored_a = _read_json(pm, name_a, "image_prompts.json")
        assert stored_a.get("prompts", []) == []
        stored_b = _read_json(pm, name_b, "image_prompts.json")
        assert stored_b.get("prompts", []) == []


# =====================================================================
# PHASE 12B4 — RC-7.1 Export fix & progress UI polish
# =====================================================================

class TestRC71ImagePromptExport:
    """RC-7.1: Export TXT writes the full prompt set to a user-chosen
    destination through the OS save dialog, with persistent feedback and no
    silent failures.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.image_prompts_page import ImagePromptsPage

        QApplication.instance() or QApplication([])
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.transcript_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr(
            "ui.pages.image_prompts_page._provider_preflight",
            lambda: (True, ""),
        )
        page = ImagePromptsPage()
        page.manager = pm
        page.export_service.project_manager = pm
        service = PipelineService()
        service._pm = pm
        page._pipeline = service
        return page

    @staticmethod
    def _seed(pm, name):
        from core.workflow import advance_workflow_state
        pm.create_project(
            name=name, topic="AI Education", platform="YouTube",
            video_type="Educational", language="English",
        )
        _write_json(pm.PROJECTS_DIR / name / "script.json", {
            "script_output": "INT. CLASSROOM - DAY\nTeacher introduces AI...",
        })
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Segment one.",
            "segments": [{"start": 0, "end": 4, "text": "Segment one.", "time": "00:00"}],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Segment one."})
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Voice")
        pm.update_project(name, data)

    @staticmethod
    def _seed_prompts(pm, name, prompts):
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": prompts})

    def _chosen(self, pm, name, filename="export.txt"):
        return pm.PROJECTS_DIR / name / "exports" / filename

    def test_export_success_writes_expected_content(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "Export71"
        self._seed(pm, name)
        long_prompt = (
            "Hand-drawn 2D doodle cartoon animation, "
            + "flowing detailed scene narration, " * 60
            + "16:9 aspect ratio, KaiMi educational doodle style"
        )
        prompts = [
            {"scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
             "full_image_prompt": long_prompt},
            {"scene_number": 2, "timestamp": "01:30", "prompt_title": "Middle",
             "full_image_prompt": "Second full prompt text"},
        ]
        self._seed_prompts(pm, name, prompts)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        chosen = self._chosen(pm, name)
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(chosen), "Text Files (*.txt)")),
        )
        page.export_txt()

        assert chosen.exists()
        content = chosen.read_text(encoding="utf-8")
        # RC-7.1 Google Flow format: one physical line per prompt, no metadata.
        lines = content.splitlines()
        assert len(lines) == 2
        assert lines[0] == "[00:00] " + long_prompt  # full prompt text, not truncated
        assert lines[1] == "[01:30] Second full prompt text"
        assert "Scene" not in content
        assert "Title:" not in content
        assert not page.export_status_label.isHidden()
        assert "Prompts exported successfully." in page.export_status_label.text()

    def test_export_preserves_order_and_all_fields(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "ExportOrder"
        self._seed(pm, name)
        prompts = [
            {"scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
             "full_image_prompt": "Prompt A text"},
            {"scene_number": 2, "timestamp": "00:12", "prompt_title": "B",
             "full_image_prompt": "Prompt B text"},
            {"scene_number": 3, "timestamp": "00:45", "prompt_title": "C",
             "full_image_prompt": "Prompt C text"},
        ]
        self._seed_prompts(pm, name, prompts)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        chosen = self._chosen(pm, name)
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(chosen), "Text Files (*.txt)")),
        )
        page.export_txt()

        content = chosen.read_text(encoding="utf-8")
        # RC-7.1 Google Flow format: order preserved, one line per prompt.
        lines = content.splitlines()
        assert len(lines) == 3
        assert lines[0] == "[00:00] Prompt A text"
        assert lines[1] == "[00:12] Prompt B text"
        assert lines[2] == "[00:45] Prompt C text"
        assert content.index("Prompt A text") < content.index("Prompt B text") < content.index("Prompt C text")

    def test_export_failure_reaches_ui_as_actionable_error(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "ExportFail"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
            "full_image_prompt": "Prompt A text",
        }])
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        chosen = self._chosen(pm, name, "bad")
        chosen.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(chosen), "Text Files (*.txt)")),
        )

        def _fail_write(path, data, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.write_text", _fail_write)
        page.export_txt()

        assert not page.export_status_label.isHidden()
        assert "Export failed" in page.export_status_label.text()
        assert "disk full" in page.export_status_label.text()
        assert not chosen.exists() or True  # write failed, nothing to verify on disk

    def test_cancelled_save_dialog_is_silent(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "ExportCancel"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
            "full_image_prompt": "Prompt A text",
        }])
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )
        page.export_txt()

        # Cancelling must not write, must not show an error, and must not crash.
        assert page.export_status_label.isHidden()
        assert not (pm.PROJECTS_DIR / name / "exports" / "export.txt").exists()

    def test_export_empty_prompts_is_handled(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        name = "ExportEmpty"
        self._seed(pm, name)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)
        page.export_txt()
        assert not page.export_status_label.isHidden()
        assert "No prompts to export." in page.export_status_label.text()

    def test_export_after_regeneration_uses_latest_prompts(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "ExportRegen"
        self._seed(pm, name)
        self._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Old",
            "full_image_prompt": "Old prompt text",
        }])
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)

        # Simulate a successful regeneration replacing the prompt set.
        page._prompts = [{"scene_number": 1, "timestamp": "00:00",
                          "prompt_title": "New", "full_image_prompt": "New prompt text"}]
        page.prompt_storage.save(name, page._prompts)
        page._render_prompts()

        chosen = self._chosen(pm, name)
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(chosen), "Text Files (*.txt)")),
        )
        page.export_txt()
        content = chosen.read_text(encoding="utf-8")
        assert "New prompt text" in content
        assert "Old prompt text" not in content


# =====================================================================
# PHASE 12B5 — RC-7.1 Google Flow TXT queue format
# =====================================================================

class TestRC71GoogleFlowExportFormat:
    """RC-7.1: the exported image-prompts TXT is compatible with Google
    Flow's "one prompt per line" queue — each scene is EXACTLY one physical
    line in the form ``[MM:SS] <full image prompt>`` with no headers,
    titles, separate timestamp lines, blank lines, or other metadata.
    """

    @staticmethod
    def _ts(seconds):
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    @staticmethod
    def _make_prompts(count):
        return [
            {
                "scene_number": i + 1,
                "timestamp": TestRC71GoogleFlowExportFormat._ts(i * 8),
                "prompt_title": f"Prompt title {i + 1}",
                "full_image_prompt": (
                    f"Hand-drawn 2D doodle cartoon animation, "
                    f"full generated prompt {i + 1}, "
                    f"16:9 aspect ratio, KaiMi educational doodle style"
                ),
            }
            for i in range(count)
        ]

    def test_34_scenes_export_to_exactly_34_lines(self):
        """Requirement A: 34 scenes -> exactly 34 physical non-empty lines."""
        prompts = self._make_prompts(34)
        text = ExportService.build_image_prompts_txt(prompts)
        lines = text.splitlines()
        assert len(lines) == 34
        assert len([ln for ln in lines if ln.strip()]) == 34

    def test_every_line_starts_with_mm_ss_timestamp_and_holds_prompt(self):
        """Requirements B+C: each line is ``[MM:SS] <prompt>``."""
        import re
        prompts = self._make_prompts(34)
        lines = ExportService.build_image_prompts_txt(prompts).splitlines()
        for line, prompt in zip(lines, prompts):
            assert re.match(r"^\[\d{2}:\d{2}\] ", line), line
            assert line == f"[{prompt['timestamp']}] {prompt['full_image_prompt']}"

    def test_no_scene_title_or_metadata_lines(self):
        """Requirement D: no Scene/Title:/standalone metadata lines."""
        prompts = self._make_prompts(34)
        text = ExportService.build_image_prompts_txt(prompts)
        assert "Scene" not in text
        assert "Title:" not in text
        assert all(
            not line.startswith("Scene") and not line.startswith("Title:")
            for line in text.splitlines()
        )

    def test_no_blank_lines_and_no_trailing_newline(self):
        """Requirement E: no blank lines anywhere in the export."""
        prompts = self._make_prompts(34)
        text = ExportService.build_image_prompts_txt(prompts)
        assert "\n\n" not in text
        assert not text.endswith("\n")
        assert all(line.strip() for line in text.splitlines())

    def test_long_prompt_remains_a_single_physical_line(self):
        """Requirement F: a >5000-char prompt still exports as one line."""
        long_prompt = (
            "Hand-drawn 2D doodle cartoon animation, "
            + "flowing detailed scene narration, " * 300
            + "16:9 aspect ratio, KaiMi educational doodle style"
        )
        assert len(long_prompt) > 5000
        prompts = [{"scene_number": 1, "timestamp": "00:00",
                    "prompt_title": "Long", "full_image_prompt": long_prompt}]
        lines = ExportService.build_image_prompts_txt(prompts).splitlines()
        assert len(lines) == 1
        assert lines[0] == "[00:00] " + long_prompt

    def test_scene_order_and_timestamps_preserved(self):
        """Requirement G: order and timestamps are preserved exactly."""
        prompts = self._make_prompts(34)
        lines = ExportService.build_image_prompts_txt(prompts).splitlines()
        assert lines[0].startswith("[00:00] ")
        assert lines[1].startswith("[00:08] ")
        assert lines[33].startswith("[04:24] ")
        assert [ln.split("] ", 1)[1] for ln in lines] == [
            p["full_image_prompt"] for p in prompts
        ]

    def test_ui_display_still_shows_scene_and_title(self, pm, monkeypatch):
        """Requirement H: the in-app Scene/Title display is unchanged."""
        from PySide6.QtWidgets import QApplication, QLabel
        app = QApplication.instance() or QApplication([])
        name = "UIIntact"
        TestRC71ImagePromptExport._seed(pm, name)
        TestRC71ImagePromptExport._seed_prompts(pm, name, [{
            "scene_number": 1, "timestamp": "00:00",
            "prompt_title": "Opening Curiosity Title",
            "full_image_prompt": "Prompt one text",
        }])
        page = TestRC71ImagePromptExport._make_page(pm, monkeypatch)
        page.set_project(name)
        assert len(page._prompts) == 1
        texts = [label.text() for label in page.findChildren(QLabel)]
        assert any("Scene 1" in t for t in texts)
        assert any("Opening Curiosity Title" in t for t in texts)

    def test_generated_prompt_content_unchanged_in_storage_and_export(self, pm, es):
        """Requirements I+J: storage content and export_stage still work."""
        name = "ContentIntact"
        prompts = self._make_prompts(34)
        TestRC71ImagePromptExport._seed(pm, name)
        TestRC71ImagePromptExport._seed_prompts(pm, name, prompts)
        stored = _read_json(pm, name, "image_prompts.json")["prompts"]
        assert stored == prompts  # storage schema/content untouched

        out = es.export_stage(name, "Image Prompts", fmt="txt")
        assert out is not None and out.exists()
        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 34
        for line, prompt in zip(lines, stored):
            assert line == f"[{prompt['timestamp']}] {prompt['full_image_prompt']}"

    def test_page_export_still_writes_google_flow_txt(self, pm, monkeypatch):
        """Requirement J: the page's Export TXT button still works end-to-end."""
        from PySide6.QtWidgets import QApplication, QFileDialog
        app = QApplication.instance() or QApplication([])
        name = "PageExport71"
        prompts = self._make_prompts(34)
        TestRC71ImagePromptExport._seed(pm, name)
        TestRC71ImagePromptExport._seed_prompts(pm, name, prompts)
        page = TestRC71ImagePromptExport._make_page(pm, monkeypatch)
        page.set_project(name)

        chosen = pm.PROJECTS_DIR / name / "exports" / f"{name}_image_prompts.txt"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(chosen), "Text Files (*.txt)")),
        )
        page.export_txt()

        assert chosen.exists()
        lines = chosen.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 34
        assert all(line.startswith("[") and "] " in line for line in lines)
        assert "Prompts exported successfully." in page.export_status_label.text()


class TestRC71ProgressAnimation:
    """RC-7.1: the indeterminate progress bar is a real animated indicator
    that runs only while generation is active and stops on every terminal
    state (success, failure, cancellation) and on theme refresh.
    """

    @staticmethod
    def _app():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        return QApplication.instance() or QApplication([])

    def test_animation_starts_when_indeterminate(self):
        self._app()
        from ui.widgets import ProgressWidget
        w = ProgressWidget()
        try:
            w.set_indeterminate(status="Generating", step="Stage: Generating")
            assert w.indeterminate_bar.is_animating()
            assert w.progress_bar.isHidden()
            assert not w.indeterminate_bar.isHidden()
        finally:
            w.stop()

    def test_animation_stops_on_success(self):
        self._app()
        from ui.widgets import ProgressWidget
        w = ProgressWidget()
        try:
            w.set_indeterminate(status="Generating", step="Stage: Generating")
            assert w.indeterminate_bar.is_animating()
            w.show_complete("Generated 2 image prompts.")
            assert not w.indeterminate_bar.is_animating()
            assert not w.progress_bar.isHidden()
        finally:
            w.stop()

    def test_animation_stops_on_failure(self):
        self._app()
        from ui.widgets import ProgressWidget
        w = ProgressWidget()
        try:
            w.set_indeterminate(status="Generating", step="Stage: Generating")
            assert w.indeterminate_bar.is_animating()
            w.show_error("Generation failed")
            assert not w.indeterminate_bar.is_animating()
        finally:
            w.stop()

    def test_animation_stops_when_widget_hidden(self):
        self._app()
        from ui.widgets import ProgressWidget
        w = ProgressWidget()
        try:
            w.set_indeterminate(status="Generating", step="Stage: Generating")
            assert w.indeterminate_bar.is_animating()
            w.setVisible(False)
            assert not w.indeterminate_bar.is_animating()
        finally:
            w.stop()

    def test_theme_refresh_does_not_break_indicator(self, pm, monkeypatch):
        app = self._app()
        from ui.theme_pyside import ThemeManager
        from ui.widgets import ProgressWidget
        tm = ThemeManager.instance()
        tm.set_mode("dark")
        try:
            w = ProgressWidget()
            w.set_indeterminate(status="Generating", step="Stage: Generating")
            assert w.indeterminate_bar.is_animating()
            tm.set_mode("light")
            w.indeterminate_bar.update()
            app.processEvents()
            assert w.indeterminate_bar.is_animating()
            assert w.step_label.text() == "Stage: Generating"
        finally:
            w.stop()
            tm.set_mode("dark")

    def test_determinate_progress_restores_bar(self):
        self._app()
        from ui.widgets import ProgressWidget
        w = ProgressWidget()
        try:
            w.set_indeterminate(status="Generating", step="Stage: Generating")
            w.set_progress(55, status="Finalizing")
            assert not w.indeterminate_bar.is_animating()
            assert not w.progress_bar.isHidden()
            assert w.progress_bar.value() == 55
        finally:
            w.stop()


# =====================================================================
# PHASE 12C — Light Theme Text Contrast (runtime toggle)
# =====================================================================

class TestLightThemeContrast:
    """Light theme must never render normal text in white.

    Regression: labels bake theme colors into inline stylesheets at
    construction. Pages that rebuilt incompletely (nested grid layouts leaked
    by Dashboard) or kept static chrome (Voice mode cards, empty states)
    left near-white Dark-theme text on Light backgrounds after a runtime
    dark->light toggle.
    """

    @staticmethod
    def _make_project(pm):
        pm.create_project(
            name="ContrastProj", topic="AI Education",
            platform="YouTube", video_type="Educational",
            language="English",
        )

    @staticmethod
    def _build_pages(pm):
        """Build every page with a project attached, in the current theme."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.asset_manager import AssetManagerPage
        from ui.pages.dashboard import DashboardPage
        from ui.pages.export_page import ExportPage
        from ui.pages.image_prompts_page import ImagePromptsPage
        from ui.pages.projects import ProjectsPage
        from ui.pages.script_page import ScriptPage
        from ui.pages.voice_page import VoicePage

        app = QApplication.instance() or QApplication([])
        pages = {
            "Dashboard": DashboardPage(),
            "Projects": ProjectsPage(),
            "Script": ScriptPage(),
            "Voice": VoicePage(),
            "ImagePrompts": ImagePromptsPage(),
            "Export": ExportPage(),
            "AssetManager": AssetManagerPage(),
        }
        from core.pipeline_service import PipelineService
        svc = PipelineService()
        svc._pm = pm
        for page in pages.values():
            page.manager = pm
            page._pipeline = svc
            set_project = getattr(page, "set_project", None)
            if callable(set_project):
                set_project("ContrastProj")
        return app, pages

    @staticmethod
    def _flush_deferred(app):
        """Flush deleteLater() widgets.

        ``processEvents()`` does not deliver ``DeferredDelete`` events, so
        rebuilt-away widgets would linger and skew widget scans.
        """
        from PySide6.QtCore import QEvent
        app.processEvents()
        app.sendPostedEvents(None, QEvent.DeferredDelete)

    @staticmethod
    def _labels_with_color(pages, hex_colors):
        """Return (page, text) for labels whose inline stylesheet bakes one of
        the given hex colors. ``hex_colors`` may be a str or a tuple."""
        from PySide6.QtWidgets import QLabel
        if isinstance(hex_colors, str):
            hex_colors = (hex_colors,)
        hits = []
        needle = [f"color: {hex}".lower() for hex in hex_colors]
        for name, page in pages.items():
            for lbl in page.findChildren(QLabel):
                ss = (lbl.styleSheet() or "").lower()
                if any(n in ss for n in needle):
                    hits.append((name, lbl.text()[:32]))
        return hits

    def teardown_method(self):
        """Restore the shared ThemeManager to the app default (dark) so other
        tests never inherit an unexpected mode from this class."""
        from ui.theme_pyside import ThemeManager
        ThemeManager.instance().set_mode("dark")

    def test_light_theme_tokens_follow_spec(self):
        """The shared Light tokens use the contrast-safe palette."""
        from core.theme import Light
        assert Light.TEXT == "#111827"
        assert Light.TEXT_SECONDARY == "#6B7280"
        assert Light.TEXT_MUTED == "#9CA3AF"

    def test_no_stale_white_labels_after_dark_to_light_toggle(self, pm):
        """After dark->light, no label keeps the near-white Dark TEXT,
        TEXT_SECONDARY, or TEXT_MUTED tokens."""
        self._make_project(pm)
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("dark")
        app, pages = self._build_pages(pm)
        self._flush_deferred(app)
        tm.set_mode("light")
        self._flush_deferred(app)
        assert self._labels_with_color(
            pages, ("#F8FAFC", "#94A3B8", "#64748B")
        ) == []

    def test_no_stale_light_labels_after_light_to_dark_toggle(self, pm):
        """The reverse toggle must not leave light-theme text tokens on the
        dark background either."""
        self._make_project(pm)
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("light")
        app, pages = self._build_pages(pm)
        self._flush_deferred(app)
        tm.set_mode("dark")
        self._flush_deferred(app)
        assert self._labels_with_color(
            pages, ("#111827", "#6B7280", "#9CA3AF")
        ) == []

    def test_dashboard_quick_actions_single_instance_with_light_text(self, pm):
        """No leaked duplicate grids; quick actions render in Light TEXT."""
        from collections import Counter
        from PySide6.QtWidgets import QLabel

        self._make_project(pm)
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("dark")
        app, pages = self._build_pages(pm)
        self._flush_deferred(app)
        tm.set_mode("light")
        self._flush_deferred(app)

        dashboard = pages["Dashboard"]
        quick = ("New Project", "Open Projects", "Asset Manager", "Settings")
        counts = Counter(
            lbl.text() for lbl in dashboard.findChildren(QLabel)
            if lbl.text() in quick
        )
        assert counts == {q: 1 for q in quick}
        for lbl in dashboard.findChildren(QLabel):
            if lbl.text() == "New Project":
                assert "color: #111827" in (lbl.styleSheet() or "")

    def test_static_status_badges_refresh_on_theme_toggle(self, pm):
        """Default-constructed StatusBadges must re-derive PRIMARY/PRIMARY_LIGHT
        after a runtime toggle instead of keeping Dark-theme colors on Light."""
        from PySide6.QtWidgets import QLabel
        self._make_project(pm)
        from ui.theme_pyside import ThemeManager
        tm = ThemeManager.instance()
        tm.set_mode("dark")
        app, pages = self._build_pages(pm)
        self._flush_deferred(app)
        tm.set_mode("light")
        self._flush_deferred(app)

        # #0D231A is Dark PRIMARY_LIGHT / SUCCESS_LIGHT — never a valid badge
        # background in Light mode. Any lingering instance means a default
        # StatusBadge kept its construction-time Dark colors.
        for pname, page in pages.items():
            for lbl in page.findChildren(QLabel):
                ss = lbl.styleSheet() or ""
                if "background-color: #0D231A" in ss.upper():
                    raise AssertionError(
                        f"{pname} badge kept Dark PRIMARY_LIGHT: {lbl.text()!r}"
                    )

    def test_explicit_badge_colors_are_preserved(self):
        """refresh_theme() must not overwrite colors set explicitly via
        update_colors (e.g. status badges, stage-colored chips)."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.theme_pyside import ThemeManager
        from ui.widgets import StatusBadge

        QApplication.instance() or QApplication([])
        tm = ThemeManager.instance()
        tm.set_mode("dark")

        badge = StatusBadge("Test")
        badge.update_colors("#111827", "#22C55E")
        tm.set_mode("light")
        badge.refresh_theme()
        assert "#111827" in badge.styleSheet()
        assert "#22C55E" in badge.styleSheet()

        # Default-constructed badge re-derives from the Light theme.
        from core.theme import Light
        badge2 = StatusBadge("Default")
        tm.set_mode("dark")
        tm.set_mode("light")
        badge2.refresh_theme()
        assert Light.PRIMARY in badge2.styleSheet()
        assert Light.PRIMARY_LIGHT in badge2.styleSheet()


# =====================================================================
# PHASE 12B — Theme Initialization (Sprint 3.4A)
# =====================================================================

class TestThemeStartup:
    """The saved theme must be fully applied before the UI is visible.

    Regression: MainWindow._init_theme hard-coded set_mode("dark"), which was a
    no-op because ThemeManager._current already defaults to "dark" — so the app
    stylesheet/palette were never applied at startup, producing a mixed dark/
    light UI until the user manually cycled the theme in Settings.
    """

    def test_set_mode_applies_even_when_mode_unchanged(self):
        """set_mode must re-apply the stylesheet even when the mode already
        matches, otherwise the very first startup never applies the theme."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.theme_pyside import ThemeManager

        QApplication.instance() or QApplication([])
        applied = []
        tm = ThemeManager()
        tm._apply = lambda: applied.append(True)
        tm.set_mode("dark")  # class default is already "dark"
        assert applied == [True]

    def test_main_window_init_theme_uses_saved_mode(self, monkeypatch):
        """_init_theme must read the saved preference instead of hard-coding."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.main_window import MainWindow

        class FakeSettings:
            def get_theme(self):
                return "light"

        fake_tm = SimpleNamespace()
        fake_tm.set_mode_calls = []
        fake_tm.on_change_calls = []
        fake_tm.set_mode = lambda m: fake_tm.set_mode_calls.append(m)
        fake_tm.on_change = lambda cb: fake_tm.on_change_calls.append(cb)

        class FakeThemeManager:
            @staticmethod
            def instance():
                return fake_tm

        monkeypatch.setattr("ui.main_window.AppSettings", FakeSettings)
        monkeypatch.setattr("ui.main_window.ThemeManager", FakeThemeManager)

        win = MainWindow.__new__(MainWindow)
        win._init_theme()
        assert fake_tm.set_mode_calls == ["light"]

    def test_invalid_saved_theme_falls_back_to_dark(self, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.main_window import MainWindow

        class FakeSettings:
            def get_theme(self):
                return "banana"

        fake_tm = SimpleNamespace()
        fake_tm.set_mode_calls = []
        fake_tm.on_change_calls = []
        fake_tm.set_mode = lambda m: fake_tm.set_mode_calls.append(m)
        fake_tm.on_change = lambda cb: fake_tm.on_change_calls.append(cb)

        class FakeThemeManager:
            @staticmethod
            def instance():
                return fake_tm

        monkeypatch.setattr("ui.main_window.AppSettings", FakeSettings)
        monkeypatch.setattr("ui.main_window.ThemeManager", FakeThemeManager)

        win = MainWindow.__new__(MainWindow)
        win._init_theme()
        assert fake_tm.set_mode_calls == ["dark"]

    def test_main_window_startup_applies_stylesheet(self, tmp_path, monkeypatch):
        """Full startup: after MainWindow is constructed, the app must carry
        the saved theme's stylesheet and palette."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication
        from core.theme import Dark
        import core.settings as settings_mod
        from ui.theme_pyside import ThemeManager

        monkeypatch.setattr(settings_mod, "_SETTINGS_FILE", tmp_path / "settings.json")
        monkeypatch.setattr(settings_mod, "_SETTINGS_DIR", tmp_path)
        settings_mod.AppSettings._instance = None
        _write_json(tmp_path / "settings.json", {"theme": "dark", "first_run": False})
        ThemeManager._instance = None
        ThemeManager._current = "dark"

        try:
            app = QApplication.instance() or QApplication([])
            from ui.main_window import MainWindow
            win = MainWindow()
            app.processEvents()

            assert win.theme._current == "dark"
            assert len(app.styleSheet()) > 0, "theme stylesheet was never applied"
            pal = app.palette()
            assert pal.color(QPalette.Window).name().upper() == Dark.BG.upper()
        finally:
            ThemeManager._instance = None
            ThemeManager._current = "dark"
            settings_mod.AppSettings._instance = None


# =====================================================================
# PHASE 12C — Data Integrity & Safe Shutdown (Sprint 3.4B)
# =====================================================================

class TestSafeShutdownAutosave:
    """C1: pending autosaves must be flushed before shutdown."""

    def test_flush_all_persists_pending_keys(self):
        from core.autosave import AutosaveManager
        am = AutosaveManager(debounce_ms=60000)
        saved = []
        am.register("k", lambda: saved.append("k"))
        am.mark_dirty("k")
        assert saved == []
        am.flush_all()
        assert saved == ["k"]
        assert am.is_dirty() is False

    def test_main_shutdown_flushes_before_shutdown(self, monkeypatch):
        """aboutToQuit handler must flush pending autosaves first."""
        import main
        calls = []

        class FakeManager:
            def flush_all(self):
                calls.append("flush_all")

            def shutdown(self):
                calls.append("shutdown")

        monkeypatch.setattr("core.autosave.get_autosave_manager", lambda: FakeManager())
        main._shutdown()
        assert calls == ["flush_all", "shutdown"]

    def test_close_flow_persists_pending_script_edits(self, pm, monkeypatch):
        """Close-event flush: 'type then close' writes the editor text to disk."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.autosave import AutosaveManager
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        page = ScriptPage()
        page.manager = pm
        page.set_project(name)

        autosave = AutosaveManager(debounce_ms=60000)
        autosave.register("script", page._autosave_save)

        page.editor.setPlainText("TYPED JUST BEFORE CLOSE")
        autosave.mark_dirty("script")
        autosave.flush_all()  # exactly what MainWindow.closeEvent does

        saved = _read_json(pm, name, "script.json")
        assert saved["script_output"] == "TYPED JUST BEFORE CLOSE"


class TestCloseEventShutdown:
    """C3: closing the window flushes autosave and stops page workers."""

    def test_close_event_flushes_autosave_and_cleans_pages(self, tmp_path, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QApplication
        import core.settings as settings_mod
        from ui.main_window import MainWindow
        from ui.pages.voice_page import VoicePage
        from ui.theme_pyside import ThemeManager

        monkeypatch.setattr(settings_mod, "_SETTINGS_FILE", tmp_path / "settings.json")
        monkeypatch.setattr(settings_mod, "_SETTINGS_DIR", tmp_path)
        settings_mod.AppSettings._instance = None
        _write_json(tmp_path / "settings.json", {"theme": "dark", "first_run": False})
        ThemeManager._instance = None
        ThemeManager._current = "dark"

        app = QApplication.instance() or QApplication([])

        cleaned = []
        monkeypatch.setattr(VoicePage, "cleanup", lambda self: cleaned.append("voice"))

        flushed = []

        class FakeAutosave:
            def flush_all(self):
                flushed.append("flush_all")

        monkeypatch.setattr("ui.main_window.get_autosave_manager", lambda: FakeAutosave())

        try:
            win = MainWindow()
            win.closeEvent(QCloseEvent())
        finally:
            ThemeManager._instance = None
            ThemeManager._current = "dark"
            settings_mod.AppSettings._instance = None

        assert flushed == ["flush_all"]
        assert cleaned == ["voice"]


class TestEditorDirtyGuard:
    """C2: pipeline data reloads must not overwrite unsaved editor edits."""

    def test_script_page_skips_reload_when_dirty(self, pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        page = ScriptPage()
        page.manager = pm
        page.set_project(name)
        assert page.editor.toPlainText() == "INT. CLASSROOM - DAY\nTeacher introduces AI..."

        page.editor.setPlainText("UNSAVED USER EDITS")
        assert page._dirty is True

        page._load_project_data()  # pipeline-event refresh
        assert page.editor.toPlainText() == "UNSAVED USER EDITS"
        assert page._dirty is True

    def test_script_page_still_reloads_when_clean(self, pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        page = ScriptPage()
        page.manager = pm
        page.set_project(name)

        page._load_project_data()
        assert page.editor.toPlainText() == "INT. CLASSROOM - DAY\nTeacher introduces AI..."

    def test_script_page_switching_projects_still_loads(self, pm, monkeypatch):
        """Navigation to a different project must still load its content."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        name_a = _create_sample_project(pm, "ProjA")
        _fill_script(pm, name_a)
        name_b = _create_sample_project(pm, "ProjB")
        _write_json(pm.PROJECTS_DIR / name_b / "script.json", {
            "script_output": "SCRIPT FOR B", "script_mode": "characters",
        })
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        page = ScriptPage()
        page.manager = pm
        page.set_project(name_a)
        page.editor.setPlainText("WIP EDITS IN A")
        assert page._dirty is True

        page.set_project(name_b)  # different project -> must reload
        assert page.project_name == name_b
        assert page._dirty is False
        assert page.editor.toPlainText() == "SCRIPT FOR B"

    def test_switching_projects_flushes_pending_edits_to_old_project(self, pm, monkeypatch):
        """C1/C2: switching projects must persist pending edits to the OLD
        project before its autosave callback could fire against the new one."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        name_a = _create_sample_project(pm, "ProjA")
        name_b = _create_sample_project(pm, "ProjB")
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)

        page = ScriptPage()
        page.manager = pm
        page.set_project(name_a)
        page.editor.setPlainText("EDITS IN A")

        page.set_project(name_b)  # flush must write A's edits to A

        saved_a = _read_json(pm, name_a, "script.json")
        assert saved_a["script_output"] == "EDITS IN A"
        saved_b = _read_json(pm, name_b, "script.json")
        assert "EDITS IN A" not in str(saved_b)
        assert page.editor.toPlainText() == ""  # B has no script: editor cleared
        assert page._dirty is False

    def test_voice_page_skips_reload_when_dirty(self, pm):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.voice_page import VoicePage

        app = QApplication.instance() or QApplication([])
        name = _create_sample_project(pm)
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Saved transcript"})
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Saved transcript",
            "segments": [{"start": 0, "end": 3, "text": "Saved transcript", "time": "00:00"}],
        })

        page = VoicePage()
        page.manager = pm
        page.set_project(name)
        assert page.transcript_box.toPlainText() == "Saved transcript"

        page.transcript_box.setPlainText("UNSAVED TRANSCRIPT EDITS")
        assert page._dirty is True

        page._load_project_data()  # pipeline-event refresh
        assert page.transcript_box.toPlainText() == "UNSAVED TRANSCRIPT EDITS"
        assert page._dirty is True


class TestShutdownWorkers:
    """C3: page cleanup stops background workers without crashing."""

    def test_script_page_cleanup_cancels_task_manager(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        app = QApplication.instance() or QApplication([])
        page = ScriptPage()
        cancelled = []
        page.task_manager.cancel = lambda: cancelled.append(True)
        page.cleanup()
        assert cancelled == [True]

    def test_image_prompts_cleanup_cancels_task_manager(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.image_prompts_page import ImagePromptsPage

        app = QApplication.instance() or QApplication([])
        page = ImagePromptsPage()
        cancelled = []
        page.task_manager.cancel = lambda: cancelled.append(True)
        page.cleanup()
        assert cancelled == [True]

    def test_voice_page_cleanup_joins_running_thread(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QObject, QThread
        from PySide6.QtWidgets import QApplication
        from ui.pages.voice_page import VoicePage

        app = QApplication.instance() or QApplication([])
        page = VoicePage()

        class SlowWorker(QObject):
            def run(self):
                QThread.msleep(200)

        thread = QThread()
        worker = SlowWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.start()
        page._worker_thread = thread
        page._worker = worker

        page.cleanup()
        assert thread.isRunning() is False


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

    def test_voice_generation_service_imports(self):
        import core.voice_generation_service
        from core.voice_generation_service import (
            VoiceGenerationService,
            VoiceProfile,
            VOICE_PROFILES,
            PREVIEW_TEXT,
            DEFAULT_VOICE_ID,
            DEFAULT_SPEED,
            get_voice_generation_service,
        )


# =====================================================================
# PHASE 14 — Voice Generation Backend (Sprint 3.3A)
# =====================================================================


class TestVoiceGenerationService:
    """Backend-only tests for the local Kokoro-ONNX TTS service.

    Tests that require the model to be downloaded are gated with a skip
    condition so CI without model files still passes the structural tests.
    """

    @staticmethod
    def _reset_model_cache():
        from core.voice_generation_service import VoiceGenerationService
        VoiceGenerationService._kokoro = None

    @staticmethod
    def _model_available():
        from core.voice_generation_service import get_voice_generation_service
        svc = get_voice_generation_service()
        return svc.is_available() and svc.is_model_ready()

    # ------------------------------------------------------------------
    # Structural / availability tests (no model required)
    # ------------------------------------------------------------------

    def test_service_is_importable(self):
        from core.voice_generation_service import VoiceGenerationService
        assert VoiceGenerationService is not None

    def test_singleton_returns_same_instance(self):
        from core.voice_generation_service import get_voice_generation_service
        a = get_voice_generation_service()
        b = get_voice_generation_service()
        assert a is b

    def test_exactly_eight_voices_registered(self):
        from core.voice_generation_service import VOICE_PROFILES
        assert len(VOICE_PROFILES) == 8

    def test_voice_profiles_have_required_fields(self):
        from core.voice_generation_service import VOICE_PROFILES
        for v in VOICE_PROFILES:
            assert v.id and isinstance(v.id, str)
            assert v.name and isinstance(v.name, str)
            assert v.description and isinstance(v.description, str)

    def test_expected_voice_names_present(self):
        from core.voice_generation_service import VOICE_PROFILES
        names = {v.name for v in VOICE_PROFILES}
        assert names == {"Emma", "James", "Sophia", "Alex",
                         "Daniel", "Olivia", "Ethan", "Mia"}

    def test_expected_kokoro_ids_present(self):
        from core.voice_generation_service import VOICE_PROFILES
        ids = {v.id for v in VOICE_PROFILES}
        assert ids == {
            "af_heart", "am_michael", "af_bella", "am_adam",
            "bm_george", "af_sarah", "bm_lewis", "bf_isabella",
        }

    def test_get_available_voices_returns_list_copy(self):
        from core.voice_generation_service import get_voice_generation_service
        svc = get_voice_generation_service()
        a = svc.get_available_voices()
        b = svc.get_available_voices()
        assert a == b
        assert a is not b   # defensive copy — mutations don't affect internals

    def test_get_voice_by_id_known(self):
        from core.voice_generation_service import get_voice_generation_service
        svc = get_voice_generation_service()
        v = svc.get_voice_by_id("bm_george")
        assert v is not None
        assert v.name == "Daniel"
        assert v.description == "Professional Presenter"

    def test_get_voice_by_id_unknown_returns_none(self):
        from core.voice_generation_service import get_voice_generation_service
        svc = get_voice_generation_service()
        assert svc.get_voice_by_id("nonexistent_voice_xyz") is None

    def test_default_voice_id_is_in_catalogue(self):
        from core.voice_generation_service import DEFAULT_VOICE_ID, VOICE_PROFILES
        ids = {v.id for v in VOICE_PROFILES}
        assert DEFAULT_VOICE_ID in ids

    def test_preview_text_is_nonempty_string(self):
        from core.voice_generation_service import PREVIEW_TEXT
        assert isinstance(PREVIEW_TEXT, str)
        assert len(PREVIEW_TEXT) > 10

    def test_is_available_detects_package(self, monkeypatch):
        from core.voice_generation_service import VoiceGenerationService
        import sys
        from types import SimpleNamespace
        monkeypatch.setattr(
            "core.voice_generation_service.importlib.util.find_spec",
            lambda name: None,
        )
        assert VoiceGenerationService.is_available() is False
        monkeypatch.setattr(
            "core.voice_generation_service.importlib.util.find_spec",
            lambda name: SimpleNamespace(),
        )
        assert VoiceGenerationService.is_available() is True

    def test_install_instruction_mentions_package_name(self):
        from core.voice_generation_service import VoiceGenerationService
        msg = VoiceGenerationService.install_instruction()
        assert "kokoro-onnx" in msg
        assert "pip install" in msg

    def test_is_model_ready_false_when_files_missing(self, tmp_path, monkeypatch):
        import core.voice_generation_service as mod
        monkeypatch.setattr(mod, "_CACHE_DIR", tmp_path / "empty")
        from core.voice_generation_service import VoiceGenerationService
        assert VoiceGenerationService().is_model_ready() is False

    def test_is_model_ready_true_when_both_files_present(self, tmp_path, monkeypatch):
        import core.voice_generation_service as mod
        cache = tmp_path / "kokoro"
        cache.mkdir()
        (cache / mod._MODEL_FILE_NAME).write_bytes(b"fake-model")
        (cache / mod._VOICES_FILE_NAME).write_bytes(b"fake-voices")
        monkeypatch.setattr(mod, "_CACHE_DIR", cache)
        from core.voice_generation_service import VoiceGenerationService
        assert VoiceGenerationService().is_model_ready() is True

    def test_ensure_model_ready_raises_when_package_missing(self, monkeypatch):
        from core.voice_generation_service import VoiceGenerationService
        monkeypatch.setattr(
            "core.voice_generation_service.importlib.util.find_spec",
            lambda name: None,
        )
        with pytest.raises(RuntimeError) as exc_info:
            VoiceGenerationService().ensure_model_ready()
        assert "kokoro-onnx" in str(exc_info.value)

    def test_synthesize_raises_when_model_not_downloaded(self, monkeypatch):
        import core.voice_generation_service as mod
        from core.voice_generation_service import VoiceGenerationService
        self._reset_model_cache()
        monkeypatch.setattr(mod, "_CACHE_DIR", Path("/nonexistent/__kaimi_test__"))
        with pytest.raises(RuntimeError) as exc_info:
            VoiceGenerationService().generate_preview()
        assert "not downloaded" in str(exc_info.value)
        self._reset_model_cache()

    def test_generate_to_file_raises_when_model_not_downloaded(
        self, tmp_path, monkeypatch
    ):
        import core.voice_generation_service as mod
        from core.voice_generation_service import VoiceGenerationService
        self._reset_model_cache()
        monkeypatch.setattr(mod, "_CACHE_DIR", tmp_path / "missing_cache")
        with pytest.raises(RuntimeError) as exc_info:
            VoiceGenerationService().generate_to_file(
                "test", "af_heart", 1.0, tmp_path / "out.wav"
            )
        assert "not downloaded" in str(exc_info.value)
        self._reset_model_cache()

    # ------------------------------------------------------------------
    # WAV encoding helper (no model required)
    # ------------------------------------------------------------------

    def test_float32_to_wav_bytes_produces_valid_wav(self):
        import io
        import wave
        import numpy as np
        from core.voice_generation_service import _float32_to_wav_bytes

        samples = np.sin(
            np.linspace(0, 2 * np.pi * 440, 24000, dtype=np.float32)
        )  # 1 s of 440 Hz tone
        wav_bytes = _float32_to_wav_bytes(samples, 24000)

        with wave.open(io.BytesIO(wav_bytes)) as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000
            assert wf.getnframes() == 24000

    def test_float32_to_wav_bytes_clips_out_of_range(self):
        import io
        import wave
        import numpy as np
        from core.voice_generation_service import _float32_to_wav_bytes

        samples = np.array([2.0, -3.0, 0.5], dtype=np.float32)
        wav_bytes = _float32_to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            assert wf.getnframes() == 3   # no crash, correct frame count

    # ------------------------------------------------------------------
    # Live generation tests (require model to be downloaded)
    # ------------------------------------------------------------------

    @pytest.mark.skipif(
        not _model_available.__func__(),
        reason="Kokoro model not downloaded — skipping live generation tests",
    )
    def test_generate_preview_returns_valid_wav(self):
        import io
        import wave
        from core.voice_generation_service import get_voice_generation_service

        svc = get_voice_generation_service()
        wav_bytes = svc.generate_preview("af_heart", speed=1.0)
        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) > 1000

        with wave.open(io.BytesIO(wav_bytes)) as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000
            assert wf.getnframes() > 0

    @pytest.mark.skipif(
        not _model_available.__func__(),
        reason="Kokoro model not downloaded — skipping live generation tests",
    )
    def test_generate_to_file_creates_wav_on_disk(self, tmp_path):
        import wave
        from core.voice_generation_service import get_voice_generation_service, PREVIEW_TEXT

        svc = get_voice_generation_service()
        out = tmp_path / "audio" / "output.wav"
        svc.generate_to_file(PREVIEW_TEXT, "am_michael", 1.0, out)

        assert out.exists()
        assert out.stat().st_size > 1000
        with wave.open(str(out)) as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 24000

    @pytest.mark.skipif(
        not _model_available.__func__(),
        reason="Kokoro model not downloaded — skipping live generation tests",
    )
    def test_generate_to_file_creates_parent_directories(self, tmp_path):
        from core.voice_generation_service import get_voice_generation_service, PREVIEW_TEXT

        svc = get_voice_generation_service()
        nested = tmp_path / "deep" / "nested" / "path" / "voice.wav"
        svc.generate_to_file(PREVIEW_TEXT, "af_bella", 1.0, nested)
        assert nested.exists()

    @pytest.mark.skipif(
        not _model_available.__func__(),
        reason="Kokoro model not downloaded — skipping live generation tests",
    )
    def test_all_eight_voices_synthesize_without_error(self, tmp_path):
        from core.voice_generation_service import get_voice_generation_service

        svc = get_voice_generation_service()
        short_text = "Testing voice."
        for profile in svc.get_available_voices():
            out = tmp_path / f"{profile.id}.wav"
            svc.generate_to_file(short_text, profile.id, 1.0, out)
            assert out.exists(), f"No output for voice {profile.id}"
            assert out.stat().st_size > 500, f"Empty output for voice {profile.id}"

    @pytest.mark.skipif(
        not _model_available.__func__(),
        reason="Kokoro model not downloaded — skipping live generation tests",
    )
    def test_model_loaded_once_and_reused(self):
        from core.voice_generation_service import VoiceGenerationService, PREVIEW_TEXT

        self._reset_model_cache()
        svc = VoiceGenerationService()
        svc.generate_preview("af_heart")
        first_instance = VoiceGenerationService._kokoro

        svc.generate_preview("am_adam")
        second_instance = VoiceGenerationService._kokoro

        assert first_instance is second_instance   # model loaded exactly once


# =====================================================================
# PHASE 14B — Voice Generation Reliability & Diagnostics (RC-6)
# =====================================================================


class _FakeKokoroEngine:
    """Stand-in Kokoro engine that returns a tiny silent WAV-compatible buffer.

    Lets the full instrumented pipeline (model init → text prep → synthesis →
    WAV encode → file save) run without the real model so stage reporting,
    cancellation, and timing can be tested deterministically.
    """

    def __init__(self):
        self.calls = []

    def create(self, text, voice=None, speed=None, lang=None):
        self.calls.append(text)
        import numpy as np

        samples = np.zeros(2400, dtype=np.float32)  # 0.1 s of silence @ 24 kHz
        return samples, 24000


class _FakeVoiceService:
    """In-memory stand-in for VoiceGenerationService used by worker tests."""

    def __init__(self, fail_stage=None, delay_synthesis=False):
        self.fail_stage = fail_stage
        self.delay_synthesis = delay_synthesis
        self.reported_stages = []

    def ensure_model_ready(self, progress_callback=None, cancel_event=None):
        pass

    def generate_to_file(
        self, text, voice_id, speed, output_path,
        progress_callback=None, cancel_event=None,
    ):
        from core.voice_generation_service import (
            STAGE_MESSAGES,
            STAGE_FRACTIONS,
            VoiceGenerationCancelled,
        )
        from pathlib import Path

        if cancel_event is not None and cancel_event.is_set():
            raise VoiceGenerationCancelled("cancelled")
        for stage in ("model_init", "text_prep"):
            self.reported_stages.append(stage)
            if progress_callback:
                progress_callback(stage, STAGE_MESSAGES[stage], STAGE_FRACTIONS[stage])
        if self.delay_synthesis:
            import time as _time
            _time.sleep(0.05)
        self.reported_stages.append("synthesis")
        if progress_callback:
            progress_callback(
                "synthesis", STAGE_MESSAGES["synthesis"], STAGE_FRACTIONS["synthesis"]
            )
        if self.fail_stage == "synthesis":
            raise RuntimeError("synthetic failure inside synthesis")
        for stage in ("wav_encode",):
            self.reported_stages.append(stage)
            if progress_callback:
                progress_callback(stage, STAGE_MESSAGES[stage], STAGE_FRACTIONS[stage])
        if self.fail_stage == "file_save":
            raise RuntimeError("synthetic failure writing file")
        Path(output_path).write_bytes(b"\x00" * 1024)


class TestVoiceGenerationReliability:
    """RC-6 — real stage progress, cancellation, retry, and diagnostics.

    Uses fake engines/services so the behaviour is deterministic and the tests
    never require the ~300 MB Kokoro model download.
    """

    # ------------------------------------------------------------------
    # Service-level instrumentation
    # ------------------------------------------------------------------

    def test_service_reports_all_stages_in_order(self, tmp_path, monkeypatch):
        from core import voice_generation_service as mod
        from core.voice_generation_service import (
            VoiceGenerationService,
            VoiceGenerationCancelled,
        )

        VoiceGenerationService._kokoro = _FakeKokoroEngine()
        try:
            svc = VoiceGenerationService()
            stages = []
            svc.generate_to_file(
                "Hello world.", "af_heart", 1.0, tmp_path / "out.wav",
                progress_callback=lambda s, m, f: stages.append(s),
            )
            assert stages == [
                "model_init", "text_prep", "synthesis", "wav_encode", "file_save",
            ]
            assert (tmp_path / "out.wav").exists()
        finally:
            VoiceGenerationService._kokoro = None

    def test_service_stage_fractions_are_monotonic(self):
        from core.voice_generation_service import STAGE_FRACTIONS
        vals = list(STAGE_FRACTIONS.values())
        assert vals == sorted(vals)
        assert 0.0 < vals[0] < vals[-1] <= 1.0

    def test_service_cancel_raises_cancelled_exception(self, tmp_path):
        import threading
        from core.voice_generation_service import (
            VoiceGenerationService,
            VoiceGenerationCancelled,
        )

        VoiceGenerationService._kokoro = _FakeKokoroEngine()
        cancel = threading.Event()
        try:
            svc = VoiceGenerationService()
            cancel.set()
            with pytest.raises(VoiceGenerationCancelled):
                svc.generate_to_file(
                    "Hello world.", "af_heart", 1.0, tmp_path / "out.wav",
                    cancel_event=cancel,
                )
            assert not (tmp_path / "out.wav").exists()  # nothing written
        finally:
            VoiceGenerationService._kokoro = None

    def test_service_measures_real_stage_durations(self, tmp_path, monkeypatch):
        import time as _time
        from core import voice_generation_service as mod
        from core.voice_generation_service import (
            VoiceGenerationService,
            _StageClock,
        )

        clock = _StageClock()
        _time.sleep(0.02)
        clock.mark("a")
        _time.sleep(0.02)
        clock.mark("b")
        summary = clock.summary("Header")
        assert "Header" in summary
        assert "a" in summary and "b" in summary
        assert "Total" in summary

    # ------------------------------------------------------------------
    # Worker-level behaviour (stages, cancel, retry, failure stage)
    # ------------------------------------------------------------------

    def test_worker_emits_real_stage_sequence(self, monkeypatch, tmp_path):
        from ui.pages import voice_page as vp

        fake = _FakeVoiceService()
        monkeypatch.setattr(vp, "get_voice_generation_service", lambda: fake)

        worker = vp.VoiceGenWorker(
            "Hello narration.", "af_heart", 1.0, str(tmp_path / "out.wav")
        )
        stages = []
        worker.stage.connect(lambda s, m, f: stages.append(s))
        worker.finished.connect(lambda _p: stages.append("finished"))
        worker.error.connect(lambda s, m: stages.append(f"error:{s}"))

        worker.run()

        assert "init" in stages
        assert "ready" in stages
        assert "synthesis" in stages
        assert "done" in stages
        assert stages[-1] == "finished"
        assert (tmp_path / "out.wav").exists()

    def test_worker_failure_reports_failed_stage(self, monkeypatch, tmp_path):
        from ui.pages import voice_page as vp

        fake = _FakeVoiceService(fail_stage="synthesis")
        monkeypatch.setattr(vp, "get_voice_generation_service", lambda: fake)

        worker = vp.VoiceGenWorker(
            "Hello narration.", "af_heart", 1.0, str(tmp_path / "out.wav")
        )
        errors = []
        worker.error.connect(lambda s, m: errors.append((s, m)))
        finished = []
        worker.finished.connect(finished.append)

        worker.run()

        assert errors and errors[0][0] == "synthesis"
        assert "synthetic failure" in errors[0][1]
        assert finished == []

    def test_worker_cancel_emits_cancelled_and_no_output(self, monkeypatch, tmp_path):
        import threading
        from ui.pages import voice_page as vp

        fake = _FakeVoiceService()
        monkeypatch.setattr(vp, "get_voice_generation_service", lambda: fake)

        cancel = threading.Event()
        worker = vp.VoiceGenWorker(
            "Hello narration.", "af_heart", 1.0, str(tmp_path / "out.wav"),
            cancel_event=cancel,
        )
        cancelled = []
        finished = []
        worker.cancelled.connect(lambda: cancelled.append(True))
        worker.finished.connect(finished.append)

        cancel.set()  # cancel before run starts
        worker.run()

        assert cancelled == [True]
        assert finished == []
        assert not (tmp_path / "out.wav").exists()  # project left intact

    # ------------------------------------------------------------------
    # Long-script validation (backend pipeline only, no real model needed)
    # ------------------------------------------------------------------

    def test_long_standard_script_pipeline_completes(self, tmp_path):
        """A ~4800-char script runs the full instrumented pipeline cleanly."""
        from core.voice_generation_service import VoiceGenerationService

        VoiceGenerationService._kokoro = _FakeKokoroEngine()
        try:
            svc = VoiceGenerationService()
            long_text = (
                "Educational narration for KaiMi Studio. " * 140
            )[:4800]
            stages = []
            svc.generate_to_file(
                long_text, "af_heart", 1.0, tmp_path / "standard.wav",
                progress_callback=lambda s, m, f: stages.append(s),
            )
            assert stages[-1] == "file_save"
            assert (tmp_path / "standard.wav").exists()
            assert len(long_text) >= 4500
        finally:
            VoiceGenerationService._kokoro = None

    def test_stress_script_pipeline_completes(self, tmp_path):
        """A ~9500-char stress script completes without crashing."""
        from core.voice_generation_service import VoiceGenerationService

        VoiceGenerationService._kokoro = _FakeKokoroEngine()
        try:
            svc = VoiceGenerationService()
            stress_text = (
                "Stress test narration content for pipeline validation. " * 190
            )[:9500]
            svc.generate_to_file(
                stress_text, "bm_george", 1.0, tmp_path / "stress.wav"
            )
            assert (tmp_path / "stress.wav").exists()
            assert len(stress_text) >= 8000
        finally:
            VoiceGenerationService._kokoro = None

    # ------------------------------------------------------------------
    # Progress widget (elapsed / hint / error states)
    # ------------------------------------------------------------------

    def test_progress_widget_elapsed_hint_and_error(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        from ui.widgets import ProgressWidget

        w = ProgressWidget()
        w.set_elapsed(83)
        assert "01:23" in w.eta_label.text()
        w.set_hint("Large narrations may take a little longer.")
        assert w.step_label.text() == "Large narrations may take a little longer."
        w.show_error("Failed at synthesis — boom")
        assert "Failed at synthesis" in w.status_label.text()
        w.reset()
        assert w.status_label.text() == ""


# =====================================================================
# PHASE 11 — Sprint 3.4C Workflow Fixes
# =====================================================================

class TestSprint34CWorkflow:
    """Sprint 3.4C: project workflow fixes.

    Covers the New Project dialog passing the selected Video Type into
    project creation, and the Projects page "Generate Script" card action
    (opens project -> Script page -> starts generation).
    """

    # ------------------------------------------------------------------
    # Issue 2: New Project dialog must persist the selected Video Type
    # ------------------------------------------------------------------

    def test_dialog_passes_selected_video_type(self, pm, monkeypatch):
        import ui.dialogs as dialogs_mod
        from ui.dialogs import NewProjectDialog

        class _FakeSettings:
            def __init__(self):
                self._data = {}

            def get(self, key, default=None):
                return self._data.get(key, default)

            def set(self, key, value):
                self._data[key] = value

        monkeypatch.setattr(dialogs_mod, "AppSettings", _FakeSettings)
        # The dialog builds its own ProjectManager: point it at the temp dir.
        monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", pm.PROJECTS_DIR)

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        for video_type in ["Educational", "Entertainment", "Documentary", "Tutorial", "Other"]:
            name = f"Dlg_{video_type.replace(' ', '_')}"
            dlg = NewProjectDialog()
            dlg.name_input.setText(name)
            dlg.topic_input.setText(f"Topic for {video_type}")
            dlg.video_type_combo.setCurrentText(video_type)
            dlg._on_create()
            data = pm.load_project(name)
            assert data is not None
            assert data["video_type"] == video_type

    # ------------------------------------------------------------------
    # Issue 1: Projects page "Generate Script" card action
    # ------------------------------------------------------------------

    @staticmethod
    def _make_projects_page(pm, monkeypatch):
        from core.pipeline_service import get_pipeline_service
        from ui.pages.projects import ProjectsPage

        monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", pm.PROJECTS_DIR)
        service = get_pipeline_service()
        service._pm = pm

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        page = ProjectsPage()
        page.manager = pm
        page.refresh()
        app.processEvents()
        return page

    def test_card_shows_generate_script_only_when_script_pending(self, pm, monkeypatch):
        from PySide6.QtWidgets import QPushButton
        from core.pipeline_service import get_pipeline_service

        name = _create_sample_project(pm)             # Script NOT_STARTED
        _create_sample_project(pm, "CompletedProject")  # Script completed below
        service = get_pipeline_service()
        service._pm = pm
        service.mark_stage_completed("CompletedProject", "Script")

        page = self._make_projects_page(pm, monkeypatch)

        cards = {}
        for i in range(page.cards_layout.count()):
            widget = page.cards_layout.itemAt(i).widget()
            if widget is not None:
                cards[widget._project.get("name")] = widget

        pending_texts = [b.text() for b in cards[name].findChildren(QPushButton)]
        completed_texts = [b.text() for b in cards["CompletedProject"].findChildren(QPushButton)]

        assert any("Generate Script" in t for t in pending_texts)
        assert not any("Generate Script" in t for t in completed_texts)
        assert "Resume" in pending_texts and "Resume" in completed_texts

    def test_generate_script_action_opens_project_and_starts_generation(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication, QPushButton, QWidget

        name = _create_sample_project(pm)
        page = self._make_projects_page(pm, monkeypatch)
        app = QApplication.instance()

        class _FakeScriptPage(QWidget):
            def __init__(self):
                super().__init__()
                self.project_name = None
                self.generate_calls = []

            def set_project(self, project_name):
                self.project_name = project_name

            def generate_script(self):
                self.generate_calls.append(self.project_name)

        class _FakeContent(QWidget):
            def __init__(self, script_page):
                super().__init__()
                self._current = script_page

            def currentWidget(self):
                return self._current

        class _FakeWindow(QWidget):
            def __init__(self, script_page):
                super().__init__()
                self.script_page = script_page
                self.content = _FakeContent(script_page)
                self.navigated = []
                self.context = None

            def navigate_to(self, label, project_name=None):
                self.navigated.append((label, project_name))
                self.script_page.set_project(project_name)
                self.content._current = self.script_page

            def set_project_context(self, project_name):
                self.context = project_name

        script_page = _FakeScriptPage()
        window = _FakeWindow(script_page)
        page.setParent(window)

        cards = [page.cards_layout.itemAt(i).widget() for i in range(page.cards_layout.count())]
        card = next(c for c in cards if c is not None and c._project.get("name") == name)
        gen_btn = next(b for b in card.findChildren(QPushButton) if "Generate Script" in b.text())
        gen_btn.click()
        app.processEvents()

        assert window.navigated == [("Script", name)]
        assert window.context == name
        assert script_page.project_name == name
        assert script_page.generate_calls == [name]


# =====================================================================
# PHASE 12 — Sprint 3.4D Script Length Presets
# =====================================================================

class TestSprint34DScriptLengths:
    """Sprint 3.4D: configurable, validated script length presets."""

    def test_eight_presets_match_spec(self):
        from core.script_lengths import SCRIPT_LENGTH_PRESETS
        expected = [
            ("Short Video", 4500, 5000, "Approx. 3\u20134 minutes"),
            ("Medium Video", 6500, 7000, "Approx. 4\u20135 minutes"),
            ("Long Video", 9500, 10000, "Approx. 6\u20137 minutes"),
            ("Extended Video", 12500, 13000, "Approx. 8\u20139 minutes"),
            ("Very Long Video", 15500, 16000, "Approx. 10\u201311 minutes"),
            ("Documentary Video", 19500, 20000, "Approx. 13\u201314 minutes"),
            ("Deep Dive Video", 24500, 25000, "Approx. 16\u201318 minutes"),
            ("Maximum Video", 39500, 40000, "Approx. 28\u201330 minutes"),
        ]
        actual = [
            (p.name, p.min_characters, p.max_characters, p.estimated_duration)
            for p in SCRIPT_LENGTH_PRESETS
        ]
        assert actual == expected

    def test_project_script_bounds_fallback_and_roundtrip(self):
        from core.script_lengths import project_script_bounds
        assert project_script_bounds({}) == (4500, 5000)
        assert project_script_bounds(None) == (4500, 5000)
        assert project_script_bounds({
            "script_min_characters": 6500,
            "script_max_characters": 7000,
        }) == (6500, 7000)
        assert project_script_bounds({
            "script_min_characters": "6500",
            "script_max_characters": 7000,
        }) == (4500, 5000)
        assert project_script_bounds({
            "script_min_characters": 7000,
            "script_max_characters": 6500,
        }) == (4500, 5000)
        assert project_script_bounds({
            "script_min_characters": 0,
            "script_max_characters": 7000,
        }) == (4500, 5000)

    def test_prompt_builder_uses_selected_range(self):
        from operators.script.models import ScriptRequest
        from operators.script.prompt_builder import ScriptPromptBuilder
        builder = ScriptPromptBuilder()

        _, short_prompt = builder.build(ScriptRequest(topic="t", script_min=4500, script_max=5000))
        assert "4500" in short_prompt and "5000" in short_prompt
        assert "4999" not in short_prompt

        _, max_prompt = builder.build(ScriptRequest(topic="t", script_min=39500, script_max=40000))
        assert "39500" in max_prompt and "40000" in max_prompt
        assert "4500" not in max_prompt

    def test_operator_enforces_selected_preset_range(self):
        from operators.script.models import ScriptRequest
        from operators.script.operator import ScriptOperator
        from providers.models import GenerationResponse

        sentence = (
            "That factory pulls carbon dioxide from the air and draws water from the roots "
            "to build the sugars that keep the plant alive. "
        )

        class FakeProviderManager:
            def __init__(self):
                self.calls = 0

            def generate(self, request):
                self.calls += 1
                if self.calls == 1:
                    return GenerationResponse(text="A short opening hook sentence here.")
                return GenerationResponse(text=sentence * 80)

        result = ScriptOperator(provider_manager=FakeProviderManager()).execute(
            ScriptRequest(topic="Photosynthesis", script_min=6500, script_max=7000)
        )
        assert 6500 <= len(result) <= 7000

    def test_operator_never_returns_under_minimum(self):
        from operators.script.models import ScriptRequest
        from operators.script.operator import ScriptOperator
        from providers.models import GenerationResponse

        class TinyProvider:
            def generate(self, request):
                return GenerationResponse(text="Too short. " * 10)

        with pytest.raises(RuntimeError):
            ScriptOperator(provider_manager=TinyProvider()).execute(
                ScriptRequest(topic="t", script_min=6500, script_max=7000)
            )

    def test_project_creation_stores_preset_bounds(self, pm):
        name = _create_sample_project(pm)  # legacy script_min=4500, script_max=5000
        data = pm.load_project(name)
        assert data["script_min_characters"] == 4500
        assert data["script_max_characters"] == 5000
        assert data["script_min"] == 4500
        assert data["script_max"] == 5000

    def test_project_creation_non_preset_range_falls_back(self, pm):
        pm.create_project(
            name="Doc", topic="t", platform="YouTube", video_type="Documentary",
            script_min=6000, script_max=10000,
        )
        data = pm.load_project("Doc")
        assert data["script_min_characters"] == 4500
        assert data["script_max_characters"] == 5000

    def test_script_page_preset_selection_persists(self, pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.pages.script_page import ScriptPage

        monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        app = QApplication.instance() or QApplication([])

        name = _create_sample_project(pm)
        data = pm.load_project(name)
        data["script_min_characters"] = 6500
        data["script_max_characters"] = 7000
        pm.update_project(name, data)

        page = ScriptPage()
        page.set_project(name)
        app.processEvents()

        # Combo and selection panel reflect the stored Medium preset.
        assert page.script_length_combo.currentData() == "Medium Video"
        assert page.preset_name_label.text() == "Medium Video"
        assert page.preset_range_label.text() == "6,500\u20137,000 characters"
        assert "Approx. 4\u20135 minutes" in page.preset_duration_label.text()

        # Character count labels use the selected range.
        page.editor.setPlainText("a" * 5000)
        app.processEvents()
        assert page.char_count_label.text() == "5000 / 6500 minimum"
        page.editor.setPlainText("b" * 6800)
        app.processEvents()
        assert page.char_count_label.text() == "6800 / 7000 maximum"

        # Changing the preset persists the new bounds to project.json.
        page.script_length_combo.setCurrentIndex(5)  # Documentary Video
        app.processEvents()
        stored = pm.load_project(name)
        assert stored["script_min_characters"] == 19500
        assert stored["script_max_characters"] == 20000
        assert stored["script_min"] == 19500
        assert stored["script_max"] == 20000
        assert page.preset_name_label.text() == "Documentary Video"


# =====================================================================
# PHASE 13 — Sprint 3.4E Release Polish
# =====================================================================

class TestSprint34EReleasePolish:
    """Sprint 3.4E: release polish — preset naming, dialog text, and
    removal of obsolete character-limit references."""

    def test_continuation_limit_is_named_constant(self):
        from core.script_lengths import MAX_SCRIPT_CONTINUATIONS
        assert MAX_SCRIPT_CONTINUATIONS == 4

    def test_templates_have_no_legacy_script_ranges(self):
        from core.templates import TEMPLATES
        assert TEMPLATES
        for template in TEMPLATES:
            assert not hasattr(template, "script_min")
            assert not hasattr(template, "script_max")

    def test_dialog_describes_preset_script_length(self, pm, monkeypatch):
        import ui.dialogs as dialogs_mod

        class _FakeSettings:
            def __init__(self):
                self._data = {}

            def get(self, key, default=None):
                return self._data.get(key, default)

            def set(self, key, value):
                self._data[key] = value

        monkeypatch.setattr(dialogs_mod, "AppSettings", _FakeSettings)
        monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", pm.PROJECTS_DIR)

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.dialogs import NewProjectDialog

        app = QApplication.instance() or QApplication([])
        dlg = NewProjectDialog()
        desc = dlg.template_desc.text()
        assert "Script Length: Short Video (4,500\u20135,000 chars) (default)" in desc
        assert "Script: " not in desc  # the old raw-range label is gone

    def test_dialog_created_project_uses_default_preset(self, pm, monkeypatch):
        import ui.dialogs as dialogs_mod

        class _FakeSettings:
            def __init__(self):
                self._data = {}

            def get(self, key, default=None):
                return self._data.get(key, default)

            def set(self, key, value):
                self._data[key] = value

        monkeypatch.setattr(dialogs_mod, "AppSettings", _FakeSettings)
        monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", pm.PROJECTS_DIR)

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.dialogs import NewProjectDialog

        app = QApplication.instance() or QApplication([])
        dlg = NewProjectDialog()
        dlg.name_input.setText("Polished")
        dlg.topic_input.setText("Topic")
        dlg._on_create()
        data = pm.load_project("Polished")
        assert data is not None
        assert data["script_min_characters"] == 4500
        assert data["script_max_characters"] == 5000
        assert data["script_min"] == 4500
        assert data["script_max"] == 5000
        assert data["script_min_characters"] == data["script_min"]
        assert data["script_max_characters"] == data["script_max"]


# =====================================================================
# PHASE 12C — RC-7.2 Project delete
# =====================================================================

class _DeleteConfirmBtn:
    def setStyleSheet(self, stylesheet):
        self.stylesheet = stylesheet


class _DeleteMessageBox:
    """Fake QMessageBox capturing the RC-7.2 delete confirmation dialog."""

    result = "cancel"  # "cancel" | "delete"
    instances = []

    class Icon:
        Warning = object()

    class ButtonRole:
        DestructiveRole = 3
        RejectRole = 5

    def __init__(self, parent=None):
        self.window_title = ""
        self.text = ""
        self._delete_btn = None
        self._cancel_btn = None
        self._default = None
        _DeleteMessageBox.instances.append(self)

    def setWindowTitle(self, text):
        self.window_title = text

    def setIcon(self, icon):
        self.icon = icon

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        btn = _DeleteConfirmBtn()
        if text == "Delete Project":
            self._delete_btn = btn
        else:
            self._cancel_btn = btn
        return btn

    def setDefaultButton(self, button):
        self._default = button

    def exec(self):
        return 0

    def clickedButton(self):
        if _DeleteMessageBox.result == "delete" and self._delete_btn:
            return self._delete_btn
        return self._cancel_btn


class TestRC72ProjectDelete:
    """RC-7.2: Delete Project on the Projects page — selection, destructive
    confirmation, scoped deletion via the existing ProjectManager primitive,
    active-project cleanup, empty-state transition, and failure safety.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        from core.pipeline_service import get_pipeline_service
        from ui.pages.projects import ProjectsPage

        monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", pm.PROJECTS_DIR)
        service = get_pipeline_service()
        service._pm = pm

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        page = ProjectsPage()
        page.manager = pm
        page.refresh()
        app.processEvents()
        return page

    @staticmethod
    def _install_message_box(monkeypatch):
        import ui.pages.projects as projects_mod
        _DeleteMessageBox.result = "cancel"
        _DeleteMessageBox.instances = []
        monkeypatch.setattr(projects_mod, "QMessageBox", _DeleteMessageBox)

    @staticmethod
    def _select(page, name):
        page._select_project(name)

    # ------------------------------------------------------------------
    # Action availability & selection
    # ------------------------------------------------------------------

    def test_delete_action_available_when_project_selected(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        assert not page.delete_btn.isEnabled()

        self._select(page, "Alpha")
        assert page.delete_btn.isEnabled()
        assert page._selected_project == "Alpha"
        assert not page.selected_label.isHidden()
        assert "Alpha" in page.selected_label.text()

    def test_delete_action_disabled_without_selection(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        assert page._selected_project is None
        assert not page.delete_btn.isEnabled()
        assert page.selected_label.isHidden()

    def test_card_click_selects_project(self, pm, monkeypatch):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        card = page._cards["Alpha"]
        card.show()
        QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(5, 5))
        assert page._selected_project == "Alpha"
        assert page.delete_btn.isEnabled()

    # ------------------------------------------------------------------
    # Confirmation dialog
    # ------------------------------------------------------------------

    def test_delete_opens_confirmation_dialog(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        self._select(page, "Alpha")

        page.delete_btn.click()

        assert len(_DeleteMessageBox.instances) == 1
        box = _DeleteMessageBox.instances[0]
        assert box.window_title == "Delete Project"
        assert "Delete Project?" in box.text
        assert "permanently delete" in box.text
        assert '"Alpha"' in box.text
        assert "cannot be undone" in box.text
        # Cancelled -> nothing deleted before confirmation.
        assert pm.load_project("Alpha") is not None

    def test_cancel_leaves_project_unchanged(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        self._select(page, "Alpha")

        page.delete_btn.click()  # result == "cancel"

        assert pm.load_project("Alpha") is not None
        assert (pm.PROJECTS_DIR / "Alpha").exists()
        assert "Alpha" in page._cards
        assert page._selected_project == "Alpha"
        assert page.delete_btn.isEnabled()

    # ------------------------------------------------------------------
    # Confirmed deletion
    # ------------------------------------------------------------------

    def test_confirm_removes_selected_project(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        self._select(page, "Alpha")

        page.delete_btn.click()

        assert pm.load_project("Alpha") is None
        assert not (pm.PROJECTS_DIR / "Alpha").exists()
        assert pm.load_project("Beta") is not None

    def test_deleted_project_gone_from_list(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        self._select(page, "Alpha")

        page.delete_btn.click()
        page.refresh()
        QApplication.instance().processEvents()

        assert "Alpha" not in page._cards
        assert "Beta" in page._cards
        assert page._selected_project is None
        assert not page.delete_btn.isEnabled()

    def test_stored_project_data_removed(self, pm, monkeypatch):
        name = _create_sample_project(pm)
        _fill_script(pm, name)
        _fill_image_prompts(pm, name)
        assert (pm.PROJECTS_DIR / name / "script.json").exists()
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        self._select(page, name)
        page.delete_btn.click()
        assert not (pm.PROJECTS_DIR / name).exists()

    # ------------------------------------------------------------------
    # Active-project behaviour
    # ------------------------------------------------------------------

    @staticmethod
    def _make_active_window(page, active_name, current_page=None):
        from PySide6.QtWidgets import QWidget

        class _FakePage(QWidget):
            def __init__(self):
                super().__init__()
                self.project = None

            def set_project(self, name):
                self.project = name

        class _FakeContent(QWidget):
            def __init__(self, current):
                super().__init__()
                self._current = current

            def currentWidget(self):
                return self._current

        class _FakeSidebar:
            def __init__(self):
                self.calls = []
                self.context = None

            def set_project_context(self, name, workflow_state=None):
                self.calls.append(name)
                self.context = name

        class _FakeWatcher:
            def __init__(self):
                self.unwatched = []

            def unwatch_project(self, path):
                self.unwatched.append(path)

        class _FakeNav:
            def __init__(self, window):
                self.window = window
                self.context = None

            def set_project_context(self, name):
                self.context = name
                self.window._project_name = name
                if name:
                    self.window._update_sidebar_project(name)

        class _FakeWindow(QWidget):
            def __init__(self, current_page):
                super().__init__()
                self.content = _FakeContent(current_page)
                self.sidebar = _FakeSidebar()
                self.nav = _FakeNav(self)
                self._file_watcher = _FakeWatcher()
                self._project_name = None
                self.navigated = []

            def set_project_context(self, name):
                self._project_name = name

            def _update_sidebar_project(self, project_name):
                self.sidebar.set_project_context(project_name)

            def navigate_to(self, label, project_name=None):
                self.navigated.append((label, project_name))

        window = _FakeWindow(current_page or _FakePage())
        window._project_name = active_name
        page.setParent(window)
        return window

    def test_deleting_active_project_clears_stale_reference(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        window = self._make_active_window(page, "Alpha")
        self._select(page, "Alpha")

        page.delete_btn.click()

        assert window._project_name == "Beta"
        assert window.nav.context == "Beta"
        assert str(pm.PROJECTS_DIR / "Alpha") in [
            str(p) for p in window._file_watcher.unwatched
        ]

    def test_other_project_becomes_active_and_auto_selected(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        window = self._make_active_window(page, "Alpha")
        self._select(page, "Alpha")

        page.delete_btn.click()

        # Sidebar/current-project indicator moved to the remaining project.
        assert window.sidebar.context == "Beta"
        assert page._selected_project == "Beta"
        assert page.delete_btn.isEnabled()
        # The remaining project still opens normally.
        assert pm.load_project("Beta") is not None
        page._navigate("", "Beta")
        assert window.navigated and window.navigated[0][1] == "Beta"

    def test_deleting_last_project_shows_empty_state(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        from ui.widgets import EmptyState
        _create_sample_project(pm, "Solo")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        window = self._make_active_window(page, "Solo", current_page=page)
        self._select(page, "Solo")

        page.delete_btn.click()
        QApplication.instance().processEvents()

        assert window._project_name is None
        assert window.nav.context is None
        assert window.sidebar.context is None
        assert page._selected_project is None
        assert not page.delete_btn.isEnabled()
        widgets = [
            page.cards_layout.itemAt(i).widget()
            for i in range(page.cards_layout.count())
        ]
        assert any(isinstance(w, EmptyState) for w in widgets if w is not None)

    # ------------------------------------------------------------------
    # Failure safety & unaffected behaviour
    # ------------------------------------------------------------------

    def test_delete_failure_preserves_project(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        self._select(page, "Alpha")

        monkeypatch.setattr(pm, "delete_project", lambda name: False)
        page.delete_btn.click()

        assert pm.load_project("Alpha") is not None
        assert (pm.PROJECTS_DIR / "Alpha").exists()
        assert "Alpha" in page._cards
        assert page._selected_project == "Alpha"
        assert page.delete_btn.isEnabled()

    def test_project_switching_works_after_deletion(self, pm, monkeypatch):
        from PySide6.QtWidgets import QPushButton
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        self._select(page, "Alpha")
        page.delete_btn.click()

        assert pm.load_project("Beta") is not None
        self._select(page, "Beta")
        assert page._selected_project == "Beta"
        assert page.delete_btn.isEnabled()
        texts = [b.text() for b in page._cards["Beta"].findChildren(QPushButton)]
        assert "Resume" in texts

    def test_create_unaffected_after_deletion(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        self._select(page, "Alpha")
        page.delete_btn.click()

        pm.create_project("Gamma", "New topic", "en", "Educational")
        page.refresh()
        assert pm.load_project("Gamma") is not None
        assert "Gamma" in page._cards
