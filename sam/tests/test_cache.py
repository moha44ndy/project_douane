import hashlib
import json
import unittest
import uuid
from unittest.mock import patch

from sam import api as api_mod
from sam.cache import (
    CLASSIFY_CACHE_DISABLED_KEY,
    cache_classify_is_disabled,
    cache_classify_set_disabled,
    cache_clear_classify,
    cache_get,
    cache_set,
    _enabled,
)


class TestClassifyCacheLogic(unittest.TestCase):
    def test_classify_text_query_returns_cached_without_rag(self) -> None:
        query = "Sac de voyage cuir neuf test cache logique"
        cached_json = json.dumps(
            {
                "narrative": "depuis cache",
                "classifications": [{"hs_code": "4202.91.90.00", "description": query}],
            }
        )
        with patch("sam.api.cache_classify_is_disabled", return_value=False):
            with patch("sam.api.cache_get", return_value=cached_json) as mock_get:
                out = api_mod._classify_text_query(query, request_id="t-cache")
        mock_get.assert_called_once()
        obj = json.loads(out)
        self.assertTrue(obj["classifications"])
        self.assertIn("4202.91", obj["classifications"][0]["hs_code"])

    def test_classify_skips_cache_when_disabled(self) -> None:
        query = "ordinateur portable"
        with patch("sam.api.cache_classify_is_disabled", return_value=True):
            with patch("sam.api.cache_get") as mock_get:
                with self.assertRaises(Exception):
                    api_mod._classify_text_query(query, request_id="t-off")
                mock_get.assert_not_called()


class TestCacheKey(unittest.TestCase):
    def test_same_query_same_key(self) -> None:
        q = "Mercedes-Benz Classe S 500 neuf"
        k1 = api_mod._classify_cache_key(q)
        k2 = api_mod._classify_cache_key(q)
        self.assertEqual(k1, k2)
        self.assertTrue(k1.startswith("classify:v2:"))

    def test_case_insensitive_key(self) -> None:
        k1 = api_mod._classify_cache_key("Sac de voyage CUIR")
        k2 = api_mod._classify_cache_key("sac de voyage cuir")
        self.assertEqual(k1, k2)

    def test_different_queries_different_keys(self) -> None:
        k1 = api_mod._classify_cache_key("ordinateur portable")
        k2 = api_mod._classify_cache_key("telephone mobile")
        self.assertNotEqual(k1, k2)


@unittest.skipUnless(_enabled(), "Upstash Redis non configuré (UPSTASH_REDIS_REST_URL/TOKEN)")
class TestUpstashCacheIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._prev_disabled = cache_classify_is_disabled()
        cache_classify_set_disabled(False)

    @classmethod
    def tearDownClass(cls) -> None:
        cache_classify_set_disabled(cls._prev_disabled)

    def test_set_and_get_roundtrip(self) -> None:
        key = f"mosam:test:roundtrip:{uuid.uuid4().hex}"
        payload = '{"narrative":"test","classifications":[{"hs_code":"8703.23.19.00"}]}'
        cache_set(key, payload, ex=120)
        got = cache_get(key)
        self.assertEqual(got, payload)

    def test_get_missing_returns_none(self) -> None:
        key = f"mosam:test:missing:{uuid.uuid4().hex}"
        self.assertIsNone(cache_get(key))

    def test_classify_cache_flow_write_then_read(self) -> None:
        query = f"TEST_CACHE_FLOW_{uuid.uuid4().hex}"
        cache_key = api_mod._classify_cache_key(query)
        raw = json.dumps(
            {
                "narrative": "test cache flow",
                "classifications": [{"hs_code": "8703.23.19.00", "description": query}],
            },
            ensure_ascii=False,
        )
        cache_set(cache_key, raw, ex=120)
        cached = cache_get(cache_key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached, raw)
        obj = json.loads(cached)
        self.assertEqual(obj["classifications"][0]["hs_code"], "8703.23.19.00")

    def test_disable_flag_blocks_read_semantics(self) -> None:
        was = cache_classify_is_disabled()
        try:
            cache_classify_set_disabled(True)
            self.assertTrue(cache_classify_is_disabled())
            cache_classify_set_disabled(False)
            self.assertFalse(cache_classify_is_disabled())
        finally:
            cache_classify_set_disabled(was)

    def test_clear_classify_removes_test_keys(self) -> None:
        query = f"TEST_CLEAR_{uuid.uuid4().hex}"
        cache_key = api_mod._classify_cache_key(query)
        cache_set(cache_key, '{"narrative":"x","classifications":[]}', ex=120)
        self.assertIsNotNone(cache_get(cache_key))
        deleted = cache_clear_classify()
        self.assertGreaterEqual(deleted, 1)
        self.assertIsNone(cache_get(cache_key))


if __name__ == "__main__":
    unittest.main()
