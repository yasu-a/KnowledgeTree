"""プロジェクト保存形式版とMigrationのドメインルールを検証する。"""

from pathlib import Path

import pytest

from knowledge_tree.project_format_version import ProjectCompatibility, ProjectFormatVersion
from knowledge_tree.project_migrator import ProjectMigrator


def test_minor_difference_is_directly_readable_and_major_difference_requires_migration() -> None:
    """同一majorのminor差は直接読め、古いmajorだけMigration対象になる。"""
    assert ProjectFormatVersion(0, 0).compatibility_with(ProjectFormatVersion(0, 1)) == ProjectCompatibility.DIRECTLY_READABLE
    assert ProjectFormatVersion(0, 1).compatibility_with(ProjectFormatVersion(1, 0)) == ProjectCompatibility.MIGRATION_REQUIRED
    assert ProjectFormatVersion(2, 0).compatibility_with(ProjectFormatVersion(1, 0)) == ProjectCompatibility.UNSUPPORTED_FUTURE_VERSION


def test_project_migrator_applies_registered_major_migration(tmp_path: Path) -> None:
    """Migrationは旧モデルを介さず、プロジェクトフォルダを次のmajor形式へ変換する。"""
    class MigrationFromZeroToOne:
        """テスト用に0.1から1.0へ変換するMigration。"""

        @property
        def from_version(self) -> ProjectFormatVersion:
            """変換元版を返す。"""
            return ProjectFormatVersion(0, 1)

        @property
        def to_version(self) -> ProjectFormatVersion:
            """変換先版を返す。"""
            return ProjectFormatVersion(1, 0)

        def apply(self, project_directory: Path) -> None:
            """変換が行われたことを示すマーカーを作る。"""
            (project_directory / "migrated.txt").write_text("done", encoding="utf-8")

    migrator = ProjectMigrator((MigrationFromZeroToOne(),))

    assert migrator.migrate(tmp_path, ProjectFormatVersion(0, 1), ProjectFormatVersion(1, 0)) == ProjectFormatVersion(1, 0)
    assert (tmp_path / "migrated.txt").read_text(encoding="utf-8") == "done"


def test_project_migrator_rejects_missing_major_migration(tmp_path: Path) -> None:
    """必要なmajor Migrationが未登録なら、データを推測変換せず失敗する。"""
    with pytest.raises(ValueError):
        ProjectMigrator().migrate(tmp_path, ProjectFormatVersion(0, 1), ProjectFormatVersion(1, 0))
