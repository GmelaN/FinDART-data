from __future__ import annotations

from app.models.document import SourceType
from app.services.sources.rss import RssFeed, RssFetcher


DEFAULT_POLICY_BRIEFING_FEEDS = [
    RssFeed("대한민국 정책브리핑", "정책뉴스", "https://www.korea.kr/rss/policy.xml", SourceType.policy.value),
    RssFeed("대한민국 정책브리핑", "보도자료", "https://www.korea.kr/rss/pressrelease.xml", SourceType.policy.value),
    RssFeed("대한민국 정책브리핑", "이슈인사이트", "https://www.korea.kr/rss/insight.xml", SourceType.policy.value),
    RssFeed("재정경제부", "부처", "https://www.korea.kr/rss/dept_mofe.xml", SourceType.policy.value),
    RssFeed("산업통상부", "부처", "https://www.korea.kr/rss/dept_motir.xml", SourceType.policy.value),
    RssFeed("국토교통부", "부처", "https://www.korea.kr/rss/dept_molit.xml", SourceType.policy.value),
    RssFeed("중소벤처기업부", "부처", "https://www.korea.kr/rss/dept_mss.xml", SourceType.policy.value),
    RssFeed("금융위원회", "위원회", "https://www.korea.kr/rss/dept_fsc.xml", SourceType.policy.value),
]


class PolicyBriefingRssFetcher(RssFetcher):
    source_name = "policy_briefing"

    def __init__(self, feeds: list[RssFeed] | None = None, **kwargs):
        super().__init__(feeds or DEFAULT_POLICY_BRIEFING_FEEDS, **kwargs)
