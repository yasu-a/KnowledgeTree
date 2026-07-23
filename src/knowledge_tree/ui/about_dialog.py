"""KnowledgeTreeのアプリケーション情報を表示するダイアログ。"""

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from knowledge_tree.application_version import ApplicationVersion
from knowledge_tree.project_format_version import ProjectFormatVersion


class AboutDialog(QDialog):
    """アプリケーション版とプロジェクト保存形式版を表示する。"""

    def __init__(
        self,
        application_version: ApplicationVersion,
        project_format_version: ProjectFormatVersion,
        parent: QWidget | None = None,
    ) -> None:
        """表示対象のアプリ版・保存形式版を設定して初期化する。"""
        super().__init__(parent)
        self.setWindowTitle("KnowledgeTreeについて")
        self.setModal(True)
        self.setMinimumWidth(320)
        title_label = QLabel("KnowledgeTree", self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        version_label = QLabel(f"アプリケーションバージョン: {application_version}", self)
        format_label = QLabel(f"プロジェクト形式バージョン: {project_format_version}", self)
        description_label = QLabel("研究知識をグラフとして整理するデスクトップアプリケーション", self)
        description_label.setWordWrap(True)
        repository_label = QLabel('<a href="https://github.com/yasu-a/KnowledgeTree">github.com/yasu-a/KnowledgeTree</a>', self)
        repository_label.setOpenExternalLinks(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addWidget(format_label)
        layout.addSpacing(8)
        layout.addWidget(description_label)
        layout.addWidget(repository_label)
        layout.addWidget(buttons)
