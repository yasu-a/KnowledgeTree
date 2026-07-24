"""世代スナップショット保存と0.1から1.0へのmigrationを検証する。"""

import json
import shutil
from pathlib import Path

import pytest

from knowledge_tree.domain_graph import MemoNode, QuestionNode, ReferenceNode
from knowledge_tree.graph_layout import GraphLayout, NodeLayout
from knowledge_tree.application_version import APPLICATION_VERSION
from knowledge_tree.project_content import ProjectContent
from knowledge_tree.project_storage import ProjectSnapshot, ProjectStorage


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "projects" / "v0_1_full"


def test_creating_a_project_writes_one_complete_active_snapshot(tmp_path: Path) -> None:
    """新規プロジェクトは一世代へ意味論・レイアウト・設定をまとめて保存する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("量子研究")
    project_directory = tmp_path / "userdata" / "projects" / "量子研究"
    manifest = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))
    generation = project_directory / "snapshots" / manifest["active_snapshot"]

    assert len(snapshot.graph.nodes) >= 1
    assert manifest["version"] == {"major": 1, "minor": 0}
    assert all((generation / name).is_file() for name in ("graph.json", "layout.json", "project_settings.json"))
    assert (project_directory / "references" / "papers.csv").read_text(encoding="cp932").startswith("id,title,authors")


def test_graph_json_contains_only_kind_specific_semantic_fields(tmp_path: Path) -> None:
    """問いへ文献参照や位置を混在させず、UI情報はlayout.jsonへ分離する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("分離")
    project_directory = tmp_path / "userdata" / "projects" / "分離"
    manifest = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))
    generation = project_directory / "snapshots" / manifest["active_snapshot"]
    graph_data = json.loads((generation / "graph.json").read_text(encoding="utf-8"))
    layout_data = json.loads((generation / "layout.json").read_text(encoding="utf-8"))
    question = next(node for node in graph_data["nodes"] if node["kind"] == "question")
    reference = next(node for node in graph_data["nodes"] if node["kind"] == "reference")

    assert "position_x" not in question and "style_key" not in question and "reference_link" not in question
    assert set(reference) == {"id", "kind", "reference_link"}
    assert {item["node_id"] for item in layout_data["nodes"]} == {item["id"] for item in graph_data["nodes"]}


def test_save_switches_manifest_only_after_writing_a_complete_new_generation(tmp_path: Path) -> None:
    """不完全な孤立世代があってもmanifestが指す世代だけを読み込む。"""
    storage = ProjectStorage(tmp_path / "userdata")
    created = storage.create_project("世代")
    project_directory = tmp_path / "userdata" / "projects" / "世代"
    manifest_before = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))
    (project_directory / "snapshots" / "incomplete").mkdir()
    (project_directory / "snapshots" / "incomplete" / "graph.json").write_text("{}", encoding="utf-8")

    storage.save_project("世代", created)
    manifest_after = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))

    assert manifest_after["active_snapshot"] != manifest_before["active_snapshot"]
    assert storage.load_project("世代").graph.nodes


def test_save_keeps_the_active_and_immediately_previous_snapshots_only(tmp_path: Path) -> None:
    """世代保存は直前のバックアップを残し、古い世代と不完全世代を整理する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("整理")
    project_directory = tmp_path / "userdata" / "projects" / "整理"
    snapshots_directory = project_directory / "snapshots"
    first_generation_id = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))["active_snapshot"]
    (snapshots_directory / "incomplete").mkdir()

    storage.save_project("整理", snapshot)
    second_generation_id = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))["active_snapshot"]
    storage.save_project("整理", snapshot)
    third_generation_id = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))["active_snapshot"]

    assert {path.name for path in snapshots_directory.iterdir() if path.is_dir()} == {second_generation_id, third_generation_id}
    assert first_generation_id not in {path.name for path in snapshots_directory.iterdir() if path.is_dir()}
    assert not (snapshots_directory / "incomplete").exists()


def test_storage_rejects_layout_that_does_not_match_semantic_graph(tmp_path: Path) -> None:
    """同じ保存世代内でgraphとlayoutのID対応が崩れる保存を拒否する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    snapshot = storage.create_project("不整合")
    invalid_content = ProjectContent(snapshot.graph, GraphLayout((), snapshot.layout.edge_layouts), snapshot.settings)

    with pytest.raises(ValueError, match="一致"):
        storage.save_project("不整合", ProjectSnapshot(invalid_content))


def test_loading_fixture_migrates_a_full_v0_1_project_to_v1_0(tmp_path: Path) -> None:
    """実際の0.1形式フィクスチャを一時ディレクトリで1.0へ移行して検証する。"""
    project_directory = tmp_path / "userdata" / "projects" / "旧プロジェクト"
    shutil.copytree(FIXTURE_DIRECTORY, project_directory)
    storage = ProjectStorage(tmp_path / "userdata")

    migrated = storage.load_project("旧プロジェクト")
    manifest = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))
    generation = project_directory / "snapshots" / manifest["active_snapshot"]

    assert manifest["version"] == {"major": APPLICATION_VERSION.major, "minor": APPLICATION_VERSION.minor}
    assert isinstance(next(node for node in migrated.graph.nodes if node.id == "q-and"), QuestionNode)
    assert isinstance(next(node for node in migrated.graph.nodes if node.id == "memo"), MemoNode)
    assert isinstance(next(node for node in migrated.graph.nodes if node.id == "paper"), ReferenceNode)
    assert migrated.layout.node_layout("q-and").position_x == 10.0
    assert migrated.layout.edge_layout("e-refines").label_anchor == 0.3
    assert json.loads((generation / "graph.json").read_text(encoding="utf-8"))["schema_version"] == 1
    assert (project_directory / "references" / "papers.csv").read_text(encoding="cp932").startswith("id,title")


def test_project_storage_rejects_unsafe_project_names(tmp_path: Path) -> None:
    """親ディレクトリへ脱出できるプロジェクト名は拒否する。"""
    with pytest.raises(ValueError):
        ProjectStorage(tmp_path / "userdata").create_project("../outside")
