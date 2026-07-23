"""永続化前の、アプリ全体で共有する実行時設定。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PaletteColor:
    """名前と16進数表記を持つ、選択用の自然配色。"""

    name: str
    hex_color: str


@dataclass(frozen=True)
class EdgeType:
    """新規有向エッジへ適用する関係ラベルと色の組。"""

    id: str
    label: str
    color_hex: str


NATURAL_PALETTE: tuple[PaletteColor, ...] = (
    PaletteColor("スレート", "#64748b"), PaletteColor("ブルー", "#2563eb"), PaletteColor("シアン", "#0891b2"),
    PaletteColor("ティール", "#0f766e"), PaletteColor("エメラルド", "#059669"), PaletteColor("グリーン", "#65a30d"),
    PaletteColor("ライム", "#84a80b"), PaletteColor("アンバー", "#d97706"), PaletteColor("オレンジ", "#ea580c"),
    PaletteColor("レッド", "#dc2626"), PaletteColor("ローズ", "#e11d48"), PaletteColor("ピンク", "#db2777"),
    PaletteColor("フクシア", "#c026d3"), PaletteColor("パープル", "#7c3aed"), PaletteColor("インディゴ", "#4f46e5"),
)


class GlobalSettings:
    """userdataへの永続化前に使う、エッジ種類コレクションの所有者。"""

    def __init__(self) -> None:
        """初期エッジ種類とID採番状態を設定する。"""
        self._edge_types = [
            EdgeType("refines", "refines", "#2563eb"),
            EdgeType("contributes-to", "contributesTo", "#006d77"),
            EdgeType("leads-to", "leadsTo", "#7c3aed"),
        ]
        self._next_edge_type_number = 1

    def edge_types(self) -> tuple[EdgeType, ...]:
        """現在定義されているエッジ種類を表示順で返す。"""
        return tuple(self._edge_types)

    def add_edge_type(self) -> EdgeType:
        """既定値を持つ新しいエッジ種類をコレクション末尾へ追加する。"""
        edge_type = EdgeType(f"custom-{self._next_edge_type_number}", "新しい関係", "#64748b")
        self._next_edge_type_number += 1
        self._edge_types.append(edge_type)
        return edge_type

    def remove_edge_type(self, edge_type_id: str) -> bool:
        """指定IDのエッジ種類を削除し、成功したか返す。"""
        for index, edge_type in enumerate(self._edge_types):
            if edge_type.id == edge_type_id:
                self._edge_types.pop(index)
                return True
        return False

    def update_edge_type(self, edge_type_id: str, label: str, color_hex: str) -> None:
        """指定エッジ種類のラベルと色を更新する。"""
        for index, edge_type in enumerate(self._edge_types):
            if edge_type.id == edge_type_id:
                self._edge_types[index] = EdgeType(edge_type.id, label, color_hex)
                return
