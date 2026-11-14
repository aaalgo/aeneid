import contextlib
import io
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from models import Base, Work, Card, Line, Morphology
from compute_morphology import (extract_words, align, analyze_card, process_cards,
                                AnalysisError, MODEL)


def word(text, lemma=None, feats=None):
    return NS(text=text, lemma=lemma or text.lower(), upos='NOUN', feats=feats)


def token(text, start=None, end=None, words=None):
    return NS(text=text, start_char=start, end_char=end,
              words=words if words is not None else [word(text)])


def pipeline(tokens):
    return Mock(return_value=NS(sentences=[NS(tokens=tokens)]))


class AlignmentTests(unittest.TestCase):
    def test_unicode_extraction(self):
        text = '12 “Ārma,” virumque Tantaene quidve a\u0304!'
        words = extract_words(text)
        self.assertEqual([w.word for w in words], ['Ārma', 'virumque', 'Tantaene', 'quidve', 'a\u0304'])
        for w in words:
            self.assertEqual(text[w.start:w.end], w.word)

    def test_offsets_split_punctuation_and_repetition(self):
        text = 'Arma, virumque arma.'
        tokens = [token('Arma', 0, 4), token(',', 4, 5), token('virum', 6, 11),
                  token('que', 11, 14), token('arma', 15, 19), token('.', 19, 20)]
        self.assertEqual(align(extract_words(text), tokens, text), [[0], [2, 3], [4]])

    def test_dp_missing_and_inconsistent_offsets(self):
        text = 'Arma virumque cano'
        for start in (None, 100):
            with self.subTest(start=start):
                tokens = [token('Arma', start, 4), token('virum'), token('que'), token('cano')]
                self.assertEqual(align(extract_words(text), tokens, text), [[0], [1, 2], [3]])

    def test_gap_does_not_shift(self):
        text = 'Arma ignota cano arma'
        self.assertEqual(align(extract_words(text), [token('Arma'), token('cano'), token('arma')], text),
                         [[0], [], [1], [2]])

    def test_multiple_words_and_multiline_card(self):
        lines = [NS(id=1, number=1, latin='Arma virumque'), NS(id=2, number=2, latin='cano.')]
        nlp = pipeline([token('Arma', 0, 4), token('virumque', 5, 13,
                       [word('virum', 'vir', 'Number=Sing|Case=Acc'), word('que')]),
                       token('cano', 14, 18), token('.', 18, 19)])
        result, count, failures = analyze_card(NS(id=3), lines, nlp)
        nlp.assert_called_once_with('Arma virumque\ncano.')
        self.assertEqual((count, failures), (3, 0))
        self.assertEqual(result[1][1], {'word': 'virumque', 'parse': 'vir | NOUN | Case=Acc, Number=Sing\nque | NOUN'})
        self.assertEqual(json.loads(json.dumps(result))["1"][1]['parse'], result[1][1]['parse'])
        self.assertEqual(result[2][0]['word'], 'cano')

    def test_merged_token(self):
        lines = [NS(id=1, number=1, latin='Arma cano')]
        result, _, _ = analyze_card(NS(id=1), lines,
                                   pipeline([token('Arma cano', words=[word('Arma'), word('cano')])]))
        self.assertEqual([x['parse'] for x in result[1]], ['arma | NOUN', 'cano | NOUN'])

    def test_isolated_failure_keeps_empty_parse(self):
        lines = [NS(id=1, number=1, latin='Arma ignota cano arma cano')]
        with self.assertLogs('compute_morphology', level='WARNING') as logs:
            result, count, failures = analyze_card(NS(id=7), lines,
                pipeline([token('Arma'), token('cano'), token('arma'), token('cano')]))
        self.assertEqual((count, failures), (5, 1))
        self.assertEqual(result[1][1], {'word': 'ignota', 'parse': ''})
        self.assertEqual(result[1][2]['parse'], 'cano | NOUN')
        self.assertIn('Card 7, line 1', logs.output[0])

    def test_severe_failure(self):
        with self.assertRaises(AnalysisError):
            analyze_card(NS(id=1), [NS(id=1, number=1, latin='Arma cano')], pipeline([]))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        with self.factory.begin() as session:
            session.add(Work(id=1, title='Aeneid', author='Virgil'))
            session.add(Card(id=1, work_id=1, book=1, number=1, latin_start=1, latin_end=2, english='text'))
            session.add_all([Line(id=1, work_id=1, book=1, number=1, latin='Arma'),
                             Line(id=2, work_id=1, book=1, number=2, latin='cano')])
            session.add(Morphology(line_id=1, data=[{'word': 'Arma', 'parse': 'cached'}], model='old'))
        self.nlp = pipeline([token('Arma', 0, 4), token('cano', 5, 9)])

    def tearDown(self):
        self.engine.dispose()

    def run_cards(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return process_cards(self.factory, self.nlp, **kwargs)

    def rows(self):
        with self.factory() as session:
            return session.scalars(select(Morphology).order_by(Morphology.line_id)).all()

    def test_partial_resume_force(self):
        totals = self.run_cards()
        self.assertEqual((totals['processed'], totals['lines']), (1, 1))
        self.assertEqual(self.rows()[0].data[0]['parse'], 'cached')
        self.assertEqual(self.nlp.call_count, 1)
        totals = self.run_cards()
        self.assertEqual((totals['skipped'], totals['processed']), (1, 0))
        self.assertEqual(self.nlp.call_count, 1)
        totals = self.run_cards(force=True)
        self.assertEqual(totals['lines'], 2)
        self.assertEqual(self.rows()[0].model, MODEL)
        self.assertEqual(self.rows()[0].data[0]['parse'], 'arma | NOUN')

    def test_dry_run_and_filters(self):
        self.assertEqual(self.run_cards(dry_run=True)['lines'], 0)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.run_cards(book=2)['processed'], 0)
        self.assertEqual(self.run_cards(card=99)['processed'], 0)
        self.assertEqual(self.run_cards(limit=0)['processed'], 0)

    def test_analysis_failure_preserves_cache(self):
        self.nlp.side_effect = RuntimeError('inference failure')
        with self.assertLogs('compute_morphology', level='ERROR'):
            totals = self.run_cards(force=True)
        self.assertEqual((totals['failed'], totals['processed'], totals['lines']), (1, 0, 0))
        self.assertEqual(self.rows()[0].data[0]['parse'], 'cached')
        self.assertEqual(len(self.rows()), 1)

    def test_failed_card_continues_to_next(self):
        with self.factory.begin() as session:
            session.add(Card(id=2, work_id=1, book=2, number=1,
                             latin_start=1, latin_end=1, english='other'))
            session.add(Line(id=3, work_id=1, book=2, number=1, latin='cano'))
        self.nlp.side_effect = [RuntimeError('bad Card'),
                               NS(sentences=[NS(tokens=[token('cano', 0, 4)])])]
        with self.assertLogs('compute_morphology', level='ERROR'):
            totals = self.run_cards()
        self.assertEqual((totals['failed'], totals['processed'], totals['lines']), (1, 1, 1))
        self.assertEqual([r.line_id for r in self.rows()], [1, 3])

    def test_write_failure_rolls_back(self):
        def fail(conn, cursor, statement, parameters, context, executemany):
            if statement.startswith('INSERT INTO morphology'):
                raise RuntimeError('write failure')
        event.listen(self.engine, 'before_cursor_execute', fail)
        try:
            with self.assertLogs('compute_morphology', level='ERROR'):
                totals = self.run_cards(force=True)
        finally:
            event.remove(self.engine, 'before_cursor_execute', fail)
        self.assertEqual((totals['processed'], totals['lines'], totals['failed']), (0, 0, 1))
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0].data[0]['parse'], 'cached')


if __name__ == '__main__':
    unittest.main()
