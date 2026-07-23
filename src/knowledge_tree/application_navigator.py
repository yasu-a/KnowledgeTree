"""アプリケーションの画面遷移とプロジェクトウィンドウを管理する。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from knowledge_tree.global_settings import GlobalSettingsStore
from knowledge_tree.project_session import ProjectSession
from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.session_state import SessionState, SessionStateStore
from knowledge_tree.ui.global_settings_dialog import GlobalSettingsDialog
from knowledge_tree.ui.main_window import MainWindow
from knowledge_tree.ui.project_list_dialog import ProjectListAction, ProjectListDialog


class ApplicationNavigator:
    """プロジェクト一覧、全体設定、複数のMainWindowを調停する。"""

    def __init__(
        self,
        application: QApplication,
        project_storage: ProjectStorage,
        global_settings_store: GlobalSettingsStore,
        session_state_store: SessionStateStore,
    ) -> None:
        """画面遷移に必要なアプリケーションと各ストアを設定する。"""
        self._application = application
        self._project_storage = project_storage
        self._global_settings_store = global_settings_store
        self._session_state_store = session_state_store
        self._windows: dict[str, MainWindow] = {}

    def start(self) -> bool:
        """全体設定を読み込み、プロジェクトを開けた場合だけTrueを返す。"""
        self._application.setQuitOnLastWindowClosed(True)
        global_settings = self._global_settings_store.load()
        session_state = self._session_state_store.load()
        # 旧active_projectを移行後、全体設定を新しい内容だけで保存し直す。
        self._global_settings_store.save(global_settings)
        if (
            global_settings.reopen_last_project
            and session_state.last_active_project in self._project_storage.project_names()
        ):
            self.open_project(session_state.last_active_project)
            return True
        self.show_project_list()
        return bool(self._windows)

    def open_project(self, project_name: str) -> MainWindow | None:
        """指定プロジェクトを開くか、既存ウィンドウを前面表示する。"""
        existing_window = self._windows.get(project_name)
        if existing_window is not None:
            existing_window.showNormal()
            existing_window.raise_()
            existing_window.activateWindow()
            self._record_active_project(project_name)
            return existing_window
        try:
            project_session = ProjectSession.open(self._project_storage, project_name)
        except ValueError as error:
            QMessageBox.warning(None, "プロジェクトを開けません", str(error))
            return None
        window = MainWindow(project_session)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.project_list_requested.connect(lambda: self.show_project_list(window))
        window.global_settings_requested.connect(lambda: self.show_global_settings(window))
        window.project_activated.connect(self._record_active_project)
        window.project_closed.connect(self._handle_project_closed)
        self._windows[project_name] = window
        window.show()
        window.activateWindow()
        self._record_active_project(project_name)
        return window

    def create_project(self, project_name: str) -> MainWindow | None:
        """デモデータ入りのプロジェクトを作成して直ちに開く。"""
        try:
            self._project_storage.create_project(project_name)
        except ValueError as error:
            QMessageBox.warning(None, "プロジェクトを作成できません", str(error))
            return None
        return self.open_project(project_name)

    def show_project_list(self, parent: QWidget | None = None) -> None:
        """モーダルなプロジェクト一覧を表示し、確定された操作をNavigatorで実行する。"""
        while True:
            dialog = ProjectListDialog(
                self._project_storage.project_names(),
                tuple(self._windows),
                parent,
            )
            dialog.exec()
            action = dialog.action()
            if action is None:
                if not self._windows:
                    self._application.quit()
                return
            if self._handle_project_list_action(action, parent):
                return

    def show_global_settings(self, parent: QWidget | None = None) -> None:
        """全体設定ダイアログを表示し、保存が確定した時だけ設定を更新する。"""
        dialog = GlobalSettingsDialog(self._global_settings_store.load(), parent)
        if dialog.exec() == GlobalSettingsDialog.DialogCode.Accepted:
            self._global_settings_store.save(dialog.settings())

    def open_project_names(self) -> tuple[str, ...]:
        """現在開いているプロジェクト名を返す。"""
        return tuple(self._windows)

    def _handle_project_list_action(self, action: ProjectListAction, parent: QWidget | None) -> bool:
        """一覧ダイアログから返された操作を実行し、処理完了ならTrueを返す。"""
        if action.kind == "open" and action.project_name is not None:
            return self.open_project(action.project_name) is not None
        if action.kind == "create" and action.project_name is not None:
            return self.create_project(action.project_name) is not None
        if action.kind == "delete" and action.project_name is not None:
            self._delete_project(action.project_name, parent)
            return False
        if action.kind == "global-settings":
            self.show_global_settings(parent)
            return False
        return False

    def _delete_project(self, project_name: str, parent: QWidget | None) -> None:
        """確認済みの閉じたプロジェクトを削除し、必要なら最後の利用状態を解除する。"""
        if project_name in self._windows:
            QMessageBox.information(parent, "プロジェクトを削除できません", "開いているプロジェクトは削除できません。先に閉じてください。")
            return
        answer = QMessageBox.question(
            parent,
            "プロジェクトを削除",
            f"プロジェクト「{project_name}」を完全に削除します。\nこの操作は元に戻せません。",
            QMessageBox.StandardButton.Delete | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Delete:
            return
        try:
            self._project_storage.delete_project(project_name)
        except ValueError as error:
            QMessageBox.warning(parent, "プロジェクトを削除できません", str(error))
            return
        session_state = self._session_state_store.load()
        if session_state.last_active_project == project_name:
            self._session_state_store.save(SessionState())

    def _record_active_project(self, project_name: str) -> None:
        """最後にアクティブだったプロジェクト名を実行状態として保存する。"""
        if project_name in self._windows:
            self._session_state_store.save(SessionState(project_name))

    def _handle_project_closed(self, project_name: str) -> None:
        """閉じたウィンドウを管理対象から外す。最後ならQtがアプリを終了する。"""
        self._windows.pop(project_name, None)
