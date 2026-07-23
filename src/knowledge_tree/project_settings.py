"""プロジェクト単位で保持するエッジ種類の設定。"""

from dataclasses import dataclass

from knowledge_tree.color_palette import ColorToken
from knowledge_tree.node_kind import NodeKind


@dataclass(frozen=True)
class EdgeType:
    """新規有向エッジへ適用する関係ラベルと色の組。"""

    id: str
    label: str
    color_token: ColorToken
    allowed_endpoints: tuple[tuple[NodeKind, NodeKind], ...]


class ProjectSettings:
    """プロジェクト内のエッジ種類コレクションを所有する。"""

    def __init__(self, edge_types: list[EdgeType] | None = None, node_colors: dict[NodeKind, ColorToken] | None = None) -> None:
        """初期エッジ種類とID採番状態を設定する。"""
        self._edge_types = list(edge_types) if edge_types is not None else list(self.default_edge_types())
        self._node_colors = dict(node_colors) if node_colors is not None else {
            NodeKind.QUESTION: ColorToken.BLUE,
            NodeKind.MEMO: ColorToken.SLATE,
            NodeKind.REFERENCE: ColorToken.EMERALD,
        }

    @staticmethod
    def default_edge_types() -> tuple[EdgeType, ...]:
        """新規プロジェクトへ書き出す初期関係種類を返す。"""
        return (
            EdgeType("refines", "refines", ColorToken.BLUE, ((NodeKind.QUESTION, NodeKind.QUESTION),)),
            EdgeType("contributes-to", "contributesTo", ColorToken.TEAL, ((NodeKind.REFERENCE, NodeKind.QUESTION), (NodeKind.MEMO, NodeKind.QUESTION))),
            EdgeType("leads-to", "leadsTo", ColorToken.PURPLE, ((NodeKind.REFERENCE, NodeKind.REFERENCE),)),
        )

    def edge_types(self) -> tuple[EdgeType, ...]:
        """現在定義されているエッジ種類を表示順で返す。"""
        return tuple(self._edge_types)

    def copy(self) -> "ProjectSettings":
        """ダイアログ内の編集に使う、独立した設定コピーを返す。"""
        return ProjectSettings(list(self._edge_types), dict(self._node_colors))

    def replace_with(self, other: "ProjectSettings") -> None:
        """別の設定内容でこの設定を置き換える。"""
        self._edge_types = list(other.edge_types())
        self._node_colors = {node_kind: other.node_color(node_kind) for node_kind in NodeKind}

    def update_edge_color(self, edge_type_id: str, color_token: ColorToken) -> None:
        """指定関係種類の色だけを更新する。"""
        for index, edge_type in enumerate(self._edge_types):
            if edge_type.id == edge_type_id:
                self._edge_types[index] = EdgeType(edge_type.id, edge_type.label, color_token, edge_type.allowed_endpoints)
                return

    def update_edge_type(
        self,
        edge_type_id: str,
        label: str,
        color_token: ColorToken,
        allowed_endpoints: tuple[tuple[NodeKind, NodeKind], ...],
    ) -> None:
        """指定関係種類の表示名、色、接続可能なノード種別を更新する。"""
        normalized_label = label.strip()
        if not normalized_label:
            raise ValueError("関係ラベルを入力してください。")
        normalized_endpoints = tuple(dict.fromkeys(allowed_endpoints))
        for index, edge_type in enumerate(self._edge_types):
            if edge_type.id == edge_type_id:
                self._edge_types[index] = EdgeType(edge_type.id, normalized_label, color_token, normalized_endpoints)
                return
        raise ValueError("更新対象の関係種類が見つかりません。")

    def add_edge_type(self) -> EdgeType:
        """編集用の新しい関係種類を追加して返す。"""
        used_ids = {edge_type.id for edge_type in self._edge_types}
        sequence = 1
        while f"edge-type-{sequence}" in used_ids:
            sequence += 1
        edge_type = EdgeType(
            f"edge-type-{sequence}",
            "newRelation",
            ColorToken.SLATE,
            ((NodeKind.QUESTION, NodeKind.QUESTION),),
        )
        self._edge_types.append(edge_type)
        return edge_type

    def remove_edge_type(self, edge_type_id: str) -> None:
        """指定関係種類を設定から削除する。"""
        self._edge_types = [edge_type for edge_type in self._edge_types if edge_type.id != edge_type_id]

    def node_color(self, node_kind: NodeKind) -> ColorToken:
        """指定ノード種類に設定された色トークンを返す。"""
        return self._node_colors[node_kind]

    def update_node_color(self, node_kind: NodeKind, color_token: ColorToken) -> None:
        """指定ノード種類の色を更新する。"""
        self._node_colors[node_kind] = color_token

    def default_edge_type(self, source_kind: NodeKind, target_kind: NodeKind) -> EdgeType | None:
        """始点・終点種別に許可された先頭の関係種類を返す。"""
        return next((item for item in self._edge_types if (source_kind, target_kind) in item.allowed_endpoints), None)
