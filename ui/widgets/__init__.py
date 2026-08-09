import time

from PySide6.QtCore import (
    Property,
    QAbstractAnimation,
    QByteArray,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPixmap, QPainter

from ..theme_pyside import ThemeManager
from core.theme import Fonts


def clear_layout(layout):
    """Remove every widget, nested layout, and spacer from a ``QLayout``.

    Shared teardown helper for pages that rebuild their content on theme or
    data changes. Unlike a loop over ``item.widget()``, this also removes
    nested sub-layouts (e.g. grids added via ``addLayout``), so rebuilds
    never leak stale widgets that keep old theme colors.
    """
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        else:
            child = item.layout()
            if child is not None:
                clear_layout(child)
        # spacer items carry neither a widget nor a layout; dropping the
        # item (takeAt) is all that is needed.


def rebuild_page_layout(page):
    """Dispose a widget's root layout so ``_build()`` can install a fresh one.

    A ``QWidget`` accepts only one layout manager; calling
    ``QVBoxLayout(page)`` again would silently orphan the second layout and
    its widgets would never be shown. Pages that rebuild their whole content
    (e.g. the Dashboard on theme/data changes) must dispose the old layout
    first — this helper clears every widget and nested layout, then destroys
    the layout synchronously so the next ``_build()`` installs cleanly.
    """
    layout = page.layout()
    if layout is None:
        return
    clear_layout(layout)
    try:
        from shiboken6 import delete as _sip_delete
    except ImportError:  # pragma: no cover — shiboken6 ships with PySide6
        layout.deleteLater()
        return
    _sip_delete(layout)


class IconProvider:
    """Single source of truth for all application icons.
    Each icon is an SVG string rendered to QPixmap at requested size/color.
    Usage: icon = IconProvider.icon("dashboard")  # returns QIcon
           pixmap = IconProvider.pixmap("script", 20, "#22C55E")
           label = IconProvider.icon_label("voice", 16)
    """

    _cache = {}

    _SVG = {
        "dashboard": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="3" y="3" width="7" height="7" rx="1"/>'
            '<rect x="14" y="3" width="7" height="7" rx="1"/>'
            '<rect x="3" y="14" width="7" height="7" rx="1"/>'
            '<rect x="14" y="14" width="7" height="7" rx="1"/>'
            '</svg>'
        ),
        "projects": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
            '</svg>'
        ),
        "assets": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
            '<path d="M12 11v6"/>'
            '<path d="M9 14l3-3 3 3"/>'
            '</svg>'
        ),
        "script": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
            '<polyline points="14 2 14 8 20 8"/>'
            '<line x1="9" y1="13" x2="15" y2="13"/>'
            '<line x1="9" y1="17" x2="13" y2="17"/>'
            '</svg>'
        ),
        "voice": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="9" y="2" width="6" height="12" rx="3"/>'
            '<path d="M5 10a7 7 0 0 0 14 0"/>'
            '<line x1="12" y1="19" x2="12" y2="22"/>'
            '</svg>'
        ),
        "image": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="3" y="3" width="18" height="18" rx="2"/>'
            '<circle cx="8.5" cy="8.5" r="1.5"/>'
            '<path d="M21 15l-5-5L5 21"/>'
            '</svg>'
        ),
        "export": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
            '<polyline points="7 10 12 15 17 10"/>'
            '<line x1="12" y1="15" x2="12" y2="3"/>'
            '</svg>'
        ),
        "settings": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="3"/>'
            '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
            '</svg>'
        ),
        "add": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"/>'
            '<line x1="12" y1="8" x2="12" y2="16"/>'
            '<line x1="8" y1="12" x2="16" y2="12"/>'
            '</svg>'
        ),
        "storage": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
            '<path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>'
            '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'
            '</svg>'
        ),
        "check_circle": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"/>'
            '<polyline points="9 12 11 14 15 10"/>'
            '</svg>'
        ),
        "clock": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"/>'
            '<polyline points="12 6 12 12 16 14"/>'
            '</svg>'
        ),
        "check": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="3" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="4 12 10 18 20 6"/>'
            '</svg>'
        ),
        "circle": (
            '<svg viewBox="0 0 24 24" fill="{color}" stroke="none">'
            '<circle cx="12" cy="12" r="6"/>'
            '</svg>'
        ),
        "circle_empty": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2">'
            '<circle cx="12" cy="12" r="6"/>'
            '</svg>'
        ),
        "warning": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
            '<line x1="12" y1="9" x2="12" y2="13"/>'
            '<line x1="12" y1="17" x2="12.01" y2="17"/>'
            '</svg>'
        ),
        "document": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
            '<polyline points="14 2 14 8 20 8"/>'
            '</svg>'
        ),
        "external": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
            '<polyline points="15 3 21 3 21 9"/>'
            '<line x1="10" y1="14" x2="21" y2="3"/>'
            '</svg>'
        ),
        "folder_open": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
            '<path d="M6 21l4-8 4 4 4-6 4 10"/>'
            '</svg>'
        ),
    }

    @classmethod
    def _build_svg(cls, name: str, color: str = "#94A3B8") -> str:
        svg_template = cls._SVG.get(name)
        if not svg_template:
            return ""
        return svg_template.format(color=color)

    @classmethod
    def pixmap(cls, name: str, size: int = 20, color: str = None) -> QPixmap:
        if color is None:
            c = ThemeManager.instance().colors()
            color = c.TEXT_SECONDARY
        svg_data = cls._build_svg(name, color)
        if not svg_data:
            return QPixmap()
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap

    @classmethod
    def icon(cls, name: str, size: int = 20, color: str = None) -> QIcon:
        return QIcon(cls.pixmap(name, size, color))

    @classmethod
    def icon_label(cls, name: str, size: int = 20, color: str = None) -> QLabel:
        label = QLabel()
        label.setPixmap(cls.pixmap(name, size, color))
        label.setFixedSize(size, size)
        return label


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

        self.setFixedHeight(36)
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
        self._outer_layout.setContentsMargins(16, 16, 16, 16)
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


