"""Offline configurable disaster relevance classification and manual review. Python 3.10+."""
import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from filters import assess
from scraper import csv_out, load, read_profile, output_folder, DEFAULT_PROFILE, DEFAULT_LIMIT

BASE = Path(__file__).resolve().parent

_ARABIC_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه", "ـ": ""})
NON_EVENT = ['what is a', 'what are', 'how do', 'how does', 'how to', 'explained', 'simulation', 'science experiment', 'warning issued', 'could happen', 'prediction', 'anniversary', 'compilation', 'top 10']
GENERIC_OFFTOPIC = ['music video','lyric video','song lyrics','video game','gameplay','karaoke']

PARSED = ['parsed_decision','parsed_reason','parsed_title_hit','parsed_meta_hit',
          'parsed_transcript_hit','parsed_context','parsed_related','parsed_offtopic','parsed_human',
          'parsed_flags','parsed_comment_hit','parsed_non_event','parsed_seen_in_countries','manual_decision','manual_notes','event_country','event_date','event_id',
          'final_decision','age_days','views_per_day','likes_per_1000_views','comments_per_1000_views']

def normalize(t):
    # Remove accents for Latin scripts only; preserve marks in Indic and other scripts.
    t=unicodedata.normalize('NFD',str(t or '').casefold()).translate(_ARABIC_MAP)
    out=[]; latin=False
    for c in t:
        if not unicodedata.combining(c):
            latin='LATIN' in unicodedata.name(c,''); out.append(c)
        elif not latin: out.append(c)
    t=unicodedata.normalize('NFC',''.join(out))
    t=re.sub(r'[\u064b-\u065f\u0670]','',t)
    t=re.sub(r'(?<![\u0621-\u064A])ال(?=[\u0621-\u064A]{3,})','',t)
    return re.sub(r'\s+',' ',t).strip()

def hits(text, terms):
    out=[]
    for raw in terms:
        t=normalize(raw)
        if not t: continue
        # Short Latin words need a boundary; keep longer stems and non-Latin terms.
        if t.isascii() and t.isalpha() and len(t)<=4:
            found=bool(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',text))
        else: found=t in text
        if found and raw not in out: out.append(raw)
    return out

def classify(row, profile):
    terms=profile.get('terms',{})
    lang=row.get('requested_language') or row.get('search_language') or 'en'
    aliases={'he':'iw','zh-TW':'zh'}
    local=[terms.get('en',{})]
    for code in dict.fromkeys([lang,aliases.get(lang,lang),row.get('language') or '',row.get('transcript_language') or '']):
        if code!='en' and code in terms: local.append(terms[code])
    match_terms=list(dict.fromkeys([profile['keyword'],row.get('search_term') or '',*profile['translations'].values(),
        *(t for block in terms.values() for t in block.get('match',[]))]))
    title=normalize((row.get('title') or '')+' '+(row.get('search_title') or ''))
    meta=normalize(' '.join(row.get(k) or '' for k in ('description','tags')))
    transcript=normalize(row.get('transcript')); all_text=' '.join((title,meta,transcript))
    th,mh,xh=(hits(t,match_terms) for t in (title,meta,transcript))
    evidence={k:hits(all_text,[t for b in local for t in b.get(k,[])]) for k in ('context','related','offtopic','human')}
    off_title=hits(title,GENERIC_OFFTOPIC+[t for b in local for t in b.get('offtopic',[])])
    non_event=hits(title,NON_EVENT+[t for b in local for t in b.get('non_event',[])])
    comment_hit=hits(normalize(row.get('comment_text')),match_terms)
    flags=[]
    if len(meta)<40: flags.append('thin_metadata')
    if row.get('metadata_status') not in (None,'','ok'): flags.append('metadata_incomplete')
    if not row.get('transcript'): flags.append('no_transcript')
    if lang!='en' and lang not in terms and aliases.get(lang) not in terms: flags.append('limited_language_rules')
    screen, screen_reason=assess(row,profile)
    if screen=='reject':
        decision,reason='toss',screen_reason
    elif screen=='review':
        decision,reason='review',screen_reason
    elif off_title and not evidence['context'] and not xh:
        decision,reason='toss','off-topic title without supporting disaster context'
    elif non_event:
        decision,reason='review','possible educational, historical, prediction or compilation content'
    elif off_title or evidence['offtopic'] or evidence['human']:
        decision,reason='review','mixed evidence or possible human cause'
    elif th and evidence['context'] and 'metadata_incomplete' not in flags:
        decision,reason='keep','topic in title and disaster context; provisional event relevance'
    elif th or mh or xh or evidence['related'] or comment_hit:
        decision,reason='review','possible relevant event; evidence insufficient for automatic keep'
    else:
        decision,reason='review','no recognized topic term; language or metadata may be incomplete'
    return dict(parsed_decision=decision,parsed_reason=reason,parsed_title_hit='; '.join(th),
        parsed_meta_hit='; '.join(mh),parsed_transcript_hit='; '.join(xh),parsed_flags='; '.join(flags),
        parsed_comment_hit='; '.join(comment_hit),parsed_non_event='; '.join(non_event),
        **{'parsed_'+k:'; '.join(v) for k,v in evidence.items()})


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f); return list(r.fieldnames or []),list(r)

