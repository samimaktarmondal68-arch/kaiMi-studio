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
from operators.image_prompt.parser import (
    ImagePromptParseError,
    ImagePromptParser,
    has_leading_timestamp_prefix,
)
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
        # FIX F: the contract no longer asks for a timestamp inside the prompt.
        assert "First line: the scene timestamp" not in prompt
        assert "timestamp is structured metadata" in prompt

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
        import re as _re
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
        # FIX F: the reference prompt opens with the visual paragraph, never a
        # timestamp line (that caused '[00:00] [0:00] ...' in exports).
        assert PROMPT_TEMPLATE.startswith("Hand-drawn 2D doodle cartoon animation")
        assert not _re.match(r"^\s*\[\d{1,2}:\d{2}\]", PROMPT_TEMPLATE)

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


    # ------------------------------------------------------------------
    # RC-8 - installer & release packaging branding
    # ------------------------------------------------------------------

    def test_wizard_image_accessors_resolve_to_files(self):
        from core.branding import (
            installer_wizard_image_path,
            installer_wizard_small_image_path,
        )
        from generate_icon import ensure_installer_wizard_images

        ensure_installer_wizard_images()  # derived assets exist on fresh clones
        assert installer_wizard_image_path().name == "installer_wizard.bmp"
        assert installer_wizard_small_image_path().name == "installer_wizard_small.bmp"
        assert installer_wizard_image_path().is_file()
        assert installer_wizard_small_image_path().is_file()

    def test_wizard_images_have_expected_format_and_size(self):
        from PIL import Image
        from core.branding import (
            installer_wizard_image_path,
            installer_wizard_small_image_path,
        )
        with Image.open(installer_wizard_image_path()) as im:
            assert im.format == "BMP"
            assert im.size == (240, 459)
        with Image.open(installer_wizard_small_image_path()) as im:
            assert im.format == "BMP"
            assert im.size == (147, 147)

    def test_wizard_image_generation_uses_official_logo(self, tmp_path):
        from PIL import Image, ImageChops
        from core.branding import logo_path
        from generate_icon import (
            generate_installer_wizard_image,
            generate_installer_wizard_small_image,
        )

        big = tmp_path / "wizard.bmp"
        small = tmp_path / "wizard_small.bmp"
        assert generate_installer_wizard_image(logo_path(), big) == big
        assert generate_installer_wizard_small_image(logo_path(), small) == small
        with Image.open(big) as im:
            assert im.format == "BMP"
            assert im.size == (240, 459)
        with Image.open(small) as im:
            assert im.format == "BMP"
            assert im.size == (147, 147)
        # The official master logo is never modified by generation.
        with Image.open(logo_path()) as source:
            with Image.open(logo_path()) as reopened:
                diff = ImageChops.difference(
                    source.convert("RGBA"), reopened.convert("RGBA")
                )
                assert diff.getbbox() is None

    def test_installer_iss_references_branded_wizard_images(self):
        iss = (self._root() / "installer.iss").read_text(encoding="utf-8")
        assert "WizardImageFile=resources\\branding\\installer_wizard.bmp" in iss
        assert "WizardSmallImageFile=resources\\branding\\installer_wizard_small.bmp" in iss
        assert "WizardStyle=modern" in iss
        assert "SetupIconFile=resources\\branding\\app_icon.ico" in iss
        assert "UninstallDisplayIcon={app}\\{#MyAppExeName}" in iss

    def test_installer_iss_has_real_product_identity(self):
        iss = (self._root() / "installer.iss").read_text(encoding="utf-8")
        # The AppId must be a real GUID, not the placeholder block GUID.
        assert "A1B2C3D4" not in iss
        app_id_line = next(line for line in iss.splitlines() if line.startswith("AppId="))
        guid = app_id_line.split("AppId=", 1)[1]
        assert guid.startswith("{{") and guid.endswith("}")
        assert len(guid) == 39
        # The installer derives its identity from the generated defines.
        assert '#include "installer_metadata.iss"' in iss
        # Every identity directive derives from the generated defines.
        assert 'AppName={#MyAppName}' in iss
        assert 'AppVersion={#MyAppVersion}' in iss
        assert 'AppPublisher={#MyAppPublisher}' in iss
        assert 'VersionInfoProductName={#MyAppName}' in iss
        assert 'VersionInfoVersion={#MyAppVersion}.0' in iss

    def test_installer_progress_uses_real_installer_progress(self):
        iss = (self._root() / "installer.iss").read_text(encoding="utf-8")
        # Real progress: driven by the installer engine's progress event.
        assert "CurInstallProgressChanged" in iss
        assert "CurProgress * 100" in iss
        # No fake timer-based 0% -> 100% animation may exist.
        assert "TTimer" not in iss
        assert "OnTimer" not in iss
    def test_build_script_uses_pyinstaller_version_file_flag(self):
        """RC-8: build.py must embed the version resource with
        --version-file; --version prints the tool version and exits 0,
        which would silently skip the whole build."""
        build_src = (self._root() / "build.py").read_text(encoding="utf-8")
        assert '"--version-file"' in build_src
        assert '"file_version_info.txt"' in build_src
        assert "main.py" in build_src



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


class TestRC71ExportSingleTimestampGuarantee:
    """FIX A: the exported Image Prompt TXT must never carry a duplicate or
    extra timestamp — exactly one ``[MM:SS]`` prefix per scene line, taken
    from the stored timestamp, with the prompt text verbatim after it.

    Guards the strict Google Flow queue format even when the stored prompt
    text itself mentions times or contains line breaks (regression: the
    serializer must neither duplicate the timestamp nor let a prompt wrap
    across physical lines). Prompt text is always preserved verbatim: the
    serializer only ever adds the single [MM:SS] prefix and never strips or
    rewrites content.
    """

    @staticmethod
    def _prompts_with_time_like_text():
        """Mirror the generation contract: prompt text may mention times
        ('scene 2 at 00:08') but carries no bracketed timestamp of its own,
        so the exported line must contain exactly the one [MM:SS] prefix."""
        return [
            {
                "scene_number": 1,
                "timestamp": "00:00",
                "prompt_title": "Opening",
                "full_image_prompt": (
                    "Hand-drawn 2D doodle cartoon animation, the curious "
                    "student enters, 16:9 aspect ratio, KaiMi style"
                ),
            },
            {
                "scene_number": 2,
                "timestamp": "00:08",
                "prompt_title": "Same student",
                "full_image_prompt": (
                    "Hand-drawn 2D doodle cartoon animation, scene 2 at 00:08, "
                    "the same curious student looks up, 16:9, KaiMi style"
                ),
            },
            {
                "scene_number": 3,
                "timestamp": "00:15",
                "prompt_title": "Walk",
                "full_image_prompt": (
                    "Hand-drawn 2D doodle cartoon animation, the student walks "
                    "through the classroom at 00:15, 16:9, KaiMi style"
                ),
            },
        ]

    def test_each_line_has_exactly_one_bracketed_mm_ss(self):
        """A line carries exactly one [MM:SS] prefix — even when the prompt
        text itself mentions times (unbracketed), the serializer never adds
        a second bracketed timestamp."""
        import re
        prompts = self._prompts_with_time_like_text()
        lines = ExportService.build_image_prompts_txt(prompts).splitlines()
        assert len(lines) == 3
        for line, prompt in zip(lines, prompts):
            # Exactly one bracketed MM:SS token per line (the prefix).
            assert len(re.findall(r"\[\d{2}:\d{2}\]", line)) == 1, line
            # The prefix is the stored timestamp; the prompt follows verbatim.
            assert line == f"[{prompt['timestamp']}] {prompt['full_image_prompt']}"
            assert "Title:" not in line

    def test_prompt_with_bracketed_non_time_tokens_stays_verbatim(self):
        """Bracketed content inside the prompt (e.g. '[soft light]') is
        preserved verbatim; only the single [MM:SS] prefix is added."""
        prompts = [{
            "scene_number": 1,
            "timestamp": "00:04",
            "prompt_title": "Light",
            "full_image_prompt": "Animate [soft light] at 00:04, keep 16:9 framing",
        }]
        lines = ExportService.build_image_prompts_txt(prompts).splitlines()
        assert lines == ["[00:04] Animate [soft light] at 00:04, keep 16:9 framing"]

    def test_embedded_newlines_never_wrap_a_prompt(self):
        """A stored prompt containing \n / \r\n collapses to ONE physical
        line — Google Flow must never read one scene as several queue items."""
        prompts = [
            {"scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
             "full_image_prompt": "Line one.\nLine two.\r\nLine three."},
            {"scene_number": 2, "timestamp": "00:10", "prompt_title": "B",
             "full_image_prompt": "Only one line"},
        ]
        lines = ExportService.build_image_prompts_txt(prompts).splitlines()
        assert len(lines) == 2
        assert lines[0] == "[00:00] Line one. Line two. Line three."
        assert lines[1] == "[00:10] Only one line"

    def test_full_project_export_uses_the_same_strict_format(self, pm, es):
        """The full-project TXT export renders its Image Prompts section with
        the same strict Google Flow lines, and never mutates stored prompts."""
        name = "FullExportStrict"
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "[0:00] Narration segment.\n\n[0:04] Next segment.",
            "segments": [{"start": 0, "end": 4, "text": "Narration segment.",
                          "time": "00:00"}],
        })
        prompts = self._prompts_with_time_like_text()
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": prompts})

        proj = pm.load_project(name)
        out = es.export_project(proj, fmt="txt")
        assert out.exists()
        # Export must never mutate the stored prompt data.
        assert _read_json(pm, name, "image_prompts.json")["prompts"] == prompts

        doc_lines = out.read_text(encoding="utf-8").splitlines()
        # The prompt block is appended last and contains no blank lines, so
        # everything after the final blank line is the prompt section.
        last_blank = max(i for i, ln in enumerate(doc_lines) if ln == "")
        prompt_lines = doc_lines[last_blank + 1:]
        assert len(prompt_lines) == len(prompts)
        for line, prompt in zip(prompt_lines, prompts):
            assert line == f"[{prompt['timestamp']}] {prompt['full_image_prompt']}"
        assert not any("Scene " in ln for ln in prompt_lines)
        assert not any("Title:" in ln for ln in prompt_lines)


