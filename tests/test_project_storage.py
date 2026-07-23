"""プロジェクトフォルダ単位の永続化を検証する。"""

from dataclasses import replace
from pathlib import Path
import json

import pytest

from knowledge_tree.color_palette import ColorToken
from knowledge_tree.demo_graph_editor import ChildCombination, DemoGraphEditor
from knowledge_tree.project_storage import ProjectSnapshot, ProjectStorage


def test_creating_a_project_writes_json_files_and_a_cp932_literature_csv(tmp_path: Path) -> None:
    """新規プロジェクトはデモデータ、設定JSON、Excel互換CSVを含むフォルダを作る。"""
    storage = ProjectStorage(tmp_path / "userdata")

    snapshot = storage.create_project("量子研究")

    project_directory = tmp_path / "userdata" / "projects" / "量子研究"
    assert len(snapshot.graph.nodes) >= 1
    assert (project_directory / "project_settings.json").exists()
    assert (project_directory / "graph.json").exists()
    assert (project_directory / "literature_master.csv").read_text(encoding="cp932").startswith("id,title,authors")
    assert storage.active_project_name() == "量子研究"


def test_saving_and_loading_a_project_preserves_graph_layout_and_edge_types(tmp_path: Path) -> None:
    """プロジェクトJSONの往復でノード位置とエッジ種類設定を保持する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("保存確認")
    moved_node = replace(snapshot.graph.nodes[0], position_x=777.0, position_y=333.0)
    modified_graph = replace(snapshot.graph, nodes=(moved_node, *snapshot.graph.nodes[1:]))
    snapshot.settings.update_edge_type("refines", "refines", ColorToken.INDIGO)

    storage.save_project("保存確認", ProjectSnapshot(modified_graph, snapshot.settings))
    loaded = storage.load_project("保存確認")

    assert (loaded.graph.nodes[0].position_x, loaded.graph.nodes[0].position_y) == (777.0, 333.0)
    assert next(item for item in loaded.settings.edge_types() if item.id == "refines").color_token == ColorToken.INDIGO
    settings_json = json.loads((tmp_path / "userdata" / "projects" / "保存確認" / "project_settings.json").read_text(encoding="utf-8"))
    assert settings_json["edge_types"][0]["color_token"] == "indigo"
    assert "color_hex" not in settings_json["edge_types"][0]


def test_project_storage_rejects_unsafe_project_names(tmp_path: Path) -> None:
    """親ディレクトリへ脱出できる名前でプロジェクトを作成できない。"""
    storage = ProjectStorage(tmp_path / "userdata")

    with pytest.raises(ValueError):
        storage.create_project("../outside")


def test_loading_a_project_preserves_or_and_uses_new_unique_ids(tmp_path: Path) -> None:
    """保存済みのAND/ORと動的ID採番は、再読込後も維持する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("再読込確認")
    editor = DemoGraphEditor(snapshot.graph)
    first_node_id = snapshot.graph.nodes[0].id
    editor.update_question_node(first_node_id, "質問", "本文", ChildCombination.ANY)
    editor.create_question_node_at(100.0, 100.0)
    storage.save_project("再読込確認", ProjectSnapshot(editor.graph(), snapshot.settings))

    reloaded_editor = DemoGraphEditor(storage.load_project("再読込確認").graph)
    next_node_id = reloaded_editor.create_question_node_at(200.0, 200.0)

    assert reloaded_editor.child_combination(first_node_id) == ChildCombination.ANY
    assert next_node_id not in {node.id for node in editor.graph().nodes}


def test_deleting_a_project_removes_only_its_folder_and_clears_active_project(tmp_path: Path) -> None:
    """将来の削除操作は指定プロジェクトだけを削除し、アクティブ設定を解除する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("削除対象")
    storage.create_project("残す")
    storage.set_active_project("削除対象")

    storage.delete_project("削除対象")

    assert storage.project_names() == ("残す",)
    assert storage.active_project_name() is None
