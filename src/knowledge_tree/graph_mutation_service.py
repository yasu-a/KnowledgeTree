"""表示・永続化から独立した、グラフ変更のドメイン規則。"""

from dataclasses import dataclass

from knowledge_tree.node_kind import NodeKind
from knowledge_tree.project_settings import EdgeType


@dataclass(frozen=True)
class GraphNode:
    """グラフ規則の判定に必要なノードの最小表現。"""

    id: str
    kind: NodeKind


@dataclass(frozen=True)
class GraphEdge:
    """グラフ規則の判定に必要なエッジの最小表現。"""

    id: str
    source_node_id: str
    target_node_id: str
    label: str
    directed: bool


@dataclass(frozen=True)
class Graph:
    """ノード種別と関係ラベルだけを持つ、画面非依存のグラフ。"""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def node(self, node_id: str) -> GraphNode | None:
        """指定IDのノードを返す。存在しない場合はNoneを返す。"""
        return next((node for node in self.nodes if node.id == node_id), None)

    def edge(self, edge_id: str) -> GraphEdge | None:
        """指定IDのエッジを返す。存在しない場合はNoneを返す。"""
        return next((edge for edge in self.edges if edge.id == edge_id), None)

    def without_node(self, node_id: str) -> "Graph":
        """指定ノードと接続エッジを除いた新しいグラフを返す。"""
        return Graph(
            tuple(node for node in self.nodes if node.id != node_id),
            tuple(edge for edge in self.edges if node_id not in (edge.source_node_id, edge.target_node_id)),
        )

    def with_edge(self, edge: GraphEdge) -> "Graph":
        """指定エッジを追加した新しいグラフを返す。"""
        return Graph(self.nodes, (*self.edges, edge))


@dataclass(frozen=True)
class GraphMutationResult:
    """グラフ変更の可否と、拒否時に表示する理由。"""

    allowed: bool
    message: str = ""


@dataclass(frozen=True)
class EdgeConnection:
    """ノード削除後に作成する、種類ラベル付きの有向接続。"""

    source_node_id: str
    target_node_id: str
    label: str


@dataclass(frozen=True)
class NodeDeletionPlan:
    """削除時に意味を維持できる、問い間の再接続候補。"""

    reconnections: tuple[EdgeConnection, ...]


