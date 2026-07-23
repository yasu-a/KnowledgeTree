"""Canvas外部のデモ編集状態を検証する。"""

from knowledge_tree.demo_data import build_demo_graph
from knowledge_tree.demo_graph_editor import DemoGraphEditor
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel, GraphViewModel


def test_insert_node_on_edge_splits_the_edge() -> None:
    """外部デモが元のエッジを二本のエッジへ置き換える。"""
    editor = DemoGraphEditor(build_demo_graph())
    graph_before = editor.graph()

    inserted_node_id = editor.insert_node_on_edge("edge-goal")
    graph_after = editor.graph()

    assert len(graph_after.nodes) == len(graph_before.nodes) + 1
    assert len(graph_after.edges) == len(graph_before.edges) + 1
    assert any(node.id == inserted_node_id for node in graph_after.nodes)
    assert any(edge.target_node_id == inserted_node_id for edge in graph_after.edges)
    assert any(edge.source_node_id == inserted_node_id for edge in graph_after.edges)


def test_remove_node_reconnects_a_single_parent_to_multiple_children() -> None:
    """親が一つの分岐ノードは、削除時に子を親へ繰り上げる。"""
    graph = GraphViewModel(
        nodes=tuple(_node(node_id) for node_id in ("a", "b", "c", "d")),
        edges=(
            _edge("a-b", "a", "b"),
            _edge("b-c", "b", "c"),
            _edge("b-d", "b", "d"),
        ),
    )
    editor = DemoGraphEditor(graph)

    plan = editor.deletion_plan("b")
    result = editor.remove_node("b", reconnect=plan.can_reconnect_automatically)
    graph_after = editor.graph()

    assert plan.can_reconnect_automatically is True
    assert result.removed_edge_count == 3
    assert result.created_edge_count == 2
    assert {(edge.source_node_id, edge.target_node_id) for edge in graph_after.edges} == {("a", "c"), ("a", "d")}


def test_multiple_parents_and_children_require_a_choice() -> None:
    """多対多の親子接続は自動再接続しない。"""
    graph = GraphViewModel(
        nodes=tuple(_node(node_id) for node_id in ("a", "b", "c", "d", "e")),
        edges=(
            _edge("a-c", "a", "c"),
            _edge("b-c", "b", "c"),
            _edge("c-d", "c", "d"),
            _edge("c-e", "c", "e"),
        ),
    )
    editor = DemoGraphEditor(graph)

    plan = editor.deletion_plan("c")

    assert plan.requires_choice is True
    assert plan.can_reconnect_automatically is False


def test_remove_node_can_disconnect_all_edges() -> None:
    """接続を維持しない削除では、接続エッジをすべて除去する。"""
    editor = DemoGraphEditor(build_demo_graph())

    result = editor.remove_node("operation", reconnect=False)
    graph_after = editor.graph()

    assert result.removed_edge_count == 2
    assert result.created_edge_count == 0
    assert all(node.id != "operation" for node in graph_after.nodes)
    assert all("operation" not in (edge.source_node_id, edge.target_node_id) for edge in graph_after.edges)


def test_add_edge_rejects_a_connection_that_would_create_a_cycle() -> None:
    """子ノードから祖先へ戻る有向接続は、外部Controllerが拒否する。"""
    editor = DemoGraphEditor(build_demo_graph())

    edge_id = editor.add_edge("question", "diagnosis")

    assert edge_id is None


def test_reconnect_edge_keeps_its_id_and_rejects_a_cycle() -> None:
    """エッジ付け替えは外部デモの閉路制約を尊重する。"""
    editor = DemoGraphEditor(build_demo_graph())

    assert editor.reconnect_edge("edge-goal", "goal", "diagnosis") is True
    assert editor.reconnect_edge("edge-diagnosis", "diagnosis", "goal") is False
    goal_edge = next(edge for edge in editor.graph().edges if edge.id == "edge-goal")
    assert (goal_edge.source_node_id, goal_edge.target_node_id) == ("goal", "diagnosis")


def test_create_node_connected_from_adds_a_node_and_an_edge() -> None:
    """背景ドロップ用の外部デモ操作は、ノードと接続を同時に追加する。"""
    editor = DemoGraphEditor(build_demo_graph())
    graph_before = editor.graph()

    node_id = editor.create_node_connected_from("goal", 520.0, 560.0)
    graph_after = editor.graph()

    assert node_id is not None
    assert len(graph_after.nodes) == len(graph_before.nodes) + 1
    assert len(graph_after.edges) == len(graph_before.edges) + 1
    created_node = next(node for node in graph_after.nodes if node.id == node_id)
    assert (created_node.position_x, created_node.position_y) == (402.5, 507.5)
    assert any(edge.source_node_id == "goal" and edge.target_node_id == node_id for edge in graph_after.edges)


def test_manual_layout_values_are_preserved_when_the_graph_is_rebuilt() -> None:
    """外部状態へ反映したノード・ラベル位置は、再投入後も維持される。"""
    editor = DemoGraphEditor(build_demo_graph())

    editor.update_node_position("isolated", 620.0, 430.0)
    editor.update_edge_label_offset("edge-goal", 35.0, -20.0)
    graph = editor.graph()

    isolated_node = next(node for node in graph.nodes if node.id == "isolated")
    goal_edge = next(edge for edge in graph.edges if edge.id == "edge-goal")
    assert (isolated_node.position_x, isolated_node.position_y) == (620.0, 430.0)
    assert (goal_edge.label_offset_x, goal_edge.label_offset_y) == (35.0, -20.0)


def _node(node_id: str) -> GraphNodeViewModel:
    """再接続テスト用の最小ノードViewModelを作る。"""
    return GraphNodeViewModel(node_id, node_id, None, 0.0, 0.0, 100.0, 60.0, "default")


def _edge(edge_id: str, source_node_id: str, target_node_id: str) -> GraphEdgeViewModel:
    """再接続テスト用の最小有向エッジViewModelを作る。"""
    return GraphEdgeViewModel(edge_id, source_node_id, target_node_id, "", True, "default")
