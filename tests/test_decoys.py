import random
import unittest

from scripts import build_task as task


class DecoyTests(unittest.TestCase):
    def test_decoys_use_all_templates_but_never_point_to_a_file(self):
        parse_template = task.template_parser()
        parse_direction = task.direction_parser()
        for seed in range(20):
            decoys = task.generate_decoys(random.Random(seed))
            self.assertEqual(len(set(decoys)), 100)
            self.assertEqual(sorted(parse_template(s)[0] for s in decoys), list(range(100)))
            self.assertTrue(all(parse_direction(s) is None for s in decoys))
            self.assertTrue(all(not any(c.isdigit() for c in s) for s in decoys))
        self.assertEqual(task.generate_decoys(random.Random(42)), task.generate_decoys(random.Random(42)))
        self.assertNotEqual(task.generate_decoys(random.Random(42)), task.generate_decoys(random.Random(43)))

    def test_insertions_preserve_prose_and_use_random_interior_positions(self):
        prose = [f'Prose paragraph {n}.' for n in range(200)]
        clues = task.generate_decoys(random.Random(1)) + [task.direction(0, 42)]
        result = task.intersperse(prose, clues, random.Random(2))
        self.assertEqual(result[0], prose[0])
        self.assertEqual(result[-1], prose[-1])
        self.assertEqual([s for s in result if s in prose], prose)
        self.assertCountEqual([s for s in result if s in clues], clues)
        self.assertEqual(sum(len(s.split()) for s in result),
                         sum(len(s.split()) for s in prose + clues))
        self.assertNotEqual(result, task.intersperse(prose, clues, random.Random(3)))
        # Small fixtures may share a boundary, but never drop insertions.
        self.assertCountEqual(task.intersperse(prose[:2], clues, random.Random(0)), prose[:2] + clues)
