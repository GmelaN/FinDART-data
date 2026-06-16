SECTOR_ALIASES = {
    "semiconductor": ["반도체", "HBM", "메모리"],
    "power_grid": ["전력기기", "변압기", "전선"],
    "defense": ["방산", "방위산업"],
    "construction": ["건설", "SOC", "부동산"],
    "consumer": ["소비", "유통", "내수"],
}


def normalize_sector(raw: str) -> str | None:
    raw_lower = raw.lower()
    for sector, aliases in SECTOR_ALIASES.items():
        if sector == raw_lower or any(alias.lower() in raw_lower for alias in aliases):
            return sector
    return None

