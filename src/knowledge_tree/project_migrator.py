"""major更新時にプロジェクト保存形式を順番に変換するアプリケーションサービス。"""

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from knowledge_tree.project_format_version import ProjectFormatVersion


class ProjectMigration(Protocol):
    """一つの保存形式から次の保存形式へ変換する処理。"""

    @property
    def from_version(self) -> ProjectFormatVersion:
        """変換元のプロジェクト形式版を返す。"""
        ...

    @property
    def to_version(self) -> ProjectFormatVersion:
        """変換先のプロジェクト形式版を返す。"""
        ...

    def apply(self, project_directory: Path) -> None:
        """プロジェクトフォルダのJSON・CSVを新形式へ変換する。"""
        ...


class ProjectMigrator:
    """登録済みMigrationを接続し、現在の形式版まで順番に適用する。"""

    def __init__(self, migrations: Iterable[ProjectMigration] = ()) -> None:
        """利用可能なMigrationを変換元形式版ごとに登録する。"""
        self._migrations = {migration.from_version: migration for migration in migrations}

    def migrate(self, project_directory: Path, source: ProjectFormatVersion, target: ProjectFormatVersion) -> ProjectFormatVersion:
        """sourceからtargetまで必要なmajor Migrationを適用し、到達版を返す。"""
        version = source
        while version.major < target.major:
            migration = self._migrations.get(version)
            if migration is None:
                raise ValueError(f"プロジェクト形式 {version} から {target} への変換処理がありません。")
            migration.apply(project_directory)
            version = migration.to_version
        return target if version.major == target.major else version
