from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from core.theme import Dark, Light, Fonts


class DarkTheme(Dark):
    pass


class LightTheme(Light):
    pass


class ThemeManager:

    _instance = None
    _current = "dark"

    def __init__(self):
        self._callbacks = []

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def colors(self):
        return DarkTheme if self._current == "dark" else LightTheme

    def is_dark(self):
        return self._current == "dark"

    def toggle(self):
        self._current = "light" if self._current == "dark" else "dark"
        self._apply()
        for cb in self._callbacks:
            cb(self._current)

    def set_mode(self, mode):
        if mode != self._current:
            self._current = mode
            self._apply()
            for cb in self._callbacks:
                cb(self._current)

    def on_change(self, callback):
        self._callbacks.append(callback)
        def disconnect():
            if callback in self._callbacks:
                self._callbacks.remove(callback)
        return disconnect

    def _apply(self):
        app = QApplication.instance()
        if app is None:
            return
        c = self.colors()
        palette = QPalette()

        palette.setColor(QPalette.Window, QColor(c.BG))
        palette.setColor(QPalette.WindowText, QColor(c.TEXT))
        palette.setColor(QPalette.Base, QColor(c.CARD))
        palette.setColor(QPalette.Text, QColor(c.TEXT))
        palette.setColor(QPalette.Button, QColor(c.SURFACE))
        palette.setColor(QPalette.ButtonText, QColor(c.TEXT))
        palette.setColor(QPalette.PlaceholderText, QColor(c.TEXT_MUTED))
        palette.setColor(QPalette.Highlight, QColor(c.PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(c.TEXT_ON_PRIMARY))
        palette.setColor(QPalette.ToolTipBase, QColor(c.SURFACE))
        palette.setColor(QPalette.ToolTipText, QColor(c.TEXT))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(c.TEXT_MUTED))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(c.TEXT_MUTED))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(c.TEXT_MUTED))

        app.setPalette(palette)
        app.setStyleSheet(self._stylesheet(c))

    def _stylesheet(self, c):
        return f"""
            QWidget {{
                font-family: "{Fonts.FAMILY}", "{Fonts.FAMILY_ALT}", sans-serif;
                font-size: 14px;
                color: {c.TEXT};
                background-color: transparent;
            }}
            QMainWindow {{
                background-color: {c.BG};
            }}
            QFrame#sidebar {{
                background-color: {c.SIDEBAR};
                border: 1px solid {c.BORDER};
                border-radius: 16px;
                padding: 0px;
            }}
            QFrame#card {{
                background-color: {c.CARD};
                border: 1px solid {c.BORDER};
                border-radius: 12px;
            }}
            QFrame#card:hover {{
                border: 1px solid {c.PRIMARY};
            }}
            QPushButton {{
                background-color: {c.PRIMARY};
                color: {c.TEXT_ON_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {c.PRIMARY_HOVER};
                padding: 9px 19px 7px 21px;
            }}
            QPushButton:disabled {{
                background-color: {c.SURFACE};
                color: {c.TEXT_MUTED};
                border: 1px solid {c.BORDER};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {c.TEXT};
                border: 1px solid {c.BORDER};
            }}
            QPushButton#secondary:hover {{
                background-color: {c.HOVER};
                border: 1px solid {c.PRIMARY};
            }}
            QPushButton#danger {{
                background-color: {c.ERROR};
            }}
            QPushButton#danger:hover {{
                background-color: {c.ERROR_HOVER};
            }}
            QPushButton#ghost {{
                background-color: transparent;
                color: {c.TEXT_SECONDARY};
                border: none;
            }}
            QPushButton#ghost:hover {{
                background-color: {c.HOVER};
                color: {c.TEXT};
            }}
            QPushButton#nav_item {{
                background-color: transparent;
                color: {c.TEXT_SECONDARY};
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton#nav_item:hover {{
                background-color: {c.HOVER};
                color: {c.TEXT};
            }}
            QLineEdit {{
                background-color: {c.INPUT_BG};
                color: {c.TEXT};
                border: 1px solid {c.INPUT_BORDER};
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 13px;
                min-height: 18px;
            }}
            QLineEdit:focus {{
                border: 2px solid {c.PRIMARY};
                padding: 7px 13px;
            }}
            QLineEdit:disabled {{
                background-color: {c.BG};
                color: {c.TEXT_MUTED};
            }}
            QTextEdit {{
                background-color: {c.INPUT_BG};
                color: {c.TEXT};
                border: 1px solid {c.INPUT_BORDER};
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border: 2px solid {c.PRIMARY};
            }}
            QPlainTextEdit {{
                background-color: {c.INPUT_BG};
                color: {c.TEXT};
                border: 1px solid {c.INPUT_BORDER};
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
            }}
            QPlainTextEdit:focus {{
                border: 2px solid {c.PRIMARY};
            }}
            QComboBox {{
                background-color: {c.INPUT_BG};
                color: {c.TEXT};
                border: 1px solid {c.INPUT_BORDER};
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 13px;
                min-width: 140px;
                min-height: 18px;
            }}
            QComboBox:hover {{
                border: 1px solid {c.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 32px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c.TEXT_SECONDARY};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c.CARD};
                color: {c.TEXT};
                border: 1px solid {c.BORDER};
                border-radius: 12px;
                selection-background-color: {c.PRIMARY_LIGHT};
                selection-color: {c.TEXT};
                padding: 8px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border-radius: 8px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {c.HOVER};
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.SCROLLBAR};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.SCROLLBAR_HOVER};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background-color: transparent;
                height: 8px;
                margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {c.SCROLLBAR};
                border-radius: 4px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c.SCROLLBAR_HOVER};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QProgressBar {{
                background-color: {c.SURFACE};
                border: none;
                border-radius: 8px;
                text-align: center;
                height: 12px;
                font-size: 10px;
            }}
            QProgressBar::chunk {{
                background-color: {c.PRIMARY};
                border-radius: 8px;
            }}
            QLabel#title {{
                font-size: 28px;
                font-weight: bold;
                color: {c.TEXT};
                padding: 0px;
            }}
            QLabel#section {{
                font-size: 20px;
                font-weight: 600;
                color: {c.TEXT};
                padding: 0px;
            }}
            QLabel#card_title {{
                font-size: 16px;
                font-weight: 600;
                color: {c.TEXT};
                padding: 0px;
            }}
            QLabel#body {{
                font-size: 14px;
                color: {c.TEXT_SECONDARY};
            }}
            QLabel#muted {{
                font-size: 12px;
                color: {c.TEXT_MUTED};
            }}
            QGroupBox {{
                background-color: {c.CARD};
                border: 1px solid {c.BORDER};
                border-radius: 12px;
                margin-top: 8px;
                padding: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 8px;
                color: {c.TEXT};
                font-weight: bold;
            }}
            QSplitter::handle {{
                background-color: {c.BORDER};
                width: 1px;
            }}
            QToolTip {{
                background-color: {c.SURFACE};
                color: {c.TEXT};
                border: 1px solid {c.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QTableWidget {{
                background-color: {c.CARD};
                border: 1px solid {c.BORDER};
                border-radius: 12px;
                padding: 4px;
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 6px 12px;
                border-bottom: 1px solid {c.BORDER};
            }}
            QTableWidget::item:selected {{
                background-color: {c.PRIMARY_LIGHT};
                color: {c.TEXT};
            }}
            QHeaderView::section {{
                background-color: transparent;
                color: {c.TEXT_MUTED};
                border: none;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QMessageBox {{
                background-color: {c.BG};
                color: {c.TEXT};
            }}
            QMessageBox QLabel {{
                color: {c.TEXT};
            }}
            QMessageBox QPushButton {{
                min-width: 80px;
            }}
        """
