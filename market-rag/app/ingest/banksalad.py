import pandas as pd


class BanksaladCollector:
    """Parse portfolio exports locally and emit anonymized summaries only."""

    SENSITIVE_COLUMNS = {"계좌번호", "금융기관명", "거래내역", "account_number", "institution"}

    def load_export(self, path: str) -> pd.DataFrame:
        if path.endswith(".csv"):
            return pd.read_csv(path)
        return pd.read_excel(path)

    def anonymized_summary(self, path: str) -> dict:
        df = self.load_export(path)
        df = df.drop(columns=[col for col in self.SENSITIVE_COLUMNS if col in df.columns])
        return {
            "row_count": int(len(df)),
            "asset_classes": sorted(df.get("자산군", pd.Series(dtype=str)).dropna().unique().tolist()),
            "currencies": sorted(df.get("통화", pd.Series(dtype=str)).dropna().unique().tolist()),
            "note": "Raw personal finance rows are not stored in Qdrant.",
        }

