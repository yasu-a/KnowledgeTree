"""KnowledgeTree本体とプロジェクト保存で共通に使うバージョン定義。"""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, order=True)
class ApplicationVersion:
    """major/minorで管理するKnowledgeTreeの唯一のバージョン。"""

    major: int
    minor: int

    def __str__(self) -> str:
        """ユーザー表示と保存形式に使うmajor.minor表記を返す。"""
        return f"{self.major}.{self.minor}"

    def compatibility_with(self, supported_version: "ApplicationVersion") -> "ProjectCompatibility":
        """対応版に対するプロジェクトの読込方法を返す。"""
        if self.major > supported_version.major:
            return ProjectCompatibility.UNSUPPORTED_FUTURE_VERSION
        if self.major < supported_version.major:
            return ProjectCompatibility.MIGRATION_REQUIRED
        return ProjectCompatibility.DIRECTLY_READABLE


class ProjectCompatibility(StrEnum):
    """プロジェクトを開くときの形式互換性。"""

    DIRECTLY_READABLE = "directly_readable"
    MIGRATION_REQUIRED = "migration_required"
    UNSUPPORTED_FUTURE_VERSION = "unsupported_future_version"


APPLICATION_VERSION = ApplicationVersion(1, 0)
