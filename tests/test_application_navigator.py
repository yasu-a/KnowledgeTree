"""ApplicationNavigatorによる複数プロジェクト管理を検証する。"""

from pathlib import Path

from PyQt6.QtWidgets import QApplication

from knowledge_tree.application_navigator import ApplicationNavigator
from knowledge_tree.global_settings import GlobalSettings, GlobalSettingsStore
from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.session_state import SessionState, SessionStateStore
from knowledge_tree.ui.global_settings_dialog import GlobalSettingsDialog
from knowledge_tree.ui.project_list_dialog import ProjectListDialog


def _navigator(tmp_path: Path) -> tuple[ApplicationNavigator, ProjectStorage, SessionStateStore]:
    """テスト用の空userdataを使うNavigatorと関連ストアを作成する。"""
    application = QApplication.instance()
    assert isinstance(application, QApplication)
    application.setQuitOnLastWindowClosed(False)
    userdata_directory = tmp_path / "userdata"
    storage = ProjectStorage(userdata_directory)
    session_store = SessionStateStore(userdata_directory)
    return (
        ApplicationNavigator(application, storage, GlobalSettingsStore(userdata_directory), session_store),
        storage,
        session_store,
    )


def test_navigator_opens_multiple_projects_and_reuses_an_existing_window(qtbot: object, tmp_path: Path) -> None:
    """Navigatorは別プロジェクトを複数開き、同名プロジェクトは同じWindowを再利用する。"""
    navigator, storage, session_store = _navigator(tmp_path)
    storage.create_project("研究A")
    storage.create_project("研究B")

    first_window = navigator.open_project("研究A")
    second_window = navigator.open_project("研究B")
    reused_window = navigator.open_project("研究A")

    assert first_window is not None
    assert second_window is not None
    assert reused_window is first_window
    assert navigator.open_project_names() == ("研究A", "研究B")
    assert session_store.load() == SessionState("研究A")

    first_window.close()
    second_window.project_closed.disconnect()
    second_window.close()
    qtbot.wait(10)


def test_navigator_does_not_show_the_project_list_after_the_last_window_closes(qtbot: object, tmp_path: Path) -> None:
    """最後のMainWindowを閉じても、プロジェクト一覧を自動表示しない。"""
    navigator, storage, _ = _navigator(tmp_path)
    storage.create_project("研究A")
    called = []
    navigator.show_project_list = lambda parent=None: called.append(parent)  # type: ignore[method-assign]
    window = navigator.open_project("研究A")
    assert window is not None

    window.close()
    qtbot.wait(10)

    assert navigator.open_project_names() == ()
    assert called == []


def test_project_list_disables_deletion_for_an_open_project(qtbot: object) -> None:
    """一覧では、開いているプロジェクトを削除対象に選べない。"""
    dialog = ProjectListDialog(("研究A", "研究B"), ("研究A",))
    qtbot.addWidget(dialog)

    assert dialog.delete_button.isEnabled() is False
    dialog.project_list.setCurrentRow(1)
    assert dialog.delete_button.isEnabled() is True


def test_global_settings_dialog_returns_the_selected_startup_behavior(qtbot: object) -> None:
    """全体設定ダイアログは最後のプロジェクトを開く設定を編集できる。"""
    dialog = GlobalSettingsDialog(GlobalSettings())
    qtbot.addWidget(dialog)
    dialog.reopen_last_project_check.setChecked(False)

    assert dialog.settings().reopen_last_project is False
