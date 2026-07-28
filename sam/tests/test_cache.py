import hashlib
import json
import unittest
import uuid
from unittest.mock import Mock
from unittest.mock import patch

from sam import api as api_mod
from sam import cache as cache_mod
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

    def test_structured_request_skips_assistant_meta_fuzzy_match(self) -> None:
        query = "- Cisco C9200L-48P-4X-E, reference fabricant C9200L-48P-4X-E"
        cached_json = json.dumps({
            "narrative": "cached",
            "classifications": [{"hs_code": "8517.62.00.00", "description": "switch"}],
        })
        items = [api_mod.MerchandiseItem(designation="Cisco C9200L-48P-4X-E")]
        with patch("sam.api.is_assistant_meta_query") as meta_match:
            with patch("sam.api.cache_classify_is_disabled", return_value=False):
                with patch("sam.api.cache_get", return_value=cached_json):
                    raw = api_mod._classify_text_query(
                        query,
                        request_id="t-structured-meta-skip",
                        structured_items=items,
                    )

        meta_match.assert_not_called()
        self.assertEqual(json.loads(raw)["classifications"][0]["hs_code"], "8517.62.00.00")


class TestCacheKey(unittest.TestCase):
    def test_same_query_same_key(self) -> None:
        q = "Mercedes-Benz Classe S 500 neuf"
        k1 = api_mod._classify_cache_key(q)
        k2 = api_mod._classify_cache_key(q)
        self.assertEqual(k1, k2)
        self.assertTrue(k1.startswith("classify:v17:"))

    def test_case_insensitive_key(self) -> None:
        k1 = api_mod._classify_cache_key("Sac de voyage CUIR")
        k2 = api_mod._classify_cache_key("sac de voyage cuir")
        self.assertEqual(k1, k2)

    def test_different_queries_different_keys(self) -> None:
        k1 = api_mod._classify_cache_key("ordinateur portable")
        k2 = api_mod._classify_cache_key("telephone mobile")
        self.assertNotEqual(k1, k2)

    def test_single_item_cache_key_same_text_same_key(self) -> None:
        k1 = api_mod._single_item_classification_cache_key("Pompe industrielle 5KW")
        k2 = api_mod._single_item_classification_cache_key("pompe   industrielle 5kw")
        self.assertEqual(k1, k2)
        self.assertTrue(k1.startswith("classify:item:v12:"))

    def test_hyphenated_origin_does_not_collide_between_products(self) -> None:
        first = "Produit : Juniper MX204\nOrigine : Etats-Unis\nValeur : 100 USD"
        second = "Produit : Starlink Standard Kit\nOrigine : Etats-Unis\nValeur : 200 USD"

        self.assertNotEqual(
            api_mod._single_item_classification_cache_key(first),
            api_mod._single_item_classification_cache_key(second),
        )

    def test_hyphenated_origin_is_not_a_manufacturer_reference(self) -> None:
        dossier = "Produit : Juniper MX204\nOrigine : Etats-Unis\nValeur : 100 USD"

        self.assertEqual(api_mod._extract_manufacturer_reference_for_cache(dossier), "MX204")
        self.assertEqual(
            api_mod._legacy_single_item_classification_cache_key(dossier),
            api_mod._single_item_classification_cache_key(dossier),
        )

    def test_non_quality_sensitive_products_keep_default_item_cache_version(self) -> None:
        from sam.api import _single_item_classification_cache_key

        stable = [
            "Stainless steel vacuum flask with double wall",
            "LED household light bulb E27",
            "Polypropylene woven packing sack",
            "Glazed ceramic floor tile",
        ]
        for item_text in stable:
            with self.subTest(item_text=item_text):
                key = _single_item_classification_cache_key(item_text)
                self.assertTrue(key.startswith("classify:item:v12:"))

    def test_quality_sensitive_products_use_refreshed_item_cache_version(self) -> None:
        from sam.api import _single_item_classification_cache_key

        refreshed = [
            "Produit : Apple iPad Pro M4\nCaracteristiques : tablette tactile portable",
            "Produit : ABB ACS880-01-430A-3\nCaracteristiques : variateur de frequence industriel",
            "Produit : DJI Zenmuse H30T\nCaracteristiques : camera thermique multispectrale",
        ]
        for item_text in refreshed:
            with self.subTest(item_text=item_text):
                key = _single_item_classification_cache_key(item_text)
                self.assertTrue(key.startswith("classify:item:v13:"))

    def test_unlabelled_products_do_not_use_legacy_reference_key(self) -> None:
        from sam.api import (
            _legacy_single_item_classification_cache_key,
            _single_item_classification_cache_key,
        )

        for item_text in [
            "LED household light bulb E27",
            "Stainless steel vacuum flask",
            "Glazed ceramic floor tile",
        ]:
            with self.subTest(item_text=item_text):
                self.assertEqual(
                    _legacy_single_item_classification_cache_key(item_text),
                    _single_item_classification_cache_key(item_text),
                )

    def test_known_product_text_does_not_select_a_special_cache_version(self) -> None:
        from sam.api import _single_item_classification_cache_key

        source_queries = [
            "Produit : Stainless steel vacuum flask\nValeur :\n12.75 USD",
            "Produit : LED household light bulb\nCaracteristiques :\nself-contained LED lamp",
            "Produit : Polypropylene woven packing sack\nCaracteristiques :\nOpen-mouth sack",
        ]
        for source_query in source_queries:
            with self.subTest(source_query=source_query):
                key = _single_item_classification_cache_key(source_query)
                self.assertTrue(key.startswith("classify:item:v12:"))

    def test_refreshed_quality_family_skips_legacy_reference_fallback(self) -> None:
        item = (
            "Produit : ABB ACS880-01-430A-3\n"
            "Reference fabricant : ABB ACS880-01-430A-3\n"
            "Usage : variateur de frequence industriel pour moteur triphase"
        )
        self.assertEqual(
            api_mod._legacy_single_item_classification_cache_key(item),
            api_mod._single_item_classification_cache_key(item),
        )

    def test_manufacturer_reference_key_ignores_commercial_fields(self) -> None:
        first = (
            "Produit : Cisco C9200L-48P-4X-E\n"
            "Reference fabricant : C9200L-48P-4X-E\n"
            "Quantite : 2 PCE\nOrigine : Chine\nValeur : 2850 USD"
        )
        changed = (
            "Produit : Cisco C9200L-48P-4X-E\n"
            "Reference fabricant : C9200L-48P-4X-E\n"
            "Quantite : 50 U\nOrigine : Pakistan\nValeur : 99 EUR"
        )
        self.assertEqual(
            api_mod._single_item_classification_cache_key(first),
            api_mod._single_item_classification_cache_key(changed),
        )

    def test_manufacturer_reference_key_includes_functional_evidence(self) -> None:
        switch = (
            "Produit : Cisco C9200L-48P-4X-E\n"
            "Reference fabricant : C9200L-48P-4X-E\n"
            "Usage : commutateur Ethernet pour transmission de donnees"
        )
        conflicting = (
            "Produit : Cisco C9200L-48P-4X-E\n"
            "Reference fabricant : C9200L-48P-4X-E\n"
            "Usage : telephone intelligent"
        )
        self.assertNotEqual(
            api_mod._single_item_classification_cache_key(switch),
            api_mod._single_item_classification_cache_key(conflicting),
        )

    def test_numeric_labelled_manufacturer_reference_is_normalized(self) -> None:
        first = "Produit : Bosch 2607017160\nReference fabricant : 2607017160\nValeur : 22 EUR"
        changed = "Reference fabricant: 2607017160\nValeur : 100 USD"
        self.assertEqual(
            api_mod._single_item_classification_cache_key(first),
            api_mod._single_item_classification_cache_key(changed),
        )

    def test_blank_hs_code_is_rejected_before_storage(self) -> None:
        with self.assertRaisesRegex(Exception, "code tarifaire est requis"):
            api_mod._normalized_hs_code_for_storage("  ")

        self.assertEqual(
            api_mod._normalized_hs_code_for_storage(" 8517.62.00.00 "),
            "8517.62.00.00",
        )


