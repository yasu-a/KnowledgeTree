"""ユーザーが変更できるアプリ全体の設定と保存処理。"""

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class GlobalSettings:
    """プロジェクトに属さない、ユーザー編集可能な設定を表す。"""

    reopen_last_project: bool = True


class GlobalSettingsStore:
    """userdata直下のglobal_settings.jsonを読み書きする。"""

    def __init__(self, userdata_directory: Path) -> None:
        """設定ファイルを置くuserdataディレクトリを設定する。"""
        self._userdata_directory = userdata_directory
        self._path = userdata_directory / "global_settings.json"

    def load(self) -> GlobalSettings:
        """保存済みの全体設定を読み込み、未作成なら既定値を返す。"""
        if not self._path.exists():
            return GlobalSettings()
        data = self._read_json()
        reopen_last_project = data.get("reopen_last_project", True)
        if not isinstance(reopen_last_project, bool):
            raise ValueError("global_settings.jsonのreopen_last_projectが不正です。")
        return GlobalSettings(reopen_last_project)

    def save(self, settings: GlobalSettings) -> None:
        """全体設定をUTF-8 JSONとして原子的に保存する。"""
        self._userdata_directory.mkdir(parents=True, exist_ok=True)
        self._write_json({"schema_version": 1, "reopen_last_project": settings.reopen_last_project})

    def _read_json(self) -> dict[str, object]:
        """全体設定JSONを読み込み、形式エラーをValueErrorへ変換する。"""
        try:
            with self._path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("global_settings.jsonを読み込めません。") from error
        if not isinstance(data, dict):
            raise ValueError("global_settings.jsonの形式が不正です。")
        return data

    def _write_json(self, data: dict[str, object]) -> None:
        """一時ファイルを経由して全体設定JSONを書き込む。"""
        with NamedTemporaryFile("w", encoding="utf-8", dir=self._userdata_directory, delete=False) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            temporary_path = Path(file.name)
        temporary_path.replace(self._path)
