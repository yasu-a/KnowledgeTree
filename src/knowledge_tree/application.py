"""アプリケーションの生成とイベントループを担当する。"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from knowledge_tree.application_navigator import ApplicationNavigator
from knowledge_tree.global_settings import GlobalSettingsStore
from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.session_state import SessionStateStore


def run() -> int:
    """KnowledgeTree を起動する。"""
    application = QApplication(sys.argv)
    application.setApplicationName("KnowledgeTree")

    userdata_directory = Path.cwd() / "userdata"
    navigator = ApplicationNavigator(
        application,
        ProjectStorage(userdata_directory),
        GlobalSettingsStore(userdata_directory),
        SessionStateStore(userdata_directory),
    )
    if not navigator.start():
        return 0
    return application.exec()
