"""Lightweight history storage for replay and future online inference."""

from __future__ import annotations

import pandas as pd


class HistoryStore:
    """Keep recent state windows without coupling the controller to simulator internals."""

    def __init__(self, max_windows: int = 4) -> None:
        self.max_windows = max_windows
        self._windows: list[pd.DataFrame] = []

    def append(self, state_df: pd.DataFrame) -> None:
        self._windows.append(state_df.copy())
        if len(self._windows) > self.max_windows:
            self._windows = self._windows[-self.max_windows :]

    def combined(self) -> pd.DataFrame:
        if not self._windows:
            return pd.DataFrame()
        return pd.concat(self._windows, ignore_index=True)

    def latest(self) -> pd.DataFrame:
        if not self._windows:
            return pd.DataFrame()
        return self._windows[-1].copy()
