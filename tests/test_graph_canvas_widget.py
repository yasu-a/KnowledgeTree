"""ドメイン非依存Canvasの基本操作を検証する。"""

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent

from knowledge_tree.demo_data import build_demo_graph
from knowledge_tree.graph.graph_canvas_widget import GraphCanvasWidget


def test_canvas_accepts_an_externally_supplied_view_model(qtbot: object) -> None:
    """Canvasは外部ViewModelを描画し、ノード選択を公開する。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    node_center = canvas.mapFromScene(QPointF(200.0, 130.0))
    qtbot.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=node_center)

    assert canvas.selected_node_ids() == ["goal"]
    assert canvas.selected_edge_ids() == []


def test_node_drag_emits_one_committed_move_event(qtbot: object) -> None:
    """ノードのドラッグ終了時に一度だけ移動確定イベントを送る。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    node_center = canvas.mapFromScene(QPointF(200.0, 130.0))
    with qtbot.waitSignal(canvas.node_move_committed, timeout=1000) as blocker:
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=node_center)
        qtbot.mouseMove(canvas.viewport(), node_center + QPoint(45, 20))
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=node_center + QPoint(45, 20))

    assert blocker.args[0] == "goal"
    assert blocker.args[1] != blocker.args[2]


def test_moved_edge_label_gets_a_connector_to_its_edge(qtbot: object) -> None:
    """ラベルをエッジから離すと、最近傍点への補助線が更新される。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.set_graph(build_demo_graph())

    label = canvas._edge_labels["edge-goal"]
    label.setPos(label.pos() + QPointF(80.0, -45.0))

    assert canvas._edge_label_connectors["edge-goal"].path().length() > 10.0


def test_wheel_uses_modifier_keys_for_zoom_and_pan(qtbot: object) -> None:
    """Ctrlはズーム、Shiftは横移動、通常時は縦移動として扱う。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(800, 500)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()
    canvas.scale(2.0, 2.0)

    vertical_bar = canvas.verticalScrollBar()
    vertical_bar.setValue((vertical_bar.minimum() + vertical_bar.maximum()) // 2)
    vertical_before = vertical_bar.value()
    canvas.wheelEvent(_wheel_event(Qt.KeyboardModifier.NoModifier))
    assert vertical_bar.value() < vertical_before

    horizontal_bar = canvas.horizontalScrollBar()
    horizontal_bar.setValue((horizontal_bar.minimum() + horizontal_bar.maximum()) // 2)
    horizontal_before = horizontal_bar.value()
    canvas.wheelEvent(_wheel_event(Qt.KeyboardModifier.ShiftModifier))
    assert horizontal_bar.value() < horizontal_before

    scale_before = canvas.transform().m11()
    canvas.wheelEvent(_wheel_event(Qt.KeyboardModifier.ControlModifier))
    assert canvas.transform().m11() > scale_before


def test_dragging_from_a_node_edge_requests_a_connection(qtbot: object) -> None:
    """ノード外縁から別ノード内部へドラッグすると、接続要求を送る。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    source_edge = canvas.mapFromScene(QPointF(200.0, 82.0))
    target_center = canvas.mapFromScene(QPointF(527.0, 130.0))
    with qtbot.waitSignal(canvas.connection_requested, timeout=1000) as blocker:
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=source_edge)
        qtbot.mouseMove(canvas.viewport(), target_center)
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=target_center)

    assert blocker.args == ["goal", "operation"]


def test_dragging_from_a_node_edge_to_blank_requests_node_creation(qtbot: object) -> None:
    """新規接続を背景へドロップすると、外部へノード作成を要求する。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    source_edge = canvas.mapFromScene(QPointF(200.0, 82.0))
    blank_position = canvas.mapFromScene(QPointF(500.0, 560.0))
    with qtbot.waitSignal(canvas.node_creation_requested, timeout=1000) as blocker:
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=source_edge)
        qtbot.mouseMove(canvas.viewport(), blank_position)
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=blank_position)

    assert blocker.args[0] == "goal"
    requested_position = blocker.args[1]
    assert abs(requested_position.x() - 500.0) < 1.0
    assert abs(requested_position.y() - 560.0) < 1.0


