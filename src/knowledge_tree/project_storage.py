"""プロジェクトフォルダ単位でJSONと文献CSVを保存するストレージ層。"""

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from knowledge_tree.demo_data import build_demo_graph
from knowledge_tree.color_palette import ColorPalette, ColorToken
from knowledge_tree.global_settings import GlobalSettings
from knowledge_tree.project_settings import EdgeType, ProjectSettings
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel, GraphViewModel


@dataclass(frozen=True)
class ProjectSnapshot:
    """一つのプロジェクトフォルダから読み書きするグラフと設定の組。"""

    graph: GraphViewModel
    settings: ProjectSettings


class ProjectStorage:
    """userdata/projects配下のプロジェクト作成・読込・保存を担当する。"""

    def __init__(self, userdata_directory: Path) -> None:
        """userdataディレクトリと配下のprojectsディレクトリを設定する。"""
        self._userdata_directory = userdata_directory
        self._projects_directory = userdata_directory / "projects"

    def project_names(self) -> tuple[str, ...]:
        """有効なプロジェクトフォルダ名を昇順で返す。"""
        if not self._projects_directory.exists():
            return ()
        return tuple(sorted(path.name for path in self._projects_directory.iterdir() if path.is_dir()))

    def create_project(self, project_name: str) -> ProjectSnapshot:
        """デモグラフを初期データとして新規プロジェクトフォルダを作成する。"""
        project_directory = self._project_directory(project_name)
        if project_directory.exists():
            raise ValueError("同名のプロジェクトが既に存在します。")
        project_directory.mkdir(parents=True)
        snapshot = ProjectSnapshot(build_demo_graph(), ProjectSettings())
        self.save_project(project_name, snapshot)
        self._create_literature_master(project_directory)
        self.set_active_project(project_name)
        return snapshot

    def load_project(self, project_name: str) -> ProjectSnapshot:
        """指定プロジェクトの設定JSONとグラフJSONを読み込む。"""
        project_directory = self._project_directory(project_name)
        settings_data = self._read_json(project_directory / "project_settings.json")
        graph_data = self._read_json(project_directory / "graph.json")
        return ProjectSnapshot(self._graph_from_data(graph_data), self._settings_from_data(settings_data))

    def delete_project(self, project_name: str) -> None:
        """指定プロジェクトのフォルダを削除し、アクティブ状態も必要なら解除する。"""
        project_directory = self._project_directory(project_name)
        resolved_projects_directory = self._projects_directory.resolve()
        resolved_project_directory = project_directory.resolve()
        if resolved_project_directory.parent != resolved_projects_directory or not resolved_project_directory.is_dir():
            raise ValueError("削除対象のプロジェクトが見つかりません。")
        shutil.rmtree(resolved_project_directory)
        if self.active_project_name() == project_name:
            self._save_global_settings(GlobalSettings())

    def save_project(self, project_name: str, snapshot: ProjectSnapshot) -> None:
        """指定プロジェクトの設定JSONとグラフJSONを原子的に保存する。"""
        project_directory = self._project_directory(project_name)
        if not project_directory.is_dir():
            raise ValueError("保存対象のプロジェクトが見つかりません。")
        self._write_json(project_directory / "project_settings.json", self._settings_to_data(snapshot.settings))
        self._write_json(project_directory / "graph.json", self._graph_to_data(snapshot.graph))
        self._create_literature_master(project_directory)

    def active_project_name(self) -> str | None:
        """userdata直下の全体設定から、最後に開いたプロジェクト名を返す。"""
        path = self._userdata_directory / "global_settings.json"
        if not path.exists():
            return None
        return GlobalSettings(self._read_json(path).get("active_project")).active_project_name

    def set_active_project(self, project_name: str) -> None:
        """最後に開いたプロジェクト名をuserdata直下の全体設定へ保存する。"""
        self._save_global_settings(GlobalSettings(project_name))

    def _project_directory(self, project_name: str) -> Path:
        """安全性を確認したプロジェクトフォルダの絶対パスを返す。"""
        if not project_name or Path(project_name).name != project_name or any(character in project_name for character in '<>:"/\\|?*'):
            raise ValueError("プロジェクト名に使用できない文字が含まれています。")
        return self._projects_directory / project_name

    def _create_literature_master(self, project_directory: Path) -> None:
        """未作成の場合だけ、Excel互換CP932の文献マスタCSVヘッダを作成する。"""
        path = project_directory / "literature_master.csv"
        if path.exists():
            return
        with path.open("w", encoding="cp932", newline="") as file:
            csv.writer(file, lineterminator="\r\n").writerow(("id", "title", "authors", "year", "doi", "notes"))

    def _save_global_settings(self, settings: GlobalSettings) -> None:
        """アプリ全体の設定をuserdata直下のJSONへ保存する。"""
        self._userdata_directory.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self._userdata_directory / "global_settings.json",
            {"schema_version": 1, "active_project": settings.active_project_name},
        )

    def _read_json(self, path: Path) -> dict[str, object]:
        """UTF-8 JSONオブジェクトを読み込み、破損時はValueErrorに変換する。"""
        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"JSONを読み込めません: {path.name}") from error
        if not isinstance(data, dict):
            raise ValueError(f"JSONの形式が不正です: {path.name}")
        return data

    def _write_json(self, path: Path, data: dict[str, object]) -> None:
        """UTF-8 JSONを一時ファイル経由で原子的に保存する。"""
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            temporary_path = Path(file.name)
        temporary_path.replace(path)

    def _settings_to_data(self, settings: ProjectSettings) -> dict[str, object]:
        """エッジ種類設定をproject_settings.json用の辞書へ変換する。"""
        return {
            "schema_version": 2,
            "edge_types": [
                {"id": item.id, "label": item.label, "color_token": item.color_token.value}
                for item in settings.edge_types()
            ],
        }

    def _settings_from_data(self, data: dict[str, object]) -> ProjectSettings:
        """project_settings.jsonの辞書からエッジ種類設定を復元する。"""
        items = data.get("edge_types")
        if not isinstance(items, list):
            raise ValueError("project_settings.jsonのedge_typesが不正です。")
        edge_types = [self._edge_type_from_data(item) for item in items if isinstance(item, dict)]
        if not edge_types:
            raise ValueError("project_settings.jsonのedge_typesが不正です。")
        return ProjectSettings(edge_types)

    def _edge_type_from_data(self, data: dict[str, object]) -> EdgeType:
        """エッジ種類JSONを読み込み、旧式の16進数カラーも色トークンへ移行する。"""
        color_token_value = data.get("color_token")
        if isinstance(color_token_value, str):
            try:
                color_token = ColorToken(color_token_value)
            except ValueError as error:
                raise ValueError("project_settings.jsonのcolor_tokenが不正です。") from error
        else:
            old_color_hex = data.get("color_hex")
            color_token = ColorPalette.color_token_for_hex(old_color_hex) if isinstance(old_color_hex, str) else None
            if color_token is None:
                raise ValueError("project_settings.jsonのcolor_tokenが不正です。")
        return EdgeType(str(data["id"]), str(data["label"]), color_token)

    def _graph_to_data(self, graph: GraphViewModel) -> dict[str, object]:
        """Canvas用ViewModelをgraph.json用の辞書へ変換する。"""
        return {"schema_version": 1, "nodes": [node.__dict__ for node in graph.nodes], "edges": [edge.__dict__ for edge in graph.edges]}

    def _graph_from_data(self, data: dict[str, object]) -> GraphViewModel:
        """graph.jsonの辞書からCanvas用ViewModelを復元する。"""
        nodes_data, edges_data = data.get("nodes"), data.get("edges")
        if not isinstance(nodes_data, list) or not isinstance(edges_data, list):
            raise ValueError("graph.jsonのnodesまたはedgesが不正です。")
        nodes = tuple(GraphNodeViewModel(**item) for item in nodes_data if isinstance(item, dict))
        edges = tuple(GraphEdgeViewModel(**item) for item in edges_data if isinstance(item, dict))
        return GraphViewModel(nodes, edges)
