import re

from bs4 import BeautifulSoup


def strip_html(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ")


def clean_text(text: str) -> str:
    text = strip_html(text)
    text = re.sub(r"[\u200b\ufeff\xa0]", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_too_short(text: str, min_chars: int = 40) -> bool:
    return len(clean_text(text)) < min_chars

