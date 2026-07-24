"""プロジェクトを構成する意味論・レイアウト・設定の組。"""

from dataclasses import dataclass

from knowledge_tree.domain_graph import KnowledgeGraph
from knowledge_tree.graph_layout import GraphLayout
from knowledge_tree.project_settings import ProjectSettings


@dataclass(frozen=True)
class ProjectContent:
    """同一保存世代で必ず揃えるプロジェクトの本体データ。"""

    graph: KnowledgeGraph
    layout: GraphLayout
    settings: ProjectSettings
