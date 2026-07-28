from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor

from ..theme_pyside import ThemeManager
from core.theme import Fonts


class ModernButton(QPushButton):

    def __init__(self, text="", primary=True, danger=False, ghost=False, parent=None):
        super().__init__(text, parent)
        self._loading = False

        if ghost:
            self.setObjectName("ghost")
        elif danger:
            self.setObjectName("danger")
        elif primary:
            self.setObjectName("primary")
        else:
            self.setObjectName("secondary")

        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def set_loading(self, loading: bool):
        self._loading = loading
        if loading:
            self.setText("")
            self.setEnabled(False)
        else:
            self.setEnabled(True)


class ModernCard(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 2)
        c = ThemeManager.instance().colors()
        shadow.setColor(QColor(0, 0, 0, 40) if ThemeManager.instance().is_dark() else QColor(0, 0, 0, 15))
        self.setGraphicsEffect(shadow)

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout = QVBoxLayout()
        self._outer_layout.addLayout(self.content_layout)

    def enterEvent(self, event):
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setOffset(0, 4)
            shadow.setBlurRadius(40)
        c = ThemeManager.instance().colors()
        self.setStyleSheet(
            f"QFrame#card {{ border: 1px solid {c.PRIMARY}; background-color: {c.CARD}; }}"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setOffset(0, 2)
            shadow.setBlurRadius(30)
        self.setStyleSheet("")
        super().leaveEvent(event)


class ProgressWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("")
        self.status_label.setObjectName("body")
        self.status_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.status_label)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        bar_row.addWidget(self.progress_bar, 1)

        self.percentage_label = QLabel("0%")
        self.percentage_label.setObjectName("body")
        self.percentage_label.setFixedWidth(44)
        self.percentage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bar_row.addWidget(self.percentage_label)
        layout.addLayout(bar_row)

        self.step_label = QLabel("")
        self.step_label.setObjectName("muted")
        self.step_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.step_label)

        self.eta_label = QLabel("")
        self.eta_label.setObjectName("muted")
        self.eta_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.eta_label)

    def set_progress(self, pct, status="", step="", eta=""):
        self.progress_bar.setValue(pct)
        self.percentage_label.setText(f"{pct}%")
        if status:
            self.status_label.setText(status)
        if step:
            self.step_label.setText(step)
        if eta:
            self.eta_label.setText(f"Estimated Time: {eta}")

    def show_complete(self, message="Complete"):
        self.progress_bar.setValue(100)
        self.percentage_label.setText("100%")
        c = ThemeManager.instance().colors()
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self.step_label.setText("")
        self.eta_label.setText("")

    def reset(self):
        self.progress_bar.setValue(0)
        self.percentage_label.setText("0%")
        self.status_label.setText("")
        self.status_label.setStyleSheet("")
        self.step_label.setText("")
        self.eta_label.setText("")


class IconLabel(QWidget):

    def __init__(self, icon_text="", label_text="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.icon = QLabel(icon_text)
        font = self.icon.font()
        font.setPointSize(16)
        self.icon.setFont(font)
        layout.addWidget(self.icon)

        self.label = QLabel(label_text)
        self.label.setObjectName("body")
        layout.addWidget(self.label, 1)

        layout.addStretch()


class HeaderLabel(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("title")
        self.setAttribute(Qt.WA_StyledBackground, True)


class SectionLabel(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("section")
        self.setAttribute(Qt.WA_StyledBackground, True)


class BodyLabel(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("body")
        self.setAttribute(Qt.WA_StyledBackground, True)


class MutedLabel(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("muted")
        self.setAttribute(Qt.WA_StyledBackground, True)


class CardTitle(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("card_title")
        self.setAttribute(Qt.WA_StyledBackground, True)


class SearchInput(QLineEdit):

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(40)
        self.setAttribute(Qt.WA_StyledBackground, True)


class AutosaveIndicator(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("All Changes Saved")
        self.setObjectName("muted")
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        c = ThemeManager.instance().colors()
        self.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 2px 8px;")

    def set_status(self, status: str):
        c = ThemeManager.instance().colors()
        if status == "Saving...":
            self.setStyleSheet(f"{Fonts.tiny(c.WARNING)} padding: 2px 8px;")
        elif status == "Save Failed":
            self.setStyleSheet(f"{Fonts.tiny(c.ERROR)} padding: 2px 8px;")
        else:
            color = c.SUCCESS if "Saved" in status else c.TEXT_MUTED
            self.setStyleSheet(f"{Fonts.tiny(color)} padding: 2px 8px;")
        self.setText(status)


class StatusBadge(QLabel):

    def __init__(self, text="", color=None, bg=None, parent=None):
        super().__init__(text, parent)
        c = ThemeManager.instance().colors()
        self._color = color or c.PRIMARY
        self._bg = bg or c.PRIMARY_LIGHT
        self._update_style()

    def _update_style(self):
        c = ThemeManager.instance().colors()
        self.setStyleSheet(
            f"{Fonts.caption_bold(self._color)} padding: 2px 10px; "
            f"border-radius: 8px; background-color: {self._bg};"
        )

    def update_colors(self, color: str, bg: str):
        self._color = color
        self._bg = bg
        self._update_style()


class PageTitle(QLabel):

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("title")
        self.setAttribute(Qt.WA_StyledBackground, True)


class SectionHeader(QWidget):

    def __init__(self, title="", description="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("section")
        self.title_label.setAttribute(Qt.WA_StyledBackground, True)
        layout.addWidget(self.title_label)

        if description:
            c = ThemeManager.instance().colors()
            self.desc_label = QLabel(description)
            self.desc_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
            layout.addWidget(self.desc_label)


class EmptyState(QWidget):

    def __init__(self, icon="", title="", description="", parent=None,
                 action_callback=None, action_text=""):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 32, 32, 32)

        if icon:
            self.icon_label = QLabel(icon)
            self.icon_label.setStyleSheet("font-size: 48px; background: transparent;")
            self.icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.icon_label)

        if title:
            self.title_label = QLabel(title)
            c = ThemeManager.instance().colors()
            self.title_label.setStyleSheet(f"{Fonts.section_title(c.TEXT)}")
            self.title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.title_label)

        if description:
            self.desc_label = QLabel(description)
            c = ThemeManager.instance().colors()
            self.desc_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
            self.desc_label.setAlignment(Qt.AlignCenter)
            self.desc_label.setWordWrap(True)
            layout.addWidget(self.desc_label)

        if action_text and action_callback:
            self.action_btn = ModernButton(action_text, primary=True)
            self.action_btn.clicked.connect(action_callback)
            layout.addWidget(self.action_btn, 0, Qt.AlignCenter)