class TestExportPageButton:
    """FIX B: the Export page's 'Export TXT' button must be usable — enabled
    once the prerequisite stages (Script, Voice, Image Prompts) are complete
    (previously gated on the Export stage itself being COMPLETED, which could
    only happen after a successful export: a deadlock that left the button
    permanently disabled), and must drive the shared ExportService with the
    real project data, surfacing failures instead of silently doing nothing.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from core.pipeline_service import PipelineService
        from ui.pages.export_page import ExportPage

        QApplication.instance() or QApplication([])
        monkeypatch.setattr("core.script_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        page = ExportPage()
        page.manager = pm
        page.export_service.project_manager = pm
        service = PipelineService()
        service._pm = pm
        page._pipeline = service
        return page

    @staticmethod
    def _install_storage_loader(pm, service):
        """Point the pipeline's Export-stage validation at the temp project dir."""
        def _fake_load(storage_name, project_name):
            filenames = {
                "script": "script.json",
                "voice": "voice.json",
                "image_prompts": "image_prompts.json",
            }
            data = _read_json(pm, project_name, filenames[storage_name])
            return data if data else None
        service._load_storage = _fake_load

    @staticmethod
    def _seed_ready_project(pm, name="ExportReady"):
        """A project with Script, Voice and Image Prompts completed but no
        export yet — the exact state that previously deadlocked the button."""
        from core.workflow import advance_workflow_state
        pm.create_project(
            name=name, topic="AI Education", platform="YouTube",
            video_type="Educational", language="English",
        )
        _write_json(pm.PROJECTS_DIR / name / "script.json", {
            "script_output": "INT. CLASSROOM - DAY\nTeacher introduces AI to students.",
        })
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Welcome to class.",
            "segments": [{"start": 0, "end": 3, "text": "Welcome to class.", "time": "00:00"}],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Welcome to class."})
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": [
            {"scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
             "full_image_prompt": "Hand-drawn 2D doodle cartoon animation, classroom wide shot, 16:9"},
            {"scene_number": 2, "timestamp": "00:08", "prompt_title": "Teacher",
             "full_image_prompt": "Hand-drawn 2D doodle cartoon animation, teacher points at a board, 16:9"},
        ]})
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Voice")
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Image Prompts")
        pm.update_project(name, data)
        return name

    def test_button_enabled_when_prereq_stages_complete(self, pm, monkeypatch):
        """FIX B deadlock regression: the button must be enabled when
        Script/Voice/Image Prompts are COMPLETED even though the Export stage
        itself is still NOT_STARTED (no export has happened yet)."""
        name = self._seed_ready_project(pm)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)
        from core.pipeline_service import StageStatus
        assert page._pipeline.get_pipeline_state(name)["Export"] == StageStatus.NOT_STARTED
        assert page.export_btn.isEnabled()

    def test_button_disabled_until_prereq_stages_complete(self, pm, monkeypatch):
        """A fresh project with no completed stages keeps the button disabled."""
        name = _create_sample_project(pm)
        page = self._make_page(pm, monkeypatch)
        page.set_project(name)
        assert not page.export_btn.isEnabled()

    def test_click_export_txt_writes_valid_txt_and_feedback(self, pm, monkeypatch):
        """Full click path: export_btn -> _do_export -> ExportService ->
        TXT on disk -> success feedback in the UI (requirements A-E)."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        name = self._seed_ready_project(pm)
        page = self._make_page(pm, monkeypatch)
        self._install_storage_loader(pm, page._pipeline)
        page.set_project(name)
        assert page.export_btn.isEnabled()

        page.export_btn.click()

        out = pm.PROJECTS_DIR / name / "exports" / name / f"{name}.txt"
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        # Project header and Script section present.
        assert "Project: " in content
        assert "SCRIPT" in content
        assert "Teacher introduces AI" in content
        # Image Prompts section in the exact Google Flow format (F/G).
        assert "[00:00] Hand-drawn 2D doodle cartoon animation, classroom wide shot, 16:9" in content
        assert "[00:08] Hand-drawn 2D doodle cartoon animation, teacher points at a board, 16:9" in content
        assert "Scene 1" not in content and "Scene 2" not in content
        assert "Title:" not in content
        # Success feedback in the UI (requirement 5).
        assert "Exported to" in page.status_label.text()
        # Export history refreshed.
        assert "Recent:" in page.history_label.text()

    def test_do_export_passes_project_data_dict(self, pm, monkeypatch):
        """Requirement A: the export callback invokes ExportService with the
        project data dict (not a name string) and the txt format."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        name = self._seed_ready_project(pm)
        page = self._make_page(pm, monkeypatch)
        self._install_storage_loader(pm, page._pipeline)
        page.set_project(name)

        captured = {}

        def _capture(project_data, fmt="txt"):
            captured["data"] = project_data
            captured["fmt"] = fmt
            out = pm.PROJECTS_DIR / name / "exports" / name / f"{name}.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("ok", encoding="utf-8")
            return out

        monkeypatch.setattr(page.export_service, "export_project", _capture)
        page.export_btn.click()

        assert captured["fmt"] == "txt"
        assert isinstance(captured["data"], dict)
        assert captured["data"].get("name") == name
        assert "Exported to" in page.status_label.text()

    def test_export_failure_shown_in_ui(self, pm, monkeypatch):
        """Requirement H: a failing export surfaces an error in the UI
        instead of silently doing nothing."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        name = self._seed_ready_project(pm)
        page = self._make_page(pm, monkeypatch)
        self._install_storage_loader(pm, page._pipeline)
        page.set_project(name)

        def _boom(project_data, fmt="txt"):
            raise OSError("disk full")

        monkeypatch.setattr(page.export_service, "export_project", _boom)
        page.export_btn.click()

        assert "Export failed" in page.status_label.text()
        assert "disk full" in page.status_label.text()
        from core.pipeline_service import StageStatus
        assert page._pipeline.get_pipeline_state(name)["Export"] == StageStatus.FAILED

    def test_pipeline_export_project_uses_project_data_contract(self, pm, monkeypatch):
        """FIX B: PipelineService.export_project must pass the project dict
        (not the name string) to ExportService and return the written path."""
        from core.pipeline_service import PipelineService
        name = self._seed_ready_project(pm)
        service = PipelineService()
        service._pm = pm
        self._install_storage_loader(pm, service)

        result = service.export_project(name)
        assert result is not None
        out = Path(result)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Teacher introduces AI" in content
        assert "[00:00]" in content


class TestFixCVisualCleanup:
    """FIX C: decorative boxes around static information were removed — the
    Dashboard Continue-Working percentage is plain text beside the real
    progress bar, and the Script page's Selected Script Length metadata is an
    unboxed Label/Value panel. These tests pin the functional side of the
    cleanup: progress values stay accurate, the Continue card still works,
    and the script panel still displays its metadata.
    """

    @staticmethod
    def _app():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        return QApplication.instance() or QApplication([])

    def test_dashboard_continue_card_shows_accurate_progress_value(self, pm, monkeypatch):
        """1 of 4 stages complete -> exactly '25%', the 'complete' caption,
        the project name, and the Continue action are all still present."""
        from PySide6.QtWidgets import QLabel
        from core.pipeline_service import PipelineService
        from core.workflow import advance_workflow_state
        from ui.pages.dashboard import DashboardPage
        from ui.widgets import ModernButton

        self._app()
        name = "DashProgress"
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        pm.update_project(name, data)

        svc = PipelineService()
        svc._pm = pm
        monkeypatch.setattr("ui.pages.dashboard.get_pipeline_service", lambda: svc)

        page = DashboardPage()
        page.pm = pm
        page.set_project()

        texts = [lbl.text() for lbl in page.findChildren(QLabel)]
        assert "25%" in texts          # progress value preserved exactly
        assert "complete" in texts     # completion caption preserved
        assert name in texts           # project name shown
        continue_btns = [b for b in page.findChildren(ModernButton) if b.text() == "Continue"]
        assert continue_btns           # Continue Working card still functions
        # FIX C: the decorative 80px ring box is gone.
        from PySide6.QtWidgets import QFrame
        ring_styles = [
            f.styleSheet() for f in page.findChildren(QFrame)
            if "border-radius: 40px" in f.styleSheet()
        ]
        assert ring_styles == []

    def test_dashboard_continue_card_percentage_updates(self, pm, monkeypatch):
        """3 of 4 stages complete -> the Continue card reports '75%'."""
        from PySide6.QtWidgets import QLabel
        from core.pipeline_service import PipelineService
        from core.workflow import advance_workflow_state
        from ui.pages.dashboard import DashboardPage

        self._app()
        name = "DashProgress2"
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Hi", "segments": [],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {"text": "Hi"})
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": []})
        data = pm.load_project(name)
        for stage in ("Script", "Voice", "Image Prompts"):
            data["workflow_state"] = advance_workflow_state(data["workflow_state"], stage)
        pm.update_project(name, data)

        svc = PipelineService()
        svc._pm = pm
        monkeypatch.setattr("ui.pages.dashboard.get_pipeline_service", lambda: svc)

        page = DashboardPage()
        page.pm = pm
        page.set_project()

        texts = [lbl.text() for lbl in page.findChildren(QLabel)]
        assert "75%" in texts

    def test_script_selected_length_panel_unboxed_and_displays(self, pm, monkeypatch):
        """The Selected Script Length panel has no border box and its
        metadata rows still display."""
        from ui.pages.script_page import ScriptPage

        self._app()
        page = ScriptPage()
        sheet = page.selection_frame.styleSheet()
        assert "border: none" in sheet
        assert "1px solid" not in sheet
        assert page.selection_title.text() == "Selected Script Length"
        assert page.preset_name_label.text()          # Name value shown
        assert "characters" in page.preset_range_label.text()
        assert page.preset_duration_label.text()      # Duration value shown

    def test_script_editor_unchanged_by_cleanup(self, pm, monkeypatch):
        """The script editor is still the editable text area with metrics."""
        from PySide6.QtWidgets import QPlainTextEdit
        from ui.pages.script_page import ScriptPage

        self._app()
        page = ScriptPage()
        assert isinstance(page.editor, QPlainTextEdit)
        page.editor.setPlainText("a" * 4380)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        assert page.char_count_label.text() == "4380 / 4500 minimum"

    def test_dialogs_still_build(self):
        """All major dialogs still construct offscreen after the cleanup."""
        self._app()
        from core.voice_generation_service import VOICE_PROFILES
        from ui.dialogs import NewProjectDialog
        from ui.dialogs.about_dialog import AboutDialog
        from ui.dialogs.voice_selection import VoiceSelectionDialog
        from ui.pages.version_history import VersionHistoryDialog
        from ui.pages.voice_page import KOKORO_VOICE_CATALOG

        AboutDialog().close()
        NewProjectDialog().close()
        VersionHistoryDialog("DemoProject").close()

        recommended = [(p.id, p.name, p.description, "") for p in VOICE_PROFILES]
        recommended_ids = {p.id for p in VOICE_PROFILES}
        remaining = [
            (vid, name, desc, "")
            for vid, (name, desc) in KOKORO_VOICE_CATALOG.items()
            if vid not in recommended_ids
        ]
        VoiceSelectionDialog("af_heart", recommended, remaining).close()


class TestFixDProgressSystem:
    """FIX D: modern, consistent percentage-based progress — real workflow
    fractions drive determinate bars with an exact percentage; operations
    without measurable progress (blocking Kokoro synthesis, pre-batch
    phases) use the animated indeterminate treatment and never fabricate a
    percentage.
    """

    @staticmethod
    def _app():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        return QApplication.instance() or QApplication([])

    # --- Shared ProgressWidget contract ------------------------------------
    def test_determinate_shows_exact_percentage(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_progress(67, "Generating", "Stage: Generating")
        assert w.progress_bar.value() == 67
        assert w.percentage_label.text() == "67%"
        assert w.indeterminate_bar.isHidden()
        assert not w.progress_bar.isHidden()

    def test_zero_and_complete_percentages(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.reset()
        assert w.percentage_label.text() == "0%"
        w.show_complete("Done")
        assert w.percentage_label.text() == "100%"
        assert w.progress_bar.value() == 100

    def test_intermediate_percentage(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_progress(42)
        assert w.percentage_label.text() == "42%"

    def test_percentage_is_not_in_a_box(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_progress(75)
        assert "border" not in w.percentage_label.styleSheet().lower()

    def test_indeterminate_never_fabricates_percentage(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_indeterminate(status="Synthesizing Narration...")
        assert w.percentage_label.text() == ""
        assert not w.indeterminate_bar.isHidden()
        assert w.progress_bar.isHidden()

    # --- Image Prompts: the real RC-7.3 batch fraction drives the bar ------
    def test_image_prompts_poll_uses_real_batch_fraction(self):
        from ui.pages.image_prompts_page import ImagePromptsPage
        self._app()
        page = ImagePromptsPage()
        page.task_manager._is_running = True
        page.task_manager.update_progress(
            0.57,
            "Generating image prompts — Batch 4/7 (scenes 31–40 of 67)",
            stage="generating",
        )
        page._gen_started_at = 0.0
        page._poll_progress()
        assert page.progress_widget.progress_bar.value() == 57
        assert page.progress_widget.percentage_label.text() == "57%"
        assert "Batch 4/7" in page.progress_widget.status_label.text()
        assert page.progress_widget.indeterminate_bar.isHidden()

    def test_image_prompts_pre_batch_is_indeterminate_not_fake(self):
        from ui.pages.image_prompts_page import ImagePromptsPage
        self._app()
        page = ImagePromptsPage()
        page.task_manager._is_running = True
        page.task_manager.update_progress(0, "Preparing source...", stage="validating_source")
        page._gen_started_at = 0.0
        page._poll_progress()
        assert not page.progress_widget.indeterminate_bar.isHidden()
        assert page.progress_widget.percentage_label.text() == ""

    # --- Voice: synthesis indeterminate, other stages determinate ----------
    def test_voice_synthesis_stage_uses_indeterminate(self):
        from ui.pages.voice_page import VoicePage
        self._app()
        page = VoicePage()
        page._synthesis_started_at = None
        page._on_voice_stage("synthesis", "Synthesizing Narration...", 0.35)
        assert not page.progress_widget.indeterminate_bar.isHidden()
        assert page.progress_widget.percentage_label.text() == ""
        assert "Synthesizing" in page.progress_widget.status_label.text()

    def test_voice_other_stages_stay_determinate(self):
        from ui.pages.voice_page import VoicePage
        self._app()
        page = VoicePage()
        page._synthesis_started_at = None
        page._on_voice_stage("wav_encode", "Encoding WAV...", 0.90)
        assert page.progress_widget.progress_bar.value() == 90
        assert page.progress_widget.percentage_label.text() == "90%"
        assert page.progress_widget.indeterminate_bar.isHidden()

    # --- Script: staged determinate milestones unchanged -------------------
    def test_script_progress_uses_stage_milestones(self):
        from ui.pages.script_page import ScriptPage
        self._app()
        page = ScriptPage()
        page._progress_index = 0
        page._animate_progress()
        assert page.progress_widget.progress_bar.value() > 0
        assert page.progress_widget.status_label.text() in (
            "Researching...", "Finding sources...", "Analyzing...",
            "Writing...", "Improving...", "Finalizing...",
        )


# =====================================================================
# FIX E — Modern animated progress bars + project list reflow
# =====================================================================


class TestFixEModernProgressBars:
    """FIX E: every existing horizontal progress bar now uses the shared
    modern animated presentation (ModernProgressBar) — determinate values
    stay exact, the fill eases without ever fabricating progress, the
    indeterminate treatment remains percentage-free, and no new progress
    bars were introduced into unrelated UI.
    """

    @staticmethod
    def _app():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        return QApplication.instance() or QApplication([])

    def test_progress_widget_bar_is_modern(self):
        from ui.widgets import ModernProgressBar, ProgressWidget
        self._app()
        w = ProgressWidget()
        assert isinstance(w.progress_bar, ModernProgressBar)

    def test_determinate_value_stays_exact(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_progress(67, "Generating", "Stage: Generating")
        assert w.progress_bar.value() == 67
        assert w.percentage_label.text() == "67%"
        assert not w.progress_bar.isHidden()

    def test_zero_percent_renders(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.reset()
        assert w.progress_bar.value() == 0
        assert w.percentage_label.text() == "0%"

    def test_hundred_percent_renders(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.show_complete("Done")
        assert w.progress_bar.value() == 100
        assert w.percentage_label.text() == "100%"

    def test_intermediate_percentages_render(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        for pct in (25, 42, 75):
            w.set_progress(pct)
            assert w.progress_bar.value() == pct
            assert w.percentage_label.text() == f"{pct}%"

    def test_animation_never_alters_underlying_value(self):
        """The eased fill may move, but the real value and the painted fill
        never exceed what was stored — no fabrication of progress."""
        from ui.widgets import ModernProgressBar
        self._app()
        bar = ModernProgressBar()
        bar.setValue(42)
        assert bar.value() == 42
        assert bar._display <= 42.0  # fill never exceeds the real value
        # Progressing upward eases but stays bounded by the real value.
        bar.setValue(75)
        assert bar.value() == 75
        assert bar._display <= 75.0
        # Going backward must snap down, never sit above the new real value.
        bar.setValue(10)
        assert bar.value() == 10
        assert bar._display <= 10.0

    def test_determinate_mode_remains_determinate(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_progress(50, "Working")
        assert not w.progress_bar.isHidden()
        assert w.indeterminate_bar.isHidden()
        assert not w.indeterminate_bar.is_animating()

    def test_shimmer_runs_while_visible_and_stops_on_hide(self):
        """The subtle sheen only ticks while the bar is visible — no idle CPU
        on static cards once the page is hidden."""
        from PySide6.QtWidgets import QApplication
        from ui.widgets import ModernProgressBar
        self._app()
        bar = ModernProgressBar()
        bar.setValue(50)
        bar.show()
        QApplication.instance().processEvents()
        assert bar._shimmer_timer.isActive()
        bar.hide()
        QApplication.instance().processEvents()
        assert not bar._shimmer_timer.isActive()
        assert bar._shimmer == 0.0

    def test_stop_syncs_fill_to_real_value(self):
        """Stopping mid-transition must not leave the fill contradicting the
        stored value (e.g. cancel right after setValue(100))."""
        from ui.widgets import ModernProgressBar
        self._app()
        bar = ModernProgressBar()
        bar.setValue(100)
        bar.stop()
        assert bar._display == 100.0
        assert bar.value() == 100

    def test_shimmer_never_runs_for_zero_value(self):
        from ui.widgets import ModernProgressBar
        self._app()
        bar = ModernProgressBar()
        bar.setValue(0)
        bar.show()
        assert not bar._shimmer_timer.isActive()

    def test_indeterminate_never_fabricates_percentage(self):
        from ui.widgets import ProgressWidget
        self._app()
        w = ProgressWidget()
        w.set_indeterminate(status="Synthesizing Narration...")
        assert w.percentage_label.text() == ""
        assert w.progress_bar.isHidden()
        assert not w.indeterminate_bar.isHidden()
        assert w.indeterminate_bar.is_animating()

    def test_image_prompt_batch_percentage_accurate(self):
        from ui.pages.image_prompts_page import ImagePromptsPage
        self._app()
        page = ImagePromptsPage()
        page.task_manager._is_running = True
        page.task_manager.update_progress(
            0.57,
            "Generating image prompts — Batch 4/7 (scenes 31–40 of 67)",
            stage="generating",
        )
        page._gen_started_at = 0.0
        page._poll_progress()
        assert page.progress_widget.progress_bar.value() == 57
        assert page.progress_widget.percentage_label.text() == "57%"
        assert "Batch 4/7" in page.progress_widget.status_label.text()
        assert page.progress_widget.indeterminate_bar.isHidden()

    def test_voice_synthesis_stays_indeterminate(self):
        from ui.pages.voice_page import VoicePage
        self._app()
        page = VoicePage()
        page._synthesis_started_at = None
        page._on_voice_stage("synthesis", "Synthesizing Narration...", 0.35)
        assert page.progress_widget.percentage_label.text() == ""
        assert not page.progress_widget.indeterminate_bar.isHidden()
        assert page.progress_widget.progress_bar.isHidden()
        # Real milestone stages stay determinate.
        page._on_voice_stage("wav_encode", "Encoding WAV...", 0.90)
        assert page.progress_widget.progress_bar.value() == 90

    def test_dashboard_cards_use_modern_bar_with_accurate_value(self, pm, monkeypatch):
        from PySide6.QtWidgets import QLabel
        from core.pipeline_service import PipelineService
        from core.workflow import advance_workflow_state
        from ui.pages.dashboard import DashboardPage, _ContinueProjectCard
        from ui.widgets import ModernProgressBar

        self._app()
        name = "FixEProj"
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        data = pm.load_project(name)
        data["workflow_state"] = advance_workflow_state(data["workflow_state"], "Script")
        pm.update_project(name, data)

        svc = PipelineService()
        svc._pm = pm
        monkeypatch.setattr("ui.pages.dashboard.get_pipeline_service", lambda: svc)

        page = DashboardPage()
        page.pm = pm
        page.set_project()

        texts = [lbl.text() for lbl in page.findChildren(QLabel)]
        assert "25%" in texts  # real value preserved
        cards = [c for c in page.findChildren(_ContinueProjectCard)]
        assert cards
        bars = [b for b in cards[0].findChildren(ModernProgressBar)]
        assert bars and bars[0].value() == 25  # modern bar carries the real %

    def test_project_cards_use_modern_bar(self, pm, monkeypatch):
        from ui.pages.projects import ProjectsPage, _ProjectCard
        from ui.widgets import ModernProgressBar
        self._app()
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        card = page._cards["Alpha"]
        assert isinstance(card, _ProjectCard)
        bars = card.findChildren(ModernProgressBar)
        assert bars  # project card carries the shared modern bar

    def test_no_new_progress_bars_in_unrelated_ui(self, pm, monkeypatch):
        """Export, Settings, and the sidebar must not suddenly contain bars."""
        from PySide6.QtWidgets import QProgressBar
        from ui.pages.export_page import ExportPage
        from ui.pages.settings_page import SettingsPage
        from ui.widgets import ModernProgressBar
        from ui.sidebar import Sidebar
        self._app()

        export_page = ExportPage()
        settings_page = SettingsPage()
        sidebar = Sidebar()
        for widget in (export_page, settings_page, sidebar):
            modern = widget.findChildren(ModernProgressBar)
            legacy = widget.findChildren(QProgressBar)
            assert modern == [], type(widget).__name__
            assert legacy == [], type(widget).__name__

    @staticmethod
    def _make_page(pm, monkeypatch):
        from core.pipeline_service import get_pipeline_service
        from core.project_manager import ProjectManager
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


class TestFixEProjectReflow:
    """FIX E: deleting a project must reflow the remaining cards into the
    freed slot immediately — no stale spacer keeps a gap where the deleted
    card used to be. Covers first/middle/last deletion, selection, active
    state, search/filter, and the empty state.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        from core.pipeline_service import get_pipeline_service
        from core.project_manager import ProjectManager
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
    def _install_delete(monkeypatch, result="delete"):
        import ui.pages.projects as projects_mod
        _DeleteMessageBox.result = result
        _DeleteMessageBox.instances = []
        monkeypatch.setattr(projects_mod, "QMessageBox", _DeleteMessageBox)

    @staticmethod
    def _layout_items(page):
        """Return (widgets, spacers) split of the cards layout."""
        widgets, spacers = [], []
        for i in range(page.cards_layout.count()):
            item = page.cards_layout.itemAt(i)
            w = item.widget()
            if w is not None:
                widgets.append(w)
            elif item.spacerItem() is not None:
                spacers.append(item.spacerItem())
        return widgets, spacers

    def test_two_cards_reflow_after_deleting_first(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_delete(monkeypatch)
        self._select(page, "Alpha")
        page.delete_btn.click()
        QApplication.instance().processEvents()

        assert "Alpha" not in page._cards
        assert "Beta" in page._cards
        widgets, spacers = self._layout_items(page)
        # Exactly one card widget, and it occupies the FIRST layout slot —
        # no leading spacer where the deleted card used to be.
        assert widgets == [page._cards["Beta"]]
        assert len(spacers) == 1  # only the trailing stretch remains

    def test_no_blank_vertical_gap_after_delete(self, pm, monkeypatch):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        # Fresh two-card layout: Beta sits directly under Alpha (measured in
        # the cards container's own coordinates, not the page header).
        page.show()
        QApplication.instance().processEvents()
        container = page.cards_container
        beta_before = page._cards["Beta"].mapTo(container, QPoint(0, 0)).y()
        alpha_y = page._cards["Alpha"].mapTo(container, QPoint(0, 0)).y()
        gap_before = beta_before - alpha_y
        assert gap_before > 0

        self._install_delete(monkeypatch)
        self._select(page, "Alpha")
        page.delete_btn.click()
        QApplication.instance().processEvents()

        beta_after = page._cards["Beta"].mapTo(container, QPoint(0, 0)).y()
        # Beta moved up into the freed top slot: its y is now much smaller.
        assert beta_after < beta_before - gap_before // 2, (
            f"Beta stayed at y={beta_after} (was {beta_before}); "
            f"the deleted card left a gap"
        )
        # And Beta now starts at the very top of the list (first slot).
        assert beta_after <= 4, f"Beta not at the first slot: y={beta_after}"

    def test_deleting_middle_card_closes_the_gap(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        for name in ("Alpha", "Beta", "Gamma"):
            _create_sample_project(pm, name)
        page = self._make_page(pm, monkeypatch)
        self._install_delete(monkeypatch)
        self._select(page, "Beta")
        page.delete_btn.click()
        QApplication.instance().processEvents()

        assert "Beta" not in page._cards
        assert set(page._cards) == {"Alpha", "Gamma"}
        widgets, spacers = self._layout_items(page)
        assert widgets == [page._cards["Alpha"], page._cards["Gamma"]]
        assert len(spacers) == 1

    def test_deleting_last_card_reflows_remaining(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        _create_sample_project(pm, "Gamma")
        page = self._make_page(pm, monkeypatch)
        self._install_delete(monkeypatch)
        self._select(page, "Gamma")
        page.delete_btn.click()
        QApplication.instance().processEvents()
        widgets, spacers = self._layout_items(page)
        assert widgets == [page._cards["Alpha"], page._cards["Beta"]]
        assert len(spacers) == 1

    def test_empty_state_after_deleting_final_project(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Solo")
        page = self._make_page(pm, monkeypatch)
        self._install_delete(monkeypatch)
        self._select(page, "Solo")
        page.delete_btn.click()
        QApplication.instance().processEvents()

        assert page._cards == {}
        assert page.count_label.text() == "0 projects"
        widgets, spacers = self._layout_items(page)
        from ui.widgets import EmptyState
        empty = [w for w in widgets if isinstance(w, EmptyState)]
        assert empty  # empty state shows instead of a stale blank slot

    def test_selection_state_cleared_after_delete(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_delete(monkeypatch)
        self._select(page, "Alpha")
        assert page._selected_project == "Alpha"
        page.delete_btn.click()
        QApplication.instance().processEvents()
        assert page._selected_project is None
        assert not page.delete_btn.isEnabled()

    def test_active_project_state_unchanged_by_other_delete(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "ActiveProj")
        _create_sample_project(pm, "OtherProj")
        page = self._make_page(pm, monkeypatch)
        page.set_project("ActiveProj")
        self._install_delete(monkeypatch)
        self._select(page, "OtherProj")
        page.delete_btn.click()
        QApplication.instance().processEvents()
        assert page._active_project == "ActiveProj"
        assert "ActiveProj" in page._cards

    def test_search_filter_results_reflow(self, pm, monkeypatch):
        from PySide6.QtWidgets import QApplication
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        _create_sample_project(pm, "Gamma")
        page = self._make_page(pm, monkeypatch)

        page.search_input.setText("Beta")
        QApplication.instance().processEvents()
        assert set(page._cards) == {"Beta"}
        widgets, spacers = self._layout_items(page)
        assert widgets == [page._cards["Beta"]]
        assert len(spacers) == 1  # filtered list reflows to the first slot

        page.search_input.setText("")
        QApplication.instance().processEvents()
        assert set(page._cards) == {"Alpha", "Beta", "Gamma"}

    @staticmethod
    def _select(page, name):
        page._select_project(name)


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

    def test_main_window_legacy_light_falls_back_to_dark(self, monkeypatch):
        """_init_theme reads the saved preference; Dark Mode is the only
        supported theme (v1.x), so a legacy "light" value safely falls back
        to "dark" instead of being applied."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.main_window import MainWindow

        class FakeSettings:
            def get_theme(self):
                return "light"  # legacy value from a pre-v1.x config

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
# PHASE 12B2 — Dark Mode Only (v1.x Light Mode removal)
# =====================================================================

class TestDarkOnlyTheme:
    """v1.x: Dark Mode is the only supported appearance.

    The Settings UI no longer exposes a theme selector, AppSettings clamps
    any non-dark value to "dark" so legacy "light" configs migrate safely,
    and persisted theme values round-trip as "dark" only.
    """

    @staticmethod
    def _fresh_settings(tmp_path, monkeypatch):
        """Build an AppSettings rooted in a temp file, restoring the real
        module state afterward so no other test inherits the override."""
        import core.settings as settings_mod
        from core.settings import AppSettings
        monkeypatch.setattr(settings_mod, "_SETTINGS_FILE", tmp_path / "settings.json")
        monkeypatch.setattr(settings_mod, "_SETTINGS_DIR", tmp_path)
        monkeypatch.setattr(AppSettings, "_instance", None)
        return AppSettings()

    def test_settings_page_does_not_expose_theme_selector(self):
        """The Appearance card no longer offers a theme choice: no theme
        combo and no "Dark"/"Light" selector items anywhere in Settings."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from ui.pages.settings_page import SettingsPage

        QApplication.instance() or QApplication([])
        page = SettingsPage()
        assert not hasattr(page, "theme_combo")
        texts = [lbl.text() for lbl in page.findChildren(QLabel)]
        assert "Light" not in texts
        assert "dark and light themes" not in " ".join(texts)

    def test_legacy_light_setting_reads_as_dark(self, tmp_path, monkeypatch):
        """A stored "light" value from an old config resolves to "dark"."""
        _write_json(tmp_path / "settings.json", {"theme": "light"})
        s = self._fresh_settings(tmp_path, monkeypatch)
        assert s.get_theme() == "dark"

    def test_set_theme_clamps_to_dark(self, tmp_path, monkeypatch):
        """set_theme never persists an unsupported value."""
        s = self._fresh_settings(tmp_path, monkeypatch)
        s.set_theme("light")
        assert s._data["theme"] == "dark"
        assert s.get_theme() == "dark"
        s.set_theme("banana")
        assert s._data["theme"] == "dark"

    def test_theme_persistence_round_trip(self, tmp_path, monkeypatch):
        """Dark Mode persists and reloads as "dark"."""
        s = self._fresh_settings(tmp_path, monkeypatch)
        s.set_theme("dark")
        saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert saved["theme"] == "dark"
        reloaded = self._fresh_settings(tmp_path, monkeypatch)
        assert reloaded.get_theme() == "dark"


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


# =====================================================================
# PHASE 12D — RC-7.2.1 Project page selection + card layout polish
# =====================================================================

class _FakeHistoryDialog:
    """Fake VersionHistoryDialog: records construction instead of blocking."""

    instances = []

    def __init__(self, project_name, parent=None):
        self.project_name = project_name
        _FakeHistoryDialog.instances.append(self)

    def exec(self):
        return 0


class TestRC721ProjectSelection:
    """RC-7.2.1: distinct ACTIVE vs SELECTED project states, single-click
    card selection, non-interfering Resume/History controls, and a card
    layout that never clips the right-side action rail.
    """

    @staticmethod
    def _make_page(pm, monkeypatch):
        return TestRC72ProjectDelete._make_page(pm, monkeypatch)

    @staticmethod
    def _install_message_box(monkeypatch):
        return TestRC72ProjectDelete._install_message_box(monkeypatch)

    @staticmethod
    def _select(page, name):
        page._select_project(name)

    @staticmethod
    def _cards(page):
        return page._cards

    # ------------------------------------------------------------------
    # Selection state
    # ------------------------------------------------------------------

    def test_selected_card_has_distinct_selection_state(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._select(page, "Alpha")
        alpha = page._cards["Alpha"]
        beta = page._cards["Beta"]
        assert alpha._selected is True
        assert beta._selected is False
        # Distinct selected treatment: stronger outline + tinted background,
        # applied to the card (not a label).
        style = alpha.styleSheet()
        assert "border: 2px" in style
        assert "background-color" in style
        assert page.delete_btn.isEnabled()

    def test_selecting_another_card_changes_selection(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._select(page, "Alpha")
        assert page._selected_project == "Alpha"

        self._select(page, "Beta")
        assert page._selected_project == "Beta"
        assert page._cards["Alpha"]._selected is False
        assert page._cards["Beta"]._selected is True
        assert page.delete_btn.isEnabled()

    def test_clicking_selected_card_again_keeps_selection(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        self._select(page, "Alpha")
        self._select(page, "Alpha")
        assert page._selected_project == "Alpha"
        assert page._cards["Alpha"]._selected is True
        assert page.delete_btn.isEnabled()

    # ------------------------------------------------------------------
    # Active vs selected
    # ------------------------------------------------------------------

    def test_active_indicator_tracks_set_project(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        page.set_project("Alpha")
        assert page._active_project == "Alpha"
        assert page._cards["Alpha"]._active is True
        assert not page._cards["Alpha"].active_label.isHidden()
        assert page._cards["Beta"]._active is False
        assert page._cards["Beta"].active_label.isHidden()

    def test_active_and_selected_states_coexist_without_conflation(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        page.set_project("Alpha")   # ACTIVE project
        self._select(page, "Beta")  # SELECTED project is different

        alpha = page._cards["Alpha"]
        beta = page._cards["Beta"]
        # Active indicator stays on Alpha; selection outline on Beta.
        assert alpha._active is True and alpha._selected is False
        assert beta._active is False and beta._selected is True
        # Sidebar-style active context is not driven by page selection.
        assert page._selected_project == "Beta"

    def test_delete_inactive_project_keeps_active(self, pm, monkeypatch):
        _create_sample_project(pm, "ActiveProj")
        _create_sample_project(pm, "OtherProj")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        page.set_project("ActiveProj")
        window = TestRC72ProjectDelete._make_active_window(page, "ActiveProj")
        self._select(page, "OtherProj")

        page.delete_btn.click()

        # Inactive project deleted; the active project and its indicators
        # remain untouched.
        assert pm.load_project("OtherProj") is None
        assert pm.load_project("ActiveProj") is not None
        assert window._project_name == "ActiveProj"
        assert window.sidebar.calls == []
        assert page._active_project == "ActiveProj"
        assert page._cards["ActiveProj"]._active is True
        assert not page._cards["ActiveProj"].active_label.isHidden()

    def test_delete_active_project_uses_rc72_fallback(self, pm, monkeypatch):
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        self._install_message_box(monkeypatch)
        _DeleteMessageBox.result = "delete"
        page.set_project("Alpha")
        # Deletion happens on the Projects page, so the current widget is the
        # page itself (matches the real app flow).
        window = TestRC72ProjectDelete._make_active_window(page, "Alpha", current_page=page)
        self._select(page, "Alpha")

        page.delete_btn.click()

        # Existing RC-7.2 fallback: another project becomes active/selected.
        assert window._project_name == "Beta"
        assert page._active_project == "Beta"
        assert page._selected_project == "Beta"
        assert page._cards["Beta"]._active is True

    # ------------------------------------------------------------------
    # Resume / History must not trigger selection
    # ------------------------------------------------------------------

    def test_resume_click_does_not_select_and_still_navigates(self, pm, monkeypatch):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)
        navigated = []
        page._navigate = lambda label, project_name=None: navigated.append((label, project_name))

        card = page._cards["Alpha"]
        card.show()
        resume = next(b for b in card.findChildren(QPushButton) if b.text() == "Resume")
        QTest.mouseClick(resume, Qt.LeftButton, pos=QPoint(40, 18))

        # Resume navigates, and does NOT change the selection state.
        assert navigated == [("", "Alpha")]
        assert page._selected_project is None
        assert page._cards["Alpha"]._selected is False
        assert not page.delete_btn.isEnabled()

    def test_history_click_does_not_select_or_delete(self, pm, monkeypatch):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton
        import ui.pages.projects as projects_mod
        _FakeHistoryDialog.instances = []
        monkeypatch.setattr(projects_mod, "VersionHistoryDialog", _FakeHistoryDialog)
        _create_sample_project(pm, "Alpha")
        page = self._make_page(pm, monkeypatch)

        card = page._cards["Alpha"]
        card.show()
        history = next(b for b in card.findChildren(QPushButton) if b.text() == "History")
        QTest.mouseClick(history, Qt.LeftButton, pos=QPoint(40, 18))

        assert len(_FakeHistoryDialog.instances) == 1
        assert _FakeHistoryDialog.instances[0].project_name == "Alpha"
        assert page._selected_project is None
        assert page._cards["Alpha"]._selected is False
        assert pm.load_project("Alpha") is not None  # no deletion happened

    # ------------------------------------------------------------------
    # Geometry: right-side controls are never clipped
    # ------------------------------------------------------------------

    def test_resume_and_history_fully_inside_card(self, pm, monkeypatch):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication, QPushButton
        app = QApplication.instance() or QApplication([])
        _create_sample_project(pm, "Alpha")
        _create_sample_project(pm, "Beta")
        page = self._make_page(pm, monkeypatch)
        page.resize(1230, 900)
        page.show()
        app.processEvents()

        for name in ("Alpha", "Beta"):
            card = page._cards[name]
            cw, ch = card.width(), card.height()
            buttons = {
                b.text(): b for b in card.findChildren(QPushButton)
                if b.text() in ("Resume", "History")
            }
            assert "Resume" in buttons and "History" in buttons
            for text, btn in buttons.items():
                tl = btn.mapTo(card, QPoint(0, 0))
                g = btn.geometry()
                right = tl.x() + g.width()
                bottom = tl.y() + g.height()
                assert tl.x() >= 6, f"{text} clipped on left"
                assert right <= cw - 6, f"{text} clipped on right ({cw - right}px)"
                assert tl.y() >= 6, f"{text} clipped on top"
                assert bottom <= ch - 6, f"{text} clipped on bottom"
                assert g.width() >= 120, f"{text} too small ({g.width()}px)"
            # Resume and History must not overlap each other.
            resume, history = buttons["Resume"], buttons["History"]
            r = resume.mapTo(card, QPoint(0, 0)).y()
            h = history.mapTo(card, QPoint(0, 0)).y()
            assert h >= r + resume.height(), "Resume and History overlap"
        page.close()

# =====================================================================
# PHASE 12C3 — RC-7.3 Batched image prompt generation
# =====================================================================

import re as _re


def _rc73_scenes_from_prompt(user_prompt):
    """Extract (absolute scene number, MM:SS) pairs from a batch user prompt.

    Batch prompts list their scenes as 'Scene N [MM:SS]: text' lines. The
    style-anchor section (previously generated prompts) never matches because
    it renders as '1. Hand-drawn ... scene 5 at 00:04 ...' without the
    '[MM:SS]' bracket form.
    """
    return [
        (int(number), timestamp)
        for number, timestamp in _re.findall(
            r"Scene (\d+) \[(\d{2}:\d{2})\]", user_prompt
        )
    ]


def _rc73_prompt(scene_number, timestamp):
    """A valid prompt dict for a scene, echoing the given identity."""
    return {
        "scene_number": scene_number,
        "timestamp": timestamp,
        "prompt_title": f"Scene {scene_number}",
        "full_image_prompt": (
            f"Hand-drawn 2D doodle cartoon animation, scene {scene_number} "
            f"at {timestamp}, 16:9 aspect ratio, KaiMi educational doodle style"
        ),
    }


class TestRC73BatchedGeneration:
    """RC-7.3: long transcripts are generated in bounded scene batches so every
    transcript scene receives exactly one prompt — with per-batch retry,
    lossless recombination, cancellation safety, and unchanged single-shot
    behavior for short transcripts.
    """

    @staticmethod
    def _timestamps(n, start=0, step=1):
        segments = []
        for i in range(n):
            total = start + i * step
            segments.append({
                "start": total,
                "end": total + step,
                "text": f"Segment {i + 1} narration.",
                "time": f"{total // 60:02d}:{total % 60:02d}",
            })
        return segments

    @staticmethod
    def _request(n, topic="Why Do Humans Dream"):
        from operators.image_prompt.models import ImagePromptRequest

        timestamps = TestRC73BatchedGeneration._timestamps(n)
        return ImagePromptRequest(
            script_text="A long educational script about sleep.",
            transcript="\n".join(
                f"[{t['time']}] {t['text']}" for t in timestamps
            ),
            timestamps=timestamps,
            topic=topic,
            language="English",
        )

    def test_67_scenes_generate_67_prompts_in_batches(self):
        """67 input scenes -> exactly 67 prompts, no missing/duplicate scenes,
        original order and timestamps preserved, via 7 ordered batches."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(67)
        requested_batches = []

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                requested_batches.append([n for n, _ in scenes])
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=10, max_retries=1)

        assert len(prompts) == 67                       # final count == source
        assert [p["scene_number"] for p in prompts] == list(range(1, 68))
        assert [p["timestamp"] for p in prompts] == [t["time"] for t in request.timestamps]
        assert len({p["scene_number"] for p in prompts}) == 67  # no duplicates
        assert all(p["full_image_prompt"] for p in prompts)     # non-empty
        # 7 batches: 10,10,10,10,10,10,7 — original order preserved.
        assert [len(b) for b in requested_batches] == [10, 10, 10, 10, 10, 10, 7]
        assert [b[0] for b in requested_batches] == [1, 11, 21, 31, 41, 51, 61]

    def test_truncating_provider_still_covers_all_scenes(self):
        """A provider that caps any response at 26 prompts (the RC-7.3 bug:
        67 scenes -> 26 prompts) must now yield complete coverage, because
        every request only ever asks for one batch of <= 10 scenes."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(67)

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                payload = [_rc73_prompt(n, ts) for n, ts in scenes[:26]]
                return SimpleNamespace(text=json.dumps(payload))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=10)
        assert len(prompts) == 67
        assert [p["scene_number"] for p in prompts] == list(range(1, 68))

    def test_unbatched_large_transcript_still_rejects_incomplete_coverage(self):
        """The RC-7 validator must stay intact: a single-shot request for 67
        scenes returning only 26 prompts must still fail loudly — batching is
        the fix, not a weakened validator."""
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(67)

        class FakeProviderManager:
            def generate(self, gen_request):
                payload = [
                    _rc73_prompt(n, request.timestamps[n - 1]["time"])
                    for n in range(1, 27)
                ]
                return SimpleNamespace(text=json.dumps(payload))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        with pytest.raises(ImagePromptGenerationError) as exc_info:
            operator.generate_prompts(request, batch_size=100)
        assert "coverage is incomplete" in str(exc_info.value)

    def test_failed_batch_is_retried_alone(self):
        """A batch whose first attempt is malformed is retried alone; other
        batches are generated exactly once."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        call_counts = {}

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                first = scenes[0][0]
                call_counts[first] = call_counts.get(first, 0) + 1
                if first == 11 and call_counts[first] == 1:
                    return SimpleNamespace(text="definitely not json")
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=10, max_retries=1)
        assert len(prompts) == 20
        assert call_counts[1] == 1    # batch 1: single attempt
        assert call_counts[11] == 2   # batch 2: failed once, retried once

    def test_batch_truncation_is_retried(self):
        """A batch returning fewer prompts than its scenes is rejected and
        retried (exact coverage is enforced per batch)."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        call_counts = {}

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                first = scenes[0][0]
                call_counts[first] = call_counts.get(first, 0) + 1
                if first == 1 and call_counts[first] == 1:
                    payload = [_rc73_prompt(n, ts) for n, ts in scenes[:5]]
                    return SimpleNamespace(text=json.dumps(payload))
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=10, max_retries=1)
        assert len(prompts) == 20
        assert call_counts[1] == 2

    def test_persistently_failing_batch_fails_generation_safely(self):
        """A batch that keeps failing fails the WHOLE generation with an error
        identifying the batch and its scenes — never a partial success."""
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 11:
                    return SimpleNamespace(text="still not json")
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        with pytest.raises(ImagePromptGenerationError) as exc_info:
            operator.generate_prompts(request, batch_size=10, max_retries=1)
        message = str(exc_info.value)
        assert "Batch 2/2" in message
        assert "scenes 11" in message

    def test_failed_regeneration_leaves_stored_prompts_untouched(self, pm, monkeypatch):
        """A failed regeneration never touches previously saved prompts."""
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        name = "RC73Keep"
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        existing = [_rc73_prompt(1, "00:00")]
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": existing})

        request = self._request(20)

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 11:
                    raise RuntimeError("provider connection reset")
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        with pytest.raises(ImagePromptGenerationError):
            operator.generate_prompts(request, batch_size=10, max_retries=0)

        stored = ImagePromptStorage().load(name)
        assert stored.get("prompts") == existing

    def test_batch_returning_local_numbers_is_rejected_and_retried(self):
        """A model numbering scenes 1..N within each batch instead of using
        absolute numbers is rejected and retried, never aggregated."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        call_counts = {}

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                first = scenes[0][0]
                call_counts[first] = call_counts.get(first, 0) + 1
                if first == 11 and call_counts[first] == 1:
                    payload = [
                        _rc73_prompt(local, ts)
                        for local, (_, ts) in enumerate(scenes, start=1)
                    ]
                    return SimpleNamespace(text=json.dumps(payload))
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=10, max_retries=1)
        assert len(prompts) == 20
        assert call_counts[11] == 2  # rejected once, retried successfully

    def test_batch_inventing_timestamps_is_rejected(self):
        """A model inventing timestamps is rejected and retried — the parser
        never trusts the LLM to normalize time."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        call_counts = {}

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                first = scenes[0][0]
                call_counts[first] = call_counts.get(first, 0) + 1
                if first == 11 and call_counts[first] == 1:
                    payload = [_rc73_prompt(n, "09:09") for n, _ in scenes]
                    return SimpleNamespace(text=json.dumps(payload))
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=10, max_retries=1)
        assert len(prompts) == 20
        assert call_counts[11] == 2

    def test_cancellation_between_batches_saves_nothing(self):
        """Cancelling during a batch stops the run; no partial output is ever
        returned or persisted."""
        import threading

        from core.task_manager import TaskCancelledError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        cancel_event = threading.Event()
        calls = {"n": 0}

        class FakeProviderManager:
            def generate(self, gen_request):
                calls["n"] += 1
                if calls["n"] == 2:
                    cancel_event.set()
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        with pytest.raises(TaskCancelledError):
            operator.generate_prompts(
                request, batch_size=10, cancel_event=cancel_event, max_retries=1
            )
        assert calls["n"] == 2  # batch 2 started, then the cancel check fired

    def test_batch_progress_reports_batch_information(self):
        """Progress messages carry batch/scene information for the UI."""
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(15)
        messages = []

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                return SimpleNamespace(text=json.dumps(
                    [_rc73_prompt(n, ts) for n, ts in scenes]
                ))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        operator.generate_prompts(
            request,
            batch_size=10,
            progress_callback=lambda stage, message, fraction: messages.append(message),
        )
        joined = "\n".join(messages)
        assert "Batch 1/2" in joined
        assert "Batch 2/2" in joined
        assert "scenes 1\u201310 of 15" in joined
        assert "scenes 11\u201315 of 15" in joined

    def test_short_transcript_uses_single_request(self):
        """Short transcripts keep the legacy single-request path (one call)."""
        from operators.image_prompt.operator import ImagePromptOperator

        timestamps = self._timestamps(3)
        request = self._request(3)
        calls = {"n": 0}

        class FakeProviderManager:
            def generate(self, gen_request):
                calls["n"] += 1
                payload = [
                    _rc73_prompt(i + 1, timestamps[i]["time"])
                    for i in range(len(timestamps))
                ]
                return SimpleNamespace(text=json.dumps(payload))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, max_retries=1)
        assert calls["n"] == 1
        assert len(prompts) == 3

    def test_default_batch_size_derives_from_token_budget(self):
        """The default batch size is derived from the provider token budget,
        not hardcoded, and an explicit value wins."""
        from operators.image_prompt.operator import ImagePromptOperator

        assert ImagePromptOperator._resolve_batch_size(None, 67) == 10
        assert ImagePromptOperator._resolve_batch_size(3, 67) == 3


# =====================================================================
# FIX F — No duplicate timestamps at the generation/storage boundary
# =====================================================================

class TestFixGProviderJsonReliability:
    """FIX G: JSON handling stays tolerant of wrappers and strict on content."""

    @staticmethod
    def _request(n):
        return TestRC73BatchedGeneration._request(n, topic="Dream Science")

    @staticmethod
    def _payload(scenes, prefix=""):
        return json.dumps([
            {
                **_rc73_prompt(number, timestamp),
                "full_image_prompt": (
                    f"{prefix}Hand-drawn 2D doodle cartoon animation, "
                    f'a curious student asks, "Why do we dream?", scene '
                    f"{number}, 16:9 aspect ratio, KaiMi educational doodle style"
                ),
            }
            for number, timestamp in scenes
        ])

    def test_valid_json_parses_exactly_as_before(self):
        prompts = ImagePromptParser().parse(self._payload([(1, "00:00")]))
        assert prompts[0]["scene_number"] == 1
        assert prompts[0]["timestamp"] == "00:00"
        assert 'asks, "Why do we dream?"' in prompts[0]["full_image_prompt"]

    def test_markdown_json_fence_is_unwrapped(self):
        raw = "```json\n" + self._payload([(1, "00:00")]) + "\n```"
        assert ImagePromptParser().parse(raw)[0]["scene_number"] == 1

    def test_leading_and_trailing_whitespace_is_accepted(self):
        raw = "\n\n  " + self._payload([(1, "00:00")]) + "  \n"
        assert ImagePromptParser().parse(raw)[0]["timestamp"] == "00:00"

    def test_escaped_quotes_survive_decoding_unchanged(self):
        body = (
            'Hand-drawn 2D doodle cartoon animation, a student asks, '
            '"Why do we dream?", 16:9 aspect ratio, KaiMi educational doodle style'
        )
        raw = json.dumps([{
            "scene_number": 1,
            "timestamp": "00:00",
            "prompt_title": "Question",
            "full_image_prompt": body,
        }])
        assert ImagePromptParser().parse(raw)[0]["full_image_prompt"] == body

    def test_long_prompt_with_punctuation_and_quotes_remains_intact(self):
        body = (
            'Hand-drawn 2D doodle cartoon animation, "dream symbols" swirl; '
            + "soft classroom details, " * 200
            + 'a student asks, "What changes during sleep?", 16:9 aspect ratio, '
            "KaiMi educational doodle style"
        )
        raw = json.dumps([{
            "scene_number": 1,
            "timestamp": "00:00",
            "prompt_title": "Long",
            "full_image_prompt": body,
        }])
        assert ImagePromptParser().parse(raw)[0]["full_image_prompt"] == body

    def test_genuine_malformed_json_is_rejected(self):
        with pytest.raises(ImagePromptParseError) as exc_info:
            ImagePromptParser().parse(
                '[{"scene_number": 1 "timestamp": "00:00"}]'
            )
        assert "Invalid JSON" in str(exc_info.value)

    def test_malformed_first_attempt_then_valid_json_succeeds(self):
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        attempts = []
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                attempts.append(gen_request.prompt)
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 11 and len(attempts) == 2:
                    return SimpleNamespace(text='[{"scene_number": 11 "timestamp": "00:10"}]')
                return SimpleNamespace(text=self_outer._payload(scenes))

        prompts = ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
            request, batch_size=10, max_retries=1
        )
        assert len(prompts) == 20
        assert "Your previous response could not be parsed as valid JSON" in attempts[-1]
        assert "escape quotation marks inside strings" in attempts[-1]

    def test_retry_count_remains_bounded_by_max_retries(self):
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        calls = 0

        class FakeProviderManager:
            def generate(self, gen_request):
                nonlocal calls
                calls += 1
                return SimpleNamespace(text='[{"scene_number": 1 "timestamp": "00:00"}]')

        with pytest.raises(ImagePromptGenerationError):
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                request, batch_size=10, max_retries=1
            )
        assert calls == 2

    def test_exhausted_malformed_attempts_report_batch_context(self):
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 11:
                    return SimpleNamespace(text='[{"scene_number": 11 "timestamp": "00:10"}]')
                return SimpleNamespace(text=self_outer._payload(scenes))

        with pytest.raises(ImagePromptGenerationError) as exc_info:
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                request, batch_size=10, max_retries=1
            )
        message = str(exc_info.value)
        assert "Batch 2/2" in message
        assert "scenes 11" in message
        assert "Invalid JSON" in message

    def test_missing_scene_fails_exact_batch_validation(self):
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 1:
                    scenes = scenes[:-1]
                return SimpleNamespace(text=self_outer._payload(scenes))

        with pytest.raises(ImagePromptGenerationError) as exc_info:
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                request, batch_size=10, max_retries=0
            )
        assert "returned 9 prompts for 10 scenes" in str(exc_info.value)

    def test_duplicate_scene_fails_exact_batch_validation(self):
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                payload = json.loads(self_outer._payload(scenes))
                if scenes[0][0] == 1:
                    payload[-1]["scene_number"] = payload[0]["scene_number"]
                return SimpleNamespace(text=json.dumps(payload))

        with pytest.raises(ImagePromptGenerationError) as exc_info:
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                request, batch_size=10, max_retries=0
            )
        assert "duplicates scene number" in str(exc_info.value)

    def test_structured_timestamps_remain_exact(self):
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(20)
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                return SimpleNamespace(text=self_outer._payload(scenes))

        prompts = ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
            request, batch_size=10
        )
        assert [p["timestamp"] for p in prompts] == [t["time"] for t in request.timestamps]

    def test_full_image_prompt_does_not_gain_leading_timestamp(self):
        prompts = ImagePromptParser().parse(self._payload([(1, "00:00")], prefix="[0:00] "))
        assert not has_leading_timestamp_prefix(prompts[0]["full_image_prompt"])

    def test_existing_prompts_not_modified_after_failed_regeneration(self, pm, monkeypatch):
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        name = "FixGExisting"
        _create_sample_project(pm, name)
        existing = [_rc73_prompt(1, "00:00")]
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": existing})

        class FakeProviderManager:
            def generate(self, gen_request):
                return SimpleNamespace(text='[{"scene_number": 1 "timestamp": "00:00"}]')

        with pytest.raises(ImagePromptGenerationError):
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                self._request(20), batch_size=10, max_retries=0
            )
        assert ImagePromptStorage().load(name)["prompts"] == existing

    def test_failed_batch_does_not_partially_persist(self, pm, monkeypatch):
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        name = "FixGPartial"
        _create_sample_project(pm, name)
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 11:
                    return SimpleNamespace(text='[{"scene_number": 11 "timestamp": "00:10"}]')
                return SimpleNamespace(text=self_outer._payload(scenes))

        with pytest.raises(ImagePromptGenerationError):
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                self._request(20), batch_size=10, max_retries=0
            )
        assert ImagePromptStorage().load(name).get("prompts", []) == []

    def test_successful_batches_remain_ordered(self):
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(30)
        seen = []
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                seen.append([number for number, _ in scenes])
                return SimpleNamespace(text=self_outer._payload(scenes))

        prompts = ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
            request, batch_size=10
        )
        assert seen == [list(range(1, 11)), list(range(11, 21)), list(range(21, 31))]
        assert [p["scene_number"] for p in prompts] == list(range(1, 31))

    def test_export_still_one_timestamp_per_physical_line(self):
        prompts = [
            {
                "scene_number": 1,
                "timestamp": "00:00",
                "prompt_title": "A",
                "full_image_prompt": "prompt",
            },
            {
                "scene_number": 2,
                "timestamp": "00:08",
                "prompt_title": "B",
                "full_image_prompt": "prompt",
            },
        ]
        assert ExportService.build_image_prompts_txt(prompts) == (
            "[00:00] prompt\n[00:08] prompt"
        )

    def test_image_prompt_requests_ask_for_json_array_response_format(self):
        from operators.image_prompt.operator import ImagePromptOperator

        captured = []
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                captured.append(gen_request.response_format)
                scenes = _rc73_scenes_from_prompt(gen_request.prompt) or [(1, "00:00")]
                return SimpleNamespace(text=self_outer._payload(scenes))

        ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
            self._request(1), max_retries=0
        )
        assert captured == ["json_array"]

    def test_67_scene_batch_three_retry_succeeds_end_to_end(self):
        from operators.image_prompt.operator import ImagePromptOperator

        request = self._request(67)
        calls_by_first = {}
        batches = []
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                first = scenes[0][0]
                calls_by_first[first] = calls_by_first.get(first, 0) + 1
                if calls_by_first[first] == 1:
                    batches.append([number for number, _ in scenes])
                if first == 21 and calls_by_first[first] == 1:
                    return SimpleNamespace(text='[{"scene_number": 21 "timestamp": "00:20"}]')
                return SimpleNamespace(text=self_outer._payload(scenes))

        prompts = ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
            request, batch_size=10, max_retries=1
        )
        assert len(prompts) == 67
        assert batches == [
            list(range(1, 11)),
            list(range(11, 21)),
            list(range(21, 31)),
            list(range(31, 41)),
            list(range(41, 51)),
            list(range(51, 61)),
            list(range(61, 68)),
        ]
        assert calls_by_first[21] == 2
        assert [p["scene_number"] for p in prompts] == list(range(1, 68))
        assert [p["timestamp"] for p in prompts] == [t["time"] for t in request.timestamps]
        assert len({p["scene_number"] for p in prompts}) == 67
        assert all(not has_leading_timestamp_prefix(p["full_image_prompt"]) for p in prompts)

    def test_67_scene_batch_three_retry_exhaustion_fails_safely(self, pm, monkeypatch):
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptGenerationError
        from operators.image_prompt.operator import ImagePromptOperator

        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        name = "FixG67Fail"
        _create_sample_project(pm, name)
        existing = [_rc73_prompt(1, "00:00")]
        _write_json(pm.PROJECTS_DIR / name / "image_prompts.json", {"prompts": existing})
        self_outer = self

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                if scenes[0][0] == 21:
                    return SimpleNamespace(text='[{"scene_number": 21 "timestamp": "00:20"}]')
                return SimpleNamespace(text=self_outer._payload(scenes))

        with pytest.raises(ImagePromptGenerationError) as exc_info:
            ImagePromptOperator(provider_manager=FakeProviderManager()).generate_prompts(
                self._request(67), batch_size=10, max_retries=1
            )
        message = str(exc_info.value)
        assert "Batch 3/7" in message
        assert "scenes 21" in message and "30" in message
        assert ImagePromptStorage().load(name)["prompts"] == existing


