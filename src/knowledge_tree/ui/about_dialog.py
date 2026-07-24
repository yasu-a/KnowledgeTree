"""KnowledgeTreeのアプリケーション情報を表示するダイアログ。"""

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from knowledge_tree.application_version import ApplicationVersion


class AboutDialog(QDialog):
    """KnowledgeTreeの共通バージョンを表示する。"""

    def __init__(
        self,
        version: ApplicationVersion,
        legacy_project_version: ApplicationVersion | QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """表示対象のKnowledgeTreeバージョンを設定して初期化する。"""
        if isinstance(legacy_project_version, QWidget):
            parent = legacy_project_version
        super().__init__(parent)
        self.setWindowTitle("KnowledgeTreeについて")
        self.setModal(True)
        self.setMinimumWidth(320)
        title_label = QLabel("KnowledgeTree", self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        version_label = QLabel(f"バージョン: {version}", self)
        description_label = QLabel("研究知識をグラフとして整理するデスクトップアプリケーション", self)
        description_label.setWordWrap(True)
        repository_label = QLabel('<a href="https://github.com/yasu-a/KnowledgeTree">github.com/yasu-a/KnowledgeTree</a>', self)
        repository_label.setOpenExternalLinks(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addSpacing(8)
        layout.addWidget(description_label)
        layout.addWidget(repository_label)
        layout.addWidget(buttons)
