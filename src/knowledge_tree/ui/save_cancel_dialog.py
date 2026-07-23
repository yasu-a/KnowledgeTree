"""未保存変更の破棄確認を共通化するSave/Cancelダイアログ。"""

from collections.abc import Callable

from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDialog, QMessageBox, QWidget


class SaveCancelDialog(QDialog):
    """Cancelと×操作で、未保存変更の破棄を安全に確認するダイアログ。"""

    def __init__(self, has_unsaved_changes: Callable[[], bool], parent: QWidget | None = None) -> None:
        """未保存変更を判定する関数と親Widgetを設定する。"""
        super().__init__(parent)
        self._has_unsaved_changes = has_unsaved_changes
        self._discarding = False

    def discard(self) -> None:
        """Cancel操作では確認なしに編集内容を破棄して閉じる。"""
        self._discarding = True
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        """×操作時だけ、未保存変更があれば破棄確認を表示する。"""
        if not self._discarding and self._has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                "変更を破棄しますか？",
                "保存していない変更があります。破棄して閉じますか？",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
        event.accept()
