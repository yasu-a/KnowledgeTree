"""アプリ全体の設定を編集するモーダルダイアログ。"""

from PyQt6.QtWidgets import QCheckBox, QDialogButtonBox, QVBoxLayout, QWidget

from knowledge_tree.global_settings import GlobalSettings
from knowledge_tree.ui.save_cancel_dialog import SaveCancelDialog


class GlobalSettingsDialog(SaveCancelDialog):
    """ユーザーが編集できるアプリ全体の設定を表示する。"""

    def __init__(self, settings: GlobalSettings, parent: QWidget | None = None) -> None:
        """指定設定の値をフォームへ反映してダイアログを初期化する。"""
        self._original_settings = settings
        super().__init__(self._is_dirty, parent)
        self.setWindowTitle("全体設定")
        self.reopen_last_project_check = QCheckBox("起動時に最後に使用したプロジェクトを開く", self)
        self.reopen_last_project_check.setChecked(settings.reopen_last_project)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.discard)
        layout = QVBoxLayout(self)
        layout.addWidget(self.reopen_last_project_check)
        layout.addWidget(buttons)

    def settings(self) -> GlobalSettings:
        """フォームの現在値から全体設定オブジェクトを作る。"""
        return GlobalSettings(self.reopen_last_project_check.isChecked())

    def _is_dirty(self) -> bool:
        """フォーム値がダイアログ開始時の全体設定と異なるかを返す。"""
        return self.settings() != self._original_settings