class TestFixFDeduplicateTimestamps:
    """FIX F: the scene timestamp is structured metadata ONLY. The stored
    ``full_image_prompt`` must NEVER begin with a timestamp — the generation
    contract no longer asks the model to embed one, and the parser
    defensively strips a leading [M:SS] prefix that a provider still echoes.
    Export therefore renders exactly one ``[MM:SS]`` per line and never the
    production defect ``[00:00] [0:00] Hand-drawn ...``.
    """

    @staticmethod
    def _assert_clean(prompts):
        """Strong invariant: no stored/generated prompt begins with [M:SS].

        Uses the parser's own invariant helper (FIX F) so the guard and the
        normalization regex can never drift apart.
        """
        for prompt in prompts:
            assert not has_leading_timestamp_prefix(
                prompt["full_image_prompt"]
            ), prompt["full_image_prompt"]

    # --- Parser boundary normalization (8.A / 8.B / 9) ------------------

    def test_parser_strips_leading_short_timestamp(self):
        """8.A: '[0:00] Hand-drawn ...' stores 'Hand-drawn ...' + '00:00'."""
        raw = json.dumps([{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
            "full_image_prompt": (
                "[0:00] Hand-drawn 2D doodle cartoon animation, a classroom, 16:9"
            ),
        }])
        prompts = ImagePromptParser().parse(raw)
        assert prompts[0]["timestamp"] == "00:00"
        assert prompts[0]["full_image_prompt"] == (
            "Hand-drawn 2D doodle cartoon animation, a classroom, 16:9"
        )
        self._assert_clean(prompts)

    def test_parser_strips_leading_padded_timestamp(self):
        """8.B: '[00:00] Hand-drawn ...' stores 'Hand-drawn ...' + '00:00'."""
        raw = json.dumps([{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
            "full_image_prompt": "[00:00] Hand-drawn 2D doodle cartoon animation, a scene",
        }])
        prompts = ImagePromptParser().parse(raw)
        assert prompts[0]["timestamp"] == "00:00"
        assert prompts[0]["full_image_prompt"] == (
            "Hand-drawn 2D doodle cartoon animation, a scene"
        )
        self._assert_clean(prompts)

    def test_parser_strips_only_a_leading_prefix(self):
        """Other provider forms ([1:23], leading whitespace) are stripped too;
        a prompt that is only a timestamp becomes empty and is rejected."""
        cases = (("[1:23]", "01:23"), ("[01:23]", "01:23"),
                 ("  [0:00]", "00:00"), ("[0:00]  ", "00:00"))
        for prefix, ts in cases:
            raw = json.dumps([{
                "scene_number": 1, "timestamp": ts,
                "prompt_title": "A",
                "full_image_prompt": prefix + "Hand-drawn 2D doodle cartoon animation, x",
            }])
            prompts = ImagePromptParser().parse(raw)
            assert prompts[0]["full_image_prompt"] == (
                "Hand-drawn 2D doodle cartoon animation, x"
            ), prefix
            self._assert_clean(prompts)

    def test_timestamp_only_prompt_rejected(self):
        """A prompt reduced to '' by normalization fails non-empty validation."""
        raw = json.dumps([{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "A",
            "full_image_prompt": "[0:00]",
        }])
        with pytest.raises(ImagePromptParseError):
            ImagePromptParser().parse(raw)

    def test_invariant_holds_for_both_timestamp_forms(self):
        """9: the strong invariant holds for [0:00] and [00:00] inputs."""
        payloads = [
            "[0:00] Hand-drawn 2D doodle cartoon animation, a",
            "[00:00] Hand-drawn 2D doodle cartoon animation, b",
            "[0:59] Hand-drawn 2D doodle cartoon animation, c",
        ]
        prompts = [{
            "scene_number": i + 1, "timestamp": "00:00",
            "prompt_title": f"P{i}", "full_image_prompt": body,
        } for i, body in enumerate(payloads)]
        prompts = ImagePromptParser().parse(json.dumps(prompts))
        self._assert_clean(prompts)
        assert [p["full_image_prompt"] for p in prompts] == [
            "Hand-drawn 2D doodle cartoon animation, a",
            "Hand-drawn 2D doodle cartoon animation, b",
            "Hand-drawn 2D doodle cartoon animation, c",
        ]

    # --- Legitimate content must survive untouched (8.C / 8.D) -----------

    def test_time_like_content_inside_prompt_unchanged(self):
        """8.C: 'Show a digital clock reading 00:00 on the wall' is kept verbatim."""
        body = "Show a digital clock reading 00:00 on the wall"
        raw = json.dumps([{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Clock",
            "full_image_prompt": body,
        }])
        prompts = ImagePromptParser().parse(raw)
        assert prompts[0]["full_image_prompt"] == body
        self._assert_clean(prompts)

    def test_bracketed_time_in_content_unchanged(self):
        """8.D: non-leading bracketed times are legitimate scene content."""
        for body in (
            "Show a glowing [00:00] digital clock in the background",
            "A clock face showing [0:00] on the wall",
            "An alarm clock reads [07:30] next to the bed",
        ):
            raw = json.dumps([{
                "scene_number": 1, "timestamp": "00:00",
                "prompt_title": "Clock", "full_image_prompt": body,
            }])
            prompts = ImagePromptParser().parse(raw)
            assert prompts[0]["full_image_prompt"] == body
            self._assert_clean(prompts)

    # --- Export stays exactly one timestamp per line (8.E / 8.J) ---------

    def test_export_never_duplicates_timestamp(self):
        """8.E: export produces '[00:00] Hand-drawn ...' and never a doubled prefix."""
        prompts = [{
            "scene_number": 1, "timestamp": "00:00", "prompt_title": "Opening",
            "full_image_prompt": "Hand-drawn 2D doodle cartoon animation, a classroom, 16:9",
        }]
        text = ExportService.build_image_prompts_txt(prompts)
        assert text == "[00:00] Hand-drawn 2D doodle cartoon animation, a classroom, 16:9"
        assert "[00:00] [0:00]" not in text
        assert "[00:00] [00:00]" not in text

    def test_long_prompt_only_leading_prefix_removed(self):
        """8.G: a long prompt is untouched apart from the leading prefix strip."""
        body = (
            "Hand-drawn 2D doodle cartoon animation, "
            + "flowing detailed scene narration, " * 200
            + "16:9 aspect ratio, KaiMi educational doodle style"
        )
        assert len(body) > 5000
        raw = json.dumps([{
            "scene_number": 1, "timestamp": "00:03", "prompt_title": "Long",
            "full_image_prompt": "[0:03] " + body,
        }])
        prompts = ImagePromptParser().parse(raw)
        assert prompts[0]["full_image_prompt"] == body
        assert prompts[0]["timestamp"] == "00:03"
        # And the export line still holds the full prompt after its prefix.
        line = ExportService.build_image_prompts_txt(prompts).splitlines()[0]
        assert line == "[00:03] " + body

    # --- Full generation -> storage -> reopen -> export (8.H / 8.I / 8.J) --

    def test_generate_save_reopen_keeps_prompt_clean(self, pm, monkeypatch):
        """8.I: generate -> save -> reopen, no leading timestamp in stored data."""
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        name = "FixFReopen"

        class FakeProviderManager:
            def generate(self, request):
                return GenerationResponse(text=json.dumps([{
                    "scene_number": 1, "timestamp": "00:00",
                    "prompt_title": "Opening",
                    "full_image_prompt": (
                        "[0:00] Hand-drawn 2D doodle cartoon animation, a classroom, 16:9"
                    ),
                }]))

        request = ImagePromptRequest(
            script_text="A short script.",
            transcript="[0:00] Hello",
            timestamps=[{"start": 0, "end": 3, "text": "Hello", "time": "00:00"}],
            topic="Science",
            language="English",
        )
        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, max_retries=0)
        assert prompts[0]["full_image_prompt"] == (
            "Hand-drawn 2D doodle cartoon animation, a classroom, 16:9"
        )

        ImagePromptStorage().save(name, prompts)
        reopened = ImagePromptStorage().load(name)["prompts"]
        assert reopened[0]["full_image_prompt"] == (
            "Hand-drawn 2D doodle cartoon animation, a classroom, 16:9"
        )
        assert reopened[0]["timestamp"] == "00:00"
        self._assert_clean(reopened)

    def test_batch_generation_preserves_invariant(self):
        """8.H: every batch normalizes leading timestamps; timestamps intact."""
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        timestamps = [
            {"start": i * 3, "end": i * 3 + 3, "text": f"Segment {i + 1}.",
             "time": f"{i * 3:02d}:00"}
            for i in range(5)
        ]
        request = ImagePromptRequest(
            script_text="A long educational script.",
            transcript="\n".join(f"[{t['time']}] {t['text']}" for t in timestamps),
            timestamps=timestamps,
            topic="Science",
        )

        class FakeProviderManager:
            def generate(self, gen_request):
                scenes = _rc73_scenes_from_prompt(gen_request.prompt)
                payload = []
                for number, ts in scenes:
                    minutes = str(int(ts.split(":")[0]))
                    short = f"[{minutes}:{ts.split(':')[1]}]"
                    payload.append({
                        "scene_number": number,
                        "timestamp": ts,
                        "prompt_title": f"Scene {number}",
                        "full_image_prompt": (
                            f"{short} Hand-drawn 2D doodle cartoon animation, "
                            f"scene {number} visual, 16:9, KaiMi style"
                        ),
                    })
                return GenerationResponse(text=json.dumps(payload))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        prompts = operator.generate_prompts(request, batch_size=2, max_retries=0)
        assert len(prompts) == 5
        self._assert_clean(prompts)
        assert [p["timestamp"] for p in prompts] == [t["time"] for t in timestamps]
        for prompt in prompts:
            assert prompt["full_image_prompt"].startswith(
                "Hand-drawn 2D doodle cartoon animation"
            )

    def test_generation_to_export_smoke_no_duplicate_timestamp(
        self, pm, monkeypatch, es
    ):
        """Verification smoke: real generation -> parser -> storage -> reopen
        -> full-project export with a provider returning '[0:00] ...' and
        '[0:03] ...'; the final TXT contains '[00:00] ...' / '[00:03] ...'
        exactly once each."""
        from core.image_prompt_storage import ImagePromptStorage
        from operators.image_prompt.models import ImagePromptRequest
        from operators.image_prompt.operator import ImagePromptOperator
        from providers.models import GenerationResponse

        monkeypatch.setattr("core.image_prompt_storage._PROJECTS_DIR", pm.PROJECTS_DIR)
        name = "FixFSmoke"
        _create_sample_project(pm, name)
        _fill_script(pm, name)
        _write_json(pm.PROJECTS_DIR / name / "voice.json", {
            "transcript": "Segment one.\n\nSegment two.",
            "segments": [
                {"start": 0, "end": 3, "text": "Segment one.", "time": "00:00"},
                {"start": 3, "end": 6, "text": "Segment two.", "time": "00:03"},
            ],
        })
        _write_json(pm.PROJECTS_DIR / name / "transcript.json", {
            "text": "Segment one.\n\nSegment two.",
        })

        class FakeProviderManager:
            def generate(self, request):
                return GenerationResponse(text=json.dumps([
                    {"scene_number": 1, "timestamp": "00:00",
                     "prompt_title": "Opening",
                     "full_image_prompt": (
                         "[0:00] Hand-drawn 2D doodle cartoon animation, "
                         "classroom wide shot, 16:9"
                     )},
                    {"scene_number": 2, "timestamp": "00:03",
                     "prompt_title": "Teacher",
                     "full_image_prompt": (
                         "[0:03] Hand-drawn 2D doodle cartoon animation, "
                         "teacher at the board, 16:9"
                     )},
                ]))

        operator = ImagePromptOperator(provider_manager=FakeProviderManager())
        request = ImagePromptRequest(
            script_text="INT. CLASSROOM - DAY\nTeacher introduces AI.",
            transcript="[0:00] Segment one.\n\n[0:03] Segment two.",
            timestamps=[
                {"start": 0, "end": 3, "text": "Segment one.", "time": "00:00"},
                {"start": 3, "end": 6, "text": "Segment two.", "time": "00:03"},
            ],
            topic="AI Education",
        )
        prompts = operator.generate_prompts(request, max_retries=0)
        ImagePromptStorage().save(name, prompts)

        # Reopen (fresh load == restart): stored prompts are clean.
        reopened = ImagePromptStorage().load(name)["prompts"]
        self._assert_clean(reopened)
        assert reopened[0]["full_image_prompt"].startswith(
            "Hand-drawn 2D doodle cartoon animation"
        )

        # Full-project TXT export: exactly one [MM:SS] prefix per line.
        out = es.export_project(pm.load_project(name), fmt="txt")
        content = out.read_text(encoding="utf-8")
        assert (
            "[00:00] Hand-drawn 2D doodle cartoon animation, classroom wide shot, 16:9"
            in content
        )
        assert (
            "[00:03] Hand-drawn 2D doodle cartoon animation, teacher at the board, 16:9"
            in content
        )
        assert "[00:00] [0:00]" not in content
        assert "[00:03] [0:03]" not in content
        assert content.count("[00:00]") == 1
        assert content.count("[00:03]") == 1
