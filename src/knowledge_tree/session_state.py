"""ユーザーが直接編集しない実行セッション状態と保存処理。"""

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class SessionState:
    """次回起動時に復元する最小限の実行状態。"""

    last_active_project: str | None = None


class SessionStateStore:
    """userdata直下のsession_state.jsonを読み書きする。"""

    def __init__(self, userdata_directory: Path) -> None:
        """状態ファイルと旧全体設定ファイルを置くディレクトリを設定する。"""
        self._userdata_directory = userdata_directory
        self._path = userdata_directory / "session_state.json"
        self._legacy_global_settings_path = userdata_directory / "global_settings.json"

    def load(self) -> SessionState:
        """セッション状態を読み込み、旧active_projectがあれば一度だけ移行する。"""
        if self._path.exists():
            return self._state_from_data(self._read_json(self._path))
        legacy_state = self._legacy_state()
        if legacy_state.last_active_project is not None:
            self.save(legacy_state)
        return legacy_state

    def save(self, state: SessionState) -> None:
        """セッション状態をUTF-8 JSONとして原子的に保存する。"""
        self._userdata_directory.mkdir(parents=True, exist_ok=True)
        self._write_json({"schema_version": 1, "last_active_project": state.last_active_project})

    def _legacy_state(self) -> SessionState:
        """旧global_settings.jsonのactive_projectをセッション状態へ変換する。"""
        if not self._legacy_global_settings_path.exists():
            return SessionState()
        data = self._read_json(self._legacy_global_settings_path)
        active_project = data.get("active_project")
        return SessionState(active_project if isinstance(active_project, str) else None)

    def _state_from_data(self, data: dict[str, object]) -> SessionState:
        """JSON辞書から検証済みのセッション状態を作る。"""
        project_name = data.get("last_active_project")
        if project_name is not None and not isinstance(project_name, str):
            raise ValueError("session_state.jsonのlast_active_projectが不正です。")
        return SessionState(project_name)

    def _read_json(self, path: Path) -> dict[str, object]:
        """指定JSONオブジェクトを読み込み、形式エラーをValueErrorへ変換する。"""
        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"{path.name}を読み込めません。") from error
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}の形式が不正です。")
        return data

    def _write_json(self, data: dict[str, object]) -> None:
        """一時ファイルを経由してセッション状態JSONを書き込む。"""
        with NamedTemporaryFile("w", encoding="utf-8", dir=self._userdata_directory, delete=False) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            temporary_path = Path(file.name)
        temporary_path.replace(self._path)
