"""プロジェクト内容を世代単位のJSONスナップショットとして保存する。"""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from knowledge_tree.demo_data import build_demo_project
from knowledge_tree.domain_graph import ChildCombination, KnowledgeEdge, KnowledgeGraph, MemoNode, QuestionNode, ReferenceNode
from knowledge_tree.graph_layout import EdgeLayout, GraphLayout, NodeLayout
from knowledge_tree.application_version import APPLICATION_VERSION, ApplicationVersion, ProjectCompatibility
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.project_content import ProjectContent
from knowledge_tree.project_migrator import ProjectMigrator
from knowledge_tree.migrations.version_zero_to_one import VersionZeroToOneMigration
from knowledge_tree.project_settings import EdgeType, ProjectSettings
from knowledge_tree.reference_catalog import ReferenceCatalog, ReferenceKind, ReferenceLink
from knowledge_tree.color_palette import ColorToken


@dataclass(frozen=True)
class ProjectSnapshot:
    """同一保存世代から読み書きするプロジェクト本体。"""

    content: ProjectContent

    @property
    def graph(self) -> KnowledgeGraph:
        """プロジェクトの意味論的グラフを返す。"""
        return self.content.graph

    @property
    def layout(self) -> GraphLayout:
        """プロジェクトのCanvasレイアウトを返す。"""
        return self.content.layout

    @property
    def settings(self) -> ProjectSettings:
        """プロジェクト設定を返す。"""
        return self.content.settings


