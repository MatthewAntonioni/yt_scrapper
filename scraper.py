"""Collect regional YouTube search results and metadata; no official Data API."""
import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from filters import assess

BASE = Path(__file__).resolve().parent
DEFAULT_PROFILE = BASE / 'landslide.json'
DEFAULT_LIMIT = 10
DELAY = 3.0
FIELDS = '''platform keyword country code search_language requested_language translation_status search_term rank video_id url search_title title channel channel_id channel_url channel_country channel_subscribers upload_date duration_sec views likes comments search_views search_views_text views_source views_collected_at description tags category language transcript transcript_language transcript_generated transcript_status transcript_error comment_text comment_sample_count comment_status comment_error searched_at collected_at metadata_source metadata_status metadata_error missing_metrics event_country candidate_status candidate_reason'''.split()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def save(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def csv_out(path, fields, rows):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            # Prevent spreadsheet formulas embedded in public text. JSON keeps originals.
            w.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
    tmp.replace(path)


def number(x):
    try:
        n = int(x)
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None


def duration(x):
    try:
        if isinstance(x, int): return x
        n = 0
        for part in x.split(':'): n = n * 60 + int(part)
        return n
    except (AttributeError, ValueError): return None


def text_list(x):
    return x if isinstance(x, str) else '; '.join(map(str, x or []))


def settings(profile, country):
    lang = country['language']
    translations = profile['translations']
    term = profile.get('search_terms', {}).get(lang, translations.get(lang, profile['keyword']))
    return {'requested_language': lang, 'search_language': {'iw':'he','zh-TW':'zh', 'mt': 'en'}.get(lang,lang), 'search_term': term, 'translation_status': 'original' if lang=='en' else ('translated' if lang in translations else 'fallback_english_keyword')}


def read_profile(path):
    p = load(path)
    if not isinstance(p, dict) or not isinstance(p.get('keyword'), str) or not p['keyword'].strip():
        raise ValueError('Profile needs a nonempty keyword.')
    if not isinstance(p.get('translations'), dict) or any(not isinstance(t,str) or not t.strip() for t in p['translations'].values()):
        raise ValueError('translations must map language codes to nonempty text.')
    if not isinstance(p.get('search_terms', {}), dict) or any(not isinstance(t,str) or not t.strip() for t in p.get('search_terms', {}).values()):
        raise ValueError('search_terms must map language codes to nonempty text.')
    if not isinstance(p.get('terms', {}), dict): raise ValueError('terms must be a dictionary.')
    for block in p.get('terms', {}).values():
        if not isinstance(block,dict) or any(not isinstance(v,list) or any(not isinstance(t,str) for t in v) for v in block.values()):
            raise ValueError('Each language in terms must contain lists of strings.')
    return p


def output_folder(profile, limit):
    slug = re.sub(r'[^a-z0-9_-]+', '_', profile['keyword'].casefold()).strip('_-') or 'keyword'
    return BASE / 'research_data' / f'{slug}_{limit}_v2'


class StopCollection(Exception): pass


def blocked(exc):
    s = str(exc).lower().replace('’', "'")
    return (type(exc).__name__ in {'RateLimited','BotDetected','CaptchaRequired','ConsentRequired','ContextExtractionError'}
            or getattr(exc, 'status_code', None) in (401,403,429)
            or any(x in s for x in ('429','403 forbidden','too many requests','rate limit','captcha','not a bot','bot check','po-token','po token','consent wall','sign in to confirm','access denied','ip blocked')))


def ensure_not_blocked(exc):
    if blocked(exc): raise StopCollection(f'Access restricted: {exc}') from exc


def search_country(yt, term, limit):
    from ytscrape import SearchFilter
    hits, seen = [], set()
    for rank,v in enumerate(yt.search(term,filter=SearchFilter.VIDEOS,max_results=limit),1):
        vid = v.video_id
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid) or vid in seen: continue
        seen.add(vid)
        hits.append(dict(video_id=vid,rank=rank,search_title=v.title,title=v.title,channel=v.channel,
                         channel_id=v.channel_id,duration_sec=duration(v.duration),search_views=number(v.views),
                         search_views_text=v.views_text,url=f'https://www.youtube.com/watch?v={vid}'))
    return hits


