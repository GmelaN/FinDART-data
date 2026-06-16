from app.normalize.text_cleaner import clean_text


SENTENCE_ENDINGS = {".", "!", "?", "。", "！", "？"}


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for idx, char in enumerate(text):
        if char not in SENTENCE_ENDINGS:
            continue
        next_idx = idx + 1
        if next_idx < len(text) and not text[next_idx].isspace():
            continue
        sentence = text[start:next_idx].strip()
        if sentence:
            sentences.append(sentence)
        start = next_idx
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences or [text.strip()]


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for start in range(0, len(sentence), max_chars - overlap):
                chunks.append(sentence[start : start + max_chars].strip())
            continue

        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())
            current = f"{current[-overlap:]} {sentence}".strip() if overlap else sentence
            if len(current) > max_chars:
                current = sentence

    if current:
        chunks.append(current.strip())
    return chunks