class TestSingleItemCacheHelpers(unittest.TestCase):
    def test_load_cached_single_item_classifications_reads_only_valid_dicts(self) -> None:
        items = ["pompe", "moteur", "vanne"]

        def _fake_cache_get(key: str):
            if key == api_mod._single_item_classification_cache_key("pompe"):
                return json.dumps({"hs_code": "8413.70.00.00", "description": "pompe"})
            if key == api_mod._single_item_classification_cache_key("moteur"):
                return "not-json"
            return None

        with patch("sam.api.cache_get", side_effect=_fake_cache_get):
            out = api_mod._load_cached_single_item_classifications(items)

        self.assertEqual(list(out.keys()), ["pompe"])
        self.assertEqual(out["pompe"]["hs_code"], "8413.70.00.00")

    def test_store_cached_single_item_classification_serializes_payload(self) -> None:
        payload = {"hs_code": "8501.52.00.00", "description": "moteur"}
        with patch("sam.api.cache_set", return_value=True) as mock_cache_set:
            stored = api_mod._store_cached_single_item_classification(
                "moteur", payload, ttl_seconds=123
            )
        self.assertTrue(stored)
        args, kwargs = mock_cache_set.call_args
        self.assertEqual(args[0], api_mod._single_item_classification_cache_key("moteur"))
        self.assertEqual(json.loads(args[1]), payload)
        self.assertEqual(kwargs["ex"], 123)

    def test_store_skips_placeholder_classification(self) -> None:
        with patch("sam.api.cache_set") as mock_cache_set:
            stored = api_mod._store_cached_single_item_classification(
                "moteur", {"hs_code": "Non renseigné", "description": "moteur"}
            )
        self.assertFalse(stored)
        mock_cache_set.assert_not_called()

    def test_load_migrates_legacy_full_text_reference_key(self) -> None:
        item = "Reference fabricant : 2607017160\nValeur : 22 EUR"
        payload = {"hs_code": "8207.90.00.00", "description": "Accessoire outil"}
        primary_key = api_mod._single_item_classification_cache_key(item)
        legacy_key = api_mod._legacy_single_item_classification_cache_key(item)
        self.assertNotEqual(primary_key, legacy_key)

        def _fake_cache_get(key: str):
            if key == legacy_key:
                return json.dumps(payload)
            return None

        with patch("sam.api.cache_get", side_effect=_fake_cache_get):
            with patch("sam.api.cache_set", return_value=True) as mock_cache_set:
                loaded = api_mod._load_cached_single_item_classifications([item])

        self.assertEqual(loaded[item]["hs_code"], payload["hs_code"])
        self.assertEqual(mock_cache_set.call_args.args[0], primary_key)


