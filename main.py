import json
import textwrap
import time
import urllib.request

import yt_dlp

# ---------- SETTINGS ----------
KEYWORD = "markiplier"
RESULTS_PER_COUNTRY = 5
GET_TRANSCRIPTS = True
OUTPUT_FILE = "C:/Users/zanma/scrapper_resilts/results.txt"
DELAY_SECONDS = 1  # pause between requests to avoid rate limiting

# Optional: real per-country proxies, e.g. {"DE": "http://user:pass@host:port"}
PROXIES = {}

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

video_cache = {}  # video id -> details, so repeat videos aren't re-fetched


def make_opts(code, flat=False):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "geo_bypass_country": code,
    }
    if code in PROXIES:
        opts["proxy"] = PROXIES[code]
    if flat:
        opts["extract_flat"] = True
    return opts


def search_ids(code):
    query = f"ytsearch{RESULTS_PER_COUNTRY}:{KEYWORD}"
    with yt_dlp.YoutubeDL(make_opts(code, flat=True)) as ydl:
        info = ydl.extract_info(query, download=False)
    return [e["id"] for e in info.get("entries", []) if e.get("id")]


def fetch_transcript(info):
    """Try manual subs first, then auto captions; video's language, then English."""
    langs = [l for l in (info.get("language"), "en") if l]
    for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang in langs:
            key = next((k for k in source if k == lang or k.startswith(lang + "-")), None)
            if not key:
                continue
            fmt = next((f for f in source[key] if f.get("ext") == "json3"), None)
            if not fmt:
                continue
            try:
                with urllib.request.urlopen(fmt["url"], timeout=20) as r:
                    data = json.load(r)
                text = " ".join(
                    seg.get("utf8", "")
                    for ev in data.get("events", [])
                    for seg in ev.get("segs", [])
                ).replace("\n", " ")
                return " ".join(text.split())
            except Exception:
                continue
    return None


def get_video(code, vid):
    if vid in video_cache:
        return video_cache[vid]
    url = f"https://www.youtube.com/watch?v={vid}"
    with yt_dlp.YoutubeDL(make_opts(code)) as ydl:
        info = ydl.extract_info(url, download=False)
    details = {
        "title": info.get("title"),
        "channel": info.get("uploader"),
        "url": url,
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "transcript": fetch_transcript(info) if GET_TRANSCRIPTS else None,
    }
    video_cache[vid] = details
    return details


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else "N/A"


def main():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'YouTube search results for: "{KEYWORD}"\n')
        f.write("=" * 70 + "\n\n")

        for code, country in COUNTRIES.items():
            print(f"Searching {country} ({code})...")
            f.write(f"{'#' * 70}\n# {country} ({code})\n{'#' * 70}\n\n")
            try:
                ids = search_ids(code)
            except Exception as e:
                f.write(f"  Search failed: {e}\n\n")
                continue

            for i, vid in enumerate(ids, 1):
                try:
                    v = get_video(code, vid)
                except Exception as e:
                    f.write(f"  {i}. [{vid}] failed: {e}\n\n")
                    continue
                f.write(f"  {i}. {v['title']}\n")
                f.write(f"     Channel:  {v['channel']}\n")
                f.write(f"     URL:      {v['url']}\n")
                f.write(f"     Views:    {fmt(v['views'])}\n")
                f.write(f"     Likes:    {fmt(v['likes'])}\n")
                f.write(f"     Comments: {fmt(v['comments'])}\n")
                if GET_TRANSCRIPTS:
                    f.write("     Transcript:\n")
                    if v["transcript"]:
                        f.write(textwrap.fill(v["transcript"], width=90,
                                              initial_indent="       ",
                                              subsequent_indent="       ") + "\n")
                    else:
                        f.write("       (not available)\n")
                f.write("\n")
                time.sleep(DELAY_SECONDS)
            f.flush()

    print(f"Done. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()