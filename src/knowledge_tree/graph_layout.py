"""グラフの意味から独立したCanvasレイアウトモデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeLayout:
    """ノードのCanvas上の位置と大きさ。"""

    node_id: str
    position_x: float
    position_y: float
    width: float
    height: float


@dataclass(frozen=True)
class EdgeLayout:
    """エッジラベルのCanvas上の補正位置。"""

    edge_id: str
    label_anchor: float = 0.5
    label_offset_x: float = 0.0
    label_offset_y: float = 0.0


@dataclass(frozen=True)
class GraphLayout:
    """グラフに対応するノード・エッジのレイアウト。"""

    node_layouts: tuple[NodeLayout, ...]
    edge_layouts: tuple[EdgeLayout, ...]

    def node_layout(self, node_id: str) -> NodeLayout:
        """指定ノードのレイアウトを返す。"""
        return next(layout for layout in self.node_layouts if layout.node_id == node_id)

    def edge_layout(self, edge_id: str) -> EdgeLayout:
        """指定エッジのレイアウトを返す。"""
        return next(layout for layout in self.edge_layouts if layout.edge_id == edge_id)
