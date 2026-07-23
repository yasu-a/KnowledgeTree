"""userdata直下に保存する、アプリ全体の設定。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GlobalSettings:
    """アプリ全体で最後に開いたプロジェクトを記録する。"""

    active_project_name: str | None = None
