"""開いている一つのプロジェクトの実行時編集状態。"""

from knowledge_tree.demo_data import build_demo_graph
from knowledge_tree.demo_graph_editor import DemoGraphEditor
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.project_storage import ProjectSnapshot, ProjectStorage


class ProjectSession:
    """一つのプロジェクトの編集状態と保存を担当する。"""

    def __init__(
        self,
        project_name: str,
        project_storage: ProjectStorage | None,
        snapshot: ProjectSnapshot,
    ) -> None:
        """読込済みスナップショットを編集可能なプロジェクト状態へ展開する。"""
        self._project_name = project_name
        self._project_storage = project_storage
        self._project_settings = snapshot.settings
        self._graph_editor = DemoGraphEditor(snapshot.graph)

    @classmethod
    def open(cls, project_storage: ProjectStorage, project_name: str) -> "ProjectSession":
        """保存済みプロジェクトを読み込み、新しい編集セッションを作成する。"""
        return cls(project_name, project_storage, project_storage.load_project(project_name))

    @classmethod
    def demo(cls) -> "ProjectSession":
        """保存先を持たないCanvasテスト用のデモセッションを作成する。"""
        return cls("__demo__", None, ProjectSnapshot(build_demo_graph(), ProjectSettings()))

    @property
    def project_name(self) -> str:
        """このセッションが開いているプロジェクト名を返す。"""
        return self._project_name

    @property
    def project_settings(self) -> ProjectSettings:
        """このプロジェクトに属する設定を返す。"""
        return self._project_settings

    @property
    def graph_editor(self) -> DemoGraphEditor:
        """このプロジェクトのグラフ編集状態を返す。"""
        return self._graph_editor

    def save(self) -> None:
        """保存先を持つ場合だけ、現在のグラフと設定をプロジェクトへ保存する。"""
        if self._project_storage is not None:
            self._project_storage.save_project(
                self._project_name,
                ProjectSnapshot(self._graph_editor.graph(), self._project_settings),
            )
