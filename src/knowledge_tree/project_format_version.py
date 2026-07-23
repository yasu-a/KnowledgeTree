"""プロジェクト保存形式のバージョンと互換性ルール。"""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, order=True)
class ProjectFormatVersion:
    """major/minorで管理するプロジェクト保存形式のバージョン。"""

    major: int
    minor: int

    def __str__(self) -> str:
        """project.json向けのmajor.minor表記を返す。"""
        return f"{self.major}.{self.minor}"

    def compatibility_with(self, supported_version: "ProjectFormatVersion") -> "ProjectCompatibility":
        """対応アプリの保存形式版に対する読込方法を返す。"""
        if self.major > supported_version.major:
            return ProjectCompatibility.UNSUPPORTED_FUTURE_VERSION
        if self.major < supported_version.major:
            return ProjectCompatibility.MIGRATION_REQUIRED
        return ProjectCompatibility.DIRECTLY_READABLE


class ProjectCompatibility(StrEnum):
    """プロジェクト保存形式を読み込む際の互換性判定。"""

    DIRECTLY_READABLE = "directly_readable"
    MIGRATION_REQUIRED = "migration_required"
    UNSUPPORTED_FUTURE_VERSION = "unsupported_future_version"


CURRENT_PROJECT_FORMAT_VERSION = ProjectFormatVersion(0, 1)
