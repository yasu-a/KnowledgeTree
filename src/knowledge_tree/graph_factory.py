"""新規グラフ要素をUUIDで生成するドメインファクトリ。"""

from typing import Protocol
from uuid import uuid4

from knowledge_tree.domain_graph import ChildCombination, KnowledgeEdge, MemoNode, QuestionNode, ReferenceNode
from knowledge_tree.reference_catalog import ReferenceLink


class GraphIdGenerator(Protocol):
    """グラフ要素用の一意IDを発行する抽象。"""

    def new_id(self) -> str:
        """新しい一意IDを返す。"""
        ...


class UuidGraphIdGenerator:
    """UUID4を利用する通常実行用のID発行器。"""

    def new_id(self) -> str:
        """ランダムなUUID4文字列を返す。"""
        return uuid4().hex


class GraphFactory:
    """新規ノード・エッジの意味論的な初期値を一箇所に集約する。"""

    def __init__(self, id_generator: GraphIdGenerator | None = None) -> None:
        """利用するID発行器を設定する。"""
        self._id_generator = id_generator or UuidGraphIdGenerator()

    def create_question(
        self,
        title: str = "新しい問い",
        body: str = "",
        child_combination: ChildCombination = ChildCombination.NONE,
    ) -> QuestionNode:
        """既定内容の質問ノードを生成する。"""
        return QuestionNode(self._id_generator.new_id(), title, body, child_combination)

    def create_memo(self, title: str = "新しいメモ", body: str = "") -> MemoNode:
        """既定内容のメモノードを生成する。"""
        return MemoNode(self._id_generator.new_id(), title, body)

    def create_reference(self, reference_link: ReferenceLink | None = None) -> ReferenceNode:
        """文献未選択でも作成できる文献ノードを生成する。"""
        return ReferenceNode(self._id_generator.new_id(), reference_link)

    def create_edge(self, source_node_id: str, target_node_id: str, label: str) -> KnowledgeEdge:
        """指定両端と関係ラベルを持つ有向エッジを生成する。"""
        return KnowledgeEdge(self._id_generator.new_id(), source_node_id, target_node_id, label)
