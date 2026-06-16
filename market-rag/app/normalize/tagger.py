from collections.abc import Iterable


MACRO_RULES = {
    "rates": ["금리", "기준금리", "국고채", "채권금리", "회사채", "장기금리"],
    "fx": ["환율", "원화", "달러", "외환", "usd/krw", "원/달러", "엔화"],
    "inflation": ["물가", "cpi", "근원 cpi", "인플레이션", "소비자물가"],
    "growth": ["성장", "gdp", "생산", "경기", "산업생산"],
    "employment": ["고용", "실업률", "취업자", "임금"],
    "exports": ["수출", "수입", "무역수지", "수출입"],
}

SECTOR_RULES = {
    "semiconductor": ["반도체", "hbm", "메모리", "파운드리"],
    "power_grid": ["전력망", "변압기", "전선", "송전", "배전", "전력기기"],
    "defense": ["방산", "무기체계", "방위산업", "국방", "수출형 무기"],
    "construction": ["건설", "부동산", "soc", "주택", "인프라"],
    "consumer": ["소비", "유통", "내수", "소매판매", "면세"],
}

ASSET_RULES = {
    "kr_equity": ["한국 증시", "코스피", "코스닥", "국내주식"],
    "us_equity": ["미국 증시", "나스닥", "s&p500", "미국주식"],
    "bond": ["채권", "국채", "회사채"],
    "cash": ["현금", "예금", "mmf"],
    "fx": ["달러", "환율", "외화"],
}

RISK_RULES = {
    "rate_up": ["금리 상승", "장기금리 상승", "긴축"],
    "krw_weakness": ["원화 약세", "환율 상승", "달러 강세"],
    "semiconductor_downturn": ["반도체 부진", "메모리 가격 하락", "수출 둔화"],
}


def _match_rules(text: str, rules: dict[str, Iterable[str]]) -> list[str]:
    lower = text.lower()
    return [tag for tag, words in rules.items() if any(word.lower() in lower for word in words)]


def tag_text(text: str) -> dict[str, list[str]]:
    return {
        "macro_tags": _match_rules(text, MACRO_RULES),
        "sector_tags": _match_rules(text, SECTOR_RULES),
        "asset_tags": _match_rules(text, ASSET_RULES),
        "risk_tags": _match_rules(text, RISK_RULES),
    }

