"""グラフのノードを描画・操作する Graphics Item。"""

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneContextMenuEvent, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem, QWidget

from knowledge_tree.graph.styles import NodeStyle
from knowledge_tree.viewmodels.graph_viewmodels import GraphNodeViewModel


class NodeItem(QGraphicsObject):
    """表示モデルだけを保持する、汎用的な角丸ノード。"""

    move_started = pyqtSignal(str, object)
    move_committed = pyqtSignal(str, object, object)
    position_changed = pyqtSignal(str)
    context_requested = pyqtSignal(str, object, object)
    double_clicked = pyqtSignal(str)

    def __init__(self, view_model: GraphNodeViewModel, style: NodeStyle) -> None:
        """表示モデルとスタイルからノードGraphics Itemを初期化する。"""
        super().__init__()
        self._view_model = view_model
        self._style = style
        self._drag_start_position: QPointF | None = None
        self._connection_target_active = False
        self._hovered = False
        self.setPos(view_model.position_x, view_model.position_y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, view_model.movable and not view_model.locked)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, view_model.selectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1.0)

    @property
    def node_id(self) -> str:
        """外部に公開する表示ノードID。"""
        return self._view_model.id

    def update_from_view_model(self, view_model: GraphNodeViewModel, style: NodeStyle) -> None:
        """外部のViewModel更新を描画へ反映する。"""
        self.prepareGeometryChange()
        self._view_model = view_model
        self._style = style
        self.setPos(view_model.position_x, view_model.position_y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, view_model.movable and not view_model.locked)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, view_model.selectable)
        self.update()

    def set_connection_target_active(self, active: bool) -> None:
        """接続ドラッグのドロップ候補であることを強調表示する。"""
        if self._connection_target_active != active:
            self._connection_target_active = active
            self.update()

    def is_connection_zone_at(self, scene_position: QPointF) -> bool:
        """scene座標がノード外縁の接続開始領域にあるかを返す。"""
        return self._is_connection_zone(self.mapFromScene(scene_position))

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        """移動中にも接続エッジが追随できるよう位置変化を通知する。"""
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.position_changed.emit(self.node_id)
        return result

    def boundingRect(self) -> QRectF:
        """ローカル座標の描画範囲を返す。"""
        return QRectF(0.0, 0.0, self._view_model.width, self._view_model.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        """角丸枠・主テキスト・副テキストを描画する。"""
        del widget
        rectangle = self.boundingRect()
        border = self._style.selection_border if self.isSelected() or self._connection_target_active else self._style.border
        pen_width = 2.5 if self.isSelected() or self._connection_target_active else 1.5
        if self._hovered and not self.isSelected():
            pen_width = 2.2
        painter.setPen(QPen(border, pen_width))
        painter.setBrush(self._style.background)
        painter.drawRoundedRect(rectangle.adjusted(1.5, 1.5, -1.5, -1.5), 10.0, 10.0)

        title_font = QFont(painter.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(self._style.text)
        title_rect = QRectF(12.0, 10.0, rectangle.width() - 24.0, rectangle.height() * 0.58)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self._view_model.text)

        if self._view_model.secondary_text:
            secondary_font = QFont(painter.font())
            secondary_font.setBold(False)
            secondary_font.setPointSizeF(max(8.0, secondary_font.pointSizeF() - 1.0))
            painter.setFont(secondary_font)
            painter.setPen(self._style.secondary_text)
            secondary_rect = QRectF(12.0, rectangle.height() * 0.62, rectangle.width() - 24.0, rectangle.height() * 0.30)
            painter.drawText(secondary_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self._view_model.secondary_text)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """hover状態を反映する。"""
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """hover状態を解除する。"""
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """辺付近では接続操作ができることをカーソルで示す。"""
        if self._is_connection_zone(event.pos()):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """ノード移動の開始位置を記録する。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = QPointF(self.pos())
            self.move_started.emit(self.node_id, QPointF(self._drag_start_position))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """位置が変わった場合のみ、移動確定を通知する。"""
        super().mouseReleaseEvent(event)
        if self._drag_start_position is not None and self._drag_start_position != self.pos():
            self.move_committed.emit(self.node_id, QPointF(self._drag_start_position), QPointF(self.pos()))
        self._drag_start_position = None

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        """メニュー内容を作らず、要求だけを外へ通知する。"""
        self.context_requested.emit(self.node_id, event.scenePos(), event.screenPos())
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """ダブルクリックを外へ通知する。"""
        self.double_clicked.emit(self.node_id)
        event.accept()

    def _is_connection_zone(self, position: QPointF) -> bool:
        """ノード外縁の接続開始領域かを判定する。"""
        rectangle = self.boundingRect()
        if not rectangle.contains(position):
            return False
        edge_width = 8.0
        return (
            position.x() - rectangle.left() <= edge_width
            or rectangle.right() - position.x() <= edge_width
            or position.y() - rectangle.top() <= edge_width
            or rectangle.bottom() - position.y() <= edge_width
        )
