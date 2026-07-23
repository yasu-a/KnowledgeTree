"""永続化を伴わない、Canvas操作確認用の外部デモ状態。"""

from dataclasses import dataclass, replace

from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel, GraphViewModel


@dataclass(frozen=True)
class NodeDeletionPlan:
    """削除前に外部Controllerへ提示する親子再接続の候補。"""

    parent_node_ids: tuple[str, ...]
    child_node_ids: tuple[str, ...]

    @property
    def can_reconnect_automatically(self) -> bool:
        """親または子のどちらかが一つだけなら、安全に一括再接続できる。"""
        return bool(self.parent_node_ids and self.child_node_ids) and (
            len(self.parent_node_ids) == 1 or len(self.child_node_ids) == 1
        )

    @property
    def requires_choice(self) -> bool:
        """多対多の再接続で、ユーザー判断が必要かを返す。"""
        return len(self.parent_node_ids) >= 2 and len(self.child_node_ids) >= 2


@dataclass(frozen=True)
class NodeRemovalResult:
    """削除で変化したエッジ数を表す。"""

    removed_edge_count: int
    created_edge_count: int


class DemoGraphEditor:
    """デモ用グラフを外部で更新し、CanvasへViewModelとして渡す。"""

    def __init__(self, graph: GraphViewModel) -> None:
        """初期ViewModelを、デモ操作用の可変状態へ展開する。"""
        self._nodes = {node.id: node for node in graph.nodes}
        self._edges = {edge.id: edge for edge in graph.edges}
        self._next_node_number = 1
        self._next_edge_number = 1

    def graph(self) -> GraphViewModel:
        """現在のデモ状態をCanvas投入用のViewModelに変換する。"""
        return GraphViewModel(nodes=tuple(self._nodes.values()), edges=tuple(self._edges.values()))

    def insert_node_on_edge(self, edge_id: str) -> str:
        """エッジを二つに分割し、中間にデモノードを追加する。"""
        # 分割前の接続と配置を取得する。
        edge = self._edges.pop(edge_id)
        source = self._nodes[edge.source_node_id]
        target = self._nodes[edge.target_node_id]
        node_id = f"inserted-node-{self._next_node_number}"
        self._next_node_number += 1
        width = 60.0
        height = 52.0
        source_center_x = source.position_x + source.width / 2.0
        source_center_y = source.position_y + source.height / 2.0
        target_center_x = target.position_x + target.width / 2.0
        target_center_y = target.position_y + target.height / 2.0
        # 二つのノードの中点へ、挿入用ノードを配置する。
        self._nodes[node_id] = GraphNodeViewModel(
            id=node_id,
            text="挿入",
            secondary_text=None,
            position_x=(source_center_x + target_center_x) / 2.0 - width / 2.0,
            position_y=(source_center_y + target_center_y) / 2.0 - height / 2.0,
            width=width,
            height=height,
            style_key="default",
        )
        # 元エッジを前半に置き換え、後半エッジへラベルを引き継ぐ。
        self._edges[edge_id] = GraphEdgeViewModel(
            id=edge_id,
            source_node_id=edge.source_node_id,
            target_node_id=node_id,
            label="",
            directed=edge.directed,
            style_key=edge.style_key,
            label_anchor=edge.label_anchor,
            label_offset_x=edge.label_offset_x,
            label_offset_y=edge.label_offset_y,
        )
        second_edge_id = f"inserted-edge-{self._next_edge_number}"
        self._next_edge_number += 1
        self._edges[second_edge_id] = GraphEdgeViewModel(
            id=second_edge_id,
            source_node_id=node_id,
            target_node_id=edge.target_node_id,
            label=edge.label,
            directed=edge.directed,
            style_key=edge.style_key,
            label_offset_y=-42.0 if edge.label else 0.0,
        )
        return node_id

    def deletion_plan(self, node_id: str) -> NodeDeletionPlan:
        """有向エッジだけを使い、親子を再接続する候補を作る。"""
        incoming_edges = self._incoming_edges(node_id)
        outgoing_edges = self._outgoing_edges(node_id)
        parent_node_ids = tuple(dict.fromkeys(edge.source_node_id for edge in incoming_edges))
        child_node_ids = tuple(dict.fromkeys(edge.target_node_id for edge in outgoing_edges))
        return NodeDeletionPlan(parent_node_ids=parent_node_ids, child_node_ids=child_node_ids)

    def remove_node(self, node_id: str, reconnect: bool) -> NodeRemovalResult:
        """ノードを削除し、必要に応じて親子を新しい有向エッジで再接続する。"""
        # 削除前に再接続に必要な入出力エッジを控える。
        incoming_edges = self._incoming_edges(node_id)
        outgoing_edges = self._outgoing_edges(node_id)
        connected_edge_ids = [
            edge_id
            for edge_id, edge in self._edges.items()
            if edge.source_node_id == node_id or edge.target_node_id == node_id
        ]
        # ノード本体と接続済みエッジを取り除く。
        self._nodes.pop(node_id)
        for edge_id in connected_edge_ids:
            self._edges.pop(edge_id)
        created_edge_count = 0
        # 選択された場合だけ、親と子の組合せを新規エッジで結ぶ。
        if reconnect:
            for incoming_edge in incoming_edges:
                for outgoing_edge in outgoing_edges:
                    if incoming_edge.source_node_id == outgoing_edge.target_node_id:
                        continue
                    if self._has_directed_edge(incoming_edge.source_node_id, outgoing_edge.target_node_id):
                        continue
                    edge_id = self._new_edge_id("rewired-edge")
                    self._edges[edge_id] = GraphEdgeViewModel(
                        id=edge_id,
                        source_node_id=incoming_edge.source_node_id,
                        target_node_id=outgoing_edge.target_node_id,
                        label=outgoing_edge.label,
                        directed=True,
                        style_key=outgoing_edge.style_key,
                    )
                    created_edge_count += 1
        return NodeRemovalResult(len(connected_edge_ids), created_edge_count)

    def remove_edges(self, edge_ids: list[str]) -> int:
        """指定エッジをデモ状態から削除する。"""
        removed_count = 0
        for edge_id in edge_ids:
            if self._edges.pop(edge_id, None) is not None:
                removed_count += 1
        return removed_count

    def add_edge(self, source_node_id: str, target_node_id: str) -> str | None:
        """接続ドラッグ用の既定有向エッジを外部状態へ追加する。"""
        # 自己接続・重複・閉路となる接続は、デモの主構造として許可しない。
        if (
            source_node_id == target_node_id
            or self._has_directed_edge(source_node_id, target_node_id)
            or self.would_create_directed_cycle(source_node_id, target_node_id)
        ):
            return None
        edge_id = self._new_edge_id("demo-edge")
        self._edges[edge_id] = GraphEdgeViewModel(
            id=edge_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            label="新規接続",
            directed=True,
            style_key="default",
        )
        return edge_id

    def create_node_connected_from(self, source_node_id: str, position_x: float, position_y: float) -> str | None:
        """背景ドロップ位置にデモノードを作り、指定ノードから接続する。"""
        if source_node_id not in self._nodes:
            return None
        # ドロップ位置を中心に、デモ用の既定ノードを作る。
        node_id = f"created-node-{self._next_node_number}"
        self._next_node_number += 1
        width = 235.0
        height = 105.0
        self._nodes[node_id] = GraphNodeViewModel(
            id=node_id,
            text="新しい問い",
            secondary_text="背景へドロップして追加",
            position_x=position_x - width / 2.0,
            position_y=position_y - height / 2.0,
            width=width,
            height=height,
            style_key="question",
        )
        # 接続に成功した場合だけノード作成を確定する。
        if self.add_edge(source_node_id, node_id) is not None:
            return node_id
        self._nodes.pop(node_id)
        return None

    def reconnect_edge(self, edge_id: str, source_node_id: str, target_node_id: str) -> bool:
        """既存エッジの片端を別ノードへ付け替える。デモ固有の閉路・重複を拒否する。"""
        edge = self._edges.get(edge_id)
        if edge is None or source_node_id == target_node_id:
            return False
        # 有向エッジだけは、付け替え後の重複と閉路を検査する。
        if edge.directed and (
            self._has_directed_edge(source_node_id, target_node_id, excluded_edge_id=edge_id)
            or self._would_create_directed_cycle(source_node_id, target_node_id, excluded_edge_id=edge_id)
        ):
            return False
        self._edges[edge_id] = replace(edge, source_node_id=source_node_id, target_node_id=target_node_id)
        return True

    def update_node_position(self, node_id: str, position_x: float, position_y: float) -> None:
        """Canvas上で確定した手動ノード位置を外部デモ状態へ反映する。"""
        self._nodes[node_id] = replace(
            self._nodes[node_id],
            position_x=position_x,
            position_y=position_y,
        )

    def update_edge_label_offset(self, edge_id: str, offset_x: float, offset_y: float) -> None:
        """Canvas上で確定したラベル位置を外部デモ状態へ反映する。"""
        self._edges[edge_id] = replace(
            self._edges[edge_id],
            label_offset_x=offset_x,
            label_offset_y=offset_y,
        )

    def would_create_directed_cycle(self, source_node_id: str, target_node_id: str) -> bool:
        """sourceからtargetを作ると既存の有向経路を閉路にするか判定する。"""
        return self._would_create_directed_cycle(source_node_id, target_node_id)

    def _would_create_directed_cycle(
        self,
        source_node_id: str,
        target_node_id: str,
        excluded_edge_id: str | None = None,
    ) -> bool:
        """指定エッジを除外した有向グラフで、追加予定の接続が閉路を作るか調べる。"""
        pending_node_ids = [target_node_id]
        visited_node_ids: set[str] = set()
        while pending_node_ids:
            node_id = pending_node_ids.pop()
            if node_id == source_node_id:
                return True
            if node_id in visited_node_ids:
                continue
            visited_node_ids.add(node_id)
            # 現在ノードから辿れる子を、次の探索候補へ追加する。
            pending_node_ids.extend(
                edge.target_node_id
                for edge_id, edge in self._edges.items()
                if edge_id != excluded_edge_id and edge.directed and edge.source_node_id == node_id
            )
        return False

    def _incoming_edges(self, node_id: str) -> list[GraphEdgeViewModel]:
        """指定ノードへ入る有向エッジを返す。"""
        return [
            edge
            for edge in self._edges.values()
            if edge.directed and edge.target_node_id == node_id and edge.source_node_id != node_id
        ]

    def _outgoing_edges(self, node_id: str) -> list[GraphEdgeViewModel]:
        """指定ノードから出る有向エッジを返す。"""
        return [
            edge
            for edge in self._edges.values()
            if edge.directed and edge.source_node_id == node_id and edge.target_node_id != node_id
        ]

    def _has_directed_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        excluded_edge_id: str | None = None,
    ) -> bool:
        """除外対象以外に同じ向きの有向エッジがあるか返す。"""
        return any(
            edge.directed and edge.source_node_id == source_node_id and edge.target_node_id == target_node_id
            for edge_id, edge in self._edges.items()
            if edge_id != excluded_edge_id
        )

    def _new_edge_id(self, prefix: str) -> str:
        """指定接頭辞を使った、デモ内で一意なエッジIDを発行する。"""
        edge_id = f"{prefix}-{self._next_edge_number}"
        self._next_edge_number += 1
        return edge_id
