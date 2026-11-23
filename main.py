import csv
import json
import random
import textwrap
import time
from pathlib import Path

import yt_dlp

# ---------- SETTINGS ----------
KEYWORD = "landslide"             # English; translations below are written for this word
EXTRA_MATCH_TERMS = ["mudslide"]  # extra words that count as relevant
RESULTS_PER_COUNTRY = 10
COUNTRY_LIMIT = 1                 # test with a few first; set to None for all
USE_TRANSLATIONS = True

# Which stages to run. Remove one to skip it.
STAGES = ["search", "details", "transcripts"]

# Stage 3 (transcripts) pacing: this is the part YouTube throttles hardest
TRANSCRIPTS_PER_RUN = 15              # stop after this many per run (None = no cap)
TRANSCRIPT_DELAY = (30, 60)           # seconds between transcript fetches
REST_EVERY = 10                       # longer rest after this many transcripts
REST_SECONDS = 600
TRANSCRIPTS_ONLY_FOR_MATCHES = False  # True = skip videos whose title/description/tags don't match

# Other delays (seconds)
SEARCH_DELAY = (5, 10)            # between country searches
VIDEO_DELAY = (8, 15)             # between metadata fetches
BREAK_SECONDS = 300               # wait after a 429 in stage 2 before one retry

# Optional: real per-country proxies, e.g. {"DE": "http://user:pass@host:port"}
PROXIES = {}

BASE_DIR = Path(__file__).resolve().parent
SEARCH_FILE = BASE_DIR / "search.jsonl"            # stage 1: one line per country
DETAILS_FILE = BASE_DIR / "details.jsonl"          # stage 2: one line per video
TRANSCRIPTS_FILE = BASE_DIR / "transcripts.jsonl"  # stage 3: one line per video
OUTPUT_TXT = BASE_DIR / "results.txt"
OUTPUT_CSV = BASE_DIR / "results.csv"

# ---------- COUNTRIES (code: name) ----------
COUNTRIES = {
    "DZ": "Algeria", "AR": "Argentina", "AU": "Australia", "AT": "Austria",
    "AZ": "Azerbaijan", "BH": "Bahrain", "BD": "Bangladesh", "BY": "Belarus",
    "BE": "Belgium", "BO": "Bolivia", "BA": "Bosnia and Herzegovina",
    "BR": "Brazil", "BG": "Bulgaria", "CA": "Canada", "CL": "Chile",
    "CO": "Colombia", "CR": "Costa Rica", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czechia", "DK": "Denmark", "DO": "Dominican Republic",
    "EC": "Ecuador", "EG": "Egypt", "SV": "El Salvador", "EE": "Estonia",
    "FI": "Finland", "FR": "France", "GE": "Georgia", "DE": "Germany",
    "GH": "Ghana", "GR": "Greece", "GT": "Guatemala", "HN": "Honduras",
    "HK": "Hong Kong", "HU": "Hungary", "IS": "Iceland", "IN": "India",
    "ID": "Indonesia", "IQ": "Iraq", "IE": "Ireland", "IL": "Israel",
    "IT": "Italy", "JM": "Jamaica", "JP": "Japan", "JO": "Jordan",
    "KZ": "Kazakhstan", "KE": "Kenya", "KW": "Kuwait", "LV": "Latvia",
    "LB": "Lebanon", "LY": "Libya", "LI": "Liechtenstein", "LT": "Lithuania",
    "LU": "Luxembourg", "MY": "Malaysia", "MT": "Malta", "MX": "Mexico",
    "ME": "Montenegro", "MA": "Morocco", "NP": "Nepal", "NL": "Netherlands",
    "NZ": "New Zealand", "NI": "Nicaragua", "NG": "Nigeria",
    "MK": "North Macedonia", "NO": "Norway", "OM": "Oman", "PK": "Pakistan",
    "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "PR": "Puerto Rico",
    "QA": "Qatar", "RO": "Romania", "RU": "Russia", "SA": "Saudi Arabia",
    "SN": "Senegal", "RS": "Serbia", "SG": "Singapore", "SK": "Slovakia",
    "SI": "Slovenia", "ZA": "South Africa", "KR": "South Korea", "ES": "Spain",
    "LK": "Sri Lanka", "SE": "Sweden", "CH": "Switzerland", "TW": "Taiwan",
    "TZ": "Tanzania", "TH": "Thailand", "TN": "Tunisia", "TR": "Turkey",
    "UG": "Uganda", "UA": "Ukraine", "AE": "United Arab Emirates",
    "GB": "United Kingdom", "US": "United States", "UY": "Uruguay",
    "VE": "Venezuela", "VN": "Vietnam", "YE": "Yemen", "ZW": "Zimbabwe",
}

