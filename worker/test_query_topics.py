import unittest
from .query_topics import query_topic


class QueryTopicTest(unittest.TestCase):
    def test_equivalent_queries(self):
        expected = query_topic("sidewalk")
        self.assertTrue(expected[1])
        for query in ("Pavement", "Sidewalks", "الرَّصيف؟", "ทางเท้า", "फुटपाथ", "فٹ پاتھ"):
            self.assertEqual(query_topic(query), expected)

    def test_specific_queries_keep_modifiers(self):
        anchors, broad = query_topic("cars parked on the sidewalk")
        self.assertEqual(anchors, query_topic("sidewalk")[0])
        self.assertFalse(broad)
        self.assertEqual(query_topic("tree blocking a sidewalk"), (None, False))
        self.assertEqual(query_topic("water leaking from the ceiling"), (None, False))
