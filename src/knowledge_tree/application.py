"""アプリケーションの生成とイベントループを担当する。"""

import sys

from PyQt6.QtWidgets import QApplication

from knowledge_tree.ui.main_window import MainWindow


def run() -> int:
    """KnowledgeTree を起動する。"""
    application = QApplication(sys.argv)
    application.setApplicationName("KnowledgeTree")

    window = MainWindow()
    window.show()
    return application.exec()
