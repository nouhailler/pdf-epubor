"""Panneau de logs et progression"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QProgressBar, QLabel, QListWidget,
    QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QColor, QFont
import datetime


class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setMaximumHeight(240)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Barre de progression
        prog_layout = QHBoxLayout()
        prog_layout.setSpacing(8)
        lbl_prog = QLabel("Progression :")
        prog_layout.addWidget(lbl_prog)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(22)
        prog_layout.addWidget(self.progress_bar)
        layout.addLayout(prog_layout)

        # Logs
        log_layout = QHBoxLayout()
        log_layout.setSpacing(8)

        # Zone log principale
        log_left = QVBoxLayout()
        log_left.setSpacing(4)
        log_header = QHBoxLayout()
        log_header.setSpacing(6)
        log_header.addWidget(QLabel("Journal de conversion"))
        log_header.addStretch()

        btn_copy = QPushButton("Copier")
        btn_copy.setFixedHeight(26)
        btn_copy.clicked.connect(self._copy_logs)
        btn_clear = QPushButton("Effacer")
        btn_clear.setFixedHeight(26)
        btn_clear.clicked.connect(self._clear_logs)
        log_header.addWidget(btn_copy)
        log_header.addWidget(btn_clear)
        log_left.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        font = QFont("Monospace", 9)
        self.log_text.setFont(font)
        log_left.addWidget(self.log_text)

        log_layout.addLayout(log_left, 3)

        # Liste batch
        batch_right = QVBoxLayout()
        batch_right.setSpacing(4)
        batch_right.addWidget(QLabel("Lot en cours"))
        self.batch_list = QListWidget()
        batch_right.addWidget(self.batch_list)
        log_layout.addLayout(batch_right, 1)

        layout.addLayout(log_layout)

    def append_log(self, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        self.log_text.append(line)
        # Auto-scroll
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def start_batch(self, paths: list):
        self.batch_list.clear()
        for path in paths:
            import os
            item = QListWidgetItem(f"⏳ {os.path.basename(path)}")
            self.batch_list.addItem(item)

    def _copy_logs(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.log_text.toPlainText())

    def _clear_logs(self):
        self.log_text.clear()
        self.progress_bar.setValue(0)