class TestCacheValueCompatibility(unittest.TestCase):
    def test_classification_value_field_is_not_treated_as_legacy_wrapper(self) -> None:
        raw = json.dumps(
            {
                "hs_code": "8517.62.00.00",
                "description": "Commutateur reseau",
                "value": "2850 USD",
            }
        )
        response = Mock(status_code=200)
        response.json.return_value = {"result": raw}
        with patch("sam.cache._enabled", return_value=True):
            with patch("sam.cache.requests.post", return_value=response):
                self.assertEqual(cache_get("classify:item:test"), raw)

    def test_legacy_value_only_wrapper_is_still_unwrapped(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"result": json.dumps({"value": "legacy-payload"})}
        with patch("sam.cache._enabled", return_value=True):
            with patch("sam.cache.requests.post", return_value=response):
                self.assertEqual(cache_get("legacy:test"), "legacy-payload")

    def test_validated_cached_response_keeps_classification_shape(self) -> None:
        raw = json.dumps({
            "narrative": "cached",
            "classifications": [{"hs_code": "8517.62.00.00", "value": "2850 USD"}],
        })
        self.assertEqual(api_mod._validated_cached_response_raw(raw), raw)

    def test_validated_cached_response_rejects_invalid_shape(self) -> None:
        self.assertIsNone(api_mod._validated_cached_response_raw('{"value":"2850 USD"}'))


class TestCacheStatusLocalTTL(unittest.TestCase):
    def setUp(self) -> None:
        with cache_mod._CLASSIFY_STATUS_LOCK:
            cache_mod._CLASSIFY_STATUS.update({
                "disabled": False,
                "expires_at": 0.0,
                "refreshing": False,
                "initialized": False,
            })

    def test_stale_status_returns_immediately_and_starts_background_refresh(self) -> None:
        thread = Mock()
        with patch("sam.cache._enabled", return_value=True):
            with patch("sam.cache.threading.Thread", return_value=thread) as thread_cls:
                self.assertFalse(cache_mod.cache_classify_is_disabled())
        thread_cls.assert_called_once()
        thread.start.assert_called_once()

    def test_fresh_local_status_avoids_remote_refresh(self) -> None:
        cache_mod._set_local_classify_disabled(True)
        with patch("sam.cache._enabled", return_value=True):
            with patch("sam.cache.threading.Thread") as thread_cls:
                self.assertTrue(cache_mod.cache_classify_is_disabled())
        thread_cls.assert_not_called()

    def test_successful_admin_update_refreshes_local_status(self) -> None:
        response = Mock(status_code=200, content=b'{"result":"OK"}')
        response.json.return_value = {"result": "OK"}
        with patch("sam.cache._enabled", return_value=True):
            with patch("sam.cache.requests.post", return_value=response):
                self.assertTrue(cache_mod.cache_classify_set_disabled(True))
                self.assertTrue(cache_mod.cache_classify_is_disabled())