# ---------- MAIN LANGUAGE PER COUNTRY ----------
LANGUAGES = {
    "DZ": "ar", "AR": "es", "AU": "en", "AT": "de", "AZ": "az", "BH": "ar",
    "BD": "bn", "BY": "be", "BE": "nl", "BO": "es", "BA": "bs", "BR": "pt",
    "BG": "bg", "CA": "en", "CL": "es", "CO": "es", "CR": "es", "HR": "hr",
    "CY": "el", "CZ": "cs", "DK": "da", "DO": "es", "EC": "es", "EG": "ar",
    "SV": "es", "EE": "et", "FI": "fi", "FR": "fr", "GE": "ka", "DE": "de",
    "GH": "en", "GR": "el", "GT": "es", "HN": "es", "HK": "zh-TW", "HU": "hu",
    "IS": "is", "IN": "hi", "ID": "id", "IQ": "ar", "IE": "en", "IL": "iw",
    "IT": "it", "JM": "en", "JP": "ja", "JO": "ar", "KZ": "kk", "KE": "sw",
    "KW": "ar", "LV": "lv", "LB": "ar", "LY": "ar", "LI": "de", "LT": "lt",
    "LU": "fr", "MY": "ms", "MT": "mt", "MX": "es", "ME": "sr", "MA": "ar",
    "NP": "ne", "NL": "nl", "NZ": "en", "NI": "es", "NG": "en", "MK": "mk",
    "NO": "no", "OM": "ar", "PK": "ur", "PA": "es", "PG": "en", "PY": "es",
    "PE": "es", "PH": "tl", "PL": "pl", "PT": "pt", "PR": "es", "QA": "ar",
    "RO": "ro", "RU": "ru", "SA": "ar", "SN": "fr", "RS": "sr", "SG": "en",
    "SK": "sk", "SI": "sl", "ZA": "en", "KR": "ko", "ES": "es", "LK": "si",
    "SE": "sv", "CH": "de", "TW": "zh-TW", "TZ": "sw", "TH": "th", "TN": "ar",
    "TR": "tr", "UG": "en", "UA": "uk", "AE": "ar", "GB": "en", "US": "en",
    "UY": "es", "VE": "es", "VN": "vi", "YE": "ar", "ZW": "en",
}

# ---------- HAND-WRITTEN TRANSLATIONS OF "landslide" ----------
MANUAL_TRANSLATIONS = {
    "ar": "انهيار أرضي", "es": "deslizamiento de tierra", "de": "Erdrutsch",
    "az": "torpaq sürüşməsi", "bn": "ভূমিধস", "be": "апалзень",
    "nl": "aardverschuiving", "bs": "klizište", "pt": "deslizamento de terra",
    "bg": "свлачище", "hr": "klizište", "el": "κατολίσθηση", "cs": "sesuv půdy",
    "da": "jordskred", "et": "maalihe", "fi": "maanvyörymä",
    "fr": "glissement de terrain", "ka": "მეწყერი", "hu": "földcsuszamlás",
    "is": "aurskriða", "hi": "भूस्खलन", "id": "tanah longsor",
    "iw": "מפולת אדמה", "it": "frana", "ja": "地すべり", "kk": "жер көшкіні",
    "sw": "maporomoko ya ardhi", "lv": "zemes nogruvums", "lt": "nuošliauža",
    "ms": "tanah runtuh", "mt": "frana", "sr": "клизиште", "ne": "पहिरो",
    "mk": "свлечиште", "no": "jordskred", "ur": "لینڈ سلائیڈ",
    "tl": "pagguho ng lupa", "pl": "osuwisko", "ro": "alunecare de teren",
    "ru": "оползень", "sk": "zosuv pôdy", "sl": "plaz", "ko": "산사태",
    "si": "නායයෑම", "sv": "jordskred", "th": "ดินถล่ม", "tr": "heyelan",
    "uk": "зсув", "vi": "sạt lở đất", "zh-TW": "山崩",
}

if COUNTRY_LIMIT:
    COUNTRIES = dict(list(COUNTRIES.items())[:COUNTRY_LIMIT])


