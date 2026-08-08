# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Voice selection dialog (RC-1).

The full voice library lives here instead of on the Voice page. The dialog
offers a search box, a Recommended section, and an All Voices section. Every
card shows the voice name, description, language, a Preview button and a
Select button; double-clicking a card selects it too. Selecting a voice
emits :attr:`voice_selected` and closes the dialog.

The dialog itself is UI-only. Preview generation and playback are delegated
back to the Voice page through :attr:`preview_requested`, so the existing
preview system is reused as-is.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.theme import Fonts
from ..theme_pyside import ThemeManager
from ..widgets import ModernButton, MutedLabel, SearchInput
from . import _dialog_styles


class _DialogVoiceCard(QFrame):
    """A single voice card inside the selection dialog."""

    preview_requested = Signal(str)
    select_requested = Signal(str)

    def __init__(self, voice_id, name, description, language, selected,
                 parent=None):
        super().__init__(parent)
        self.voice_id = voice_id
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        c = ThemeManager.instance().colors()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        header.addWidget(self.name_label)
        header.addStretch()
        self.selected_badge = QLabel("Selected")
        self.selected_badge.setStyleSheet(
            f"{Fonts.tiny(c.SUCCESS)} padding: 2px 8px; border-radius: 6px; "
            f"background-color: {c.SUCCESS_LIGHT};"
        )
        self.selected_badge.setVisible(False)
        header.addWidget(self.selected_badge)
        layout.addLayout(header)

        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        self.lang_label = QLabel(language)
        self.lang_label.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)}")
        layout.addWidget(self.lang_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.preview_btn = ModernButton("Preview", primary=False)
        self.preview_btn.clicked.connect(
            lambda: self.preview_requested.emit(self.voice_id)
        )
        btn_row.addWidget(self.preview_btn)

        self.select_btn = ModernButton("Select", primary=True)
        self.select_btn.clicked.connect(
            lambda: self.select_requested.emit(self.voice_id)
        )
        btn_row.addWidget(self.select_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.set_selected(selected)

    def set_selected(self, selected: bool):
        c = ThemeManager.instance().colors()
        if selected:
            self.setStyleSheet(
                f"QFrame#card {{ border: 1px solid {c.PRIMARY}; "
                f"background-color: {c.CARD}; }}"
            )
            self.selected_badge.setVisible(True)
            self.select_btn.setText("Selected")
            self.select_btn.setEnabled(False)
        else:
            self.setStyleSheet("")
            self.selected_badge.setVisible(False)
            self.select_btn.setText("Select")
            self.select_btn.setEnabled(True)

    def mouseDoubleClickEvent(self, event):
        self.select_requested.emit(self.voice_id)
        super().mouseDoubleClickEvent(event)


class VoiceSelectionDialog(QDialog):
    """Modal voice picker used by the Voice page.

    Args:
        current_voice_id: The voice selected before the dialog opened; its
            card is shown with a Selected indicator so the previous choice
            is always remembered.
        recommended: List of ``(voice_id, name, description, language)``
            tuples for the Recommended section.
        remaining: List of ``(voice_id, name, description, language)``
            tuples for the All Voices section.

    Signals:
        preview_requested: Emitted with a voice_id when the user asks to
            preview a voice. The owning page performs the generation.
        voice_selected: Emitted with a voice_id when the user selects a
            voice; the dialog then closes.
    """

    preview_requested = Signal(str)
    voice_selected = Signal(str)

    _GRID_COLUMNS = 3

    def __init__(self, current_voice_id, recommended, remaining, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a Voice")
        self.setMinimumSize(760, 640)
        self.setModal(True)
        self.setStyleSheet(_dialog_styles())
        self._selected_voice_id = current_voice_id
        self._recommended = list(recommended)
        self._remaining = list(remaining)
        self._voice_cards = {}
        self._build()
        self._rebuild()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        c = ThemeManager.instance().colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Choose a Voice")
        title.setStyleSheet(f"{Fonts.css(20, '600', c.TEXT)}")
        layout.addWidget(title)

        subtitle = QLabel(
            "Pick the narrator for this project. Preview any voice before choosing."
        )
        subtitle.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        layout.addWidget(subtitle)

        self.voice_search = SearchInput(
            "Search voices by name, description, or language..."
        )
        self.voice_search.textChanged.connect(self._on_search)
        layout.addWidget(self.voice_search)

        # One continuous scroll area for the whole library (RC-6.1 Part 5).
        # Recommended cards stay pinned at the top, followed by All Voices;
        # only this scroll area scrolls — no nested scrollbars.
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QScrollArea.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.content_scroll, 1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        rec_header = QHBoxLayout()
        rec_header.setSpacing(8)
        rec_title = QLabel("Recommended")
        rec_title.setStyleSheet(f"{Fonts.caption_bold(c.TEXT)}")
        rec_header.addWidget(rec_title)
        self.recommended_count = MutedLabel("")
        rec_header.addWidget(self.recommended_count)
        rec_header.addStretch()
        content_layout.addLayout(rec_header)

        self.recommended_container = QWidget()
        self.recommended_grid = QGridLayout(self.recommended_container)
        self.recommended_grid.setContentsMargins(0, 0, 0, 0)
        self.recommended_grid.setSpacing(10)
        content_layout.addWidget(self.recommended_container)

        all_header = QHBoxLayout()
        all_header.setSpacing(8)
        all_title = QLabel("All Voices")
        all_title.setStyleSheet(f"{Fonts.caption_bold(c.TEXT)}")
        all_header.addWidget(all_title)
        self.all_voices_count = MutedLabel("")
        all_header.addWidget(self.all_voices_count)
        all_header.addStretch()
        content_layout.addLayout(all_header)

        self.all_voices_container = QWidget()
        self.all_voices_grid = QGridLayout(self.all_voices_container)
        self.all_voices_grid.setContentsMargins(0, 0, 0, 0)
        self.all_voices_grid.setSpacing(10)
        content_layout.addWidget(self.all_voices_container)

        content_layout.addStretch()
        self.content_scroll.setWidget(content)

        hint = MutedLabel("Double-click a voice or click Select to choose it.")
        layout.addWidget(hint)

    # ------------------------------------------------------------------
    # Library rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(name, description, language, query):
        if not query:
            return True
        haystack = f"{name} {description} {language}".lower()
        return query in haystack

    def _on_search(self, _text):
        self._rebuild()

    def _rebuild(self):
        query = self.voice_search.text().strip().lower()
        self._clear_layout(self.recommended_grid)
        self._clear_layout(self.all_voices_grid)
        self._voice_cards = {}

        recommended_count = 0
        for voice_id, name, description, language in self._recommended:
            if not self._matches(name, description, language, query):
                continue
            self._add_card(
                self.recommended_grid, voice_id, name, description, language
            )
            recommended_count += 1

        remaining_count = 0
        for voice_id, name, description, language in self._remaining:
            if not self._matches(name, description, language, query):
                continue
            self._add_card(
                self.all_voices_grid, voice_id, name, description, language
            )
            remaining_count += 1

        self.recommended_count.setText(
            f"{recommended_count} shown \u00b7 {len(self._recommended)} total"
        )
        self.all_voices_count.setText(
            f"{remaining_count} shown \u00b7 {len(self._remaining)} available"
        )
        self._sync_selected()

    def _add_card(self, grid, voice_id, name, description, language):
        card = _DialogVoiceCard(
            voice_id,
            name,
            description,
            language,
            selected=(voice_id == self._selected_voice_id),
        )
        card.preview_requested.connect(self.preview_requested)
        card.select_requested.connect(self._select_voice)
        self._voice_cards[voice_id] = card
        index = grid.count()
        grid.addWidget(card, index // self._GRID_COLUMNS, index % self._GRID_COLUMNS)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ------------------------------------------------------------------
    # Selection / preview state
    # ------------------------------------------------------------------

    def _sync_selected(self):
        for voice_id, card in self._voice_cards.items():
            card.set_selected(voice_id == self._selected_voice_id)

    def _select_voice(self, voice_id):
        """Select a voice, notify the parent, and close the dialog."""
        self._selected_voice_id = voice_id
        self._sync_selected()
        self.voice_selected.emit(voice_id)
        self.accept()

    def set_preview_loading(self, voice_id, loading: bool):
        """Show/hide the Generating state on a card's Preview button."""
        card = self._voice_cards.get(voice_id)
        if card is None:
            return
        card.preview_btn.setText("Generating..." if loading else "Preview")
        card.preview_btn.setEnabled(not loading)
