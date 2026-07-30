from PySide6.QtCore import QObject, Signal


class PipelineEvents(QObject):
    stage_started = Signal(str, str)
    stage_completed = Signal(str, str)
    stage_failed = Signal(str, str, str)
    project_updated = Signal(str)
    project_created = Signal(str)
    project_deleted = Signal(str)
    export_completed = Signal(str, str)
    assets_changed = Signal(str)
    health_changed = Signal(str)


_pipeline_events_instance = None


def get_pipeline_events() -> PipelineEvents:
    global _pipeline_events_instance
    if _pipeline_events_instance is None:
        _pipeline_events_instance = PipelineEvents()
    return _pipeline_events_instance
