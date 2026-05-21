"""성경 본문을 제목 + 최대 2줄로 나눕니다."""


def split_two_lines(text: str, max_lines: int = 2) -> list[str]:
    """공백 단위로 단어를 나눈 뒤, 줄 수를 넘지 않도록 균형 있게 배분합니다."""
    words = text.split()
    if not words:
        return [""]
    if max_lines < 1:
        max_lines = 1
    if len(words) <= max_lines:
        return words + [""] * (max_lines - len(words))

    # 단어 수를 줄 수에 맞게 균등 분할 (앞 줄에 하나 더 배분)
    line_count = min(max_lines, len(words))
    base, extra = divmod(len(words), line_count)
    lines: list[str] = []
    idx = 0
    for line_no in range(line_count):
        take = base + (1 if line_no < extra else 0)
        chunk = words[idx : idx + take]
        idx += take
        lines.append(" ".join(chunk))
    return lines


def format_verse(title: str, body: str) -> tuple[str, list[str], str]:
    """장절 제목과 본문 2줄, 원문을 반환합니다."""
    lines = split_two_lines(body.strip(), max_lines=2)
    while len(lines) < 2:
        lines.append("")
    return title, lines[:2], body.strip()
