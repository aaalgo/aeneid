import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
import server
from models import Base, Work, Card, Line, Annotation, InterlinearGloss

class GlossTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.tmp.name)/'test.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.old = server.SessionLocal
        server.SessionLocal = self.factory
        server.app.config['TESTING'] = True
        self.calls = []
        server.app.config['GLOSS_GENERATOR'] = self.provider
        with self.factory.begin() as s:
            s.add(Work(id=1,title='Aeneid',author='Virgil'))
            s.add(Card(id=1,work_id=1,book=1,number=1,latin_start=1,latin_end=8,english='Reference'))
            for n in range(1,12):
                s.add(Line(id=n,work_id=1,book=1,number=n,latin='Arma virumque cano, Troiae!'))
            s.add(Annotation(line_id=1,data={'original':True},model='old'))
        self.client = server.app.test_client()
    def tearDown(self):
        server.SessionLocal = self.old
        server.app.config.pop('GLOSS_GENERATOR',None)
        self.engine.dispose()
        self.tmp.cleanup()
    def provider(self,ctx,model):
        self.calls.append(copy.deepcopy(ctx))
        return {'lines':[{'number':t['number'],'gloss':[{**tok,'english':'word'} for tok in t['tokens']]} for t in ctx['target_lines']]}
    def post(self,**kw):
        return self.client.post('/api/gloss',json={'work_id':1,'book':1,'start':1,'end':8,**kw})
    def seed(self,numbers,invalid=False):
        with self.factory.begin() as s:
            for n in numbers:
                s.add(InterlinearGloss(line_id=n,model='older',prompt_version=99,data=[] if invalid else [{**t,'english':'cached'} for t in server.tokenize_latin('Arma virumque cano, Troiae!')]))
    def test_missing_repeat_annotation_and_context(self):
        r=self.post();self.assertEqual(r.status_code,200)
        self.assertTrue(all(not l['cached'] for l in r.json['lines']))
        self.assertEqual(len(self.calls),1)
        self.assertEqual([x['number'] for x in self.calls[0]['latin_context']],list(range(1,12)))
        self.assertEqual(self.calls[0]['english_reference'][0]['english'],'Reference')
        r=self.post();self.assertTrue(all(l['cached'] for l in r.json['lines']))
        self.assertEqual(len(self.calls),1)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(Annotation)).data,{'original':True})
            self.assertEqual(s.scalar(select(func.count()).select_from(InterlinearGloss)),8)
    def test_cache_patterns(self):
        for cached in [list(range(1,9)),[1,8],[1,3,5,7]]:
            with self.subTest(cached=cached):
                with self.factory.begin() as s:s.query(InterlinearGloss).delete()
                self.calls.clear();self.seed(cached)
                r=self.post();self.assertEqual(r.status_code,200)
                self.assertEqual([l['number'] for l in r.json['lines'] if l['cached']],cached)
                if len(cached)==8:self.assertEqual(self.calls,[])
                else:self.assertEqual([t['number'] for t in self.calls[0]['target_lines']],[n for n in range(1,9) if n not in cached])
    def test_invalid_cache_repaired(self):
        self.seed([1],invalid=True)
        self.assertEqual(self.post().status_code,200)
    def test_validation_failures_atomic(self):
        def bad_token(r):r['lines'][0]['gloss'][0]['token']='fake'
        def bad_index(r):r['lines'][0]['gloss'][0]['index']=True
        def empty(r):r['lines'][0]['gloss'][0]['english']=' '
        def duplicate(r):r['lines'][1]=r['lines'][0]
        def missing(r):r['lines'].pop()
        def reorder(r):r['lines'][0]['gloss'].reverse()
        def unexpected(r):r['lines'][0]['number']=99
        for corrupt in [bad_token,bad_index,empty,duplicate,missing,reorder,unexpected]:
            def provider(ctx,model):
                result=self.provider(ctx,model);corrupt(result);return result
            server.app.config['GLOSS_GENERATOR']=provider
            self.assertEqual(self.post().status_code,502)
        with self.factory() as s:self.assertEqual(s.scalar(select(func.count()).select_from(InterlinearGloss)),0)
    def test_bad_ranges_and_missing(self):
        for kw in [{'start':0},{'end':0},{'start':9,'end':8},{'end':31},{'start':True},{'book':'1'},{'work_id':None}]:
            self.assertEqual(self.post(**kw).status_code,400)
        for payload in [[],None,'bad']:
            self.assertEqual(self.client.post('/api/gloss',json=payload).status_code,400)
        for kw in [{'work_id':9},{'book':9},{'end':12}]:self.assertEqual(self.post(**kw).status_code,404)
        with self.factory.begin() as s:s.delete(s.get(Line,4))
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.calls,[])
    def test_unavailable(self):
        def unavailable(*args):raise server.GlossUnavailable()
        server.app.config['GLOSS_GENERATOR']=unavailable
        self.assertEqual(self.post().status_code,503)
    def test_no_reference(self):
        with self.factory.begin() as s:s.query(Card).delete()
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.calls[0]['english_reference'],[])
    def test_existing_endpoints(self):
        for url in ['/api/health','/api/works','/api/works/1','/api/works/1/books/1/cards','/api/cards/1','/api/lines/1']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertEqual(set(self.client.get('/api/lines/1').json),{'id','work_id','book','number','latin','annotation','morphology'})
        self.assertEqual(self.calls,[])
    def test_overlap(self):
        barrier=Barrier(2)
        def provider(ctx,model):
            barrier.wait(timeout=5)
            return self.provider(ctx,model)
        server.app.config['GLOSS_GENERATOR']=provider
        def call(end):
            with server.app.test_client() as client:return client.post('/api/gloss',json={'work_id':1,'book':1,'start':1,'end':end}).status_code
        with ThreadPoolExecutor(2) as pool:self.assertEqual(list(pool.map(call,[7,8])),[200,200])
        with self.factory() as s:self.assertEqual(s.scalar(select(func.count()).select_from(InterlinearGloss)),8)
    def test_tokens(self):
        self.assertEqual([x['token'] for x in server.tokenize_latin("Arma, virumque; mene' l’ora — Troiae! a\u0304rma")],['Arma','virumque',"mene'",'l’ora','Troiae','a\u0304rma'])

if __name__=='__main__':unittest.main()
