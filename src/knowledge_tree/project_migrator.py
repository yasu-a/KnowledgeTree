"""major更新時にプロジェクト保存形式を順番に変換するアプリケーションサービス。"""

from collections.abc import Iterable
from abc import ABC, abstractmethod
from pathlib import Path

from knowledge_tree.application_version import ApplicationVersion


class ProjectMigration(ABC):
    """一つの保存形式から次の保存形式へ変換する処理。"""

    @property
    @abstractmethod
    def from_version(self) -> ApplicationVersion:
        """変換元のプロジェクト形式版を返す。"""
        ...

    @property
    @abstractmethod
    def to_version(self) -> ApplicationVersion:
        """変換先のプロジェクト形式版を返す。"""
        ...

    @abstractmethod
    def apply(self, project_directory: Path) -> None:
        """プロジェクトフォルダのJSON・CSVを新形式へ変換する。"""
        ...


class ProjectMigrator:
    """登録済みMigrationを接続し、現在の形式版まで順番に適用する。"""

    def __init__(self, migrations: Iterable[ProjectMigration] = ()) -> None:
        """利用可能なMigrationを変換元形式版ごとに登録する。"""
        self._migrations = {migration.from_version: migration for migration in migrations}

    def migrate(self, project_directory: Path, source: ApplicationVersion, target: ApplicationVersion) -> ApplicationVersion:
        """sourceからtargetまで必要なmajor Migrationを適用し、到達版を返す。"""
        version = source
        while version.major < target.major:
            migration = self._migrations.get(version)
            if migration is None:
                raise ValueError(f"プロジェクト形式 {version} から {target} への変換処理がありません。")
            migration.apply(project_directory)
            version = migration.to_version
        return target if version.major == target.major else version
