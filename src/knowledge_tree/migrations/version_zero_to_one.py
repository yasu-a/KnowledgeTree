"""0.1形式のプロジェクトを1.0形式へ変換するmigration。"""

from pathlib import Path

from knowledge_tree.application_version import ApplicationVersion
from knowledge_tree.domain_graph import ChildCombination, KnowledgeEdge, KnowledgeGraph, MemoNode, QuestionNode, ReferenceNode
from knowledge_tree.graph_layout import EdgeLayout, GraphLayout, NodeLayout
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.project_content import ProjectContent
from knowledge_tree.project_migrator import ProjectMigration, ProjectMigrator


class VersionZeroToOneMigration(ProjectMigration):
    """旧0.1のViewModel混在形式を1.0の世代スナップショットへ変換する。"""

    @property
    def from_version(self) -> ApplicationVersion:
        """変換元版を返す。"""
        return ApplicationVersion(0, 1)

    @property
    def to_version(self) -> ApplicationVersion:
        """このmigrationが導入した1.0形式を明示して返す。"""
        return ApplicationVersion(1, 0)

    def apply(self, project_directory: Path) -> None:
        """旧root直下ファイルを読み、意味論とレイアウトへ分離して保存する。"""
        # 循環importを避け、実際のJSON入出力は既存ストレージへ委譲する。
        from knowledge_tree.project_storage import ProjectSnapshot, ProjectStorage

        storage = ProjectStorage(project_directory.parent.parent, ProjectMigrator())
        graph_data = storage._read_json(project_directory / "graph.json")
        settings_data = storage._read_json(project_directory / "project_settings.json")
        nodes: list[QuestionNode | MemoNode | ReferenceNode] = []
        layouts: list[NodeLayout] = []
        for item in graph_data.get("nodes", []):
            if not isinstance(item, dict):
                continue
            node_id = str(item["id"])
            kind = NodeKind(str(item.get("node_kind", NodeKind.QUESTION.value)))
            if kind == NodeKind.QUESTION:
                nodes.append(QuestionNode(node_id, str(item.get("text", "")), str(item.get("secondary_text") or ""), ChildCombination(str(item.get("badge_text") or ""))))
            elif kind == NodeKind.MEMO:
                nodes.append(MemoNode(node_id, str(item.get("text", "")), str(item.get("secondary_text") or "")))
            else:
                nodes.append(ReferenceNode(node_id, storage._reference_link_from_data(item.get("reference_link"))))
            layouts.append(NodeLayout(node_id, float(item["position_x"]), float(item["position_y"]), float(item["width"]), float(item["height"])))
        edges: list[KnowledgeEdge] = []
        edge_layouts: list[EdgeLayout] = []
        for item in graph_data.get("edges", []):
            if not isinstance(item, dict):
                continue
            edge_id = str(item["id"])
            edges.append(KnowledgeEdge(edge_id, str(item["source_node_id"]), str(item["target_node_id"]), str(item.get("label", ""))))
            edge_layouts.append(EdgeLayout(edge_id, float(item.get("label_anchor", 0.5)), float(item.get("label_offset_x", 0.0)), float(item.get("label_offset_y", 0.0))))
        content = ProjectContent(KnowledgeGraph(tuple(nodes), tuple(edges)), GraphLayout(tuple(layouts), tuple(edge_layouts)), storage._settings_from_data(settings_data))
        storage.save_project(project_directory.name, ProjectSnapshot(content))