class GraphMutationService:
    """エッジ種類設定に基づき、グラフ変更の意味的な可否を判定する。"""

    def __init__(self, graph: Graph, edge_types: tuple[EdgeType, ...]) -> None:
        """判定対象のグラフと、ラベルで識別する関係種類を設定する。"""
        self._graph = graph
        self._edge_types_by_label = {edge_type.label: edge_type for edge_type in edge_types}

    def validate_create_edge(self, source_node_id: str, target_node_id: str, label: str) -> GraphMutationResult:
        """新しい有向エッジを作成できるかを検証する。"""
        return self._validate_directed_edge(self._graph, source_node_id, target_node_id, label)

    def validate_create_edge_to_new_node(
        self,
        source_node_id: str,
        target_node_kind: NodeKind,
        label: str,
    ) -> GraphMutationResult:
        """新規ノードへ向かう有向エッジの、種類と関係ラベルを検証する。"""
        source = self._graph.node(source_node_id)
        if source is None:
            return GraphMutationResult(False, "接続元ノードが見つかりません。")
        return self._validate_edge_endpoints(source.kind, target_node_kind, label)

    def validate_reconnect_edge(
        self,
        edge_id: str,
        source_node_id: str,
        target_node_id: str,
    ) -> GraphMutationResult:
        """指定エッジを新しい両端へ付け替えられるかを検証する。"""
        edge = self._graph.edge(edge_id)
        if edge is None:
            return GraphMutationResult(False, "付け替えるエッジが見つかりません。")
        if not edge.directed:
            return GraphMutationResult(False, "無向エッジの付け替えはこのプロジェクトでは扱えません。")
        return self._validate_directed_edge(
            self._graph,
            source_node_id,
            target_node_id,
            edge.label,
            excluded_edge_id=edge_id,
        )

    def validate_edge_type_change(self, edge_id: str, label: str) -> GraphMutationResult:
        """既存エッジの関係種類を、現在の両端ノードで変更できるかを検証する。"""
        edge = self._graph.edge(edge_id)
        if edge is None:
            return GraphMutationResult(False, "変更するエッジが見つかりません。")
        source = self._graph.node(edge.source_node_id)
        target = self._graph.node(edge.target_node_id)
        if source is None or target is None:
            return GraphMutationResult(False, "エッジの接続先ノードが見つかりません。")
        return self._validate_edge_endpoints(source.kind, target.kind, label)

    def validate_split_edge(self, edge_id: str, inserted_node_kind: NodeKind) -> GraphMutationResult:
        """指定エッジを、指定種別の新規ノードで二分割できるかを検証する。"""
        edge = self._graph.edge(edge_id)
        if edge is None:
            return GraphMutationResult(False, "分割するエッジが見つかりません。")
        if not edge.directed:
            return GraphMutationResult(False, "無向エッジの分割はこのプロジェクトでは扱えません。")
        source = self._graph.node(edge.source_node_id)
        target = self._graph.node(edge.target_node_id)
        if source is None or target is None:
            return GraphMutationResult(False, "エッジの接続先ノードが見つかりません。")
        first_result = self._validate_edge_endpoints(source.kind, inserted_node_kind, edge.label)
        if not first_result.allowed:
            return first_result
        return self._validate_edge_endpoints(inserted_node_kind, target.kind, edge.label)

    def plan_node_deletion(self, node_id: str) -> NodeDeletionPlan:
        """削除後にも保持できる、同一種類の問い間接続だけを計画する。"""
        deleted_node = self._graph.node(node_id)
        if deleted_node is None or deleted_node.kind != NodeKind.QUESTION:
            return NodeDeletionPlan(())

        # 削除対象の問いに接続する、同一ラベルの問い間エッジだけを収集する。
        incoming_by_label: dict[str, list[GraphEdge]] = {}
        outgoing_by_label: dict[str, list[GraphEdge]] = {}
        for edge in self._graph.edges:
            if not edge.directed or not edge.label:
                continue
            if edge.target_node_id == node_id:
                source = self._graph.node(edge.source_node_id)
                if source is not None and source.kind == NodeKind.QUESTION:
                    incoming_by_label.setdefault(edge.label, []).append(edge)
            elif edge.source_node_id == node_id:
                target = self._graph.node(edge.target_node_id)
                if target is not None and target.kind == NodeKind.QUESTION:
                    outgoing_by_label.setdefault(edge.label, []).append(edge)

        remaining_graph = self._graph.without_node(node_id)
        reconnections: list[EdgeConnection] = []
        for label in incoming_by_label.keys() & outgoing_by_label.keys():
            incoming_edges = incoming_by_label[label]
            outgoing_edges = outgoing_by_label[label]
            parents = tuple(dict.fromkeys(edge.source_node_id for edge in incoming_edges))
            children = tuple(dict.fromkeys(edge.target_node_id for edge in outgoing_edges))
            # 多対多の省略は、問いの構造を意図せず広げるため自動化しない。
            if len(parents) > 1 and len(children) > 1:
                continue
            for parent_node_id in parents:
                for child_node_id in children:
                    validation = self._validate_directed_edge(remaining_graph, parent_node_id, child_node_id, label)
                    if not validation.allowed:
                        continue
                    reconnection = EdgeConnection(parent_node_id, child_node_id, label)
                    reconnections.append(reconnection)
                    remaining_graph = remaining_graph.with_edge(
                        GraphEdge(
                            f"planned-reconnection-{len(reconnections)}",
                            parent_node_id,
                            child_node_id,
                            label,
                            True,
                        )
                    )
        return NodeDeletionPlan(tuple(reconnections))

    def _validate_directed_edge(
        self,
        graph: Graph,
        source_node_id: str,
        target_node_id: str,
        label: str,
        excluded_edge_id: str | None = None,
    ) -> GraphMutationResult:
        """ノード存在・種類・重複・閉路を含め、有向エッジを検証する。"""
        source = graph.node(source_node_id)
        target = graph.node(target_node_id)
        if source is None or target is None:
            return GraphMutationResult(False, "接続するノードが見つかりません。")
        if source_node_id == target_node_id:
            return GraphMutationResult(False, "同じノード自身へは接続できません。")
        endpoint_result = self._validate_edge_endpoints(source.kind, target.kind, label)
        if not endpoint_result.allowed:
            return endpoint_result
        if any(
            edge.id != excluded_edge_id
            and edge.directed
            and edge.source_node_id == source_node_id
            and edge.target_node_id == target_node_id
            for edge in graph.edges
        ):
            return GraphMutationResult(False, "同一方向の接続がすでにあります。")
        if self._would_create_directed_cycle(graph, source_node_id, target_node_id, excluded_edge_id):
            return GraphMutationResult(False, "有向グラフに閉路ができるため接続できません。")
        return GraphMutationResult(True)

    def _validate_edge_endpoints(
        self,
        source_kind: NodeKind,
        target_kind: NodeKind,
        label: str,
    ) -> GraphMutationResult:
        """ラベルが示す関係種類で、ノード種別の組合せが許可されるかを検証する。"""
        if not label:
            return GraphMutationResult(True)
        edge_type = self._edge_types_by_label.get(label)
        if edge_type is None:
            return GraphMutationResult(False, "この関係ラベルはプロジェクト設定に定義されていません。")
        if (source_kind, target_kind) not in edge_type.allowed_endpoints:
            return GraphMutationResult(False, "この関係では、選択したノード種類を接続できません。")
        return GraphMutationResult(True)

    @staticmethod
    def _would_create_directed_cycle(
        graph: Graph,
        source_node_id: str,
        target_node_id: str,
        excluded_edge_id: str | None,
    ) -> bool:
        """指定エッジを除外した有向グラフで、追加予定の接続が閉路を作るか判定する。"""
        pending_node_ids = [target_node_id]
        visited_node_ids: set[str] = set()
        while pending_node_ids:
            node_id = pending_node_ids.pop()
            if node_id == source_node_id:
                return True
            if node_id in visited_node_ids:
                continue
            visited_node_ids.add(node_id)
            pending_node_ids.extend(
                edge.target_node_id
                for edge in graph.edges
                if edge.id != excluded_edge_id and edge.directed and edge.source_node_id == node_id
            )
        return False
