# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Professional About dialog for KaiMi Studio.

Displays the complete application identity from :mod:`core.version`:
name, description, version, build, engine/workflow/schema versions, author,
official email (with a copy button), and copyright.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.branding import logo_pixmap
from core.notifications import NotificationService
from core.theme import Fonts
from core.version import (
    APP_DESCRIPTION,
    APP_NAME,
    AUTHOR,
    BUILD,
    BUILD_DATE,
    COPYRIGHT,
    ENGINE_VERSION,
    OFFICIAL_EMAIL,
    RELEASE_CHANNEL,
    SCHEMA_VERSION,
    VERSION,
    WORKFLOW_VERSION,
)
from ..theme_pyside import ThemeManager
from ui.dialogs import _dialog_styles


class AboutDialog(QDialog):
    """Modal dialog presenting KaiMi Studio's application identity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(_dialog_styles())
        self._build()

    def _build(self):
        c = ThemeManager.instance().colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── Header (official logo lockup above the title) ─────────────
        logo_label = QLabel()
        logo_label.setPixmap(logo_pixmap(200))
        logo_label.setFixedSize(200, 200)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(logo_label)

        name = QLabel(APP_NAME)
        name.setStyleSheet(f"{Fonts.css(26, 'bold', c.PRIMARY)}")
        name.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)

        desc = QLabel(APP_DESCRIPTION)
        desc.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        channel = QLabel(f"{RELEASE_CHANNEL} \u2014 v{VERSION} \u2014 Build {BUILD}")
        channel.setStyleSheet(f"{Fonts.caption(c.TEXT_MUTED)}")
        channel.setAlignment(Qt.AlignCenter)
        layout.addWidget(channel)

        layout.addSpacing(4)

        # ── Metadata card ─────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(8)

        card_layout.addLayout(self._make_row("Version", VERSION))
        card_layout.addLayout(self._make_row("Build", BUILD))
        card_layout.addLayout(self._make_row("Engine", ENGINE_VERSION))
        card_layout.addLayout(self._make_row("Workflow", WORKFLOW_VERSION))
        card_layout.addLayout(self._make_row("Schema", SCHEMA_VERSION))
        card_layout.addLayout(self._make_row("Build Date", BUILD_DATE))
        card_layout.addLayout(self._make_row("Author", AUTHOR))
        card_layout.addLayout(self._make_email_row())

        layout.addWidget(card)

        copyright_lbl = QLabel(COPYRIGHT)
        copyright_lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)}")
        copyright_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_lbl)

        layout.addSpacing(4)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _make_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        """Two-column metadata row: muted label + value."""
        c = ThemeManager.instance().colors()
        row = QHBoxLayout()
        row.setSpacing(16)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"{Fonts.label(c.TEXT_MUTED)} min-width: 120px;")
        row.addWidget(lbl)

        value = QLabel(value_text)
        value.setStyleSheet(f"{Fonts.body(c.TEXT)}")
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(value)
        row.addStretch()
        return row

    def _make_email_row(self) -> QHBoxLayout:
        """Email row with an inline copy button."""
        c = ThemeManager.instance().colors()
        row = QHBoxLayout()
        row.setSpacing(16)

        lbl = QLabel("Official Email")
        lbl.setStyleSheet(f"{Fonts.label(c.TEXT_MUTED)} min-width: 120px;")
        row.addWidget(lbl)

        value = QLabel(OFFICIAL_EMAIL)
        value.setStyleSheet(f"{Fonts.body(c.TEXT)}")
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(value)
        row.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("secondary")
        copy_btn.setFixedHeight(36)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_email)
        row.addWidget(copy_btn)
        return row

    def _copy_email(self) -> None:
        """Copy the official email to the clipboard with user feedback."""
        QApplication.clipboard().setText(OFFICIAL_EMAIL)
        NotificationService.get().info("Official email copied to clipboard.")
