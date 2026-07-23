"""グラフのエッジと移動可能なラベルを描画する Graphics Item。"""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsSceneContextMenuEvent, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem, QWidget

from knowledge_tree.graph.styles import EdgeStyle
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel


class EdgeItem(QGraphicsObject):
    """始点・終点の境界間を結ぶ、意味を持たないエッジ。"""

    context_requested = pyqtSignal(str, object, object)
    double_clicked = pyqtSignal(str)

    def __init__(self, view_model: GraphEdgeViewModel, style: EdgeStyle) -> None:
        """表示モデルとスタイルからエッジGraphics Itemを初期化する。"""
        super().__init__()
        self._view_model = view_model
        self._style = style
        self._path = QPainterPath()
        self._target_inward_normal = QPointF(1.0, 0.0)
        self._source_endpoint = QPointF()
        self._target_endpoint = QPointF()
        self._hovered = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0.0)

    @property
    def edge_id(self) -> str:
        """外部に公開する表示エッジID。"""
        return self._view_model.id

    @property
    def view_model(self) -> GraphEdgeViewModel:
        """経路再計算に必要な表示モデルを返す。"""
        return self._view_model

    def update_from_view_model(self, view_model: GraphEdgeViewModel, style: EdgeStyle) -> None:
        """表示モデルの変更を反映する。"""
        self._view_model = view_model
        self._style = style
        self.update()

    def update_geometry(self, source_rect: QRectF, target_rect: QRectF) -> None:
        """接続ノードのscene上の矩形から経路を再計算する。"""
        # 両ノードの境界上に、向かい合う接続点を求める。
        self.prepareGeometryChange()
        start, source_normal = self._connection_port(source_rect, target_rect.center())
        end, target_normal = self._connection_port(target_rect, source_rect.center())
        self._source_endpoint = QPointF(start)
        self._target_endpoint = QPointF(end)
        self._target_inward_normal = -target_normal
        # 直線配置では直線になる、端点法線ベースのベジェ曲線を構成する。
        path = QPainterPath(start)
        delta = end - start
        distance = max(1.0, math.hypot(delta.x(), delta.y()))
        endpoint_handle = min(96.0, max(28.0, distance * 0.34))
        path.cubicTo(
            start + source_normal * endpoint_handle,
            end + target_normal * endpoint_handle,
            end,
        )
        self._path = path
        self.update()

    def endpoint_for_node(self, node_id: str) -> QPointF | None:
        """指定ノード側の接続端を返す。接続していなければNoneを返す。"""
        if self._view_model.source_node_id == node_id:
            return QPointF(self._source_endpoint)
        if self._view_model.target_node_id == node_id:
            return QPointF(self._target_endpoint)
        return None

    def label_base_position(self) -> QPointF:
        """ラベルアンカーに対応するscene上の位置を返す。"""
        anchor = min(1.0, max(0.0, self._view_model.label_anchor))
        return self._path.pointAtPercent(anchor)

    def closest_point(self, position: QPointF) -> QPointF:
        """指定位置に最も近いエッジ上の点を近似計算する。"""
        best_point = self._path.pointAtPercent(0.0)
        best_distance_squared = float("inf")
        for index in range(201):
            point = self._path.pointAtPercent(index / 200.0)
            distance_x = point.x() - position.x()
            distance_y = point.y() - position.y()
            distance_squared = distance_x * distance_x + distance_y * distance_y
            if distance_squared < best_distance_squared:
                best_point = point
                best_distance_squared = distance_squared
        return best_point

    def boundingRect(self) -> QRectF:
        """太い選択線・矢印を含む描画範囲を返す。"""
        return self._path.boundingRect().adjusted(-14.0, -14.0, 14.0, 14.0)

    def shape(self) -> QPainterPath:
        """選択しやすい太さのヒット領域を返す。"""
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        return stroker.createStroke(self._path)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        """線と、有向の場合は終端矢印を描画する。"""
        del option, widget
        color = self._style.selection_line if self.isSelected() else self._style.line
        width = 3.0 if self.isSelected() else 1.8
        if self._hovered and not self.isSelected():
            width = 2.5
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        if self._view_model.directed and not self._path.isEmpty():
            self._draw_arrow(painter, color)

    def _draw_arrow(self, painter: QPainter, color: QColor) -> None:
        """終点方向へ小さな矢印を描く。"""
        end = self._path.pointAtPercent(1.0)
        angle = math.atan2(self._target_inward_normal.y(), self._target_inward_normal.x())
        length = 11.0
        left = QPointF(end.x() - length * math.cos(angle - 0.45), end.y() - length * math.sin(angle - 0.45))
        right = QPointF(end.x() - length * math.cos(angle + 0.45), end.y() - length * math.sin(angle + 0.45))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF((end, left, right)))

    @staticmethod
    def _connection_port(rectangle: QRectF, toward: QPointF) -> tuple[QPointF, QPointF]:
        """接続先に最も近い辺と、その外向き法線を返す。"""
        center = rectangle.center()
        delta_x = toward.x() - center.x()
        delta_y = toward.y() - center.y()
        if abs(delta_x) < 0.001 and abs(delta_y) < 0.001:
            return center, QPointF(1.0, 0.0)
        horizontal_scale = (rectangle.width() / 2.0) / abs(delta_x) if abs(delta_x) >= 0.001 else float("inf")
        vertical_scale = (rectangle.height() / 2.0) / abs(delta_y) if abs(delta_y) >= 0.001 else float("inf")
        if horizontal_scale <= vertical_scale:
            normal = QPointF(1.0 if delta_x >= 0.0 else -1.0, 0.0)
            return QPointF(center.x() + normal.x() * rectangle.width() / 2.0, center.y() + delta_y * horizontal_scale), normal
        normal = QPointF(0.0, 1.0 if delta_y >= 0.0 else -1.0)
        return QPointF(center.x() + delta_x * vertical_scale, center.y() + normal.y() * rectangle.height() / 2.0), normal


    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """ホバー開始を記録してエッジの見た目を更新する。"""
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """ホバー終了を記録してエッジの見た目を更新する。"""
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        """エッジ用コンテキストメニューの要求を外部へ通知する。"""
        self.context_requested.emit(self.edge_id, event.scenePos(), event.screenPos())
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """エッジのダブルクリックを外部へ通知する。"""
        self.double_clicked.emit(self.edge_id)
        event.accept()


