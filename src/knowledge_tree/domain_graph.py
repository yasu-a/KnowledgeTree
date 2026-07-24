"""KnowledgeTreeプロジェクトの意味論的なグラフモデル。"""

from dataclasses import dataclass
from enum import StrEnum

from knowledge_tree.node_kind import NodeKind
from knowledge_tree.reference_catalog import ReferenceLink


class ChildCombination(StrEnum):
    """質問の子ノードを満たすための組合せ条件。"""

    NONE = ""
    ALL = "AND"
    ANY = "OR"


@dataclass(frozen=True)
class QuestionNode:
    """研究上の問いを表すノード。"""

    id: str
    title: str
    body: str
    child_combination: ChildCombination = ChildCombination.NONE

    @property
    def kind(self) -> NodeKind:
        """このノードの種別を返す。"""
        return NodeKind.QUESTION


@dataclass(frozen=True)
class MemoNode:
    """自由記述のメモを表すノード。"""

    id: str
    title: str
    body: str

    @property
    def kind(self) -> NodeKind:
        """このノードの種別を返す。"""
        return NodeKind.MEMO


@dataclass(frozen=True)
class ReferenceNode:
    """文献マスタのレコードを参照するノード。"""

    id: str
    reference_link: ReferenceLink | None = None

    @property
    def kind(self) -> NodeKind:
        """このノードの種別を返す。"""
        return NodeKind.REFERENCE


KnowledgeNode = QuestionNode | MemoNode | ReferenceNode


@dataclass(frozen=True)
class KnowledgeEdge:
    """プロジェクト上の有向な関係エッジ。"""

    id: str
    source_node_id: str
    target_node_id: str
    label: str


@dataclass(frozen=True)
class KnowledgeGraph:
    """意味論的なノードとエッジの集合。"""

    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]

    def node_by_id(self, node_id: str) -> KnowledgeNode:
        """IDに一致するノードを返し、なければKeyErrorを送出する。"""
        return next(node for node in self.nodes if node.id == node_id)

    def node_kind(self, node_id: str) -> NodeKind:
        """IDに一致するノードの種別を返す。"""
        return self.node_by_id(node_id).kind
