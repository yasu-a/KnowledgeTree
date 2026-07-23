"""プロジェクトの作成・選択・削除を行うモーダルダイアログ。"""

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


@dataclass(frozen=True)
class ProjectListAction:
    """プロジェクト一覧ダイアログからNavigatorへ返す操作要求。"""

    kind: str
    project_name: str | None = None


class ProjectListDialog(QDialog):
    """プロジェクトの選択、新規作成、削除、全体設定表示を要求する。"""

    def __init__(
        self,
        project_names: tuple[str, ...],
        open_project_names: tuple[str, ...],
        parent: QWidget | None = None,
    ) -> None:
        """現在のプロジェクト一覧と開いている名前を表示する。"""
        super().__init__(parent)
        self.setWindowTitle("プロジェクトを開く")
        self.resize(360, 300)
        self._open_project_names = set(open_project_names)
        self._action: ProjectListAction | None = None
        self.project_list = QListWidget(self)
        self.open_button = QPushButton("開く", self)
        self.create_button = QPushButton("新規作成", self)
        self.delete_button = QPushButton("削除", self)
        self.global_settings_button = QPushButton("全体設定…", self)
        self._build_layout()
        self._populate_projects(project_names)
        self._connect_events()

    def action(self) -> ProjectListAction | None:
        """確定されたNavigator向け操作要求を返す。"""
        return self._action

    def _build_layout(self) -> None:
        """プロジェクト一覧、操作ボタン、キャンセルボタンを配置する。"""
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.delete_button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("プロジェクト", self))
        layout.addWidget(self.project_list)
        layout.addLayout(button_layout)
        layout.addWidget(self.global_settings_button, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_projects(self, project_names: tuple[str, ...]) -> None:
        """名前一覧からリスト項目を作り、先頭を選択する。"""
        for project_name in project_names:
            item = QListWidgetItem(project_name)
            if project_name in self._open_project_names:
                item.setToolTip("現在開いています")
            self.project_list.addItem(item)
        if self.project_list.count():
            self.project_list.setCurrentRow(0)
        self._update_button_state()

    def _connect_events(self) -> None:
        """選択と各操作ボタンをダイアログ結果へ接続する。"""
        self.project_list.currentItemChanged.connect(lambda current, previous: self._update_button_state())
        self.project_list.itemDoubleClicked.connect(lambda item: self._request_open(item.text()))
        self.open_button.clicked.connect(self._request_selected_open)
        self.create_button.clicked.connect(self._request_create)
        self.delete_button.clicked.connect(self._request_selected_delete)
        self.global_settings_button.clicked.connect(self._request_global_settings)

    def _update_button_state(self) -> None:
        """選択とオープン状態に応じて操作ボタンの有効状態を更新する。"""
        project_name = self._selected_project_name()
        self.open_button.setEnabled(project_name is not None)
        self.delete_button.setEnabled(project_name is not None and project_name not in self._open_project_names)

    def _selected_project_name(self) -> str | None:
        """リストで選択中のプロジェクト名を返す。"""
        item = self.project_list.currentItem()
        return item.text() if item is not None else None

    def _request_selected_open(self) -> None:
        """選択中プロジェクトを開く要求として確定する。"""
        project_name = self._selected_project_name()
        if project_name is not None:
            self._request_open(project_name)

    def _request_open(self, project_name: str) -> None:
        """指定プロジェクトを開く要求を設定してダイアログを閉じる。"""
        self._action = ProjectListAction("open", project_name)
        self.accept()

    def _request_create(self) -> None:
        """入力されたプロジェクト名で新規作成要求を設定する。"""
        project_name, accepted = QInputDialog.getText(self, "プロジェクトを新規作成", "プロジェクト名")
        if accepted and project_name.strip():
            self._action = ProjectListAction("create", project_name.strip())
            self.accept()

    def _request_selected_delete(self) -> None:
        """選択中プロジェクトの削除要求を設定してダイアログを閉じる。"""
        project_name = self._selected_project_name()
        if project_name is not None and project_name not in self._open_project_names:
            self._action = ProjectListAction("delete", project_name)
            self.accept()

    def _request_global_settings(self) -> None:
        """全体設定表示要求を設定してダイアログを閉じる。"""
        self._action = ProjectListAction("global-settings")
        self.accept()