# ---------- HELPERS ----------
def get_term(code):
    lang = LANGUAGES.get(code, "en")
    if not USE_TRANSLATIONS or lang == "en":
        return KEYWORD
    return MANUAL_TRANSLATIONS.get(lang, KEYWORD)


def match_terms(code):
    """Words that make a video relevant for this country."""
    return list(dict.fromkeys([KEYWORD, get_term(code)] + EXTRA_MATCH_TERMS))


def find_matches(text, terms):
    text = (text or "").lower()
    return [t for t in terms if t.lower() in text]


def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def is_valid_detail(r):
    """Counts only if it has the current fields and no error.
    Old-format or failed records are ignored and re-fetched."""
    return "upload_date" in r and "has_captions" in r and not r.get("error")


def load_transcripts():
    """video id -> (status, text). status is 'ok' or 'none' (no captions found).
    Also picks up transcripts saved by older versions of this script."""
    out = {}
    for r in load_jsonl(DETAILS_FILE):
        if r.get("transcript"):
            out[r["id"]] = ("ok", r["transcript"])
    for r in load_jsonl(TRANSCRIPTS_FILE):
        if r.get("status") in ("ok", "none"):
            out[r["id"]] = (r["status"], r.get("transcript"))
    return out


def is_blocked(e):
    s = str(e)
    return "429" in s or "Too Many Requests" in s


def pause(span):
    time.sleep(random.uniform(*span))


def make_opts(code, flat=False):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "geo_bypass_country": code,
        "sleep_interval_requests": 2,
        "retries": 5,
    }
    if code in PROXIES:
        opts["proxy"] = PROXIES[code]
    if flat:
        opts["extract_flat"] = True
    return opts


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else "N/A"


def fmt_date(d):
    """YYYYMMDD -> YYYY-MM-DD"""
    if d and len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d or ""


# ---------- STAGE 1: one cheap search per country ----------
def stage1():
    done = {r["code"] for r in load_jsonl(SEARCH_FILE)}
    for code, country in COUNTRIES.items():
        if code in done:
            continue
        term = get_term(code)
        print(f"[Stage 1] Searching {country} ({code})...")
        try:
            query = f"ytsearch{RESULTS_PER_COUNTRY}:{term}"
            with yt_dlp.YoutubeDL(make_opts(code, flat=True)) as ydl:
                info = ydl.extract_info(query, download=False)
        except Exception as e:
            if is_blocked(e):
                print("  Blocked (429). Stopping; rerun later to resume.")
                return False
            print(f"  Search failed: {e}")
            continue  # not saved, so it's retried next run

        videos = []
        for e in info.get("entries", []):
            if not e or not e.get("id"):
                continue
            videos.append({
                "id": e["id"],
                "title": e.get("title"),
                "description": e.get("description"),
            })
        # list order = search rank (1 = top result)
        append_jsonl(SEARCH_FILE, {"code": code, "country": country,
                                   "term": term, "videos": videos})
        print(f"  Found {len(videos)} videos")
        pause(SEARCH_DELAY)
    return True


# ---------- STAGE 2: metadata for every video (no transcripts) ----------
def fetch_details(vid, code):
    url = f"https://www.youtube.com/watch?v={vid}"
    with yt_dlp.YoutubeDL(make_opts(code)) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "id": vid,
        "title": info.get("title"),
        "channel": info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "channel_url": info.get("channel_url") or info.get("uploader_url"),
        "url": url,
        "upload_date": fmt_date(info.get("upload_date")),
        "duration_sec": info.get("duration"),
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "language": info.get("language"),
        "tags": info.get("tags") or [],
        "description": info.get("description"),
        # lets stage 3 skip videos that have no captions at all
        "has_captions": bool(info.get("subtitles") or info.get("automatic_captions")),
    }


def stage2():
    searches = load_jsonl(SEARCH_FILE)
    already = {r["id"] for r in load_jsonl(DETAILS_FILE) if is_valid_detail(r)}

    todo = {}  # deduplicated by video id
    for rec in searches:
        if rec["code"] not in COUNTRIES:
            continue
        for v in rec["videos"]:
            if v["id"] not in already and v["id"] not in todo:
                todo[v["id"]] = rec["code"]

    print(f"[Stage 2] {len(todo)} videos to fetch")
    for n, (vid, code) in enumerate(todo.items(), 1):
        print(f"  {n}/{len(todo)}  {vid}")
        for attempt in (1, 2):
            try:
                append_jsonl(DETAILS_FILE, fetch_details(vid, code))
                break
            except Exception as e:
                if is_blocked(e):
                    if attempt == 1:
                        print(f"  Blocked (429). Waiting {BREAK_SECONDS}s, then retrying once...")
                        time.sleep(BREAK_SECONDS)
                        continue
                    print("  Still blocked. Stopping; rerun later to resume.")
                    return False
                append_jsonl(DETAILS_FILE, {"id": vid, "error": str(e)})
                break
        pause(VIDEO_DELAY)
    return True