def dlp_details(ydl, vid):
    d = ydl.extract_info('https://www.youtube.com/watch?v='+vid, download=False)
    if not d: raise RuntimeError('No metadata returned')
    date = d.get('upload_date') or ''
    if re.fullmatch(r'\d{8}',date): date = f'{date[:4]}-{date[4:6]}-{date[6:]}'
    stamp = now()
    return dict(title=d.get('title'),channel=d.get('channel') or d.get('uploader'),channel_id=d.get('channel_id'),
                channel_url=d.get('channel_url'),channel_subscribers=number(d.get('channel_follower_count')),
                upload_date=date,duration_sec=number(d.get('duration')),views=number(d.get('view_count')),
                likes=number(d.get('like_count')),comments=number(d.get('comment_count')),language=d.get('language'),
                description=d.get('description'),tags=text_list(d.get('tags')),category=text_list(d.get('categories')),
                collected_at=stamp,views_collected_at=stamp,views_source='yt-dlp',metadata_source='yt-dlp',metadata_status='ok')


def basic_details(yt, vid):
    d=yt.video(vid)
    stamp=now()
    return dict(title=d.title,channel=d.channel,channel_id=d.channel_id,channel_url=d.owner_profile_url,
                upload_date=d.upload_date or d.published,duration_sec=number(d.length_seconds),views=number(d.views),
                description=d.description,tags=text_list(d.keywords),category=d.category,collected_at=stamp,
                views_collected_at=stamp,views_source='ytscrape',metadata_source='ytscrape',metadata_status='partial')


def export(folder, manifest, state):
    rows,raw,coverage=[],[],[]
    for code in state['requested']:
        country=manifest['countries'][code]
        cfg=settings(manifest['profile'],country)
        s=state['searches'].get(code,{})
        hits=s.get('hits',[])
        complete=0
        for h in hits:
            d=state['details'].get(h['video_id'],{})
            row=dict(platform='youtube',keyword=manifest['profile']['keyword'],country=country['name'],code=code,**cfg,**h)
            row.update({k:v for k,v in d.items() if v is not None and v!=''})
            row['searched_at']=s.get('searched_at')
            row['metadata_status']=d.get('metadata_status','pending')
            if row.get('views') is None and row.get('search_views') is not None:
                row.update(views=row['search_views'],views_source='search (possibly rounded)',views_collected_at=s.get('searched_at'))
            row['missing_metrics']='; '.join(k for k in ('views','likes','comments') if row.get(k) is None)
            if row['metadata_status']=='ok': complete+=1
            # Excel cell limit: full text remains in state.json for analysis.
            for k in ('description','transcript','comment_text'):
                if isinstance(row.get(k),str): row[k]=row[k][:32000]
            row['candidate_status']=h.get('candidate_status','not_examined')
            row['candidate_reason']=h.get('candidate_reason','')
            raw.append(row)
            if row['candidate_status'] in ('selected','processing'): rows.append(row)
        coverage.append(dict(country=country['name'],code=code,**cfg,requested=manifest['limit'],returned=len(hits),
                             metadata_ok=complete,selected=sum(h.get('candidate_status')=='selected' for h in hits),excluded=sum(h.get('candidate_status')=='excluded' for h in hits),deferred=sum(h.get('candidate_status')=='deferred' for h in hits),candidate_limit=manifest['candidates'],unexamined=sum(not h.get('candidate_status') for h in hits),collection_finished=bool(s.get('finished')),status=s.get('status','pending'),error=s.get('error',''),searched_at=s.get('searched_at','')))
    csv_out(folder/'results.csv',FIELDS,rows)
    csv_out(folder/'raw_candidates.csv',FIELDS,raw)
    csv_out(folder/'coverage.csv','country code requested_language search_language translation_status search_term requested candidate_limit returned selected excluded deferred unexamined collection_finished metadata_ok status error searched_at'.split(),coverage)
    return len(rows)


