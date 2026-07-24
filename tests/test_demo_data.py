"""サンプルデータの構造を検証する。"""

from knowledge_tree.demo_data import build_demo_project
from knowledge_tree.graph_presenter import GraphPresenter


def test_demo_project_contains_semantic_nodes_edges_and_layout() -> None:
    """デモ構築はCanvas知識なしに意味論とレイアウトを提供する。"""
    project = build_demo_project()

    assert len(project.graph.nodes) >= 8
    assert len(project.graph.edges) >= 5
    assert {node.id for node in project.graph.nodes} == {layout.node_id for layout in project.layout.node_layouts}


def test_demo_project_uses_factory_generated_ids() -> None:
    """別々に作るデモプロジェクトは、手書きでない異なるUUIDのIDを持つ。"""
    first = build_demo_project()
    second = build_demo_project()

    first_ids = {node.id for node in first.graph.nodes}
    second_ids = {node.id for node in second.graph.nodes}
    assert first_ids.isdisjoint(second_ids)
    assert all(len(identifier) == 32 for identifier in (*first_ids, *(edge.id for edge in first.graph.edges)))


def test_canvas_view_model_does_not_carry_project_semantics() -> None:
    """Canvas用モデルはノード種別や文献リンクを持たず、表示情報だけを持つ。"""
    project = build_demo_project()
    canvas_graph = GraphPresenter().present(project.graph, project.layout, project.settings)

    reference_node = next(node for node in canvas_graph.nodes if node.text == "削除された文献")
    assert not hasattr(reference_node, "node_kind")
    assert not hasattr(reference_node, "reference_link")
