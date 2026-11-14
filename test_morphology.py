import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import server
from models import Base, Work, Card, Line, Morphology, Annotation


class MorphologyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patch = patch.object(server, 'SessionLocal', self.factory)
        self.patch.start()
        self.client = server.app.test_client()
        with self.factory.begin() as session:
            session.add(Work(id=1, title='Aeneid', author='Virgil'))
            for i in range(1, 4):
                session.add(Card(id=i, work_id=1, book=1, number=i,
                                 latin_start=1, latin_end=3, english='Translation'))
                session.add(Line(id=i, work_id=1, book=1, number=i, latin='Arma cano.'))
            session.add(Annotation(line_id=1, data={'original': True}, model='existing'))

    def tearDown(self):
        self.patch.stop()
        self.engine.dispose()

    def seed(self, ids):
        with self.factory.begin() as session:
            for i in ids:
                session.add(Morphology(line_id=i, data=[{'word': 'Arma', 'parse': f'analysis {i}'}]))

    def test_card_coverage_and_existing_fields(self):
        for ids in [[], [1, 3], [1, 2, 3]]:
            with self.subTest(ids=ids):
                with self.factory.begin() as session:
                    session.query(Morphology).delete()
                self.seed(ids)
                result = self.client.get('/api/cards/2').json
                self.assertEqual({k: v for k, v in result.items() if k != 'lines'}, {
                    'id': 2, 'work_id': 1, 'book': 1, 'number': 2,
                    'latin_start': 1, 'latin_end': 3, 'english': 'Translation', 'prev': 1, 'next': 3})
                for line in result['lines']:
                    i = line['id']
                    self.assertEqual(line['morphology'], [{'word': 'Arma', 'parse': f'analysis {i}'}] if i in ids else None)
                    self.assertEqual(line['latin'], 'Arma cano.')
                    self.assertEqual(line['number'], i)
                    self.assertEqual(set(line), {'id', 'number', 'latin', 'annotation', 'morphology'})
                self.assertEqual(result['lines'][0]['annotation']['data'], {'original': True})
                self.assertIsNone(result['lines'][1]['annotation'])
        self.assertIsNone(self.client.get('/api/cards/1').json['prev'])
        self.assertIsNone(self.client.get('/api/cards/3').json['next'])

    def test_individual_line(self):
        self.seed([1])
        line = self.client.get('/api/lines/1').json
        self.assertEqual(line['morphology'], [{'word': 'Arma', 'parse': 'analysis 1'}])
        self.assertEqual((line['work_id'], line['book'], line['number']), (1, 1, 1))
        self.assertEqual(line['annotation']['data'], {'original': True})
        self.assertIsNone(self.client.get('/api/lines/2').json['morphology'])
        self.assertEqual(self.client.get('/api/lines/999').status_code, 404)

    def test_eager_loading(self):
        self.seed([1, 2, 3])
        queries = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        self.client.get('/api/cards/1')
        self.assertEqual(len([q for q in queries if 'FROM morphology' in q]), 1)


if __name__ == '__main__':
    unittest.main()