class EdgeLabelItem(QGraphicsObject):
    """アンカーからの相対オフセットで位置を保つエッジラベル。"""

    move_committed = pyqtSignal(str, object, object)
    position_changed = pyqtSignal(str)
    context_requested = pyqtSignal(str, object, object)
    double_clicked = pyqtSignal(str)

    def __init__(self, edge_id: str, text: str, style: EdgeStyle, offset: QPointF) -> None:
        """エッジラベルと、そのアンカーからの初期オフセットを設定する。"""
        super().__init__()
        self._edge_id = edge_id
        self._text = text
        self._style = style
        self._base_position = QPointF()
        self._offset = QPointF(offset)
        self._drag_start_offset: QPointF | None = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(2.0)

    @property
    def edge_id(self) -> str:
        """紐付くエッジIDを返す。"""
        return self._edge_id

    def update_from_view_model(self, view_model: GraphEdgeViewModel, style: EdgeStyle) -> None:
        """ラベルの文字列・スタイル・相対位置を更新する。"""
        self.prepareGeometryChange()
        self._text = view_model.label
        self._style = style
        self._offset = QPointF(view_model.label_offset_x, view_model.label_offset_y)
        self.setPos(self._base_position + self._offset)
        self.update()

    def set_base_position(self, position: QPointF) -> None:
        """エッジ経路の変化に追随して相対位置を更新する。"""
        self._base_position = QPointF(position)
        self.setPos(self._base_position + self._offset)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        """補助線がラベル移動中にも追随できるよう位置変化を通知する。"""
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.position_changed.emit(self._edge_id)
        return result

    def boundingRect(self) -> QRectF:
        """ラベル文字列に合わせたローカル描画範囲を返す。"""
        metrics = QFontMetricsF(QFont())
        return QRectF(0.0, 0.0, max(44.0, metrics.horizontalAdvance(self._text) + 16.0), metrics.height() + 8.0)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        """選択状態に応じた枠線とラベル文字列を描画する。"""
        del option, widget
        rectangle = self.boundingRect()
        border = self._style.selection_line if self.isSelected() else self._style.line
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(self._style.label_background)
        painter.drawRoundedRect(rectangle, 5.0, 5.0)
        painter.setPen(border)
        painter.drawText(rectangle, Qt.AlignmentFlag.AlignCenter, self._text)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """ラベル移動前の相対オフセットを記録する。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_offset = QPointF(self._offset)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """ラベル移動後に、変化があれば新しいオフセットを通知する。"""
        super().mouseReleaseEvent(event)
        if self._drag_start_offset is not None:
            self._offset = self.pos() - self._base_position
            if self._drag_start_offset != self._offset:
                self.move_committed.emit(self._edge_id, QPointF(self._drag_start_offset), QPointF(self._offset))
        self._drag_start_offset = None

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        """ラベルに対するコンテキストメニュー要求をエッジとして通知する。"""
        self.context_requested.emit(self._edge_id, event.scenePos(), event.screenPos())
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """ラベルのダブルクリックをエッジ操作として通知する。"""
        self.double_clicked.emit(self._edge_id)
        event.accept()


class EdgeLabelConnectorItem(QGraphicsPathItem):
    """エッジラベルと、その最近傍のエッジ点を結ぶ視覚補助線。"""

    def __init__(self, style: EdgeStyle) -> None:
        """エッジラベルと経路を結ぶ補助線を初期化する。"""
        super().__init__()
        self._style = style
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(0.5)
        self._apply_style()

    def update_style(self, style: EdgeStyle) -> None:
        """エッジのスタイル変更を補助線へ反映する。"""
        self._style = style
        self._apply_style()

    def update_geometry(self, edge: EdgeItem, label_rectangle: QRectF) -> None:
        """ラベル矩形の外縁とエッジ最近傍点を結ぶ線を更新する。"""
        edge_point = edge.closest_point(label_rectangle.center())
        label_point = self._nearest_point_on_rectangle(label_rectangle, edge_point)
        path = QPainterPath(label_point)
        path.lineTo(edge_point)
        self.setPath(path)

    def _apply_style(self) -> None:
        """現在のエッジスタイルから半透明の補助線スタイルを適用する。"""
        color = QColor(self._style.line)
        color.setAlpha(150)
        self.setPen(QPen(color, 0.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

    @staticmethod
    def _nearest_point_on_rectangle(rectangle: QRectF, target: QPointF) -> QPointF:
        """targetに最も近い矩形外縁の点を返す。"""
        center = rectangle.center()
        delta_x = target.x() - center.x()
        delta_y = target.y() - center.y()
        if abs(delta_x) < 0.001 and abs(delta_y) < 0.001:
            return center
        horizontal_scale = (rectangle.width() / 2.0) / abs(delta_x) if abs(delta_x) >= 0.001 else float("inf")
        vertical_scale = (rectangle.height() / 2.0) / abs(delta_y) if abs(delta_y) >= 0.001 else float("inf")
        if horizontal_scale <= vertical_scale:
            return QPointF(
                center.x() + (rectangle.width() / 2.0 if delta_x >= 0.0 else -rectangle.width() / 2.0),
                center.y() + delta_y * horizontal_scale,
            )
        return QPointF(
            center.x() + delta_x * vertical_scale,
            center.y() + (rectangle.height() / 2.0 if delta_y >= 0.0 else -rectangle.height() / 2.0),
        )
