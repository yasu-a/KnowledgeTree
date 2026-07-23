"""プロジェクトフォルダ単位でJSONと文献CSVを保存するストレージ層。"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from knowledge_tree.demo_data import build_demo_graph
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.reference_catalog import ReferenceCatalog, ReferenceKind, ReferenceLink
from knowledge_tree.color_palette import ColorToken
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
        catalog = ReferenceCatalog(project_directory)
        catalog.ensure_files()
        catalog.create_paper("既存の専用診断を比較する")
        return snapshot

    def load_project(self, project_name: str) -> ProjectSnapshot:
        """指定プロジェクトの設定JSONとグラフJSONを読み込む。"""
        project_directory = self._project_directory(project_name)
        settings_data = self._read_json(project_directory / "project_settings.json")
        graph_data = self._read_json(project_directory / "graph.json")
        return ProjectSnapshot(self._graph_from_data(graph_data), self._settings_from_data(settings_data))

    def reference_catalog(self, project_name: str) -> ReferenceCatalog:
        """指定プロジェクトの種類別文献マスタを操作するカタログを返す。"""
        project_directory = self._project_directory(project_name)
        if not project_directory.is_dir():
            raise ValueError("参照対象のプロジェクトが見つかりません。")
        return ReferenceCatalog(project_directory)

    def delete_project(self, project_name: str) -> None:
        """指定プロジェクトのフォルダを安全性を確認して削除する。"""
        project_directory = self._project_directory(project_name)
        resolved_projects_directory = self._projects_directory.resolve()
        resolved_project_directory = project_directory.resolve()
        if resolved_project_directory.parent != resolved_projects_directory or not resolved_project_directory.is_dir():
            raise ValueError("削除対象のプロジェクトが見つかりません。")
        shutil.rmtree(resolved_project_directory)

    def save_project(self, project_name: str, snapshot: ProjectSnapshot) -> None:
        """指定プロジェクトの設定JSONとグラフJSONを原子的に保存する。"""
        project_directory = self._project_directory(project_name)
        if not project_directory.is_dir():
            raise ValueError("保存対象のプロジェクトが見つかりません。")
        self._write_json(project_directory / "project_settings.json", self._settings_to_data(snapshot.settings))
        self._write_json(project_directory / "graph.json", self._graph_to_data(snapshot.graph))
        ReferenceCatalog(project_directory).ensure_files()

    def _project_directory(self, project_name: str) -> Path:
        """安全性を確認したプロジェクトフォルダの絶対パスを返す。"""
        if not project_name or Path(project_name).name != project_name or any(character in project_name for character in '<>:"/\\|?*'):
            raise ValueError("プロジェクト名に使用できない文字が含まれています。")
        return self._projects_directory / project_name

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
            "schema_version": 3,
            "edge_types": [
                {
                    "id": item.id,
                    "label": item.label,
                    "color_token": item.color_token.value,
                    "allowed_endpoints": [[source_kind.value, target_kind.value] for source_kind, target_kind in item.allowed_endpoints],
                }
                for item in settings.edge_types()
            ],
            "node_colors": {node_kind.value: settings.node_color(node_kind).value for node_kind in NodeKind},
        }

    def _settings_from_data(self, data: dict[str, object]) -> ProjectSettings:
        """project_settings.jsonの辞書からエッジ種類設定を復元する。"""
        items = data.get("edge_types")
        if not isinstance(items, list):
            raise ValueError("project_settings.jsonのedge_typesが不正です。")
        edge_types = [self._edge_type_from_data(item) for item in items if isinstance(item, dict)]
        if not edge_types:
            raise ValueError("project_settings.jsonのedge_typesが不正です。")
        colors_data = data.get("node_colors")
        if not isinstance(colors_data, dict):
            raise ValueError("project_settings.jsonのnode_colorsが不正です。")
        node_colors = {node_kind: ColorToken(str(colors_data[node_kind.value])) for node_kind in NodeKind}
        return ProjectSettings(edge_types, node_colors)

    def _edge_type_from_data(self, data: dict[str, object]) -> EdgeType:
        """エッジ種類JSONを読み込み、接続可能なノード種別も復元する。"""
        color_token = ColorToken(str(data["color_token"]))
        endpoint_data = data.get("allowed_endpoints")
        if not isinstance(endpoint_data, list):
            defaults = {item.id: item.allowed_endpoints for item in ProjectSettings.default_edge_types()}
            endpoint_rules = defaults.get(str(data["id"]), ())
        else:
            endpoint_rules = tuple(self._endpoint_pair_from_data(item) for item in endpoint_data)
        return EdgeType(str(data["id"]), str(data["label"]), color_token, endpoint_rules)

    def _endpoint_pair_from_data(self, data: object) -> tuple[NodeKind, NodeKind]:
        """JSONの始点・終点種別の組をNodeKindの組へ変換する。"""
        if not isinstance(data, list) or len(data) != 2 or not all(isinstance(item, str) for item in data):
            raise ValueError("project_settings.jsonのallowed_endpointsが不正です。")
        return NodeKind(data[0]), NodeKind(data[1])

    def _graph_to_data(self, graph: GraphViewModel) -> dict[str, object]:
        """Canvas用ViewModelをgraph.json用の辞書へ変換する。"""
        nodes = [
            {
                **node.__dict__,
                "node_kind": node.node_kind.value,
                "reference_link": None if node.reference_link is None else {"kind": node.reference_link.kind.value, "id": node.reference_link.id},
            }
            for node in graph.nodes
        ]
        return {"schema_version": 2, "nodes": nodes, "edges": [edge.__dict__ for edge in graph.edges]}

    def _graph_from_data(self, data: dict[str, object]) -> GraphViewModel:
        """graph.jsonの辞書からCanvas用ViewModelを復元する。"""
        nodes_data, edges_data = data.get("nodes"), data.get("edges")
        if not isinstance(nodes_data, list) or not isinstance(edges_data, list):
            raise ValueError("graph.jsonのnodesまたはedgesが不正です。")
        nodes = tuple(self._node_from_data(item) for item in nodes_data if isinstance(item, dict) and isinstance(item.get("node_kind"), str))
        edges = tuple(GraphEdgeViewModel(**item) for item in edges_data if isinstance(item, dict))
        return GraphViewModel(nodes, edges)

    def _reference_link_from_data(self, data: object) -> ReferenceLink | None:
        """graph.jsonの文献参照をReferenceLinkへ変換する。"""
        if data is None:
            return None
        if not isinstance(data, dict) or not isinstance(data.get("kind"), str) or not isinstance(data.get("id"), str):
            raise ValueError("graph.jsonのreference_linkが不正です。")
        return ReferenceLink(ReferenceKind(data["kind"]), data["id"])

    def _node_from_data(self, data: dict[str, object]) -> GraphNodeViewModel:
        """新旧のgraph.jsonノードを、現在のGraphNodeViewModelへ変換する。"""
        node_data = dict(data)
        legacy_reference_id = node_data.pop("reference_id", None)
        reference_link_data = node_data.pop("reference_link", None)
        reference_link = self._reference_link_from_data(reference_link_data)
        if reference_link is None and isinstance(legacy_reference_id, str):
            reference_link = self._legacy_reference_link(legacy_reference_id)
        return GraphNodeViewModel(
            **{
                **node_data,
                "node_kind": NodeKind(str(node_data["node_kind"])),
                "reference_link": reference_link,
            }
        )

    def _legacy_reference_link(self, reference_id: str) -> ReferenceLink | None:
        """旧reference_idの接頭辞から、移行時だけ文献リンクを復元する。"""
        for kind in ReferenceKind:
            if reference_id.startswith(f"{kind.value}-"):
                return ReferenceLink(kind, reference_id)
        return None
