"""Offline integration tests using simulated library responses; no network."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj, ModuleType
from unittest.mock import patch
import scraper
import analyze


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))


class FakeYT:
    searches=[]
    def __init__(self,region,language,timeout): self.region=region
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def search(self,term,**kwargs):
        self.searches.append((self.region,term))
        return [Obj(video_id='abcdefghijk',title='Massive landslide after heavy rain',channel='News',channel_id='UC1',duration='1:20',views=1000,views_text='1K')]
    def transcript(self,vid,**kwargs): return Obj(text='Heavy rain caused a landslide.',language_code='en',is_generated=True)
    def comments(self,vid,**kwargs): return [Obj(text='landslide in town')]


class FakeDLP:
    calls=0
    def __init__(self,*args): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def extract_info(self,url,download):
        type(self).calls+=1
        return {'title':'Massive landslide after heavy rain','description':'Heavy rain caused a landslide and blocked the road.','view_count':2000,'like_count':0,'comment_count':None,'upload_date':'20260102','duration':80}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.folder=Path(self.tmp.name)
        FakeYT.searches=[]; FakeDLP.calls=0
        yt=ModuleType('ytscrape'); yt.YouTube=FakeYT; yt.SearchFilter=Obj(VIDEOS='videos')
        dlp=ModuleType('yt_dlp'); dlp.YoutubeDL=FakeDLP
        self.p=patch.dict(sys.modules,{'ytscrape':yt,'yt_dlp':dlp}); self.p.start()
        self.sleep=patch('scraper.time.sleep'); self.sleep.start()
    def tearDown(self): self.p.stop(); self.sleep.stop(); self.tmp.cleanup()
    def collect(self,*codes):
        with patch.object(sys,'argv',['scraper.py','--countries',*codes,'--limit','5','--comment-sample','2','--output',str(self.folder)]): return scraper.main()
    def parse(self):
        with patch.object(sys,'argv',['analyze.py','--input',str(self.folder/'results.csv')]): analyze.main()
    def test_pipeline_resume_manual(self):
        self.assertEqual(self.collect('CA','JP'),0)
        self.assertEqual(FakeYT.searches,[('CA','landslide natural disaster'),('JP','土砂崩れ 自然災害')]); self.assertEqual(FakeDLP.calls,1)
        rows=read(self.folder/'results.csv'); self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['likes'],'0'); self.assertEqual(rows[0]['comments'],'')
        self.assertEqual(rows[0]['comment_sample_count'],'1'); self.assertEqual(rows[0]['transcript_status'],'ok')
        self.collect('CA','JP'); self.assertEqual(FakeDLP.calls,1); self.assertEqual(len(FakeYT.searches),2)
        self.parse(); self.assertEqual(len(read(self.folder/'kept.csv')),2); self.assertEqual(len(read(self.folder/'kept_unique.csv')),1)
        p=self.folder/'decisions.csv'; rows=read(p); rows[0]['manual_decision']='toss'; rows[0]['event_country']='JP'
        scraper.csv_out(p,list(rows[0]),rows); self.parse(); self.assertEqual(len(read(self.folder/'kept.csv')),0)
        self.assertEqual(read(self.folder/'parsed.csv')[1]['event_country'],'JP')
    def test_block_stops_and_keeps_search(self):
        with patch.object(FakeDLP,'extract_info',side_effect=RuntimeError('HTTP Error 429: Too Many Requests')):
            self.assertEqual(self.collect('CA','JP'),1)
        self.assertEqual(len(FakeYT.searches),1)
        rows=read(self.folder/'results.csv'); self.assertEqual(rows[0]['metadata_status'],'pending'); self.assertEqual(rows[0]['views_source'],'search (possibly rounded)')
        self.assertEqual(read(self.folder/'coverage.csv')[1]['status'],'pending')
    def test_screen_and_fill_from_later_ranks(self):
        def search(self,term,**kwargs):
            self.searches.append((self.region,term))
            self.asserted_limit=kwargs['max_results']
            titles=['Fleetwood Mac - Landslide','The Chicks - Landslide','Landslide (2004 Remaster)',
                    'Top 10 landslides','Landslide after heavy rain','Landslide blocks road',
                    'Landslide destroys home','Landslide struck village','Landslide after rain','Landslide at hillside']
            return [Obj(video_id=f'video{i:06d}',title=t,channel='News',channel_id='UC1',duration='1:20',views=1000,views_text='1K') for i,t in enumerate(titles)]
        with patch.object(FakeYT,'search',search):
            self.assertEqual(self.collect('CA'),0)
        raw=read(self.folder/'raw_candidates.csv')
        self.assertEqual(len(raw),10)
        self.assertEqual(FakeDLP.calls,5)
        self.assertEqual([r['candidate_status'] for r in raw],['excluded']*3+['deferred']+['selected']*5+['not_examined'])
        self.assertEqual([r['rank'] for r in read(self.folder/'results.csv')],['5','6','7','8','9'])
        self.parse()
        self.assertEqual(len(read(self.folder/'parsed.csv')),9)
        self.assertEqual(sum(r['final_decision']=='toss' for r in read(self.folder/'parsed.csv')),3)
        self.assertEqual(len(read(self.folder/'review.csv')),1)
    def test_profiles_and_music(self):
        countries=scraper.load(scraper.BASE/'countries.json')
        languages={c['language'] for c in countries.values()}
        for name in ('landslide','earthquake','tsunami','flood','hurricane'):
            p=scraper.read_profile(scraper.BASE/(name+'.json'))
            self.assertEqual(set(p['search_terms']),languages)
            self.assertEqual(analyze.classify({'title':name+' music video','category':'Music'},p)['parsed_decision'],'toss')
        p=scraper.read_profile(scraper.DEFAULT_PROFILE)
        self.assertEqual(analyze.classify({'title':'Fleetwood Mac - Landslide','category':'Music','transcript':'landslide after heavy rain'},p)['parsed_decision'],'toss')
        self.assertEqual(analyze.classify({'title':'地滑り15選','requested_language':'ja'},p)['parsed_decision'],'review')
    def test_profile_switch(self):
        p=scraper.read_profile(scraper.BASE/'earthquake_example.json')
        self.assertEqual(scraper.settings(p,{'language':'ja'})['search_term'],'地震')
        self.assertEqual(analyze.classify({'title':'Earthquake struck town','description':'Damage reported','search_language':'en'},p)['parsed_decision'],'keep')
        self.assertEqual(analyze.classify({'title':'Massive landslide after heavy rain','search_language':'en'},p)['parsed_decision'],'review')
        self.assertEqual(analyze.classify({'title':'Earthquake music video','search_language':'en'},p)['parsed_decision'],'toss')
        self.assertEqual(analyze.classify({'title':'How do earthquakes happen?','search_language':'en'},p)['parsed_decision'],'review')

if __name__=='__main__': unittest.main()
