"""プロジェクトのドメイン状態とレイアウトを編集するアプリケーションサービス。"""

from dataclasses import dataclass, replace

from knowledge_tree.domain_graph import ChildCombination, KnowledgeEdge, KnowledgeGraph, MemoNode, QuestionNode, ReferenceNode
from knowledge_tree.graph_factory import GraphFactory
from knowledge_tree.graph_layout import EdgeLayout, GraphLayout, NodeLayout
from knowledge_tree.graph_presenter import GraphPresenter
from knowledge_tree.graph_mutation_service import EdgeConnection
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.project_content import ProjectContent
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.reference_catalog import ReferenceCatalog, ReferenceLink
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel, GraphViewModel


@dataclass(frozen=True)
class NodeRemovalResult:
    """ノード削除で変化したエッジ数を表す。"""

    removed_edge_count: int
    created_edge_count: int


class ProjectGraphEditor:
    """UI要求を意味論的なグラフとレイアウトの更新へ変換する。"""

    def __init__(
        self,
        content: ProjectContent,
        reference_catalog: ReferenceCatalog | None = None,
        graph_factory: GraphFactory | None = None,
    ) -> None:
        """保存済みコンテンツを編集可能な状態として保持する。"""
        self._nodes = {node.id: node for node in content.graph.nodes}
        self._edges = {edge.id: edge for edge in content.graph.edges}
        self._node_layouts = {item.node_id: item for item in content.layout.node_layouts}
        self._edge_layouts = {item.edge_id: item for item in content.layout.edge_layouts}
        self._settings = content.settings
        self._reference_catalog = reference_catalog
        self._factory = graph_factory or GraphFactory()
        self._presenter = GraphPresenter()

    def content(self) -> ProjectContent:
        """現在の意味論・レイアウト・設定を保存用コンテンツとして返す。"""
        return ProjectContent(self.semantic_graph(), self.layout(), self._settings)

    def semantic_graph(self) -> KnowledgeGraph:
        """現在の意味論的なグラフを返す。"""
        return KnowledgeGraph(tuple(self._nodes.values()), tuple(self._edges.values()))

    def layout(self) -> GraphLayout:
        """現在のCanvasレイアウトを返す。"""
        return GraphLayout(tuple(self._node_layouts.values()), tuple(self._edge_layouts.values()))

    def graph(self) -> GraphViewModel:
        """Canvasへ渡す現在の表示用グラフを返す。"""
        return self._presenter.present(self.semantic_graph(), self.layout(), self._settings, self._reference_catalog)

    def node_view_model(self, node_id: str) -> GraphNodeViewModel:
        """指定ノードの現在のCanvas用表示モデルを返す。"""
        return next(node for node in self.graph().nodes if node.id == node_id)

    def edge_view_model(self, edge_id: str) -> GraphEdgeViewModel:
        """指定エッジの現在のCanvas用表示モデルを返す。"""
        return next(edge for edge in self.graph().edges if edge.id == edge_id)

    def child_combination(self, node_id: str) -> ChildCombination:
        """指定質問ノードの子の組合せ条件を返す。"""
        node = self._nodes[node_id]
        return node.child_combination if isinstance(node, QuestionNode) else ChildCombination.NONE

    def node_kind(self, node_id: str) -> NodeKind:
        """指定ノードの意味論的な種別を返す。"""
        return self._nodes[node_id].kind

    def reference_link(self, node_id: str) -> ReferenceLink | None:
        """指定文献ノードの参照先を返し、他種別ならNoneを返す。"""
        node = self._nodes[node_id]
        return node.reference_link if isinstance(node, ReferenceNode) else None

    def update_question_node(self, node_id: str, title: str, body: str, combination: ChildCombination) -> None:
        """質問ノードの意味論的な本文と組合せ条件を更新する。"""
        node = self._nodes[node_id]
        if isinstance(node, QuestionNode):
            self._nodes[node_id] = replace(node, title=title, body=body, child_combination=combination)

    def update_memo_node(self, node_id: str, title: str, body: str) -> None:
        """メモノードの意味論的な内容を更新する。"""
        node = self._nodes[node_id]
        if isinstance(node, MemoNode):
            self._nodes[node_id] = replace(node, title=title, body=body)

    def update_reference_node(self, node_id: str, reference_link: ReferenceLink | None, title: str = "", secondary_text: str | None = None) -> None:
        """文献ノードの参照先だけを更新する。表示文字列はカタログから導出する。"""
        node = self._nodes[node_id]
        if isinstance(node, ReferenceNode):
            self._nodes[node_id] = replace(node, reference_link=reference_link)

    def update_edge_type(self, edge_id: str, label: str, style_key: str = "") -> None:
        """エッジの意味論的な関係ラベルを更新する。"""
        self._edges[edge_id] = replace(self._edges[edge_id], label=label)

    def update_edge_label(self, edge_id: str, label: str) -> None:
        """互換操作としてエッジの関係ラベルだけを更新する。"""
        self.update_edge_type(edge_id, label)

    def rename_edge_labels(self, replacements: dict[str, tuple[str, str]]) -> None:
        """設定変更に伴い意味論的な関係ラベルを一括置換する。"""
        for edge_id, edge in tuple(self._edges.items()):
            if edge.label in replacements:
                self._edges[edge_id] = replace(edge, label=replacements[edge.label][0])

    def update_node_position(self, node_id: str, position_x: float, position_y: float) -> None:
        """ノード位置だけをレイアウトへ反映する。"""
        self._node_layouts[node_id] = replace(self._node_layouts[node_id], position_x=position_x, position_y=position_y)

    def update_edge_label_offset(self, edge_id: str, offset_x: float, offset_y: float) -> None:
        """エッジラベル位置だけをレイアウトへ反映する。"""
        self._edge_layouts[edge_id] = replace(self._edge_layouts[edge_id], label_offset_x=offset_x, label_offset_y=offset_y)

    def create_question_node_at(self, position_x: float, position_y: float) -> str:
        """指定点を中心として新しい質問ノードを作る。"""
        return self._add_node(self._factory.create_question(), position_x, position_y, *self._default_node_size(NodeKind.QUESTION))

    def create_memo_node_at(self, position_x: float, position_y: float) -> str:
        """指定点を中心として新しいメモノードを作る。"""
        return self._add_node(self._factory.create_memo(), position_x, position_y, *self._default_node_size(NodeKind.MEMO))

    def create_reference_node_at(self, position_x: float, position_y: float) -> str:
        """指定点を中心として未選択の文献ノードを作る。"""
        return self._add_node(self._factory.create_reference(), position_x, position_y, *self._default_node_size(NodeKind.REFERENCE))

    def create_node_connected_from(self, source_node_id: str, position_x: float, position_y: float, edge_label: str = "", edge_style_key: str = "") -> str | None:
        """背景ドロップ用に質問ノードと始点からのエッジをまとめて作る。"""
        node_id = self.create_question_node_at(position_x, position_y)
        if self.add_edge(source_node_id, node_id, edge_label, edge_style_key) is not None:
            return node_id
        self._remove_node_without_reconnection(node_id)
        return None

    def add_edge(self, source_node_id: str, target_node_id: str, label: str = "", style_key: str = "") -> str | None:
        """有向エッジを追加し、重複・自己接続・閉路を拒否する。"""
        if self._invalid_connection(source_node_id, target_node_id):
            return None
        edge = self._factory.create_edge(source_node_id, target_node_id, label)
        self._edges[edge.id] = edge
        self._edge_layouts[edge.id] = EdgeLayout(edge.id)
        return edge.id

    def reconnect_edge(self, edge_id: str, source_node_id: str, target_node_id: str) -> bool:
        """既存エッジの両端を更新し、閉路・重複を拒否する。"""
        edge = self._edges.get(edge_id)
        if edge is None or self._invalid_connection(source_node_id, target_node_id, edge_id):
            return False
        self._edges[edge_id] = replace(edge, source_node_id=source_node_id, target_node_id=target_node_id)
        return True

    def remove_edges(self, edge_ids: list[str]) -> int:
        """指定エッジを意味論とレイアウトから削除する。"""
        removed_count = 0
        for edge_id in edge_ids:
            if self._edges.pop(edge_id, None) is not None:
                self._edge_layouts.pop(edge_id, None)
                removed_count += 1
        return removed_count

    def remove_node(self, node_id: str, reconnections: tuple[EdgeConnection, ...] = ()) -> NodeRemovalResult:
        """ノードを削除し、許可済みの再接続だけを追加する。"""
        connected = [edge_id for edge_id, edge in self._edges.items() if node_id in (edge.source_node_id, edge.target_node_id)]
        self._remove_node_without_reconnection(node_id)
        created = sum(self.add_edge(item.source_node_id, item.target_node_id, item.label) is not None for item in reconnections)
        return NodeRemovalResult(len(connected), created)

    def insert_node_on_edge(self, edge_id: str, node_kind: NodeKind) -> str:
        """既存エッジを同じ関係ラベルの二本へ分割してノードを挿入する。"""
        edge = self._edges.pop(edge_id)
        edge_layout = self._edge_layouts.pop(edge_id)
        source_layout, target_layout = self._node_layouts[edge.source_node_id], self._node_layouts[edge.target_node_id]
        center_x = (source_layout.position_x + source_layout.width / 2 + target_layout.position_x + target_layout.width / 2) / 2
        center_y = (source_layout.position_y + source_layout.height / 2 + target_layout.position_y + target_layout.height / 2) / 2
        creators = {NodeKind.QUESTION: self._factory.create_question, NodeKind.MEMO: self._factory.create_memo, NodeKind.REFERENCE: self._factory.create_reference}
        node_id = self._add_node(creators[node_kind](), center_x, center_y, *self._default_node_size(node_kind))
        first = KnowledgeEdge(edge.id, edge.source_node_id, node_id, edge.label)
        second = self._factory.create_edge(node_id, edge.target_node_id, edge.label)
        self._edges[first.id], self._edges[second.id] = first, second
        self._edge_layouts[first.id] = edge_layout
        self._edge_layouts[second.id] = EdgeLayout(second.id, label_offset_y=-42.0 if edge.label else 0.0)
        return node_id

    def would_create_directed_cycle(self, source_node_id: str, target_node_id: str) -> bool:
        """この接続が有向閉路を作るか返す。"""
        return self._would_create_cycle(source_node_id, target_node_id)

    def _add_node(self, node: QuestionNode | MemoNode | ReferenceNode, center_x: float, center_y: float, width: float, height: float) -> str:
        """新ノードと対応する既定レイアウトを追加する。"""
        self._nodes[node.id] = node
        self._node_layouts[node.id] = NodeLayout(node.id, center_x - width / 2, center_y - height / 2, width, height)
        return node.id

    def _default_node_size(self, node_kind: NodeKind) -> tuple[float, float]:
        """ノード種別に対応する新規作成時の標準サイズを返す。"""
        return {
            NodeKind.QUESTION: (285.0, 105.0),
            NodeKind.MEMO: (270.0, 90.0),
            NodeKind.REFERENCE: (290.0, 100.0),
        }[node_kind]


    def _remove_node_without_reconnection(self, node_id: str) -> None:
        """ノードとその接続・レイアウトをまとめて取り除く。"""
        self._nodes.pop(node_id, None)
        self._node_layouts.pop(node_id, None)
        self.remove_edges([edge_id for edge_id, edge in self._edges.items() if node_id in (edge.source_node_id, edge.target_node_id)])

    def _invalid_connection(self, source_node_id: str, target_node_id: str, excluded_edge_id: str | None = None) -> bool:
        """接続先の存在、自己接続、重複、閉路をまとめて検査する。"""
        return (
            source_node_id not in self._nodes or target_node_id not in self._nodes or source_node_id == target_node_id
            or any(edge_id != excluded_edge_id and edge.source_node_id == source_node_id and edge.target_node_id == target_node_id for edge_id, edge in self._edges.items())
            or self._would_create_cycle(source_node_id, target_node_id, excluded_edge_id)
        )

    def _would_create_cycle(self, source_node_id: str, target_node_id: str, excluded_edge_id: str | None = None) -> bool:
        """targetからsourceへの既存経路を探索して閉路を判定する。"""
        pending, visited = [target_node_id], set()
        while pending:
            node_id = pending.pop()
            if node_id == source_node_id:
                return True
            if node_id not in visited:
                visited.add(node_id)
                pending.extend(edge.target_node_id for edge_id, edge in self._edges.items() if edge_id != excluded_edge_id and edge.source_node_id == node_id)
        return False
