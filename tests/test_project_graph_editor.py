"""意味論的グラフ編集サービスを検証する。"""

from knowledge_tree.demo_data import build_demo_project
from knowledge_tree.domain_graph import ChildCombination
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.project_graph_editor import ProjectGraphEditor


def _editor() -> ProjectGraphEditor:
    """デモプロジェクトを編集サービスへ展開する。"""
    return ProjectGraphEditor(build_demo_project())


def _node_id(editor: ProjectGraphEditor, title: str) -> str:
    """デモのタイトルから生成済みノードIDを取得する。"""
    return next(node.id for node in editor.semantic_graph().nodes if getattr(node, "title", None) == title)


def _edge_id(editor: ProjectGraphEditor, source_node_id: str, target_node_id: str) -> str:
    """両端ノードから生成済みエッジIDを取得する。"""
    return next(edge.id for edge in editor.semantic_graph().edges if (edge.source_node_id, edge.target_node_id) == (source_node_id, target_node_id))


def test_insert_node_on_edge_splits_the_semantic_edge() -> None:
    """エッジ分割は同じ関係ラベルの二本の意味論的エッジを作る。"""
    editor = _editor()
    goal_id = _node_id(editor, "社会的・工学的な大きな目標")
    operation_id = _node_id(editor, "量子プロセッサを\n安定して運用するには？")
    node_id = editor.insert_node_on_edge(_edge_id(editor, goal_id, operation_id), NodeKind.QUESTION)
    edges = editor.semantic_graph().edges

    assert any(edge.source_node_id == goal_id and edge.target_node_id == node_id and edge.label == "refines" for edge in edges)
    assert any(edge.source_node_id == node_id and edge.target_node_id == operation_id and edge.label == "refines" for edge in edges)


def test_new_nodes_receive_random_ids_and_default_layouts() -> None:
    """通常の新規作成では手入力IDでなくUUID由来のIDと既定レイアウトを使う。"""
    editor = _editor()
    first_id = editor.create_question_node_at(520.0, 560.0)
    second_id = editor.create_question_node_at(520.0, 560.0)

    assert first_id != second_id
    assert len(first_id) == 32
    assert (editor.layout().node_layout(first_id).position_x, editor.layout().node_layout(first_id).width) == (377.5, 285.0)


def test_editing_question_updates_semantics_and_canvas_projection() -> None:
    """質問本文とAND/ORは意味論に保存し、Canvasではバッジへ投影する。"""
    editor = _editor()
    goal_id = _node_id(editor, "社会的・工学的な大きな目標")
    editor.update_question_node(goal_id, "更新後の問い", "本文", ChildCombination.ANY)
    node = editor.node_view_model(goal_id)

    assert (node.text, node.secondary_text, node.badge_text) == ("更新後の問い", "本文", "OR")


def test_layout_changes_do_not_change_semantic_nodes() -> None:
    """ノード移動とエッジラベル移動はlayoutだけを更新する。"""
    editor = _editor()
    isolated_id = _node_id(editor, "未整理のメモ")
    goal_id = _node_id(editor, "社会的・工学的な大きな目標")
    operation_id = _node_id(editor, "量子プロセッサを\n安定して運用するには？")
    edge_id = _edge_id(editor, goal_id, operation_id)
    original = editor.semantic_graph().node_by_id(isolated_id)
    editor.update_node_position(isolated_id, 620.0, 430.0)
    editor.update_edge_label_offset(edge_id, 35.0, -20.0)

    assert editor.semantic_graph().node_by_id(isolated_id) == original
    assert (editor.layout().node_layout(isolated_id).position_x, editor.layout().edge_layout(edge_id).label_offset_y) == (620.0, -20.0)
