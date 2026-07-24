"""表示用ViewModelと操作イベントだけを扱う汎用グラフCanvas。"""

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from knowledge_tree.graph.connection_preview_item import ConnectionPreviewItem
from knowledge_tree.graph.edge_item import EdgeItem, EdgeLabelConnectorItem, EdgeLabelItem
from knowledge_tree.graph.node_item import NodeItem
from knowledge_tree.graph.styles import StyleRegistry
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel, GraphViewModel


@dataclass(frozen=True)
class _EdgeDragState:
    """新規作成・既存エッジの付け替えで共有する一時操作状態。"""

    fixed_node_id: str
    fixed_is_source: bool
    edge_id: str | None = None
    original_moving_node_id: str | None = None


class GraphCanvasWidget(QGraphicsView):
    """ドメイン知識・永続化知識を持たないグラフ表示編集Widget。"""

    node_selected = pyqtSignal(str)
    edge_selected = pyqtSignal(str)
    selection_changed = pyqtSignal(object, object)
    selection_cleared = pyqtSignal()

    canvas_clicked = pyqtSignal(object)
    canvas_double_clicked = pyqtSignal(object)
    canvas_context_requested = pyqtSignal(object, object)
    node_context_requested = pyqtSignal(str, object, object)
    edge_context_requested = pyqtSignal(str, object, object)
    node_double_clicked = pyqtSignal(str)
    edge_double_clicked = pyqtSignal(str)

    node_move_started = pyqtSignal(str, object)
    node_move_committed = pyqtSignal(str, object, object)
    edge_label_move_committed = pyqtSignal(str, object, object)
    connection_requested = pyqtSignal(str, str)
    node_creation_requested = pyqtSignal(str, object)
    edge_reconnection_requested = pyqtSignal(str, str, str)
    edge_disconnect_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(object, object)
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """空のグラフSceneと、Canvas操作状態を初期化する。"""
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._nodes: dict[str, NodeItem] = {}
        self._edges: dict[str, EdgeItem] = {}
        self._edge_labels: dict[str, EdgeLabelItem] = {}
        self._edge_label_connectors: dict[str, EdgeLabelConnectorItem] = {}
        self._connection_preview: ConnectionPreviewItem | None = None
        self._edge_drag: _EdgeDragState | None = None
        self._connection_target_node_id: str | None = None
        self._is_rebuilding_graph = False
        self._is_panning = False
        self._pan_start = QPoint()
        self._selected_node_drag_start_scene_position: QPointF | None = None
        self._selected_node_drag_start_positions: dict[str, QPointF] | None = None

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QColor("#f8fafc"))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._scene.selectionChanged.connect(self._emit_selection_changed)

    def set_graph(self, view_model: GraphViewModel) -> None:
        """外部から受け取ったViewModelで表示を全置換する。"""
        self._is_rebuilding_graph = True
        viewport = self.viewport()
        viewport.setUpdatesEnabled(False)
        try:
            # 再構築中はView更新を止め、旧Itemへの保留paintを発生させない。
            self._clear_connection_preview()
            # selectionChangedが同期発火しても、破棄済みラッパーを参照しないよう先に辞書を空にする。
            self._nodes.clear()
            self._edges.clear()
            self._edge_labels.clear()
            self._edge_label_connectors.clear()
            # Sceneが所有する全Itemを、Qtの正式な所有権規約に従って一括破棄する。
            self._scene.clear()
            # ノードを先に作り、参照先ノードがあるエッジだけを追加する。
            for node_view_model in view_model.nodes:
                self._add_node_item(node_view_model)
            for edge_view_model in view_model.edges:
                if edge_view_model.source_node_id in self._nodes and edge_view_model.target_node_id in self._nodes:
                    self._add_edge_item(edge_view_model)
            self._update_scene_rect()
        finally:
            viewport.setUpdatesEnabled(True)
            viewport.update()
            self._is_rebuilding_graph = False
        self._emit_selection_changed()

    def update_node(self, node: GraphNodeViewModel) -> None:
        """指定ノードだけを外部ViewModelで更新する。"""
        item = self._nodes.get(node.id)
        if item is None:
            self._add_node_item(node)
        else:
            item.update_from_view_model(node, StyleRegistry.node_style(node.style_key))
        self._refresh_edges_for_node(node.id)
        self._update_scene_rect()

    def update_edge(self, edge: GraphEdgeViewModel) -> None:
        """指定エッジだけを外部ViewModelで更新する。"""
        item = self._edges.get(edge.id)
        if item is None:
            if edge.source_node_id in self._nodes and edge.target_node_id in self._nodes:
                self._add_edge_item(edge)
            return
        style = StyleRegistry.edge_style(edge.style_key)
        item.update_from_view_model(edge, style)
        label_item = self._edge_labels.get(edge.id)
        # 空ラベルではラベルItemと補助線を除去し、表示上の空枠を残さない。
        if not edge.label and label_item is not None:
            self._scene.removeItem(label_item)
            self._edge_labels.pop(edge.id)
            connector_item = self._edge_label_connectors.pop(edge.id, None)
            if connector_item is not None:
                self._scene.removeItem(connector_item)
            self._refresh_edge(edge.id)
            return
        # ラベルの追加・更新に合わせて、補助線も同期させる。
        if edge.label and label_item is None:
            label_item = EdgeLabelItem(edge.id, edge.label, style, QPointF(edge.label_offset_x, edge.label_offset_y))
            self._edge_labels[edge.id] = label_item
            self._scene.addItem(label_item)
            self._connect_label_events(label_item)
            connector_item = EdgeLabelConnectorItem(style)
            self._edge_label_connectors[edge.id] = connector_item
            self._scene.addItem(connector_item)
        elif label_item is not None:
            label_item.update_from_view_model(edge, style)
            connector_item = self._edge_label_connectors.get(edge.id)
            if connector_item is not None:
                connector_item.update_style(style)
        self._refresh_edge(edge.id)

    def remove_node(self, node_id: str) -> None:
        """表示からノードと接続エッジを除去する。正本データは更新しない。"""
        connected_edge_ids = [
            edge_id
            for edge_id, edge in self._edges.items()
            if edge_id and self._edge_connects_node(edge_id, node_id)
        ]
        for edge_id in connected_edge_ids:
            self.remove_edge(edge_id)
        item = self._nodes.pop(node_id, None)
        if item is not None:
            self._scene.removeItem(item)
        self._update_scene_rect()

    def remove_edge(self, edge_id: str) -> None:
        """表示からエッジを除去する。正本データは更新しない。"""
        label_item = self._edge_labels.pop(edge_id, None)
        if label_item is not None:
            self._scene.removeItem(label_item)
        connector_item = self._edge_label_connectors.pop(edge_id, None)
        if connector_item is not None:
            self._scene.removeItem(connector_item)
        item = self._edges.pop(edge_id, None)
        if item is not None:
            self._scene.removeItem(item)

    def clear_selection(self) -> None:
        """現在の表示選択を解除する。"""
        self._scene.clearSelection()

    def select_node(self, node_id: str) -> None:
        """指定ノードだけを選択状態にする。ビュー位置は変更しない。"""
        item = self._nodes.get(node_id)
        if item is None:
            return
        self._scene.clearSelection()
        item.setSelected(True)

    def select_edge(self, edge_id: str) -> None:
        """指定エッジだけを選択状態にする。"""
        item = self._edges.get(edge_id)
        if item is None:
            return
        self._scene.clearSelection()
        item.setSelected(True)

    def selected_node_ids(self) -> list[str]:
        """選択中のノードIDを返す。"""
        return [node_id for node_id, item in self._nodes.items() if item.isSelected()]

    def selected_edge_ids(self) -> list[str]:
        """選択中のエッジまたはエッジラベルのIDを返す。"""
        selected_ids = [edge_id for edge_id, item in self._edges.items() if item.isSelected()]
        for edge_id, label_item in self._edge_labels.items():
            if label_item.isSelected() and edge_id not in selected_ids:
                selected_ids.append(edge_id)
        return selected_ids

    def fit_all(self) -> None:
        """全グラフが見える倍率へ合わせる。"""
        rectangle = self._scene.itemsBoundingRect()
        if rectangle.isNull():
            return
        self.fitInView(rectangle.adjusted(-40.0, -40.0, 40.0, 40.0), Qt.AspectRatioMode.KeepAspectRatio)
        self.zoom_changed.emit(self.transform().m11())

    def center_on_node(self, node_id: str) -> None:
        """指定ノードを中心に表示する。"""
        item = self._nodes.get(node_id)
        if item is not None:
            self.centerOn(item)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """背景の左ドラッグによるパンと、空白クリック通知を提供する。"""
        viewport_position = event.position().toPoint()
        item_at_position = self.itemAt(viewport_position)
        items_at_position = self.items(viewport_position)
        is_background = item_at_position is None
        # 背景の左ドラッグは、選択解除とCanvas移動に使う。
        if event.button() == Qt.MouseButton.LeftButton and is_background:
            self.clear_selection()
            self.canvas_clicked.emit(self.mapToScene(event.position().toPoint()))
            self._is_panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        scene_position = self.mapToScene(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton:
            node_id = self._node_id_at(scene_position)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and node_id is not None and self.selected_node_ids():
                # Shiftは選択済みノード群へ追加する操作だけに使い、エッジの複数選択は許可しない。
                self._add_node_to_selection(node_id)
                self._start_selected_node_drag(scene_position)
                event.accept()
                return
            if node_id is not None and self._nodes[node_id].isSelected() and len(self.selected_node_ids()) > 1:
                # 選択済みノードを通常ドラッグした場合も、選択中の全ノードを同じ差分だけ移動する。
                self._start_selected_node_drag(scene_position)
                event.accept()
                return
            # ノード辺は新規接続専用とし、既存エッジの端とは操作を分離する。
            if node_id is not None and self._nodes[node_id].is_connection_zone_at(scene_position):
                self._start_new_connection_drag(node_id, scene_position)
                event.accept()
                return
            # エッジ本体の端付近だけは、既存エッジの付け替え操作として扱う。
            if any(isinstance(item, EdgeItem) for item in items_at_position):
                endpoint = self._edge_endpoint_at(scene_position)
                if endpoint is not None:
                    self._start_existing_edge_drag(*endpoint, scene_position)
                    event.accept()
                    return
        if event.button() == Qt.MouseButton.RightButton and is_background:
            self.canvas_context_requested.emit(scene_position, event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """パン中はスクロールバーを移動する。"""
        if self._edge_drag is not None:
            # 新規・既存を問わず、一時エッジの可動端をポインタへ追随させる。
            self._move_connection_drag(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._selected_node_drag_start_scene_position is not None and self._selected_node_drag_start_positions is not None:
            self._move_selected_nodes(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._is_panning:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """パン状態を終了する。"""
        if self._edge_drag is not None and event.button() == Qt.MouseButton.LeftButton:
            self._finish_connection_drag(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._selected_node_drag_start_positions is not None and event.button() == Qt.MouseButton.LeftButton:
            self._commit_selected_node_drag()
            event.accept()
            return
        if self._is_panning and event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """空白ダブルクリックを外部へ通知する。"""
        if self.itemAt(event.position().toPoint()) is None:
            self.canvas_double_clicked.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Ctrlでズーム、Shiftで横移動、通常時は縦移動を行う。"""
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        # 修飾キーごとに、ズーム・横移動・縦移動を切り替える。
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if delta > 0 else 1.0 / 1.15
            current_scale = self.transform().m11()
            next_scale = current_scale * factor
            if 0.20 <= next_scale <= 4.0:
                self.scale(factor, factor)
                self.zoom_changed.emit(next_scale)
        elif event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
        else:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Delete要求を処理する。"""
        if event.key() == Qt.Key.Key_Delete:
            node_ids = self.selected_node_ids()
            edge_ids = self.selected_edge_ids()
            if node_ids or edge_ids:
                self.delete_requested.emit(node_ids, edge_ids)
            event.accept()
            return
        super().keyPressEvent(event)

    def _add_node_item(self, view_model: GraphNodeViewModel) -> None:
        """ViewModelからノードItemを作り、Canvasの通知へ接続する。"""
        item = NodeItem(view_model, StyleRegistry.node_style(view_model.style_key))
        self._nodes[view_model.id] = item
        self._scene.addItem(item)
        item.move_started.connect(self._on_node_move_started)
        item.move_committed.connect(self._on_node_move_committed)
        item.position_changed.connect(self._refresh_edges_for_node)
        item.context_requested.connect(self.node_context_requested.emit)
        item.double_clicked.connect(self.node_double_clicked.emit)

    def _add_edge_item(self, view_model: GraphEdgeViewModel) -> None:
        """ViewModelからエッジ・ラベル・補助線のItemを追加する。"""
        style = StyleRegistry.edge_style(view_model.style_key)
        item = EdgeItem(view_model, style)
        self._edges[view_model.id] = item
        self._scene.addItem(item)
        item.context_requested.connect(self.edge_context_requested.emit)
        item.double_clicked.connect(self.edge_double_clicked.emit)
        if view_model.label:
            label_item = EdgeLabelItem(view_model.id, view_model.label, style, QPointF(view_model.label_offset_x, view_model.label_offset_y))
            self._edge_labels[view_model.id] = label_item
            self._scene.addItem(label_item)
            self._connect_label_events(label_item)
            connector_item = EdgeLabelConnectorItem(style)
            self._edge_label_connectors[view_model.id] = connector_item
            self._scene.addItem(connector_item)
        self._refresh_edge(view_model.id)

    def _connect_label_events(self, item: EdgeLabelItem) -> None:
        """ラベルの移動・選択操作をCanvasのイベントへ中継する。"""
        item.move_committed.connect(self.edge_label_move_committed.emit)
        item.position_changed.connect(self._refresh_label_connector)
        item.context_requested.connect(self.edge_context_requested.emit)
        item.double_clicked.connect(self.edge_double_clicked.emit)

    def _on_node_move_started(self, node_id: str, position: QPointF) -> None:
        """ノード移動開始をCanvas利用側へ通知する。"""
        self.node_move_started.emit(node_id, position)

    def _on_node_move_committed(self, node_id: str, old_position: QPointF, new_position: QPointF) -> None:
        """エッジを再描画してから、確定したノード位置を通知する。"""
        self._refresh_edges_for_node(node_id)
        self.node_move_committed.emit(node_id, old_position, new_position)

    def _add_node_to_selection(self, node_id: str) -> None:
        """エッジ選択を解除し、指定ノードを現在のノード選択へ加える。"""
        for edge_id in self.selected_edge_ids():
            edge_item = self._edges.get(edge_id)
            if edge_item is not None:
                edge_item.setSelected(False)
            label_item = self._edge_labels.get(edge_id)
            if label_item is not None:
                label_item.setSelected(False)
        self._nodes[node_id].setSelected(True)

    def _start_selected_node_drag(self, scene_position: QPointF) -> None:
        """選択ノード群をまとめて移動するための開始座標を記録する。"""
        self._selected_node_drag_start_scene_position = QPointF(scene_position)
        self._selected_node_drag_start_positions = {
            node_id: QPointF(self._nodes[node_id].pos())
            for node_id in self.selected_node_ids()
        }

    def _move_selected_nodes(self, scene_position: QPointF) -> None:
        """開始位置からの差分だけ、選択中のノード群を移動する。"""
        if self._selected_node_drag_start_scene_position is None or self._selected_node_drag_start_positions is None:
            return
        delta = scene_position - self._selected_node_drag_start_scene_position
        for node_id, start_position in self._selected_node_drag_start_positions.items():
            node_item = self._nodes.get(node_id)
            if node_item is not None:
                node_item.setPos(start_position + delta)

    def _commit_selected_node_drag(self) -> None:
        """移動済みの選択ノードごとに位置確定イベントを通知する。"""
        start_positions = self._selected_node_drag_start_positions
        self._selected_node_drag_start_scene_position = None
        self._selected_node_drag_start_positions = None
        if start_positions is None:
            return
        for node_id, old_position in start_positions.items():
            node_item = self._nodes.get(node_id)
            if node_item is None or node_item.pos() == old_position:
                continue
            new_position = QPointF(node_item.pos())
            self._refresh_edges_for_node(node_id)
            self.node_move_committed.emit(node_id, old_position, new_position)
        self._update_scene_rect()

    def _refresh_edges_for_node(self, node_id: str) -> None:
        """指定ノードへ接続する全エッジの経路を再計算する。"""
        for edge_id in self._edges:
            if self._edge_connects_node(edge_id, node_id):
                self._refresh_edge(edge_id)

    def _edge_connects_node(self, edge_id: str, node_id: str) -> bool:
        """指定エッジが指定ノードを始点または終点に持つか返す。"""
        edge = self._edges[edge_id]
        view_model = edge.view_model
        return view_model.source_node_id == node_id or view_model.target_node_id == node_id

    def _refresh_edge(self, edge_id: str) -> None:
        """ノード矩形からエッジ経路とラベル補助線を更新する。"""
        edge = self._edges[edge_id]
        view_model = edge.view_model
        source_item = self._nodes[view_model.source_node_id]
        target_item = self._nodes[view_model.target_node_id]
        edge.update_geometry(source_item.sceneBoundingRect(), target_item.sceneBoundingRect())
        label_item = self._edge_labels.get(edge_id)
        if label_item is not None:
            label_item.set_base_position(edge.label_base_position())
            self._refresh_label_connector(edge_id)

    def _refresh_label_connector(self, edge_id: str) -> None:
        """ラベルとエッジを結ぶ補助線を現在位置へ更新する。"""
        connector_item = self._edge_label_connectors.get(edge_id)
        label_item = self._edge_labels.get(edge_id)
        edge_item = self._edges.get(edge_id)
        if connector_item is not None and label_item is not None and edge_item is not None:
            connector_item.update_geometry(edge_item, label_item.sceneBoundingRect())

    def _update_scene_rect(self) -> None:
        """全Itemを含むスクロール範囲へ、上下左右500pxの操作余白を設定する。"""
        # 空Sceneでも有効な矩形を保ち、背景へのノード追加後もスクロール可能にする。
        item_rectangle = self._scene.itemsBoundingRect()
        self._scene.setSceneRect(item_rectangle.adjusted(-500.0, -500.0, 500.0, 500.0))

    def _emit_selection_changed(self) -> None:
        """再構築中以外で、選択状態をCanvas利用側へまとめて通知する。"""
        if self._is_rebuilding_graph:
            return
        node_ids = self.selected_node_ids()
        edge_ids = self.selected_edge_ids()
        self.selection_changed.emit(node_ids, edge_ids)
        if not node_ids and not edge_ids:
            self.selection_cleared.emit()
        elif len(node_ids) == 1 and not edge_ids:
            self.node_selected.emit(node_ids[0])
        elif len(edge_ids) == 1 and not node_ids:
            self.edge_selected.emit(edge_ids[0])

    def _start_new_connection_drag(self, source_node_id: str, scene_position: QPointF) -> None:
        """ノード辺のドラッグから、新規接続用の一時エッジを作る。"""
        self._clear_connection_preview()
        self._edge_drag = _EdgeDragState(fixed_node_id=source_node_id, fixed_is_source=True)
        self._connection_preview = ConnectionPreviewItem()
        self._scene.addItem(self._connection_preview)
        self._update_connection_preview(scene_position)

    def _start_existing_edge_drag(
        self,
        edge_id: str,
        moving_endpoint_is_target: bool,
        scene_position: QPointF,
    ) -> None:
        """エッジ端のドラッグから、片端だけを動かす一時エッジを作る。"""
        self._clear_connection_preview()
        edge = self._edges[edge_id]
        fixed_node_id = edge.view_model.source_node_id if moving_endpoint_is_target else edge.view_model.target_node_id
        moving_node_id = edge.view_model.target_node_id if moving_endpoint_is_target else edge.view_model.source_node_id
        self._edge_drag = _EdgeDragState(
            fixed_node_id=fixed_node_id,
            fixed_is_source=moving_endpoint_is_target,
            edge_id=edge_id,
            original_moving_node_id=moving_node_id,
        )
        style = StyleRegistry.edge_style(edge.view_model.style_key)
        self._connection_preview = ConnectionPreviewItem(style.line, dashed=False, directed=edge.view_model.directed)
        self._set_existing_edge_drag_visible(edge_id, False)
        self._scene.addItem(self._connection_preview)
        self._update_connection_preview(scene_position)

    def _move_connection_drag(self, scene_position: QPointF) -> None:
        """一時エッジをポインタ位置へ追随させる。"""
        self._update_connection_preview(scene_position)

    def _finish_connection_drag(self, scene_position: QPointF) -> None:
        """ドロップ位置に応じて、新規作成・付け替え・切断を外部へ要求する。"""
        edge_drag = self._edge_drag
        if edge_drag is None:
            return
        target_node_id = self._node_id_at(scene_position, excluded_node_id=edge_drag.fixed_node_id)
        self._clear_connection_preview()
        # 新規接続は、ノードへ接続するか背景にノードを作るかを外部へ委譲する。
        if edge_drag.edge_id is None:
            if target_node_id is not None:
                self.connection_requested.emit(edge_drag.fixed_node_id, target_node_id)
            else:
                self.node_creation_requested.emit(edge_drag.fixed_node_id, scene_position)
            return
        # 既存エッジは、背景で削除、別ノードで端点を付け替える。
        if target_node_id is None:
            self.edge_disconnect_requested.emit(edge_drag.edge_id)
            return
        if target_node_id == edge_drag.original_moving_node_id:
            return
        source_node_id = edge_drag.fixed_node_id if edge_drag.fixed_is_source else target_node_id
        destination_node_id = target_node_id if edge_drag.fixed_is_source else edge_drag.fixed_node_id
        self.edge_reconnection_requested.emit(edge_drag.edge_id, source_node_id, destination_node_id)

    def _update_connection_preview(self, scene_position: QPointF) -> None:
        """ポインタ位置に合わせ、候補ノードの強調と一時エッジを更新する。"""
        if self._connection_preview is None or self._edge_drag is None:
            return
        edge_drag = self._edge_drag
        source_item = self._nodes[edge_drag.fixed_node_id]
        target_node_id = self._node_id_at(scene_position, excluded_node_id=edge_drag.fixed_node_id)
        # 候補が切り替わったときだけ、ノードの強調表示を入れ替える。
        if self._connection_target_node_id != target_node_id:
            if self._connection_target_node_id is not None:
                self._nodes[self._connection_target_node_id].set_connection_target_active(False)
            if target_node_id is not None:
                self._nodes[target_node_id].set_connection_target_active(True)
        target_rectangle = self._nodes[target_node_id].sceneBoundingRect() if target_node_id is not None else None
        self._connection_target_node_id = target_node_id
        self._connection_preview.update_geometry(
            source_item.sceneBoundingRect(),
            scene_position,
            target_rectangle,
            edge_drag.fixed_is_source,
        )

    def _clear_connection_preview(self) -> None:
        """一時エッジ・候補強調を片付け、隠していた既存エッジを戻す。"""
        if self._connection_target_node_id is not None:
            self._nodes[self._connection_target_node_id].set_connection_target_active(False)
        if self._connection_preview is not None:
            self._scene.removeItem(self._connection_preview)
        if self._edge_drag is not None and self._edge_drag.edge_id is not None:
            self._set_existing_edge_drag_visible(self._edge_drag.edge_id, True)
        self._connection_preview = None
        self._edge_drag = None
        self._connection_target_node_id = None

    def _node_id_at(self, scene_position: QPointF, excluded_node_id: str | None = None) -> str | None:
        """ノード内部全体をドロップ先として扱い、IDを返す。"""
        for node_id, item in self._nodes.items():
            if node_id != excluded_node_id and item.sceneBoundingRect().contains(scene_position):
                return node_id
        return None

    def _set_existing_edge_drag_visible(self, edge_id: str, visible: bool) -> None:
        """付け替え中だけ元エッジと付随ラベルを隠し、一時エッジだけを見せる。"""
        self._edges[edge_id].setVisible(visible)
        label_item = self._edge_labels.get(edge_id)
        if label_item is not None:
            label_item.setVisible(visible)
        connector_item = self._edge_label_connectors.get(edge_id)
        if connector_item is not None:
            connector_item.setVisible(visible)

    def _edge_endpoint_at(self, scene_position: QPointF) -> tuple[str, bool] | None:
        """エッジ本体上の端付近を特定し、動かす端が終点かも返す。"""
        closest_endpoint: tuple[str, bool] | None = None
        closest_distance_squared = 14.0 * 14.0
        for edge_id, edge_item in self._edges.items():
            for endpoint, is_target_endpoint in (
                (edge_item.endpoint_for_node(edge_item.view_model.source_node_id), False),
                (edge_item.endpoint_for_node(edge_item.view_model.target_node_id), True),
            ):
                if endpoint is None:
                    continue
                delta_x = endpoint.x() - scene_position.x()
                delta_y = endpoint.y() - scene_position.y()
                distance_squared = delta_x * delta_x + delta_y * delta_y
                if distance_squared <= closest_distance_squared:
                    closest_endpoint = (edge_id, is_target_endpoint)
                    closest_distance_squared = distance_squared
        return closest_endpoint