def number(x):
    try:
        n=int(x); return n if n>=0 else None
    except (ValueError,TypeError): return None

def metrics(r):
    v,l,c=(number(r.get(k)) for k in ('views','likes','comments'))
    age=None
    try:
        collected=datetime.fromisoformat((r.get('views_collected_at') or r['collected_at']).replace('Z','+00:00')).date()
        uploaded=datetime.fromisoformat(r['upload_date']).date()
        if collected>=uploaded: age=(collected-uploaded).days
    except (ValueError,TypeError,KeyError): pass
    return dict(age_days=age,views_per_day=round(v/max(age,1),3) if v is not None and age is not None else None,
        likes_per_1000_views=round(1000*l/v,3) if v and l is not None else None,
        comments_per_1000_views=round(1000*c/v,3) if v and c is not None else None)

def video_key(r):
    return r.get('video_id') or r.get('url') or ''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path)
    p.add_argument('--profile',type=Path,help='Classification rules; default saved collection profile')
    p.add_argument('--limit',type=int,default=DEFAULT_LIMIT,help='Used only to locate default input')
    p.add_argument('--strict',action='store_true',help='Only include manually approved videos in kept.csv')
    a=p.parse_args()
    if a.input is None:
        a.input=output_folder(read_profile(a.profile or DEFAULT_PROFILE),a.limit)/'results.csv'
    folder=a.input.resolve().parent
    manifest=load(folder/'manifest.json',{})
    profile=read_profile(a.profile) if a.profile else manifest.get('profile') or read_profile(DEFAULT_PROFILE)
    if manifest and profile['keyword'] != manifest['profile']['keyword']: p.error('Profile keyword differs from the collected keyword')
    if not a.input.exists(): p.error(f'No input CSV: {a.input}')
    fields,rows=read(a.input)
    # Include screened-out and deferred candidates for transparent classification/manual review.
    # Untouched candidates are not part of the analyzed sample.
    raw_path=folder/'raw_candidates.csv'
    if a.input.name=='results.csv' and raw_path.exists():
        _,raw_rows=read(raw_path)
        rows.extend(r for r in raw_rows if r.get('candidate_status') in ('excluded','deferred'))
    if a.input.name=='raw_candidates.csv':
        rows=[r for r in rows if r.get('candidate_status')!='not_examined']
    if any(r.get('keyword') and r['keyword']!=profile['keyword'] for r in rows): p.error('Input contains a different keyword; supply matching profile')
    full=load(folder/'state.json',{}).get('details',{}) if a.input.name in ('results.csv','raw_candidates.csv') else {}
    if not {'title','url','code'}.issubset(fields): p.error('Expected title, url and code columns')
    decisions_path=folder/'decisions.csv'
    manual={}
    if decisions_path.exists():
        _,existing=read(decisions_path)
        for r in existing:
            k=video_key(r); d=(r.get('manual_decision') or '').strip().lower()
            if not k or d not in ('','keep','review','toss'): p.error('Invalid video key or manual_decision in decisions.csv')
            if k in manual: p.error('Duplicate video key in decisions.csv')
            manual[k]=r
    countries=defaultdict(set); grouped=defaultdict(list)
    for i,r in enumerate(rows):
        k=video_key(r)
        if not k: p.error(f'Row {i+2} has no video ID or URL')
        countries[k].add(r['code']); grouped[k].append(r)
        evidence_row=dict(r)
        for field in ('description','transcript','comment_text'):
            if full.get(k,{}).get(field): evidence_row[field]=full[k][field]
        r.update(classify(evidence_row,profile)); r.update(metrics(r))
    review=[]; decisions=[]; kept=[]; summary=[]
    for k,group in grouped.items():
        # Use a single consistent decision per video across all regional appearances.
        suggestions={r['parsed_decision'] for r in group}
        auto=next(iter(suggestions)) if len(suggestions)==1 else 'review'
        m=manual.get(k,{})
        d=(m.get('manual_decision') or '').strip().lower()
        final=d or ('review' if a.strict and auto=='keep' else auto)
        r0=group[0]
        entry=dict(video_id=r0.get('video_id') or k,url=r0.get('url'),title=r0.get('title'),
            countries='; '.join(sorted(countries[k])),views=r0.get('views'),
            suggested_decision=auto,suggested_reason='; '.join(dict.fromkeys(r['parsed_reason'] for r in group)),
            manual_decision=d,manual_notes=m.get('manual_notes',''),event_country=m.get('event_country',r0.get('event_country','')),event_date=m.get('event_date',r0.get('event_date','')),event_id=m.get('event_id',r0.get('event_id','')),
            description_snippet=(r0.get('description') or '')[:500])
        decisions.append(entry)
        if final=='review': review.append(entry)
        for r in group:
            r.update(parsed_seen_in_countries=len(countries[k]),manual_decision=d,manual_notes=entry['manual_notes'],
                event_country=entry['event_country'],event_date=entry['event_date'],event_id=entry['event_id'],final_decision=final)
            if final=='keep': kept.append(r)
    # Preserve previous decisions if a smaller input is analyzed later.
    decisions.extend(m for k,m in manual.items() if k not in grouped)
    outfields=fields+[c for c in PARSED if c not in fields]
    csv_out(folder/'parsed.csv',outfields,rows)
    csv_out(folder/'kept.csv',outfields,kept)
    csv_out(folder/'kept_unique.csv',outfields,[g[0] for g in {k:[r for r in v if r['final_decision']=='keep'] for k,v in grouped.items()}.values() if g])
    review.sort(key=lambda r:number(r.get('views')) if number(r.get('views')) is not None else -1,reverse=True)
    decision_fields=['video_id','url','title','countries','views','suggested_decision','suggested_reason','manual_decision','manual_notes','event_country','event_date','event_id','description_snippet']
    csv_out(decisions_path,decision_fields,decisions)
    csv_out(folder/'review.csv',decision_fields,review)
    by_country=defaultdict(list)
    for r in rows: by_country[(r.get('country'),r['code'])].append(r)
    coverage_path=folder/'coverage.csv'
    if coverage_path.exists() and a.input.name=='results.csv':
        _,coverage=read(coverage_path)
        for r in coverage: by_country.setdefault((r.get('country'),r['code']),[])
    for (country,code),rs in by_country.items():
        good=[r for r in rs if r['final_decision']=='keep']
        s=dict(keyword=profile['keyword'],country=country,code=code,rows=len(rs),keep=len(good),review=sum(r['final_decision']=='review' for r in rs),toss=sum(r['final_decision']=='toss' for r in rs))
        for col in ('views','likes','comments'):
            vals=[n for r in good if (n:=number(r.get(col))) is not None]
            s[col+'_known']=len(vals); s[col+'_sum']=sum(vals) if vals else None; s[col+'_median']=median(vals) if vals else None
        summary.append(s)
    csv_out(folder/'summary.csv',['keyword','country','code','rows','keep','review','toss',*[c+'_'+suffix for c in ('views','likes','comments') for suffix in ('known','sum','median')]],summary)
    print(f'{len(rows)} regional rows; {len(grouped)} unique videos; {len(kept)} kept rows; {len(review)} unique videos to review.')
    print(f'Edit manual_decision in {decisions_path.name} (keep/review/toss), save, and rerun.')

if __name__=='__main__': main()
