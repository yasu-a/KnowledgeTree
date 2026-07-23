"""ドメインから独立したグラフ表示用モデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNodeViewModel:
    """Canvas が描画するノード。"""

    id: str
    text: str
    secondary_text: str | None
    position_x: float
    position_y: float
    width: float
    height: float
    style_key: str
    movable: bool = True
    selectable: bool = True
    locked: bool = False


@dataclass(frozen=True)
class GraphEdgeViewModel:
    """Canvas が描画するエッジ。"""

    id: str
    source_node_id: str
    target_node_id: str
    label: str
    directed: bool
    style_key: str
    label_anchor: float = 0.5
    label_offset_x: float = 0.0
    label_offset_y: float = 0.0


@dataclass(frozen=True)
class GraphViewModel:
    """Canvas に一括注入するグラフ。"""

    nodes: tuple[GraphNodeViewModel, ...]
    edges: tuple[GraphEdgeViewModel, ...]
