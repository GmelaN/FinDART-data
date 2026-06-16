from datetime import date

from app.models.market import TimeSeriesPoint


class TimeSeriesStore:
    """Interface stub for future structured DB implementation."""

    def save_timeseries(self, series_id: str, points: list[TimeSeriesPoint]) -> None:
        raise NotImplementedError("Connect a structured DB implementation later.")

    def load_timeseries(
        self, series_id: str, start_date: date | None = None, end_date: date | None = None
    ) -> list[TimeSeriesPoint]:
        raise NotImplementedError("Connect a structured DB implementation later.")

    def get_recent_change(self, series_id: str, periods: int = 1) -> float | None:
        raise NotImplementedError("Connect a structured DB implementation later.")

