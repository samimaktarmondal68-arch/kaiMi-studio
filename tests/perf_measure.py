# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Performance measurement script for KaiMi Studio.

Measures startup time, project operations, search, and export performance.
Run standalone: python -m tests.perf_measure
"""

import json
import sys
import time
import tempfile
import shutil
from pathlib import Path

# Ensure project root is on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _measure(label: str, func, *args, **kwargs):
    t0 = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    return result, elapsed


def measure_startup():
    """Measure time to import all modules."""
    _, elapsed = _measure("module_imports", lambda: __import_all())
    return elapsed


def __import_all():
    import core.theme
    import core.version
    import core.settings
    import core.logger
    import core.workflow
    import core.project_manager
    import core.export_service
    import core.history_manager
    import core.notifications
    import core.shortcuts
    import core.task_manager
    import providers.provider_manager
    import providers.registry
    import providers.models
    import providers.exceptions


def measure_project_ops(tmp_dir: Path):
    """Measure project CRUD operations."""
    from core.project_manager import ProjectManager

    pm = ProjectManager()
    pm.PROJECTS_DIR = tmp_dir / "projects"
    pm.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # Create 50 projects
    _, t = _measure("create_50", lambda: [
        pm.create_project(f"PerfTest_{i:03d}", f"Topic {i}", "English", "Educational")
        for i in range(50)
    ])
    results["create_50_projects"] = t

    # List all
    _, t = _measure("list", pm.get_projects)
    results["list_projects"] = t

    # Search
    _, t = _measure("search", pm.search_projects, "PerfTest_025")
    results["search_single"] = t

    _, t = _measure("search_all", pm.search_projects, "PerfTest")
    results["search_all_50"] = t

    # Sort
    _, t = _measure("sort", pm.sort_projects, pm.get_projects(), "name")
    results["sort_projects"] = t

    # Duplicate
    _, t = _measure("duplicate", pm.duplicate_project, "PerfTest_000", "PerfTest_000_dup")
    results["duplicate_project"] = t

    # Delete
    _, t = _measure("delete", pm.delete_project, "PerfTest_000_dup")
    results["delete_project"] = t

    return results


def measure_export(tmp_dir: Path):
    """Measure export operations."""
    from core.project_manager import ProjectManager
    from core.export_service import ExportService

    pm = ProjectManager()
    pm.PROJECTS_DIR = tmp_dir / "projects"

    # Create a test project
    pm.create_project("ExportTest", "Test topic", "English", "Educational")
    project = pm.load_project("ExportTest")

    es = ExportService(pm)
    results = {}

    for fmt in ["txt", "markdown", "json", "zip", "docx", "pdf"]:
        try:
            _, t = _measure(f"export_{fmt}", es.export_project, project, fmt)
            results[f"export_{fmt}"] = t
        except Exception as e:
            results[f"export_{fmt}"] = f"ERROR: {e}"

    return results


def measure_search_50(tmp_dir: Path):
    """Dedicated search benchmark with 50 projects."""
    from core.project_manager import ProjectManager

    pm = ProjectManager()
    pm.PROJECTS_DIR = tmp_dir / "projects"
    pm.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(50):
        pm.create_project(f"SearchTest_{i:03d}", f"Topic about {i}", "English", "Educational")

    queries = ["SearchTest_025", "Search", "010", "Topic about 42"]
    results = {}
    for q in queries:
        _, t = _measure(f"search_{q}", pm.search_projects, q)
        results[f"search_{q}"] = t

    return results


def run_all():
    print("=" * 60)
    print("KaiMi Studio — Performance Report")
    print("=" * 60)

    # Startup
    t = measure_startup()
    print(f"\nModule imports:          {t:.3f}s")

    # Create temp dir for isolated tests
    tmp = Path(tempfile.mkdtemp(prefix="kaimi_perf_"))
    try:
        results = {}
        results["startup"] = t

        # Project ops
        proj_results = measure_project_ops(tmp)
        results.update(proj_results)
        print(f"\nCreate 50 projects:     {proj_results['create_50_projects']:.3f}s")
        print(f"List projects:          {proj_results['list_projects']:.3f}s")
        print(f"Search (single):        {proj_results['search_single']:.3f}s")
        print(f"Search (all 50):        {proj_results['search_all_50']:.3f}s")
        print(f"Sort projects:          {proj_results['sort_projects']:.3f}s")
        print(f"Duplicate project:      {proj_results['duplicate_project']:.3f}s")
        print(f"Delete project:         {proj_results['delete_project']:.3f}s")

        # Search benchmark
        search_results = measure_search_50(tmp)
        results.update(search_results)

        # Export
        export_results = measure_export(tmp)
        results.update(export_results)
        print(f"\nExport TXT:             {export_results.get('export_txt', 'N/A')}")
        print(f"Export Markdown:        {export_results.get('export_markdown', 'N/A')}")
        print(f"Export JSON:            {export_results.get('export_json', 'N/A')}")
        print(f"Export ZIP:             {export_results.get('export_zip', 'N/A')}")
        print(f"Export DOCX:            {export_results.get('export_docx', 'N/A')}")
        print(f"Export PDF:             {export_results.get('export_pdf', 'N/A')}")

        # Thresholds
        print("\n" + "=" * 60)
        print("Thresholds")
        print("=" * 60)
        checks = [
            ("Startup < 3s", t < 3.0),
            ("Create 50 projects < 5s", proj_results["create_50_projects"] < 5.0),
            ("Search < 2s", proj_results["search_all_50"] < 2.0),
            ("Sort < 1s", proj_results["sort_projects"] < 1.0),
            ("Export ZIP < 3s", str(export_results.get("export_zip", 0)).startswith("0.") or (isinstance(export_results.get("export_zip", 0), float) and export_results["export_zip"] < 3.0)),
        ]
        all_pass = True
        for label, passed in checks:
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_pass = False
            print(f"  [{status}] {label}")

        print(f"\nResult: {'ALL PASS' if all_pass else 'SOME FAILED'}")

        # Save report
        report_path = _root / "logs" / "performance_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nFull report saved: {report_path}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    run_all()