class TestStructuredItemMetadataReuse(unittest.TestCase):
    def test_build_structured_inputs_keeps_frontend_metadata(self) -> None:
        item = api_mod.MerchandiseItem(
            designation="Pompe industrielle",
            material="Acier",
            usage="Transfert d'eau",
            characteristics="5KW",
            quantity="2",
            unit="PCE",
            origin="Chine",
            value="1500",
            currency="USD",
        )

        _, unique_items, item_counts, item_meta = api_mod._build_structured_inputs([item])

        self.assertEqual(len(unique_items), 1)
        label = unique_items[0]
        self.assertEqual(item_counts[label], 2)
        self.assertEqual(item_meta[label]["origin"], "Chine")
        self.assertEqual(item_meta[label]["value"], "1500")
        self.assertEqual(item_meta[label]["currency"], "USD")
        self.assertEqual(item_meta[label]["designation"], "Pompe industrielle")

    def test_merge_item_metadata_into_classifications_preserves_origin_and_value(self) -> None:
        source = "Produit : Pompe industrielle"
        classifications = [{"hs_code": "8413.70.00.00", "description": "Pompe centrifuge"}]
        item_counts = {source: 2}
        item_meta = {
            source: {
                "quantity_source": "explicit",
                "quantity_raw": "2",
                "quantity_confidence": 95,
                "designation": "Pompe industrielle",
                "origin": "Chine",
                "value": "1500",
                "currency": "USD",
            }
        }

        merged = api_mod._merge_item_metadata_into_classifications(
            classifications,
            [source],
            item_counts,
            item_meta,
            classify_input=source,
            query="pompe",
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["quantity"], 2)
        self.assertEqual(merged[0]["origin"], "Chine")
        self.assertEqual(merged[0]["value"], "1500 USD")
        self.assertEqual(merged[0]["source_query"], source)

    def test_structured_designation_preserves_decimal_model_name(self) -> None:
        source = "Produit : Samsung PM9A3 3.84TB"
        merged = api_mod._merge_item_metadata_into_classifications(
            [{"hs_code": "8471.70", "description": "Samsung PM9A3 3"}],
            [source],
            {source: 1},
            {
                source: {
                    "designation": "Samsung PM9A3 3.84TB",
                    "quantity_source": "explicit",
                    "quantity_confidence": 95,
                }
            },
            classify_input=source,
            query=source,
        )

        self.assertEqual(merged[0]["description"], "Samsung PM9A3 3.84TB")
        self.assertEqual(merged[0]["classified_product_type"], "Samsung PM9A3 3")

    def test_local_product_evidence_is_attached_when_identification_agent_was_skipped(self) -> None:
        data = {"classifications": [{"hs_code": "8517.62", "confidence": 80}]}
        evidence = {
            "designation": "Network module X1",
            "identification_status": "provided",
            "primary_function": "transmit data",
        }
        api_mod._attach_product_identification(
            data,
            [{
                "skipped": True,
                "identification_confidence": 100,
                "product_evidence": evidence,
            }],
        )

        attached = data["classifications"][0]["product_identification"]
        self.assertEqual(attached["product_evidence"], evidence)
        self.assertEqual(data["product_identification"][0]["product_evidence"], evidence)

    def test_current_metadata_overrides_cached_commercial_fields(self) -> None:
        source = "Produit : Cisco C9200L-48P-4X-E"
        cached = [{
            "hs_code": "8517.62.00.00",
            "description": "Commutateur reseau",
            "quantity": 2,
            "origin": "Chine",
            "value": "2850 USD",
        }]
        item_meta = {
            source: {
                "quantity_source": "explicit",
                "quantity_raw": "50",
                "quantity_confidence": 95,
                "origin": "Pakistan",
                "value": "99",
                "currency": "EUR",
            }
        }

        merged = api_mod._merge_item_metadata_into_classifications(
            cached,
            [source],
            {source: 50},
            item_meta,
            classify_input=source,
            query=source,
        )

        self.assertEqual(merged[0]["quantity"], 50)
        self.assertEqual(merged[0]["origin"], "Pakistan")
        self.assertEqual(merged[0]["value"], "99 EUR")

    def test_fully_cached_structured_result_skips_expensive_normalization(self) -> None:
        source = "Produit : Cisco C9200L-48P-4X-E"
        cached = {
            source: {
                "hs_code": "8517.62.00.00",
                "description": "Commutateur reseau",
                "origin": "Chine",
                "value": "2850 USD",
            }
        }
        item_meta = {
            source: {
                "quantity_source": "explicit",
                "quantity_raw": "2",
                "quantity_confidence": 95,
                "origin": "Chine",
                "value": "2850",
                "currency": "USD",
            }
        }

        with patch(
            "sam.api._load_cached_single_item_classifications", return_value=cached
        ):
            with patch("sam.api._normalize_classifications_response") as normalize:
                raw = api_mod._classify_structured_items_in_batches(
                    [source],
                    {source: 2},
                    item_meta,
                    query=source,
                    chunks=[],
                    index=None,
                    request_id="cache-fast",
                    progress=None,
                    skip_identification=True,
                )

        normalize.assert_not_called()
        parsed = json.loads(raw)
        self.assertEqual(parsed["classifications"][0]["quantity"], 2)
        self.assertEqual(parsed["classifications"][0]["value"], "2850 USD")

    def test_placeholder_classification_has_safe_defaults(self) -> None:
        out = api_mod._build_placeholder_classification("Pompe test", "missing")
        self.assertEqual(out["description"], "Pompe test")
        self.assertEqual(out["hs_code"], "Non renseigné")
        self.assertEqual(out["justification"], "missing")

    def test_quota_failure_keeps_all_rows_and_stops_later_provider_calls(self) -> None:
        items = ["Produit : Article A", "Produit : Article B"]
        quota_error = RuntimeError(
            "Error code: 429 - insufficient_quota - exceeded your current quota"
        )
        metadata = {
            item: {"quantity_source": "default", "quantity_confidence": 50}
            for item in items
        }

        with patch("sam.api._structured_form_batch_size", return_value=1):
            with patch("sam.api._reference_parallelism", return_value=1):
                with patch("sam.api._load_cached_single_item_classifications", return_value={}):
                    with patch("sam.api.process_user_input", side_effect=quota_error) as process:
                        raw = api_mod._classify_structured_items_in_batches(
                            items,
                            {item: 1 for item in items},
                            metadata,
                            query="articles",
                            chunks=[],
                            index=None,
                            request_id="quota-partial",
                            progress=None,
                            skip_identification=True,
                        )

        self.assertEqual(process.call_count, 1)
        classifications = json.loads(raw)["classifications"]
        self.assertEqual(len(classifications), 2)
        self.assertTrue(all(item["retryable"] for item in classifications))
        self.assertTrue(
            all(item["error_code"] == "openai_quota_exhausted" for item in classifications)
        )

    def test_non_provider_batch_failure_is_not_silenced(self) -> None:
        with self.assertRaisesRegex(ValueError, "programming defect"):
            with patch("sam.api._structured_form_batch_size", return_value=1):
                with patch("sam.api._load_cached_single_item_classifications", return_value={}):
                    with patch(
                        "sam.api.process_user_input",
                        side_effect=ValueError("programming defect"),
                    ):
                        api_mod._classify_structured_items_in_batches(
                            ["Produit : Article A"],
                            {"Produit : Article A": 1},
                            {
                                "Produit : Article A": {
                                    "quantity_source": "default",
                                    "quantity_confidence": 50,
                                }
                            },
                            query="article",
                            chunks=[],
                            index=None,
                            request_id="unexpected-error",
                            progress=None,
                            skip_identification=True,
                        )

    def test_structured_form_rows_are_not_merged_like_file_duplicates(self) -> None:
        source_a = "Produit : Pompe A"
        source_b = "Produit : Pompe B"
        cls = [
            {"hs_code": "8413.70.00.00", "description": "Pompe centrifuge"},
            {"hs_code": "8413.70.00.00", "description": "Pompe centrifuge"},
        ]
        item_counts = {source_a: 1, source_b: 2}
        item_meta = {
            source_a: {"quantity_source": "explicit", "quantity_raw": "1", "quantity_confidence": 95},
            source_b: {"quantity_source": "explicit", "quantity_raw": "2", "quantity_confidence": 95},
        }

        merged = api_mod._merge_item_metadata_into_classifications(
            cls,
            [source_a, source_b],
            item_counts,
            item_meta,
            classify_input=f"{source_a}\n\n{source_b}",
            query="pompes",
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["quantity"], 1)
        self.assertEqual(merged[1]["quantity"], 2)


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
