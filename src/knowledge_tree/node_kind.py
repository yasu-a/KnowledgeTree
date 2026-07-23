"""KnowledgeTreeプロジェクトで扱う意味的なノード種類。"""

from enum import StrEnum


class NodeKind(StrEnum):
    """問い、メモ、外部参照を区別する安定したノード種別。"""

    QUESTION = "question"
    MEMO = "memo"
    REFERENCE = "reference"

    @property
    def display_name(self) -> str:
        """UI向けの英語表示名を返す。"""
        return self.value.title()
