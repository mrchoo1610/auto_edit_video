"""
YouTube title / description / tags for a Full Match Condensed video.

Everything is built from facts the project already holds (players, race-to, final score, chapters, duration, optional
date / venue / channel). Nothing is invented: a line is left out when its fact is missing.

SEO rules applied (from general YouTube practice, not verified against YouTube's current documentation):
  - title: main keywords first, players + format + result, ideally <= 70 characters (hard limit 100)
  - description: the first ~150 characters carry the keywords because only they show before "show more";
    no filler sentences (no "about this video" paragraph, no call to subscribe)
  - chapters: "0:00" first line, one line per rack
  - hashtags: at most 5, no spaces (YouTube shows the first 3 above the title)
  - tags: total length <= 500 characters
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

TITLE_SOFT_LIMIT = 70
TITLE_HARD_LIMIT = 100
TAGS_MAX_CHARS = 500
HASHTAG_MAX = 5
HOOK_MAX_CHARS = 150


@dataclass
class MatchFacts:
    p1: str
    p2: str
    race_to: int
    score: Optional[Tuple[int, int]] = None        # final (p1, p2) after the last included rack
    winner: Optional[int] = None                    # 1 or 2 once someone reached race_to
    chapters: str = ""                              # chapters.txt text, "0:00 Ván 1: ..." per line
    duration_min: Optional[float] = None
    played_on: Optional[date] = None
    venue: str = ""
    tournament: str = ""
    channel: str = ""
    discipline: str = "Pool 9 bi"                   # display name used in the text
    extra_keywords: List[str] = field(default_factory=list)


def ascii_slug(text: str) -> str:
    """"Khương Liều" -> "KhuongLieu" (hashtags and tags without diacritics or spaces)."""
    t = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^0-9A-Za-z]+", "", t.title())


def _result_phrase(f: MatchFacts) -> str:
    if not f.score:
        return ""
    a, b = f.score
    if f.winner in (1, 2):
        name = f.p1 if f.winner == 1 else f.p2
        win, lose = (a, b) if f.winner == 1 else (b, a)
        return f"{name} thắng {win}-{lose}"
    return f"tỷ số {a}-{b}"


def title_candidates(f: MatchFacts) -> List[str]:
    """Best first. The first candidate within TITLE_SOFT_LIMIT wins; otherwise the shortest one under the hard limit."""
    score = f" ({f.score[0]}-{f.score[1]})" if f.score else ""
    head = f"{f.p1} vs {f.p2}"
    fmt = f"{f.discipline.title()} Race to {f.race_to}"
    return [
        f"{head} | {fmt}{score} | Full Trận Đấu Rút Gọn",
        f"{head} | {fmt}{score} | Full Rút Gọn",
        f"{head} | {fmt}{score}",
        f"{head} | Bida 9 Bi{score}",
    ]


def pick_title(f: MatchFacts) -> str:
    cands = [c for c in title_candidates(f) if len(c) <= TITLE_HARD_LIMIT]
    for c in cands:
        if len(c) <= TITLE_SOFT_LIMIT:
            return c
    return min(cands, key=len) if cands else title_candidates(f)[-1][:TITLE_HARD_LIMIT]


def title_without_score(f: MatchFacts) -> str:
    """Spoiler-free variant for viewers who want to watch before seeing the result."""
    g = MatchFacts(**{**f.__dict__, "score": None, "winner": None})
    return pick_title(g)


def hook_line(f: MatchFacts) -> str:
    """First sentence of the description: keywords up front, <= HOOK_MAX_CHARS."""
    result = _result_phrase(f)
    options = [
        f"Xem full trận {f.discipline.lower()} {f.p1} vs {f.p2}, race to {f.race_to}"
        + (f", {result}" if result else "") + ".",
        f"Full trận {f.discipline.lower()} {f.p1} vs {f.p2}, race to {f.race_to}" + (f", {result}" if result else "") + ".",
        f"{f.p1} vs {f.p2} - {f.discipline} race to {f.race_to}.",
    ]
    for o in options:
        if len(o) <= HOOK_MAX_CHARS:
            return o
    return options[-1][:HOOK_MAX_CHARS]


def hashtags(f: MatchFacts) -> List[str]:
    tags = ["#Pool9Bi", "#Bida", "#Billiards"]
    for name in (f.p1, f.p2):
        slug = ascii_slug(name)
        if slug:
            tags.append("#" + slug)
    tags.append("#9Ball")                      # first to be cut when the 5-hashtag cap is reached
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:HASHTAG_MAX]


def tags(f: MatchFacts) -> List[str]:
    """Hidden video tags, most specific first, trimmed to TAGS_MAX_CHARS (comma separated length)."""
    base = [
        f"{f.p1} vs {f.p2}", f"{f.p1}", f"{f.p2}",
        f"{ascii_slug(f.p1)} vs {ascii_slug(f.p2)}",
        "bida 9 bi", "pool 9 bi", "9 ball pool", "billiards", "bida",
        f"race to {f.race_to}", "full trận bida", "trận đấu bida", "bida pool",
        "bi-a", "9-ball", "nine ball",
    ]
    if f.tournament:
        base.insert(3, f.tournament)
    base += f.extra_keywords
    out, used, seen = [], 0, set()
    for t in base:
        t = t.strip()
        if not t or t.lower() in seen:
            continue
        cost = len(t) + (1 if out else 0)
        if used + cost > TAGS_MAX_CHARS:
            break
        seen.add(t.lower())
        out.append(t)
        used += cost
    return out


def description(f: MatchFacts) -> str:
    lines: List[str] = [hook_line(f), ""]
    info = [f"Cơ thủ: {f.p1} vs {f.p2}",
            f"Thể thức: {f.discipline}, race to {f.race_to}"]
    if f.score:
        info.append(f"Kết quả chung cuộc: {f.p1} {f.score[0]} - {f.score[1]} {f.p2}"
                    + (f" ({_result_phrase(f)})" if f.winner in (1, 2) else ""))
    if f.tournament:
        info.append(f"Giải / chương trình: {f.tournament}")
    if f.venue:
        info.append(f"Địa điểm: {f.venue}")
    if f.channel:
        info.append(f"Kênh: {f.channel}")
    if f.played_on:
        info.append(f"Ngày thi đấu: {f.played_on.strftime('%d/%m/%Y')}")
    lines += ["Thông tin trận đấu"] + [f"- {i}" for i in info] + [""]
    if f.chapters.strip():
        lines += ["Mục lục"] + f.chapters.strip().splitlines() + [""]
    lines += [" ".join(hashtags(f))]
    return "\n".join(lines).rstrip() + "\n"


def build_youtube_metadata(f: MatchFacts) -> Dict[str, object]:
    title = pick_title(f)
    desc = description(f)
    tg = tags(f)
    return {
        "title": title,
        "title_no_score": title_without_score(f),
        "title_alternatives": [c for c in title_candidates(f) if c != title and len(c) <= TITLE_HARD_LIMIT],
        "description": desc,
        "hook": hook_line(f),
        "hashtags": hashtags(f),
        "tags": tg,
        "tags_chars": len(",".join(tg)),
    }


def missing_facts(f: MatchFacts) -> List[str]:
    out = []
    if not f.venue:
        out.append("địa điểm (`--venue`)")
    if not f.played_on:
        out.append("ngày thi đấu (`--date`)")
    return out


def to_markdown(meta: Dict[str, object], missing: Sequence[str] = ()) -> str:
    """One page to copy from: every field in its own section, with the lengths that matter for SEO."""
    title = str(meta["title"])
    out = [
        "# YouTube: tiêu đề, mô tả, thẻ",
        "",
        f"## Tiêu đề ({len(title)} ký tự, nên ≤ {TITLE_SOFT_LIMIT}, tối đa {TITLE_HARD_LIMIT})",
        "",
        title,
        "",
        f"Bản không lộ kết quả ({len(str(meta['title_no_score']))} ký tự): {meta['title_no_score']}",
    ]
    alts = meta.get("title_alternatives") or []
    if alts:
        out += ["", "Phương án khác:"] + [f"- {a} ({len(a)} ký tự)" for a in alts]
    out += ["", f"## Mô tả (dòng đầu {len(str(meta['hook']))} ký tự; ~{HOOK_MAX_CHARS} ký tự đầu hiện trước khi bấm \"Xem thêm\")",
            "", str(meta["description"]).rstrip(), "",
            f"## Thẻ ({meta['tags_chars']}/{TAGS_MAX_CHARS} ký tự)", "", ", ".join(meta["tags"]),  # type: ignore[arg-type]
            "", "## Hashtag (3 cái đầu hiện trên tiêu đề)", "", " ".join(meta["hashtags"]),  # type: ignore[arg-type]
            "", "## Cần kiểm tra trước khi đăng", ""]
    if missing:
        out.append("- Mô tả chưa có: " + ", ".join(missing) + ". Thêm khi chạy lại `seo` hoặc `render` nếu muốn.")
    out += ["- Ngày thi đấu (nếu có) lấy từ tên thư mục project, hãy kiểm tra lại cho đúng.",
            "- Mốc chương trong mô tả phải khớp video đã xuất; nên dán từ `chapters.txt` cùng thư mục.",
            "- Giới hạn độ dài tiêu đề/mô tả/thẻ ở trên theo hiểu biết chung về YouTube, chưa đối chiếu lại tài liệu chính thức.",
            ""]
    return "\n".join(out)


def parse_date_from_project_name(name: str) -> Optional[date]:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", name)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
