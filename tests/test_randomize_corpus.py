import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from randomize_corpus import sample_prose, split_sentences

class RandomCorpusTests(unittest.TestCase):
    def test_one_word_deleted_without_reordering(self):
        source = ['Alpha beta.', 'Gamma delta epsilon.', 'Zeta eta theta iota.']
        result = sample_prose(source, 317, random.Random(42))
        self.assertEqual(sum(len(s.split()) for s in result), 317)
        variants = {' '.join(words[:i]+words[i+1:]) for s in source for words in [s.split()] for i in range(len(words))}
        self.assertTrue(all(s in variants for s in result))
        self.assertEqual(result, sample_prose(source, 317, random.Random(42)))
        self.assertNotEqual(result, sample_prose(source, 317, random.Random(43)))

    def test_split_quotes_and_short_units(self):
        self.assertEqual(split_sentences('One two. “Three four!” Five six? Alone.'), ['One two.', '“Three four!”', 'Five six?'])