# ---------- STAGE 3: transcripts, slow and resumable ----------
def fetch_transcript(info, ydl, langs):
    """One caption file per video: manual subs first, then auto captions."""
    for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang in langs:
            key = next((k for k in source if k == lang or k.startswith(lang + "-")), None)
            if not key:
                continue
            fmt_ = next((f for f in source[key] if f.get("ext") == "json3"), None)
            if not fmt_:
                continue
            try:
                data = json.loads(ydl.urlopen(fmt_["url"]).read().decode("utf-8"))
                text = " ".join(
                    seg.get("utf8", "")
                    for ev in data.get("events", [])
                    for seg in ev.get("segs", [])
                ).replace("\n", " ")
                return " ".join(text.split()) or None
            except Exception as e:
                if is_blocked(e):
                    raise  # stop the run on a 429
                continue
    return None


def fetch_transcript_for(vid, code):
    # caption links expire, so the video page is re-read to get fresh ones
    url = f"https://www.youtube.com/watch?v={vid}"
    country_lang = LANGUAGES.get(code, "en").split("-")[0]
    with yt_dlp.YoutubeDL(make_opts(code)) as ydl:
        info = ydl.extract_info(url, download=False)
        langs = [l for l in (info.get("language"), country_lang, "en") if l]
        return fetch_transcript(info, ydl, langs)


def stage3():
    details = {r["id"]: r for r in load_jsonl(DETAILS_FILE) if is_valid_detail(r)}
    done = set(load_transcripts())

    code_of = {}
    for rec in load_jsonl(SEARCH_FILE):
        if rec["code"] in COUNTRIES:
            for v in rec["videos"]:
                code_of.setdefault(v["id"], rec["code"])

    todo = []  # (priority, video id, country code)
    for vid, code in code_of.items():
        d = details.get(vid)
        if not d or vid in done:
            continue
        if not d.get("has_captions"):  # nothing to download, so don't waste a request
            append_jsonl(TRANSCRIPTS_FILE, {"id": vid, "status": "none", "transcript": None})
            continue
        text = " ".join([d.get("title") or "", d.get("description") or "",
                         " ".join(d.get("tags") or [])])
        matched = bool(find_matches(text, match_terms(code)))
        if TRANSCRIPTS_ONLY_FOR_MATCHES and not matched:
            continue
        todo.append((0 if matched else 1, vid, code))
    todo.sort(key=lambda t: t[0])  # videos that already look relevant go first

    batch = todo[:TRANSCRIPTS_PER_RUN] if TRANSCRIPTS_PER_RUN else todo
    print(f"[Stage 3] {len(todo)} transcripts pending; fetching {len(batch)} this run")

    for n, (_, vid, code) in enumerate(batch, 1):
        print(f"  {n}/{len(batch)}  {vid}")
        try:
            transcript = fetch_transcript_for(vid, code)
        except Exception as e:
            if is_blocked(e):
                print("  Blocked (429). Stopping. Wait a few hours (or switch connection) and rerun.")
                return False
            append_jsonl(TRANSCRIPTS_FILE, {"id": vid, "status": "error", "error": str(e)})
        else:
            append_jsonl(TRANSCRIPTS_FILE, {"id": vid, "status": "ok" if transcript else "none",
                                            "transcript": transcript})
        if n < len(batch):
            if n % REST_EVERY == 0:
                print(f"  Resting {REST_SECONDS}s...")
                time.sleep(REST_SECONDS)
            else:
                pause(TRANSCRIPT_DELAY)

    remaining = len(todo) - len(batch)
    if remaining > 0:
        print(f"  {remaining} transcripts still pending. Rerun later to continue.")
    return True


