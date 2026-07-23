"""サンプルデータの構造を検証する。"""

from knowledge_tree.demo_data import build_demo_graph


def test_demo_graph_contains_nodes_and_edges() -> None:
    """Canvas操作確認に十分なノードとエッジを提供する。"""
    graph = build_demo_graph()

    assert len(graph.nodes) >= 8
    assert len(graph.edges) >= 5
    assert {node.style_key for node in graph.nodes} >= {"default", "question", "note", "warning"}
    assert all(edge.directed for edge in graph.edges)
    assert {edge.style_key for edge in graph.edges} == {"global-edge-type:refines", "global-edge-type:contributes-to"}
