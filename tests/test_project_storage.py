"""プロジェクトフォルダ単位の永続化を検証する。"""

from dataclasses import replace
from pathlib import Path
import json

import pytest

from knowledge_tree.color_palette import ColorToken
from knowledge_tree.demo_graph_editor import ChildCombination, DemoGraphEditor
from knowledge_tree.project_storage import ProjectSnapshot, ProjectStorage
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.reference_catalog import ReferenceKind, ReferenceLink


def test_creating_a_project_writes_json_files_and_a_cp932_literature_csv(tmp_path: Path) -> None:
    """新規プロジェクトはデモデータ、設定JSON、Excel互換CSVを含むフォルダを作る。"""
    storage = ProjectStorage(tmp_path / "userdata")

    snapshot = storage.create_project("量子研究")

    project_directory = tmp_path / "userdata" / "projects" / "量子研究"
    assert len(snapshot.graph.nodes) >= 1
    assert (project_directory / "project_settings.json").exists()
    assert (project_directory / "graph.json").exists()
    assert (project_directory / "references" / "papers.csv").read_text(encoding="cp932").startswith("id,title,authors")


def test_saving_a_project_does_not_duplicate_the_initial_reference(tmp_path: Path) -> None:
    """通常保存でデモ用の初期文献を重複追加しない。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("文献重複")

    storage.save_project("文献重複", snapshot)

    assert len(storage.reference_catalog("文献重複").papers()) == 1


def test_graph_storage_preserves_a_reference_link_with_kind_and_id(tmp_path: Path) -> None:
    """グラフJSONは文献IDだけでなく、文献種別もReferenceLinkとして保持する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("文献リンク")

    loaded = storage.load_project("文献リンク")
    evidence = next(node for node in loaded.graph.nodes if node.id == "evidence")

    assert evidence.reference_link == ReferenceLink(ReferenceKind.PAPER, "paper-001")


def test_saving_and_loading_a_project_preserves_graph_layout_and_edge_types(tmp_path: Path) -> None:
    """プロジェクトJSONの往復でノード位置とエッジ種類設定を保持する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("保存確認")
    moved_node = replace(snapshot.graph.nodes[0], position_x=777.0, position_y=333.0)
    modified_graph = replace(snapshot.graph, nodes=(moved_node, *snapshot.graph.nodes[1:]))
    snapshot.settings.update_edge_color("refines", ColorToken.INDIGO)

    storage.save_project("保存確認", ProjectSnapshot(modified_graph, snapshot.settings))
    loaded = storage.load_project("保存確認")

    assert (loaded.graph.nodes[0].position_x, loaded.graph.nodes[0].position_y) == (777.0, 333.0)
    assert next(item for item in loaded.settings.edge_types() if item.id == "refines").color_token == ColorToken.INDIGO
    settings_json = json.loads((tmp_path / "userdata" / "projects" / "保存確認" / "project_settings.json").read_text(encoding="utf-8"))
    assert settings_json["edge_types"][0]["color_token"] == "indigo"
    assert settings_json["edge_types"][0]["allowed_endpoints"] == [[NodeKind.QUESTION.value, NodeKind.QUESTION.value]]
    assert "color_hex" not in settings_json["edge_types"][0]


def test_saving_and_loading_a_project_preserves_custom_edge_type_endpoints(tmp_path: Path) -> None:
    """追加した関係種類と接続可能なノード種別の設定はJSON往復後も保持する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("接続規則")
    edge_type = snapshot.settings.add_edge_type()
    snapshot.settings.update_edge_type(
        edge_type.id,
        "commentsOn",
        ColorToken.ROSE,
        ((NodeKind.QUESTION, NodeKind.MEMO),),
    )

    storage.save_project("接続規則", snapshot)
    loaded = storage.load_project("接続規則")

    assert loaded.settings.edge_types()[-1].label == "commentsOn"
    assert loaded.settings.edge_types()[-1].allowed_endpoints == ((NodeKind.QUESTION, NodeKind.MEMO),)


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


def test_deleting_a_project_removes_only_its_folder(tmp_path: Path) -> None:
    """プロジェクト削除は指定プロジェクトのフォルダだけを削除する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("削除対象")
    storage.create_project("残す")
    storage.delete_project("削除対象")

    assert storage.project_names() == ("残す",)
