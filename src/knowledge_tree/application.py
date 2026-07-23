"""アプリケーションの生成とイベントループを担当する。"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QInputDialog

from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.ui.main_window import MainWindow


def run() -> int:
    """KnowledgeTree を起動する。"""
    application = QApplication(sys.argv)
    application.setApplicationName("KnowledgeTree")

    storage = ProjectStorage(Path.cwd() / "userdata")
    project_name = storage.active_project_name()
    if project_name not in storage.project_names():
        project_name, accepted = QInputDialog.getText(None, "最初のプロジェクト", "プロジェクト名")
        if not accepted or not project_name.strip():
            return 0
        try:
            storage.create_project(project_name.strip())
        except ValueError:
            return 0
    window = MainWindow(storage, project_name)
    window.show()
    return application.exec()