def run(args, manifest, folder, state):
    from ytscrape import YouTube
    from yt_dlp import YoutubeDL
    opts={'quiet':True,'skip_download':True,'ignore_no_formats_error':True,'socket_timeout':30,
          'retries':0,'extractor_retries':0,'fragment_retries':0,'noplaylist':True,'sleep_interval_requests':1}
    def checkpoint(): save(folder/'state.json',state)
    with YoutubeDL(opts) as ydl:
        for code in args.countries:
            c=manifest['countries'][code]; cfg=settings(manifest['profile'],c)
            previous=state['searches'].get(code,{})
            if previous.get('status')=='ok' and previous.get('finished'):
                print(f"{c['name']}: cached",flush=True); continue
            print(f"{c['name']} ({code}): {cfg['search_term']}",flush=True)
            try:
                with YouTube(region=code,language=cfg['search_language'],timeout=30) as yt:
                    if previous.get('status')!='ok':
                        time.sleep(args.delay)
                        hits=search_country(yt,cfg['search_term'],manifest['candidates'])
                        state['searches'][code]=dict(status='ok',hits=hits,searched_at=now())
                        checkpoint()
                    for h in state['searches'][code]['hits']:
                        if sum(x.get('candidate_status')=='selected' for x in state['searches'][code]['hits']) >= manifest['limit']: break
                        if h.get('candidate_status') in ('selected','excluded','deferred'): continue
                        verdict, reason=assess(h,manifest['profile'])
                        if verdict!='eligible':
                            h.update(candidate_status='excluded' if verdict=='reject' else 'deferred',candidate_reason=reason); checkpoint(); continue
                        vid=h['video_id']; d=state['details'].setdefault(vid,{})
                        h['candidate_status']='processing'; checkpoint()
                        print(f"  #{h['rank']} {h['search_title']}",flush=True)
                        if not d.get('metadata_status'):
                            time.sleep(args.delay)
                            try: d.update(dlp_details(ydl,vid))
                            except Exception as e:
                                ensure_not_blocked(e)
                                d['metadata_error']=str(e)[:500]
                                # Do not try another backend after a restriction.
                                # Ordinary unavailable/format errors can retain search-only data.
                                if any(x in str(e).lower() for x in ('private video','age-restricted','age restricted','not available in your country','members-only','sign in')):
                                    d['metadata_status']='unavailable'
                                else:
                                    time.sleep(args.delay)
                                    try: d.update(basic_details(yt,vid))
                                    except Exception as e2:
                                        ensure_not_blocked(e2)
                                        d.update(metadata_status='failed',metadata_error=(str(e)+' | '+str(e2))[:700])
                            checkpoint()
                        verdict, reason=assess({**h,**d},manifest['profile'])
                        if verdict!='eligible' or d.get('metadata_status')=='unavailable':
                            h.update(candidate_status='excluded' if verdict=='reject' else 'deferred',candidate_reason=reason if verdict!='eligible' else 'video unavailable'); checkpoint(); continue
                        if not d.get('transcript_status'):
                            if not manifest['transcripts'] or d['metadata_status']=='unavailable': d['transcript_status']='skipped'
                            else:
                                time.sleep(args.delay)
                                try:
                                    langs=list(dict.fromkeys([x for x in (d.get('language'),cfg['requested_language'],cfg['search_language'],'en') if x]))
                                    t=yt.transcript(vid,languages=langs)
                                    d.update(transcript=t.text,transcript_language=t.language_code,transcript_generated=t.is_generated,transcript_status='ok')
                                except Exception as e:
                                    ensure_not_blocked(e); d['transcript_status']=type(e).__name__; d['transcript_error']=str(e)[:500]
                            checkpoint()
                        if not d.get('comment_status'):
                            if not manifest['comment_sample'] or d['metadata_status']=='unavailable': d['comment_status']='skipped'
                            else:
                                time.sleep(args.delay)
                                try:
                                    sample=[x.text for x in yt.comments(vid,max_results=manifest['comment_sample'],sort='top')]
                                    d.update(comment_text='\n'.join(sample),comment_sample_count=len(sample),comment_status='ok')
                                except Exception as e:
                                    ensure_not_blocked(e); d['comment_status']=type(e).__name__; d['comment_error']=str(e)[:500]
                            checkpoint()
                        d['done']=True
                        h.update(candidate_status='selected',candidate_reason='passed preliminary screen; final relevance not yet verified'); checkpoint()
                    state['searches'][code]['finished']=True; checkpoint()
            except StopCollection: raise
            except Exception as e:
                ensure_not_blocked(e)
                if state['searches'].get(code,{}).get('status')!='ok':
                    state['searches'][code]=dict(status='error',error=str(e)[:700],hits=[])
                checkpoint()
                # Unknown country/network/library failure: stop rather than repeat across 100 countries.
                raise StopCollection(f'Collection stopped at {code}: {e}') from e
            export(folder,manifest,state)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path,default=DEFAULT_PROFILE)
    p.add_argument('--countries',nargs='+',help='ISO codes; default all listed countries')
    p.add_argument('--limit',type=int,default=DEFAULT_LIMIT)
    p.add_argument('--candidates',type=int,help='Maximum candidate results per country; default 3 times target, capped at 100')
    p.add_argument('--output',type=Path)
    p.add_argument('--delay',type=float,default=DELAY)
    p.add_argument('--no-transcripts',action='store_true')
    p.add_argument('--comment-sample',type=int,default=0,help='Optional number of top-level comment texts per video (0 disables)')
    p.add_argument('--retry-incomplete',action='store_true',help='Retry ordinary failed/partial metadata and unavailable caption/comment fetches; never bypass blocks')
    p.add_argument('--export-only',action='store_true')
    a=p.parse_args()
    if not 1<=a.limit<=100 or not 0<=a.comment_sample<=100 or a.delay<1: p.error('limit 1–100, comment-sample 0–100, delay at least 1 second')
    a.candidates=a.candidates if a.candidates is not None else min(100,3*a.limit)
    if not a.limit<=a.candidates<=100: p.error('candidates must be between limit and 100')
    try: profile=read_profile(a.profile); countries=load(BASE/'countries.json')
    except (ValueError,OSError) as e: p.error(str(e))
    a.countries=list(dict.fromkeys(c.upper() for c in (a.countries or countries)))
    if any(c not in countries for c in a.countries): p.error('Unknown country code in --countries')
    folder=(a.output or output_folder(profile,a.limit)).resolve(); folder.mkdir(parents=True,exist_ok=True)
    manifest=dict(profile=profile,countries=countries,limit=a.limit,candidates=a.candidates,transcripts=not a.no_transcripts,comment_sample=a.comment_sample)
    old=load(folder/'manifest.json')
    if old is not None and old!=manifest: p.error('Settings differ from the saved run. Use a new --output folder or restore original settings.')
    save(folder/'manifest.json',manifest)
    state=load(folder/'state.json',{'requested':[],'searches':{},'details':{}})
    if not a.export_only:
        state['requested']=list(dict.fromkeys(state['requested']+a.countries))
        if a.retry_incomplete:
            for search in state['searches'].values():
                search.pop('finished',None)
                for h in search.get('hits',[]):
                    if h.get('candidate_status')=='selected' and any(state['details'].get(h['video_id'],{}).get(k) not in ('ok','skipped',None) for k in ('metadata_status','transcript_status','comment_status')):
                        h['candidate_status']='processing'
            for d in state['details'].values():
                if d.get('metadata_status') in ('partial','failed'):
                    for key in ('metadata_status','metadata_error','done'): d.pop(key,None)
                for k in ('transcript_status','comment_status'):
                    if d.get(k) not in ('ok','skipped',None): d.pop(k,None); d.pop('done',None)
    stopped=False
    try:
        if not a.export_only: run(a,manifest,folder,state)
    except (StopCollection,KeyboardInterrupt,ImportError) as e:
        print(f'Collection interrupted: {e or "keyboard interrupt"}. Saved progress; do not resume until access is permitted.',flush=True); stopped=True
    finally:
        save(folder/'state.json',state)
        n=export(folder,manifest,state)
        print(f'{n} regional result rows saved to {folder / "results.csv"}',flush=True)
    return 1 if stopped else 0


if __name__=='__main__': raise SystemExit(main())
