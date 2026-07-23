"""プロジェクト単位で保持するエッジ種類の設定。"""

from dataclasses import dataclass

from knowledge_tree.color_palette import ColorToken


@dataclass(frozen=True)
class EdgeType:
    """新規有向エッジへ適用する関係ラベルと色の組。"""

    id: str
    label: str
    color_token: ColorToken


class ProjectSettings:
    """プロジェクト内のエッジ種類コレクションを所有する。"""

    def __init__(self, edge_types: list[EdgeType] | None = None) -> None:
        """初期エッジ種類とID採番状態を設定する。"""
        self._edge_types = edge_types or [
            EdgeType("refines", "refines", ColorToken.BLUE),
            EdgeType("contributes-to", "contributesTo", ColorToken.TEAL),
            EdgeType("leads-to", "leadsTo", ColorToken.PURPLE),
        ]
        self._next_edge_type_number = self._next_custom_number()

    def edge_types(self) -> tuple[EdgeType, ...]:
        """現在定義されているエッジ種類を表示順で返す。"""
        return tuple(self._edge_types)

    def add_edge_type(self) -> EdgeType:
        """既定値を持つ新しいエッジ種類をコレクション末尾へ追加する。"""
        edge_type = EdgeType(f"custom-{self._next_edge_type_number}", "新しい関係", ColorToken.SLATE)
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

    def update_edge_type(self, edge_type_id: str, label: str, color_token: ColorToken) -> None:
        """指定エッジ種類のラベルと色を更新する。"""
        for index, edge_type in enumerate(self._edge_types):
            if edge_type.id == edge_type_id:
                self._edge_types[index] = EdgeType(edge_type.id, label, color_token)
                return

    def _next_custom_number(self) -> int:
        """既存のcustom IDと重複しない次の連番を求める。"""
        numbers = [
            int(edge_type.id.removeprefix("custom-"))
            for edge_type in self._edge_types
            if edge_type.id.startswith("custom-") and edge_type.id.removeprefix("custom-").isdigit()
        ]
        return max(numbers, default=0) + 1