# ---------- REPORTS ----------
def report():
    details = {r["id"]: r for r in load_jsonl(DETAILS_FILE) if is_valid_detail(r)}
    searches = {r["code"]: r for r in load_jsonl(SEARCH_FILE)}
    transcripts = load_transcripts()

    cols = ["country", "code", "search_term", "rank", "relevant", "matched_terms",
            "title", "channel", "channel_id", "channel_url", "url", "upload_date",
            "duration_sec", "views", "likes", "comments", "language", "tags",
            "description", "transcript_status", "transcript_available", "transcript"]
    total = relevant_total = pending_total = 0

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f, \
            open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as cf:
        writer = csv.DictWriter(cf, fieldnames=cols)
        writer.writeheader()
        f.write(f'YouTube search results for: "{KEYWORD}"\n')
        f.write("Relevant = title, description, tags or transcript contains a match term.\n")
        f.write("Relevant videos are shown in full; the rest are one-liners.\n")
        f.write("Transcript status: ok = found, none = no captions, pending = not fetched yet.\n")
        f.write("=" * 70 + "\n\n")

        for code, country in COUNTRIES.items():
            rec = searches.get(code)
            if not rec:
                continue
            terms = match_terms(code)

            rows = []  # (rank, details, matched, status, transcript)
            for rank, v in enumerate(rec["videos"], 1):
                d = details.get(v["id"])
                if not d:
                    continue  # metadata not fetched yet
                status, transcript = transcripts.get(v["id"], ("pending", None))
                text = " ".join([d.get("title") or "", d.get("description") or "",
                                 " ".join(d.get("tags") or []), transcript or ""])
                rows.append((rank, d, find_matches(text, terms), status, transcript))

            n_rel = sum(1 for r in rows if r[2])
            f.write(f"{'#' * 70}\n# {country} ({code})\n{'#' * 70}\n")
            f.write(f"  Search term: {rec['term']}\n")
            f.write(f"  Searched: {len(rec['videos'])}   Fetched: {len(rows)}   "
                    f"Relevant: {n_rel}\n\n")

            for rank, d, matched, status, transcript in rows:
                if matched:
                    f.write(f"  #{rank}  [RELEVANT] {d.get('title')}\n")
                    f.write(f"     Channel:  {d.get('channel')}\n")
                    f.write(f"     URL:      {d.get('url')}\n")
                    f.write(f"     Uploaded: {d.get('upload_date') or 'N/A'}   "
                            f"Duration: {d.get('duration_sec') or 'N/A'}s\n")
                    f.write(f"     Views:    {fmt(d.get('views'))}\n")
                    f.write(f"     Likes:    {fmt(d.get('likes'))}\n")
                    f.write(f"     Comments: {fmt(d.get('comments'))}\n")
                    f.write(f"     Matched:  {', '.join(matched)}\n")
                    f.write("     Transcript:\n")
                    if transcript:
                        f.write(textwrap.fill(transcript, width=90,
                                              initial_indent="       ",
                                              subsequent_indent="       ") + "\n")
                    elif status == "none":
                        f.write("       (no captions available)\n")
                    else:
                        f.write("       (pending: not fetched yet)\n")
                    f.write("\n")
                else:
                    f.write(f"  #{rank}  [not relevant] {d.get('title')} | "
                            f"{fmt(d.get('views'))} views | {d.get('url')}\n")

                writer.writerow({
                    "country": country, "code": code, "search_term": rec["term"],
                    "rank": rank, "relevant": "yes" if matched else "no",
                    "matched_terms": "; ".join(matched),
                    "title": d.get("title"), "channel": d.get("channel"),
                    "channel_id": d.get("channel_id"), "channel_url": d.get("channel_url"),
                    "url": d.get("url"), "upload_date": d.get("upload_date"),
                    "duration_sec": d.get("duration_sec"), "views": d.get("views"),
                    "likes": d.get("likes"), "comments": d.get("comments"),
                    "language": d.get("language"),
                    "tags": "; ".join(d.get("tags") or []),
                    "description": (d.get("description") or "")[:1000],
                    "transcript_status": status,
                    "transcript_available": "yes" if transcript else "no",
                    "transcript": transcript or "",
                })
                total += 1
                relevant_total += 1 if matched else 0
                pending_total += 1 if status == "pending" else 0
            f.write("\n")

    print(f"Reports written: {OUTPUT_TXT.name} and {OUTPUT_CSV.name} "
          f"({total} videos, {relevant_total} relevant, {pending_total} transcripts pending)")


def main():
    ok = True
    if ok and "search" in STAGES:
        ok = stage1()
    if ok and "details" in STAGES:
        ok = stage2()
    if ok and "transcripts" in STAGES:
        stage3()
    report()


if __name__ == "__main__":
    main()