"""開いている一つのプロジェクトの実行時編集状態。"""

from knowledge_tree.demo_data import build_demo_project
from knowledge_tree.project_content import ProjectContent
from knowledge_tree.project_graph_editor import ProjectGraphEditor
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.project_storage import ProjectSnapshot, ProjectStorage
from knowledge_tree.reference_catalog import ReferenceCatalog


class ProjectSession:
    """一つのプロジェクトの編集状態と保存を担当する。"""

    def __init__(self, project_name: str, project_storage: ProjectStorage | None, snapshot: ProjectSnapshot) -> None:
        """読込済みの意味論・レイアウトを編集可能な状態へ展開する。"""
        self._project_name = project_name
        self._project_storage = project_storage
        self._project_settings = snapshot.settings
        self._graph_editor = ProjectGraphEditor(snapshot.content, self.reference_catalog)

    @classmethod
    def open(cls, project_storage: ProjectStorage, project_name: str) -> "ProjectSession":
        """保存済みプロジェクトを読み込み、新しい編集セッションを作る。"""
        return cls(project_name, project_storage, project_storage.load_project(project_name))

    @classmethod
    def demo(cls) -> "ProjectSession":
        """保存先を持たないCanvasテスト用のデモセッションを作る。"""
        return cls("__demo__", None, ProjectSnapshot(build_demo_project()))

    @property
    def project_name(self) -> str:
        """開いているプロジェクト名を返す。"""
        return self._project_name

    @property
    def can_save(self) -> bool:
        """このセッションがプロジェクトファイルへ保存可能かを返す。"""
        return self._project_storage is not None

    @property
    def project_settings(self) -> ProjectSettings:
        """このプロジェクトの設定を返す。"""
        return self._project_settings

    @property
    def graph_editor(self) -> ProjectGraphEditor:
        """このプロジェクトの意味論的グラフ編集サービスを返す。"""
        return self._graph_editor

    @property
    def reference_catalog(self) -> ReferenceCatalog | None:
        """保存先を持つ場合に文献カタログを返す。"""
        if self._project_storage is None:
            return None
        return self._project_storage.reference_catalog(self._project_name)

    def save(self) -> None:
        """保存先を持つ場合だけ現在状態を新世代として保存する。"""
        if self._project_storage is not None:
            self._project_storage.save_project(self._project_name, ProjectSnapshot(self._graph_editor.content()))