def test_dragging_an_existing_edge_endpoint_to_blank_requests_disconnection(qtbot: object) -> None:
    """既存エッジの接続端はマウスへ追随し、空白で離すと外部へ切断を要求する。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    endpoint = canvas._edges["edge-goal"].endpoint_for_node("operation")
    assert endpoint is not None
    endpoint_position = canvas.mapFromScene(endpoint + QPointF(-10.0, 0.0))
    blank_position = canvas.mapFromScene(QPointF(700.0, 550.0))
    with qtbot.waitSignal(canvas.edge_disconnect_requested, timeout=1000) as blocker:
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=endpoint_position)
        qtbot.mouseMove(canvas.viewport(), blank_position)
        assert canvas._connection_preview is not None
        assert canvas._edges["edge-goal"].isVisible() is False
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=blank_position)

    assert blocker.args == ["edge-goal"]


def test_dragging_an_existing_edge_endpoint_to_a_node_requests_reconnection(qtbot: object) -> None:
    """既存エッジ端を別ノードで離すと、エッジIDと新しい両端を外部へ送る。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    endpoint = canvas._edges["edge-goal"].endpoint_for_node("operation")
    assert endpoint is not None
    endpoint_position = canvas.mapFromScene(endpoint + QPointF(-10.0, 0.0))
    target_center = canvas.mapFromScene(QPointF(877.0, 130.0))
    with qtbot.waitSignal(canvas.edge_reconnection_requested, timeout=1000) as blocker:
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=endpoint_position)
        qtbot.mouseMove(canvas.viewport(), target_center)
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=target_center)

    assert blocker.args == ["edge-goal", "goal", "diagnosis"]


def test_dragging_a_node_border_at_an_existing_endpoint_starts_a_new_connection(qtbot: object) -> None:
    """ノード辺の操作は、既存エッジ端と重なっていても新規接続として扱う。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    endpoint = canvas._edges["edge-goal"].endpoint_for_node("operation")
    assert endpoint is not None
    node_side_position = canvas.mapFromScene(endpoint + QPointF(4.0, 0.0))
    target_center = canvas.mapFromScene(QPointF(877.0, 130.0))
    with qtbot.waitSignal(canvas.connection_requested, timeout=1000) as blocker:
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=node_side_position)
        qtbot.mouseMove(canvas.viewport(), target_center)
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=target_center)

    assert blocker.args == ["operation", "diagnosis"]


def test_dragging_an_undirected_edge_endpoint_keeps_its_preview_undirected(qtbot: object) -> None:
    """無向エッジの付け替え中プレビューには矢印を描かない。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    endpoint = canvas._edges["edge-note"].endpoint_for_node("note")
    assert endpoint is not None
    endpoint_position = canvas.mapFromScene(endpoint + QPointF(-10.0, 0.0))
    blank_position = canvas.mapFromScene(QPointF(950.0, 560.0))
    qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=endpoint_position)
    qtbot.mouseMove(canvas.viewport(), blank_position)

    assert canvas._connection_preview is not None
    assert canvas._connection_preview._directed is False
    qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=blank_position)


def test_replacing_a_selected_graph_does_not_access_deleted_qt_items(qtbot: object) -> None:
    """選択中でも全ViewModelを再投入でき、破棄済みItemを参照しない。"""
    canvas = GraphCanvasWidget()
    qtbot.addWidget(canvas)
    canvas.resize(1000, 700)
    canvas.set_graph(build_demo_graph())
    canvas.show()
    canvas.fit_all()

    node_center = canvas.mapFromScene(QPointF(200.0, 130.0))
    qtbot.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=node_center)
    canvas.set_graph(build_demo_graph())

    assert canvas.selected_node_ids() == []


def _wheel_event(modifiers: Qt.KeyboardModifier) -> QWheelEvent:
    """指定修飾キー付きの上方向ホイールイベントを作る。"""
    return QWheelEvent(
        QPointF(300.0, 250.0),
        QPointF(300.0, 250.0),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
