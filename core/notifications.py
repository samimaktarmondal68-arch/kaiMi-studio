from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QGraphicsDropShadowEffect,
)

NOTIFICATION_WIDTH = 380
NOTIFICATION_MARGIN = 12
NOTIFICATION_SPACING = 8


class _ToastWidget(QFrame):
    def __init__(self, message, notification_type, parent=None):
        super().__init__(parent)
        from ui.theme_pyside import ThemeManager
        c = ThemeManager.instance().colors()

        self.setFixedWidth(NOTIFICATION_WIDTH)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        type_colors = {
            "success": (c.SUCCESS, "\u2714"),
            "warning": (c.WARNING, "\u26A0"),
            "error": (c.ERROR, "\u2716"),
            "info": (c.PRIMARY, "\u2139"),
        }
        accent, icon = type_colors.get(notification_type, type_colors["info"])

        self.setStyleSheet(
            f"background-color: {c.CARD}; "
            f"border: 1px solid {c.BORDER}; "
            f"border-radius: 12px;"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 16px; color: {accent}; background: transparent;")
        icon_lbl.setFixedWidth(24)
        layout.addWidget(icon_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet(f"font-size: 13px; color: {c.TEXT}; background: transparent;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl, 1)

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {c.TEXT_MUTED}; "
            f"border: none; font-size: 12px; border-radius: 12px; }}"
            f"QPushButton:hover {{ background-color: {c.HOVER}; color: {c.TEXT}; }}"
        )
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

        self._message = message
        self._dismissing = False

    def _dismiss(self):
        if self._dismissing:
            return
        self._dismissing = True
        parent = self.parent()
        if parent and hasattr(parent, '_remove_toast'):
            parent._remove_toast(self)


class ToastContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self._toasts = []

    def add_toast(self, message, notification_type, duration):
        toast = _ToastWidget(message, notification_type, self)
        toast.setVisible(False)
        self._toasts.append(toast)
        self._reposition()
        toast.setVisible(True)
        self._slide_in(toast)

        if duration > 0:
            QTimer.singleShot(duration, lambda t=toast: t._dismiss())

    def _remove_toast(self, toast):
        if toast not in self._toasts:
            return
        self._slide_out(toast)
        self._toasts.remove(toast)
        QTimer.singleShot(300, toast.deleteLater)
        self._reposition()

    def _slide_in(self, toast):
        toast.setMaximumHeight(0)
        toast.show()
        anim = QPropertyAnimation(toast, b"maximumHeight")
        anim.setDuration(300)
        anim.setStartValue(0)
        anim.setEndValue(80)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

    def _slide_out(self, toast):
        anim = QPropertyAnimation(toast, b"maximumHeight")
        anim.setDuration(250)
        anim.setStartValue(80)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.start()

    def _reposition(self):
        y = 0
        for toast in self._toasts:
            toast.move(0, y)
            y += toast.height() + NOTIFICATION_SPACING

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()


class NotificationService:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._parent = None
        self._container = None

    def set_parent(self, parent):
        self._parent = parent
        if self._container:
            self._container.deleteLater()
        self._container = ToastContainer(parent)
        self._container.setVisible(False)
        self._reposition()

    def _reposition(self):
        if not self._parent or not self._container:
            return
        pw = self._parent.width()
        ph = self._parent.height()
        cw = NOTIFICATION_WIDTH
        x = pw - cw - NOTIFICATION_MARGIN
        y = ph - NOTIFICATION_MARGIN - 80
        self._container.setGeometry(x, y, cw, ph - y - NOTIFICATION_MARGIN)
        self._container.setVisible(True)

    def show(self, message, notification_type="info", duration=3000):
        if self._container:
            self._reposition()
            self._container.add_toast(message, notification_type, duration)

    def success(self, message, duration=3000):
        self.show(message, "success", duration)

    def warning(self, message, duration=4000):
        self.show(message, "warning", duration)

    def error(self, message, duration=5000):
        self.show(message, "error", duration)

    def info(self, message, duration=3000):
        self.show(message, "info", duration)
