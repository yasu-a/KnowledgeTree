"""接続ドラッグ中だけ表示する、ドメイン非依存の一時エッジ。"""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget


class ConnectionPreviewItem(QGraphicsObject):
    """ノードからマウス位置または候補ノードへ伸びる一時矢印。"""

    def __init__(self, color: QColor | None = None, dashed: bool = True, directed: bool = True) -> None:
        """色・線種・向きを指定した一時エッジを初期化する。"""
        super().__init__()
        self._path = QPainterPath()
        self._arrow_direction = QPointF(1.0, 0.0)
        self._color = QColor(color) if color is not None else QColor("#2563eb")
        self._dashed = dashed
        self._directed = directed
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(4.0)

    def update_geometry(
        self,
        fixed_rectangle: QRectF,
        cursor_position: QPointF,
        candidate_rectangle: QRectF | None,
        fixed_is_source: bool,
    ) -> None:
        """固定端と、マウスに追随するもう一方の端で一時経路を更新する。"""
        # 固定端が始点か終点かに合わせて、経路の両端と法線を決める。
        if fixed_is_source:
            start, source_normal = self._connection_port(fixed_rectangle, cursor_position)
            if candidate_rectangle is None:
                end = QPointF(cursor_position)
                incoming_direction = self._normalized(end - start)
            else:
                end, target_normal = self._connection_port(candidate_rectangle, fixed_rectangle.center())
                incoming_direction = -target_normal
        else:
            if candidate_rectangle is None:
                start = QPointF(cursor_position)
                source_normal = self._normalized(fixed_rectangle.center() - start)
            else:
                start, source_normal = self._connection_port(candidate_rectangle, fixed_rectangle.center())
            end, target_normal = self._connection_port(fixed_rectangle, start)
            incoming_direction = -target_normal
        # 端点の距離に応じて、滑らかなベジェ曲線の制御点を作る。
        distance = max(1.0, math.hypot(end.x() - start.x(), end.y() - start.y()))
        handle = min(80.0, max(24.0, distance * 0.34))
        path = QPainterPath(start)
        path.cubicTo(start + source_normal * handle, end - incoming_direction * handle, end)
        self.prepareGeometryChange()
        self._path = path
        self._arrow_direction = incoming_direction
        self.update()

    def boundingRect(self) -> QRectF:
        """線幅と矢印を含む一時エッジの描画範囲を返す。"""
        return self._path.boundingRect().adjusted(-14.0, -14.0, 14.0, 14.0)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        """破線のプレビュー線と矢印を描画する。"""
        del option, widget
        color = QColor(self._color)
        color.setAlpha(190)
        pen_style = Qt.PenStyle.DashLine if self._dashed else Qt.PenStyle.SolidLine
        painter.setPen(QPen(color, 2.0, pen_style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        if not self._directed or self._path.isEmpty():
            return
        end = self._path.pointAtPercent(1.0)
        angle = math.atan2(self._arrow_direction.y(), self._arrow_direction.x())
        length = 10.0
        left = QPointF(end.x() - length * math.cos(angle - 0.45), end.y() - length * math.sin(angle - 0.45))
        right = QPointF(end.x() - length * math.cos(angle + 0.45), end.y() - length * math.sin(angle + 0.45))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF((end, left, right)))

    @staticmethod
    def _connection_port(rectangle: QRectF, toward: QPointF) -> tuple[QPointF, QPointF]:
        """指定方向に最も近い矩形辺上の接続点と外向き法線を返す。"""
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

    @staticmethod
    def _normalized(vector: QPointF) -> QPointF:
        """ゼロ長ベクトルにも対応して正規化したベクトルを返す。"""
        length = math.hypot(vector.x(), vector.y())
        if length < 0.001:
            return QPointF(1.0, 0.0)
        return QPointF(vector.x() / length, vector.y() / length)
