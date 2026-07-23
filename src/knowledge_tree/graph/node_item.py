"""グラフのノードを描画・操作する Graphics Item。"""

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsSceneContextMenuEvent, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem, QWidget

from knowledge_tree.graph.styles import NodeStyle
from knowledge_tree.viewmodels.graph_viewmodels import GraphNodeViewModel


class NodeItem(QGraphicsObject):
    """表示モデルだけを保持する、汎用的な角丸ノード。"""

    _TITLE_FONT_FAMILY = "Yu Gothic UI"
    _TITLE_FONT_SIZE = 16.0
    _SECONDARY_FONT_SIZE = 12.0
    _ACTIVE_BORDER_WIDTH = 4.0
    _HOVER_BORDER_WIDTH = 3.0

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
        self.setToolTip(self._tool_tip())

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
        self.setToolTip(self._tool_tip())
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
        return QRectF(0.0, 0.0, self._view_model.width, self._display_height())

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        """角丸枠・主テキスト・副テキストを描画する。"""
        del widget
        rectangle = self.boundingRect()
        border = self._style.selection_border if self.isSelected() or self._connection_target_active else self._style.border
        pen_width = self._ACTIVE_BORDER_WIDTH if self.isSelected() or self._connection_target_active else 1.5
        if self._hovered and not self.isSelected():
            pen_width = self._HOVER_BORDER_WIDTH
        painter.setPen(QPen(border, pen_width))
        painter.setBrush(self._style.background)
        border_inset = max(1.5, pen_width / 2.0)
        painter.drawRoundedRect(rectangle.adjusted(border_inset, border_inset, -border_inset, -border_inset), 10.0, 10.0)

        # Canvas固有の意味を持たないバッジを、必要なノードだけ右上へ表示する。
        if self._view_model.badge_text:
            badge_rectangle = QRectF(rectangle.width() - 52.0, 8.0, 40.0, 19.0)
            badge_font = QFont(painter.font())
            badge_font.setBold(True)
            badge_font.setPointSizeF(max(8.0, badge_font.pointSizeF() - 1.0))
            painter.setFont(badge_font)
            painter.setPen(QPen(self._style.border, 1.0))
            painter.setBrush(self._style.background)
            painter.drawRoundedRect(badge_rectangle, 7.0, 7.0)
            painter.setPen(self._style.text)
            painter.drawText(badge_rectangle, Qt.AlignmentFlag.AlignCenter, self._view_model.badge_text)

        title_font = self._title_font()
        painter.setFont(title_font)
        painter.setPen(self._style.text)
        title_width = rectangle.width() - (72.0 if self._view_model.badge_text else 24.0)
        title_height = self._title_height(title_width)
        title_rect = QRectF(12.0, 10.0, title_width, title_height)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self._view_model.text)

        if self._view_model.secondary_text:
            secondary_font = self._secondary_font()
            painter.setFont(secondary_font)
            painter.setPen(self._style.secondary_text)
            secondary_height = self._secondary_height(rectangle.width() - 24.0)
            secondary_rect = QRectF(12.0, 10.0 + title_height + 7.0, rectangle.width() - 24.0, secondary_height)
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

    def _display_height(self) -> float:
        """本文全体を収めるためのノードの必要高さを計算する。"""
        if not self._view_model.secondary_text:
            return self._view_model.height
        title_width = self._view_model.width - (72.0 if self._view_model.badge_text else 24.0)
        content_height = 10.0 + self._title_height(title_width) + 7.0 + self._secondary_height(self._view_model.width - 24.0) + 12.0
        return max(self._view_model.height, content_height)

    def _title_font(self) -> QFont:
        """タイトル用の固定サイズ日本語フォントを返す。"""
        font = QFont(self._TITLE_FONT_FAMILY)
        font.setBold(True)
        font.setPointSizeF(self._TITLE_FONT_SIZE)
        return font

    def _secondary_font(self) -> QFont:
        """ノード本文用の日本語フォントを返す。"""
        font = QFont(self._TITLE_FONT_FAMILY)
        font.setPointSizeF(self._SECONDARY_FONT_SIZE)
        return font

    def _title_height(self, width: float) -> float:
        """タイトルを指定幅で折り返した場合の必要な高さを返す。"""
        return self._text_height(self._title_font(), width, self._view_model.text)

    def _secondary_height(self, width: float) -> float:
        """本文を指定幅で折り返した場合の必要な高さを返す。"""
        return self._text_height(self._secondary_font(), width, self._view_model.secondary_text or "")

    @staticmethod
    def _text_height(font: QFont, width: float, text: str) -> float:
        """折り返しを含めたテキストの必要な描画高さを返す。"""
        metrics = QFontMetricsF(font)
        rectangle = metrics.boundingRect(
            QRectF(0.0, 0.0, max(1.0, width), 100000.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            text,
        )
        return max(metrics.lineSpacing(), rectangle.height())

    def _tool_tip(self) -> str:
        """ノード内容を確認できるツールチップを作る。"""
        return "\n\n".join(part for part in (self._view_model.text, self._view_model.secondary_text) if part)
