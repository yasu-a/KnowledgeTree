"""KnowledgeTreeアプリケーション自身のリリースバージョン。"""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class ApplicationVersion:
    """major/minorで管理するアプリケーションのリリースバージョン。"""

    major: int
    minor: int

    def __str__(self) -> str:
        """ユーザー表示・ログ向けのmajor.minor表記を返す。"""
        return f"{self.major}.{self.minor}"


APPLICATION_VERSION = ApplicationVersion(0, 1)
