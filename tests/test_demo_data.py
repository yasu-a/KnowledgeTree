"""サンプルデータの構造を検証する。"""

from knowledge_tree.demo_data import build_demo_graph


def test_demo_graph_contains_nodes_and_edges() -> None:
    """Canvas操作確認に十分なノードとエッジを提供する。"""
    graph = build_demo_graph()

    assert len(graph.nodes) >= 8
    assert len(graph.edges) >= 6
    assert {node.style_key for node in graph.nodes} >= {"default", "question", "note", "warning"}
    assert any(edge.directed for edge in graph.edges)
    assert any(not edge.directed for edge in graph.edges)
