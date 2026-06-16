from pathlib import Path

import pandas as pd


DEFAULT_COMPANY_MASTER = Path("data/processed/company_master.csv")


class EntityExtractor:
    def __init__(self, company_master_path: str | Path = DEFAULT_COMPANY_MASTER):
        self.company_master_path = Path(company_master_path)
        self._companies = self._load_company_master()

    def _load_company_master(self) -> list[dict[str, str]]:
        if not self.company_master_path.exists():
            return []
        df = pd.read_csv(self.company_master_path, dtype=str).fillna("")
        companies: list[dict[str, str]] = []
        for _, row in df.iterrows():
            name = row.get("company_name") or row.get("name") or ""
            ticker = row.get("ticker") or row.get("stock_code") or ""
            if name:
                companies.append({"company_name": name, "ticker": ticker})
        return companies

    def extract(self, text: str) -> dict[str, list[str]]:
        company_names: list[str] = []
        tickers: list[str] = []
        for item in self._companies:
            name = item["company_name"]
            ticker = item["ticker"]
            if name and name in text:
                company_names.append(name)
                if ticker:
                    tickers.append(ticker.zfill(6))
            elif ticker and ticker.zfill(6) in text:
                tickers.append(ticker.zfill(6))
                company_names.append(name)

        return {
            "company_names": sorted(set(company_names)),
            "tickers": sorted(set(tickers)),
        }