class ProjectStorage:
    """userdata/projects配下のプロジェクト作成・読込・世代保存を担当する。"""

    def __init__(self, userdata_directory: Path, project_migrator: ProjectMigrator | None = None) -> None:
        """userdataと配下のprojectsディレクトリを設定する。"""
        self._userdata_directory = userdata_directory
        self._projects_directory = userdata_directory / "projects"
        self._project_migrator = project_migrator or ProjectMigrator((VersionZeroToOneMigration(),))

    def project_names(self) -> tuple[str, ...]:
        """有効なプロジェクトフォルダ名を昇順で返す。"""
        if not self._projects_directory.exists():
            return ()
        return tuple(sorted(path.name for path in self._projects_directory.iterdir() if path.is_dir()))

    def create_project(self, project_name: str) -> ProjectSnapshot:
        """デモプロジェクトを初期内容として新規フォルダを作成する。"""
        project_directory = self._project_directory(project_name)
        if project_directory.exists():
            raise ValueError("同名のプロジェクトが既に存在します。")
        project_directory.mkdir(parents=True)
        snapshot = ProjectSnapshot(build_demo_project())
        self.save_project(project_name, snapshot)
        catalog = ReferenceCatalog(project_directory)
        catalog.ensure_files()
        catalog.create_paper("既存の専用診断を比較する")
        return snapshot

    def load_project(self, project_name: str) -> ProjectSnapshot:
        """アクティブな保存世代から意味論・レイアウト・設定を読み込む。"""
        project_directory = self._project_directory(project_name)
        self._migrate_project_if_needed(project_directory)
        snapshot_directory = self._active_snapshot_directory(project_directory)
        graph = self._graph_from_data(self._read_json(snapshot_directory / "graph.json"))
        layout = self._layout_from_data(self._read_json(snapshot_directory / "layout.json"), graph)
        settings = self._settings_from_data(self._read_json(snapshot_directory / "project_settings.json"))
        self._validate_correspondence(graph, layout)
        return ProjectSnapshot(ProjectContent(graph, layout, settings))

    def reference_catalog(self, project_name: str) -> ReferenceCatalog:
        """指定プロジェクトの種類別文献マスタを操作するカタログを返す。"""
        project_directory = self._project_directory(project_name)
        if not project_directory.is_dir():
            raise ValueError("参照対象のプロジェクトが見つかりません。")
        return ReferenceCatalog(project_directory)

    def delete_project(self, project_name: str) -> None:
        """指定プロジェクトのフォルダだけを安全性確認後に削除する。"""
        project_directory = self._project_directory(project_name)
        resolved_projects_directory = self._projects_directory.resolve()
        resolved_project_directory = project_directory.resolve()
        if resolved_project_directory.parent != resolved_projects_directory or not resolved_project_directory.is_dir():
            raise ValueError("削除対象のプロジェクトが見つかりません。")
        shutil.rmtree(resolved_project_directory)

    def save_project(self, project_name: str, snapshot: ProjectSnapshot) -> None:
        """新しい世代へ全JSONを保存後、manifestを原子的に切り替える。"""
        project_directory = self._project_directory(project_name)
        if not project_directory.is_dir():
            raise ValueError("保存対象のプロジェクトが見つかりません。")
        self._validate_correspondence(snapshot.graph, snapshot.layout)
        previous_generation_id = self._active_snapshot_id_or_none(project_directory)
        generation_id = uuid4().hex
        snapshot_directory = project_directory / "snapshots" / generation_id
        snapshot_directory.mkdir(parents=True, exist_ok=False)
        # 同一世代に意味論、レイアウト、設定を全て書き出す。
        self._write_json(snapshot_directory / "graph.json", self._graph_to_data(snapshot.graph))
        self._write_json(snapshot_directory / "layout.json", self._layout_to_data(snapshot.layout))
        self._write_json(snapshot_directory / "project_settings.json", self._settings_to_data(snapshot.settings))
        self._fsync_directory(snapshot_directory)
        # 最後にmanifestだけを交換し、読込対象の世代を一度に切り替える。
        self._write_json(project_directory / "project.json", {
            "version": {"major": APPLICATION_VERSION.major, "minor": APPLICATION_VERSION.minor},
            "active_snapshot": generation_id,
        })
        ReferenceCatalog(project_directory).ensure_files()
        self._prune_snapshots(project_directory, generation_id, previous_generation_id)

    def _project_directory(self, project_name: str) -> Path:
        """安全性を確認済みのプロジェクトフォルダパスを返す。"""
        if not project_name or Path(project_name).name != project_name or any(character in project_name for character in '<>:"/\\|?*'):
            raise ValueError("プロジェクト名に使用できない文字が含まれています。")
        return self._projects_directory / project_name

    def _migrate_project_if_needed(self, project_directory: Path) -> None:
        """保存形式版を確認し、必要なmajor migrationを適用する。"""
        source_version = self._read_project_version(project_directory)
        compatibility = source_version.compatibility_with(APPLICATION_VERSION)
        if compatibility == ProjectCompatibility.UNSUPPORTED_FUTURE_VERSION:
            raise ValueError(f"このアプリはプロジェクト {source_version} を読み込めません。対応版は {APPLICATION_VERSION} です。")
        if compatibility == ProjectCompatibility.MIGRATION_REQUIRED:
            self._project_migrator.migrate(project_directory, source_version, APPLICATION_VERSION)

    def _read_project_version(self, project_directory: Path) -> ApplicationVersion:
        """manifestから保存時のKnowledgeTreeバージョンを読み込む。"""
        manifest_path = project_directory / "project.json"
        if not manifest_path.exists():
            return ApplicationVersion(0, 1)
        data = self._read_json(manifest_path)
        version_data = data.get("version", data.get("format_version"))
        if not isinstance(version_data, dict):
            raise ValueError("project.jsonのversionが不正です。")
        major, minor = version_data.get("major"), version_data.get("minor")
        if not isinstance(major, int) or not isinstance(minor, int) or major < 0 or minor < 0:
            raise ValueError("project.jsonのversionが不正です。")
        return ApplicationVersion(major, minor)

    def _active_snapshot_directory(self, project_directory: Path) -> Path:
        """manifestが指す完全なスナップショットディレクトリを返す。"""
        generation_id = self._active_snapshot_id_or_none(project_directory)
        if generation_id is None:
            raise ValueError("project.jsonのactive_snapshotが不正です。")
        snapshot_directory = project_directory / "snapshots" / generation_id
        if not snapshot_directory.is_dir():
            raise ValueError("アクティブな保存世代が見つかりません。")
        return snapshot_directory

    def _active_snapshot_id_or_none(self, project_directory: Path) -> str | None:
        """manifestのアクティブ世代IDを、旧形式ならNoneとして返す。"""
        manifest_path = project_directory / "project.json"
        if not manifest_path.exists():
            return None
        generation_id = self._read_json(manifest_path).get("active_snapshot")
        if generation_id is None:
            return None
        if not isinstance(generation_id, str) or Path(generation_id).name != generation_id:
            raise ValueError("project.jsonのactive_snapshotが不正です。")
        return generation_id

    def _prune_snapshots(self, project_directory: Path, active_generation_id: str, previous_generation_id: str | None) -> None:
        """アクティブ世代と直前の世代以外のスナップショットを削除する。"""
        # manifestの切替成功後だけ、完全な直前世代をバックアップとして残す。
        generation_ids_to_keep = {active_generation_id}
        if previous_generation_id is not None:
            generation_ids_to_keep.add(previous_generation_id)
        snapshots_directory = project_directory / "snapshots"
        if not snapshots_directory.is_dir():
            return
        resolved_snapshots_directory = snapshots_directory.resolve()
        for snapshot_directory in snapshots_directory.iterdir():
            if snapshot_directory.is_symlink() or not snapshot_directory.is_dir() or snapshot_directory.name in generation_ids_to_keep:
                continue
            resolved_snapshot_directory = snapshot_directory.resolve()
            if resolved_snapshot_directory.parent != resolved_snapshots_directory:
                continue
            # 不完全に残った世代もアクティブではないため、この時点で安全に除去できる。
            try:
                shutil.rmtree(resolved_snapshot_directory)
            except OSError:
                # 保存自体は完了しているため、後続保存時の再試行へ委ねる。
                continue

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
        """UTF-8 JSONをfsync済みの一時ファイル経由で原子的に保存する。"""
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
            temporary_path = Path(file.name)
        temporary_path.replace(path)

    def _fsync_directory(self, directory: Path) -> None:
        """対応環境ではスナップショットディレクトリのメタデータを同期する。"""
        if hasattr(os, "O_DIRECTORY"):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _graph_to_data(self, graph: KnowledgeGraph) -> dict[str, object]:
        """意味論的グラフをUI情報を含まないgraph.jsonへ変換する。"""
        nodes: list[dict[str, object]] = []
        for node in graph.nodes:
            if isinstance(node, QuestionNode):
                nodes.append({"id": node.id, "kind": node.kind.value, "title": node.title, "body": node.body, "child_combination": node.child_combination.value})
            elif isinstance(node, MemoNode):
                nodes.append({"id": node.id, "kind": node.kind.value, "title": node.title, "body": node.body})
            else:
                nodes.append({"id": node.id, "kind": node.kind.value, "reference_link": None if node.reference_link is None else {"kind": node.reference_link.kind.value, "id": node.reference_link.id}})
        return {"schema_version": 1, "nodes": nodes, "edges": [{"id": edge.id, "source_node_id": edge.source_node_id, "target_node_id": edge.target_node_id, "label": edge.label} for edge in graph.edges]}

    def _graph_from_data(self, data: dict[str, object]) -> KnowledgeGraph:
        """graph.jsonから種別ごとの意味論的ノードを復元する。"""
        nodes_data, edges_data = data.get("nodes"), data.get("edges")
        if not isinstance(nodes_data, list) or not isinstance(edges_data, list):
            raise ValueError("graph.jsonのnodesまたはedgesが不正です。")
        nodes = tuple(self._node_from_data(item) for item in nodes_data if isinstance(item, dict))
        edges = tuple(KnowledgeEdge(str(item["id"]), str(item["source_node_id"]), str(item["target_node_id"]), str(item.get("label", ""))) for item in edges_data if isinstance(item, dict))
        return KnowledgeGraph(nodes, edges)

    def _node_from_data(self, data: dict[str, object]) -> QuestionNode | MemoNode | ReferenceNode:
        """種別に応じてgraph.jsonの一ノードを復元する。"""
        node_id, kind = data.get("id"), data.get("kind")
        if not isinstance(node_id, str) or not isinstance(kind, str):
            raise ValueError("graph.jsonのnodeが不正です。")
        if kind == NodeKind.QUESTION.value:
            return QuestionNode(node_id, str(data.get("title", "")), str(data.get("body", "")), ChildCombination(str(data.get("child_combination", ""))))
        if kind == NodeKind.MEMO.value:
            return MemoNode(node_id, str(data.get("title", "")), str(data.get("body", "")))
        if kind == NodeKind.REFERENCE.value:
            return ReferenceNode(node_id, self._reference_link_from_data(data.get("reference_link")))
        raise ValueError("graph.jsonのnode kindが不正です。")

    def _layout_to_data(self, layout: GraphLayout) -> dict[str, object]:
        """Canvasレイアウトだけをlayout.json用の辞書へ変換する。"""
        return {"schema_version": 1, "nodes": [item.__dict__ for item in layout.node_layouts], "edges": [item.__dict__ for item in layout.edge_layouts]}

    def _layout_from_data(self, data: dict[str, object], graph: KnowledgeGraph) -> GraphLayout:
        """layout.jsonを復元し、グラフとのID対応も検査する。"""
        nodes_data, edges_data = data.get("nodes"), data.get("edges")
        if not isinstance(nodes_data, list) or not isinstance(edges_data, list):
            raise ValueError("layout.jsonのnodesまたはedgesが不正です。")
        layout = GraphLayout(tuple(NodeLayout(**item) for item in nodes_data if isinstance(item, dict)), tuple(EdgeLayout(**item) for item in edges_data if isinstance(item, dict)))
        self._validate_correspondence(graph, layout)
        return layout

    def _validate_correspondence(self, graph: KnowledgeGraph, layout: GraphLayout) -> None:
        """graph.jsonとlayout.jsonが完全に同じ要素IDを持つことを検査する。"""
        if {node.id for node in graph.nodes} != {item.node_id for item in layout.node_layouts} or {edge.id for edge in graph.edges} != {item.edge_id for item in layout.edge_layouts}:
            raise ValueError("graph.jsonとlayout.jsonの要素IDが一致しません。")

    def _reference_link_from_data(self, data: object) -> ReferenceLink | None:
        """JSON文献リンクをReferenceLinkへ変換する。"""
        if data is None:
            return None
        if not isinstance(data, dict) or not isinstance(data.get("kind"), str) or not isinstance(data.get("id"), str):
            raise ValueError("graph.jsonのreference_linkが不正です。")
        return ReferenceLink(ReferenceKind(data["kind"]), data["id"])

    def _settings_to_data(self, settings: ProjectSettings) -> dict[str, object]:
        """プロジェクト設定をスナップショット用JSONへ変換する。"""
        return {"schema_version": 3, "edge_types": [{"id": item.id, "label": item.label, "color_token": item.color_token.value, "allowed_endpoints": [[source.value, target.value] for source, target in item.allowed_endpoints]} for item in settings.edge_types()], "node_colors": {kind.value: settings.node_color(kind).value for kind in NodeKind}}

    def _settings_from_data(self, data: dict[str, object]) -> ProjectSettings:
        """設定JSONをProjectSettingsへ復元する。"""
        items, colors = data.get("edge_types"), data.get("node_colors")
        if not isinstance(items, list) or not isinstance(colors, dict):
            raise ValueError("project_settings.jsonが不正です。")
        edge_types = []
        for item in items:
            if not isinstance(item, dict):
                continue
            pairs = item.get("allowed_endpoints", [])
            if not isinstance(pairs, list):
                raise ValueError("project_settings.jsonのallowed_endpointsが不正です。")
            endpoints = tuple((NodeKind(str(pair[0])), NodeKind(str(pair[1]))) for pair in pairs if isinstance(pair, list) and len(pair) == 2)
            edge_types.append(EdgeType(str(item["id"]), str(item["label"]), ColorToken(str(item["color_token"])), endpoints))
        return ProjectSettings(edge_types, {kind: ColorToken(str(colors[kind.value])) for kind in NodeKind})