class IndeterminateBar(QWidget):
    """Animated indeterminate 'processing' bar for AI generation stages.

    Paints a soft moving highlight across a rounded track instead of a static
    zero-progress bar. The animation runs only while ``start()`` is in effect
    and stops immediately on ``stop()`` (or when the widget is hidden), so no
    CPU is consumed after generation ends. Colors are read from the active
    theme on every paint, so runtime theme switches need no rebuild (RC-7.1).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(1400)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self.update)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value

    offset = Property(float, _get_offset, _set_offset)

    def start(self):
        """Begin the marquee animation (no-op when already running)."""
        if self._anim.state() != QAbstractAnimation.State.Running:
            self._anim.start()

    def stop(self):
        """Freeze the animation immediately."""
        self._anim.stop()
        self._offset = 0.0
        self.update()

    def is_animating(self) -> bool:
        """True while the marquee is actively moving."""
        return self._anim.state() == QAbstractAnimation.State.Running

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            painter.end()
            return
        c = ThemeManager.instance().colors()
        radius = height / 2.0

        # Track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c.INPUT_BG))
        painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)

        # Moving highlight: a comet that sweeps left -> right. Three copies
        # spaced one period apart keep the marquee continuous (a band exits
        # right as its twin enters from the left).
        band_w = max(40.0, width * 0.3)
        span = width + band_w
        x = -band_w + self._offset * span
        base = QColor(c.PRIMARY)

        def _draw_band(x0):
            if x0 + band_w < 0 or x0 > width:
                return
            grad = QLinearGradient(x0, 0, x0 + band_w, 0)
            grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 0))
            grad.setColorAt(0.45, QColor(base.red(), base.green(), base.blue(), 70))
            grad.setColorAt(0.7, base)
            grad.setColorAt(0.85, QColor(base.red(), base.green(), base.blue(), 120))
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(x0, 0, band_w, height), radius, radius)

        _draw_band(x)
        _draw_band(x + span)
        _draw_band(x - span)
        painter.end()


class ModernProgressBar(QWidget):
    """Modern animated determinate progress bar (FIX E).

    A custom-painted rounded bar whose fill always reflects the REAL value.
    When the value changes the fill eases smoothly toward the new value (a
    gentle interpolation that never overshoots), and while the bar is visible
    a soft highlight sweeps across the filled region only — clipped so the
    animation can never represent progress beyond the stored value. Theme
    tokens are read on every paint, so runtime theme switches need no
    rebuild. Animation runs only while the widget is visible and stops
    immediately when hidden (no idle CPU), matching IndeterminateBar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self._min = 0
        self._max = 100
        self._value = 0          # the real value, never animated upward
        self._display = 0.0      # eased fill position (0..value)
        self._shimmer = 0.0      # highlight sweep offset (0..1)

        # Eased fill transition: display eases toward the real value so the
        # fill breathes smoothly between updates without overshooting.
        self._fill_anim = QPropertyAnimation(self, b"display", self)
        self._fill_anim.setDuration(350)
        self._fill_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fill_anim.valueChanged.connect(self.update)

        # Soft highlight sweeping across the FILLED region only. Driven by a
        # modest 40 ms timer (~25 fps) rather than a high-frequency animation
        # so a page full of static cards never consumes significant CPU — the
        # sweep still reads as a gentle sheen without hammering the paint.
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(40)
        self._shimmer_timer.timeout.connect(self._tick_shimmer)
        self._shimmer_started = 0.0

    # -- Qt properties driving the paint -----------------------------------
    def _get_display(self):
        return self._display

    def _set_display(self, value: float) -> None:
        # Clamp to the real value: the fill can only ever represent up to
        # the last stored value, so no animation can fabricate progress.
        self._display = max(0.0, min(float(self._value), value))
        self.update()

    display = Property(float, _get_display, _set_display)

    # -- QProgressBar-compatible API ---------------------------------------
    def setRange(self, minimum: int, maximum: int):
        self._min = int(minimum)
        self._max = int(maximum)

    def setValue(self, value: int):
        value = max(self._min, min(self._max, int(value)))
        self._value = value
        self._fill_anim.stop()
        self._fill_anim.setStartValue(self._display)
        self._fill_anim.setEndValue(float(value))
        self._fill_anim.start()
        self._sync_shimmer()
        self.update()

    def value(self) -> int:
        return self._value

    def setTextVisible(self, visible: bool):
        pass  # text is rendered by the caller's percentage label, not the bar

    def stop(self):
        """Freeze all animation immediately (idempotent).

        Also syncs the eased fill to the real value so a bar that is stopped
        mid-transition never renders a partial fill that disagrees with its
        stored progress (FIX E).
        """
        self._fill_anim.stop()
        self._shimmer_timer.stop()
        self._display = float(self._value)
        self._shimmer = 0.0
        self.update()

    def _tick_shimmer(self):
        """Advance the highlight sweep phase once per timer tick."""
        elapsed = time.monotonic() - self._shimmer_started
        self._shimmer = (elapsed / 2.4) % 1.0
        self.update()

    def _sync_shimmer(self):
        active = self.isVisible() and self._value > 0
        if active and not self._shimmer_timer.isActive():
            self._shimmer_started = time.monotonic()
            self._shimmer_timer.start()
        elif not active and self._shimmer_timer.isActive():
            self._shimmer_timer.stop()
            self._shimmer = 0.0

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_shimmer()

    def hideEvent(self, event):
        self._shimmer_timer.stop()
        self._fill_anim.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            painter.end()
            return
        c = ThemeManager.instance().colors()
        radius = height / 2.0

        # Track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c.INPUT_BG))
        painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)

        # Fill — width derives from the eased display, always <= real value.
        fill_w = width * (self._display / max(1, self._max - self._min))
        if fill_w <= 0:
            painter.end()
            return
        fill_rect = QRectF(0, 0, min(fill_w, width), height)
        painter.setBrush(QColor(c.PRIMARY))
        painter.drawRoundedRect(fill_rect, radius, radius)

        # Soft highlight sweeping across the filled region only — clipped so
        # it can never represent progress beyond the real value.
        if self._shimmer_timer.isActive():
            band_w = max(16.0, fill_w * 0.3)
            span = fill_w + band_w
            x = -band_w + self._shimmer * span
            painter.save()
            painter.setClipRect(fill_rect)
            grad = QLinearGradient(x, 0, x + band_w, 0)
            base = QColor(c.PRIMARY)
            grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 0))
            grad.setColorAt(0.5, QColor(base.red(), base.green(), base.blue(), 120))
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
            painter.setBrush(grad)
            painter.drawRect(QRectF(x, 0, band_w, height))
            painter.restore()
        painter.end()


class ProgressWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.status_label)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)
        self.progress_bar = ModernProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        bar_row.addWidget(self.progress_bar, 1)

        self.indeterminate_bar = IndeterminateBar()
        self.indeterminate_bar.setVisible(False)
        bar_row.addWidget(self.indeterminate_bar, 1)

        self.percentage_label = QLabel("0%")
        self.percentage_label.setObjectName("muted")
        self.percentage_label.setFixedWidth(36)
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

    def setVisible(self, visible: bool):
        """Stop the marquee whenever the widget is hidden.

        ``hideEvent`` only fires after a widget has been shown, so a page
        hiding the progress widget before it was ever visible would otherwise
        leave the animation running (RC-7.1).
        """
        if not visible:
            self.indeterminate_bar.stop()
        super().setVisible(visible)

    def hideEvent(self, event):
        """Never leave the marquee animating on a hidden widget (RC-7.1)."""
        self.indeterminate_bar.stop()
        super().hideEvent(event)

    def stop(self):
        """Stop all progress animation immediately (idempotent).

        Called by pages when a generation succeeds, fails, or is cancelled so
        the marquee and the determinate fill transition never keep ticking
        after the run has ended (RC-7.1 / FIX E).
        """
        self.indeterminate_bar.stop()
        self.progress_bar.stop()

    def set_progress(self, pct, status="", step="", eta=""):
        self.indeterminate_bar.stop()
        self.indeterminate_bar.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(pct)
        self.percentage_label.setText(f"{pct}%")
        if status:
            self.status_label.setText(status)
        if step:
            self.step_label.setText(step)
        if eta:
            self.eta_label.setText(f"Estimated Time: {eta}")

    def set_elapsed(self, seconds: float):
        """Show elapsed wall-clock time in the ETA slot (e.g. 'Elapsed: 01:23').

        Used by the Voice page while generation runs: the elapsed timer ticks
        every second so the user always sees how long the stage has taken.
        """
        minutes, secs = divmod(max(0, int(seconds)), 60)
        self.eta_label.setText(f"Elapsed: {minutes:02d}:{secs:02d}")

    def set_hint(self, text: str):
        """Show a reassurance hint below the progress bar."""
        self.step_label.setText(text)

    def set_indeterminate(self, status="", step=""):
        """Switch to the animated processing bar with stage text (RC-7).

        Used when exact progress cannot be measured: the marquee animates
        instead of showing a fabricated percentage (RC-7.1 polish).
        """
        self.progress_bar.setVisible(False)
        self.indeterminate_bar.setVisible(True)
        self.indeterminate_bar.start()
        self.percentage_label.setText("")
        if status:
            self.status_label.setText(status)
        if step:
            self.step_label.setText(step)

    def set_determinate(self):
        """Restore the determinate 0-100 bar and stop any animation."""
        self.indeterminate_bar.stop()
        self.indeterminate_bar.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

    def show_error(self, message: str):
        """Switch the status line to an error state (red, bold)."""
        self.set_determinate()
        c = ThemeManager.instance().colors()
        self.progress_bar.setValue(0)
        self.percentage_label.setText("0%")
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {c.ERROR}; font-weight: bold;")
        self.step_label.setText("")
        self.eta_label.setText("")

    def show_complete(self, message="Complete"):
        self.set_determinate()
        self.progress_bar.setValue(100)
        self.percentage_label.setText("100%")
        c = ThemeManager.instance().colors()
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self.step_label.setText("")
        self.eta_label.setText("")

    def reset(self):
        self.set_determinate()
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
        layout.setSpacing(6)

        self.icon = QLabel(icon_text)
        font = self.icon.font()
        font.setPointSize(14)
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
        self.setFixedHeight(36)
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
        self._color_explicit = color is not None
        self._bg_explicit = bg is not None
        c = ThemeManager.instance().colors()
        self._color = color or c.PRIMARY
        self._bg = bg or c.PRIMARY_LIGHT
        self._update_style()

    def _update_style(self):
        c = ThemeManager.instance().colors()
        self.setStyleSheet(
            f"{Fonts.tiny(self._color)} padding: 2px 8px; "
            f"border-radius: 6px; background-color: {self._bg};"
        )

    def update_colors(self, color: str, bg: str):
        self._color = color
        self._bg = bg
        self._color_explicit = True
        self._bg_explicit = True
        self._update_style()

    def refresh_theme(self):
        """Re-derive theme-dependent colors after a runtime theme switch.

        Explicitly-set colors (constructor args or ``update_colors``) are
        kept as-is; defaults re-resolve so static badges never render
        Dark-theme PRIMARY on a Light background (Light-theme contrast
        regression).
        """
        c = ThemeManager.instance().colors()
        if not self._color_explicit:
            self._color = c.PRIMARY
        if not self._bg_explicit:
            self._bg = c.PRIMARY_LIGHT
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
        layout.setSpacing(2)

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

        self._icon_name = icon
        self.icon_label = None
        self.title_label = None
        self.desc_label = None

        if icon:
            c = ThemeManager.instance().colors()
            self.icon_label = IconProvider.icon_label(icon, 48, c.TEXT_MUTED)
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

    def refresh_theme(self):
        """Re-apply the current theme tokens to icon, title, and description.

        Called by pages on theme change so empty states never keep colors
        baked at construction (Light-theme contrast regression).
        """
        c = ThemeManager.instance().colors()
        if self.icon_label is not None and self._icon_name:
            self.icon_label.setPixmap(
                IconProvider.pixmap(self._icon_name, 48, c.TEXT_MUTED)
            )
        if self.title_label is not None:
            self.title_label.setStyleSheet(f"{Fonts.section_title(c.TEXT)}")
        if self.desc_label is not None:
            self.desc_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
