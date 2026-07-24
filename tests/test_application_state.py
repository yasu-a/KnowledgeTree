"""全体設定、実行状態、プロジェクトセッションの分離を検証する。"""

import json
from pathlib import Path

from knowledge_tree.global_settings import GlobalSettings, GlobalSettingsStore
from knowledge_tree.project_session import ProjectSession
from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.session_state import SessionState, SessionStateStore


def test_global_settings_and_session_state_are_saved_to_separate_files(tmp_path: Path) -> None:
    """ユーザー設定と最後に使用したプロジェクトは別々のJSONへ保存する。"""
    global_store = GlobalSettingsStore(tmp_path / "userdata")
    session_store = SessionStateStore(tmp_path / "userdata")

    global_store.save(GlobalSettings(reopen_last_project=False))
    session_store.save(SessionState("量子研究"))

    assert global_store.load() == GlobalSettings(reopen_last_project=False)
    assert session_store.load() == SessionState("量子研究")
    assert "last_active_project" not in json.loads((tmp_path / "userdata" / "global_settings.json").read_text(encoding="utf-8"))


def test_session_state_migrates_the_legacy_active_project_setting(tmp_path: Path) -> None:
    """旧global_settings.jsonのactive_projectは最初の読込でセッション状態へ移行する。"""
    userdata_directory = tmp_path / "userdata"
    userdata_directory.mkdir()
    (userdata_directory / "global_settings.json").write_text(
        json.dumps({"schema_version": 1, "active_project": "旧プロジェクト"}),
        encoding="utf-8",
    )

    state = SessionStateStore(userdata_directory).load()

    assert state == SessionState("旧プロジェクト")
    assert json.loads((userdata_directory / "session_state.json").read_text(encoding="utf-8"))["last_active_project"] == "旧プロジェクト"


def test_project_session_saves_its_own_graph_changes(tmp_path: Path) -> None:
    """ProjectSessionは編集後のグラフを自身のプロジェクトへ保存する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("セッション")
    session = ProjectSession.open(storage, "セッション")

    isolated_id = next(node.id for node in session.graph_editor.semantic_graph().nodes if getattr(node, "title", None) == "未整理のメモ")
    session.graph_editor.update_node_position(isolated_id, 700.0, 400.0)
    session.save()

    layout = storage.load_project("セッション").layout.node_layout(isolated_id)
    assert (layout.position_x, layout.position_y) == (700.0, 400.0)
