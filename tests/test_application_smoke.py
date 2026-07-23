"""アプリケーションUIの最小スモークテスト。"""

from knowledge_tree.ui.main_window import MainWindow
from PyQt6.QtCore import QPointF


def test_main_window_displays_the_canvas(qtbot: object) -> None:
    """MainWindowが生成され、Canvasへサンプルが投入される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle().startswith("KnowledgeTree")
    assert window.canvas.selected_node_ids() == []


def test_adding_an_edge_keeps_an_externally_updated_node_position(qtbot: object) -> None:
    """接続追加でViewModelを再投入しても、手動位置を初期値へ戻さない。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window._show_node_move("isolated", QPointF(80.0, 500.0), QPointF(620.0, 430.0))
    window._create_demo_edge("question", "isolated")

    assert window.canvas._nodes["isolated"].pos() == QPointF(620.0, 430.0)


def test_inspector_edits_a_selected_question_and_edge(qtbot: object) -> None:
    """右側インスペクタの編集は、外部状態とCanvasへ即時反映される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.canvas.select_node("goal")
    qtbot.waitUntil(lambda: window.inspector.title_edit.text() == "社会的・工学的な大きな目標")
    window.inspector.title_edit.setText("更新した質問")
    window.inspector.title_edit.editingFinished.emit()
    window.inspector.combination_combo.setCurrentIndex(1)

    node = window._demo_graph_editor.node_view_model("goal")
    assert (node.text, node.badge_text) == ("更新した質問", "OR")
    assert window.canvas._nodes["goal"]._view_model.badge_text == "OR"

    window.canvas.select_edge("edge-goal")
    qtbot.waitUntil(lambda: window.inspector.edge_type_combo.currentText() == "refines")
    assert window.inspector.edge_type_combo.itemIcon(1).isNull() is False
    window.inspector.edge_type_combo.setCurrentIndex(0)

    assert window._demo_graph_editor.edge_view_model("edge-goal").label == ""
    assert "edge-goal" not in window.canvas._edge_labels


def test_toolbar_default_label_is_used_for_new_edges(qtbot: object) -> None:
    """ツールバーの既定ラベルは、新規作成する関係エッジへ適用される。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window.default_edge_label_combo.setCurrentText("contributesTo")
    window._create_demo_edge("question", "isolated")

    edge = next(edge for edge in window._demo_graph_editor.graph().edges if edge.source_node_id == "question" and edge.target_node_id == "isolated")
    assert (edge.label, edge.style_key) == ("contributesTo", "global-edge-type:contributes-to")


def test_inspector_can_be_reopened_from_the_view_menu_and_double_click_handlers(qtbot: object) -> None:
    """閉じたインスペクタは表示メニューとダブルクリック操作で再表示できる。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.inspector_dock.hide()
    window.inspector_visibility_action.trigger()
    assert window.inspector_dock.isVisible() is True

    window.inspector_dock.hide()
    window._show_node_inspector("goal")
    assert window.inspector_dock.isVisible() is True
    assert window.canvas.selected_node_ids() == ["goal"]

    window.inspector_dock.hide()
    window._show_edge_inspector("edge-goal")
    assert window.inspector_dock.isVisible() is True
    assert window.canvas.selected_edge_ids() == ["edge-goal"]


def test_opening_inspector_preserves_the_canvas_top_left_scene_position(qtbot: object) -> None:
    """右側ドックを表示しても、Canvas左上のscene座標は見かけ上移動しない。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.inspector_dock.hide()
    qtbot.wait(10)
    top_left_before = window.canvas.mapToScene(window.canvas.viewport().rect().topLeft())

    window._show_node_inspector("goal")
    qtbot.wait(20)
    top_left_after = window.canvas.mapToScene(window.canvas.viewport().rect().topLeft())

    assert abs(top_left_after.x() - top_left_before.x()) < 2.0
    assert abs(top_left_after.y() - top_left_before.y()) < 2.0


def test_default_edge_type_combo_can_create_an_unlabeled_edge(qtbot: object) -> None:
    """（ラベルなし）を選ぶと、設定コレクション外のラベルなしエッジを作成する。"""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.default_edge_label_combo.currentText() == "（ラベルなし）"
    window._create_demo_edge("question", "isolated")

    edge = next(edge for edge in window._demo_graph_editor.graph().edges if edge.source_node_id == "question" and edge.target_node_id == "isolated")
    assert (edge.label, edge.style_key) == ("", "default")
