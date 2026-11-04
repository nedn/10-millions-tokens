import re
import unittest

from scripts import build_task as task
from scripts.number_fuzzer import representations


class NumberFuzzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parse = staticmethod(task.direction_parser())

    def test_every_number_encoding_round_trips(self):
        for n in range(1, 101):
            forms = representations(n, task.english, task.roman)
            self.assertEqual(len(set(forms)), 100)
            for style in range(100):
                template = (n + style) % 100
                sentence = task.direction(template, n, style)
                self.assertEqual(self.parse(sentence), (task.filename(n), template, style))

    def test_every_template_combines_with_every_style(self):
        for template in range(100):
            for style in range(100):
                n = (1, 19, 40, 99, 100)[(template + style) % 5]
                self.assertEqual(self.parse(task.direction(template, n, style)),
                                 (task.filename(n), template, style))

    def test_no_universal_search_phrase(self):
        word_sets = [set(re.findall(r'[a-z]+', s.lower().replace('{target}', '')))
                     for s in task.TEMPLATES]
        self.assertFalse(set.intersection(*word_sets))
        self.assertTrue(all('instruction' not in s for s in task.TEMPLATES))
        self.assertEqual(len(set(task.TEMPLATES)), 100)

    def test_story_and_malformed_labels_are_not_directions(self):
        for text in ('Go and Lise.', 'The prince gave instructions.',
                     task.TEMPLATES[0].format(target='binary 222'),
                     task.TEMPLATES[0].format(target='101')):
            self.assertIsNone(self.parse(text))

    def test_invalid_number_is_rejected(self):
        for n in (0, -1, 101):
            with self.assertRaises(ValueError):
                representations(n, task.english, task.roman)
