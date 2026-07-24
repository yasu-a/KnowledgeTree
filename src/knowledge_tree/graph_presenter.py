"""ドメイングラフをCanvas専用ViewModelへ変換するプレゼンター。"""

from knowledge_tree.domain_graph import KnowledgeEdge, KnowledgeGraph, MemoNode, QuestionNode, ReferenceNode
from knowledge_tree.graph_layout import GraphLayout
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.reference_catalog import ReferenceCatalog
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel, GraphViewModel


class GraphPresenter:
    """意味論・レイアウト・設定をCanvas表示モデルへ統合する。"""

    def present(
        self,
        graph: KnowledgeGraph,
        layout: GraphLayout,
        settings: ProjectSettings,
        reference_catalog: ReferenceCatalog | None = None,
    ) -> GraphViewModel:
        """現在のドメイン状態に対応するCanvas用グラフを返す。"""
        return GraphViewModel(
            tuple(self._present_node(node, layout, settings, reference_catalog) for node in graph.nodes),
            tuple(self._present_edge(edge, layout, settings) for edge in graph.edges),
        )

    def _present_node(
        self,
        node: QuestionNode | MemoNode | ReferenceNode,
        layout: GraphLayout,
        settings: ProjectSettings,
        reference_catalog: ReferenceCatalog | None,
    ) -> GraphNodeViewModel:
        """一つの意味論的ノードをCanvas用ノードへ変換する。"""
        node_layout = layout.node_layout(node.id)
        if isinstance(node, QuestionNode):
            text, secondary_text, badge = node.title, node.body, node.child_combination.value or None
        elif isinstance(node, MemoNode):
            text, secondary_text, badge = node.title, node.body, None
        else:
            text, secondary_text, badge = self._reference_text(node, reference_catalog)
        return GraphNodeViewModel(
            node.id, text, secondary_text, node_layout.position_x, node_layout.position_y,
            node_layout.width, node_layout.height, f"project-node:{node.kind.value}", badge,
        )

    def _reference_text(self, node: ReferenceNode, reference_catalog: ReferenceCatalog | None) -> tuple[str, str | None, str | None]:
        """文献マスタから文献ノードの表示テキストを解決する。"""
        if node.reference_link is None:
            return "文献を選択してください", None, None
        record = reference_catalog.find(node.reference_link) if reference_catalog is not None else None
        if record is None:
            return "削除された文献", None, node.reference_link.kind.value.title()
        secondary = " / ".join(value for value in (getattr(record, "authors", ""), getattr(record, "year", "")) if value)
        return record.title, secondary or None, node.reference_link.kind.value.title()

    def _present_edge(self, edge: KnowledgeEdge, layout: GraphLayout, settings: ProjectSettings) -> GraphEdgeViewModel:
        """一つの意味論的エッジをCanvas用エッジへ変換する。"""
        edge_layout = layout.edge_layout(edge.id)
        edge_type = settings.edge_type_by_label(edge.label)
        style_key = f"global-edge-type:{edge_type.id}" if edge_type is not None else "default"
        return GraphEdgeViewModel(
            edge.id, edge.source_node_id, edge.target_node_id, edge.label, True, style_key,
            edge_layout.label_anchor, edge_layout.label_offset_x, edge_layout.label_offset_y,
        )
