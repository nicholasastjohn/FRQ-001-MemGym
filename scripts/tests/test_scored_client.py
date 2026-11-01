"""No-network checks for bounded paid requests and failure/usage accounting."""

from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scored_client as client_module
from scored_client import (StrictAnthropicClient, SmokeClientError, MODEL,
                           RESERVATION_USD, _NoRedirects, _transport)


def response(text='{"answer":"blue"}', **updates):
    value = {"id": "msg_fixture", "model": MODEL, "stop_reason": "end_turn",
             "content": [{"type": "text", "text": text}],
             "usage": {"input_tokens": 10, "output_tokens": 20}}
    value.update(updates)
    return value


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "single-use-approval.jsonl"
        self.calls = []

    def client(self, reply=None, **kwargs):
        def transport(payload, key):
            self.calls.append(deepcopy(payload))
            return deepcopy(reply if reply is not None else response())
        return StrictAnthropicClient(api_key="fixture-secret-key", trace_path=self.path,
                                     transport=transport, **kwargs)

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_valid_answer_and_judge_have_exact_requests_and_costs(self):
        replies = [response(), response('{"score":0.5,"explanation":"partial"}')]

        def transport(payload, key):
            self.calls.append(deepcopy(payload))
            return replies.pop(0)

        client = StrictAnthropicClient(api_key="fixture-secret-key", trace_path=self.path,
                                      transport=transport)
        self.assertEqual(json.loads(client.get_completion("question", temperature=0))["answer"], "blue")
        self.assertEqual(client.get_json_completion("judge", response_format={})["score"], 0.5)
        self.assertEqual(len(self.calls), 2)
        for request in self.calls:
            self.assertEqual(request["model"], MODEL)
            self.assertEqual(request["max_tokens"], 1024)
            self.assertEqual(request["temperature"], 0)
            self.assertEqual(request["service_tier"], "standard_only")
            self.assertNotIn("tools", request)
            self.assertNotIn("thinking", request)
        self.assertNotIn("system", self.calls[0])
        self.assertEqual(self.calls[1]["system"], "You must respond with valid JSON.")
        summary = client.summary()
        self.assertEqual(summary["completed_calls"], 2)
        self.assertEqual(Decimal(summary["reserved_cost_usd"]), Decimal("1.23072"))
        self.assertEqual(Decimal(summary["known_usage_cost_usd"]), Decimal("0.00066"))
        self.assertFalse(summary["billing_uncertain"])
        self.assertNotIn("fixture-secret-key", self.path.read_text())

    def test_invalid_answer_is_failure_not_zero_and_retains_known_usage(self):
        for text in ('{}', '[]', 'null', '{', '{"answer":""}', '{"answer":false}'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "trace.jsonl"
                client = StrictAnthropicClient(api_key="fixture", trace_path=path,
                    transport=lambda *_: response(text))
                with self.assertRaises(SmokeClientError):
                    client.get_completion("question")
                self.assertEqual(client.summary()["completed_calls"], 0)
                self.assertGreater(Decimal(client.summary()["known_usage_cost_usd"]), 0)
                self.assertFalse(client.summary()["billing_uncertain"])
                self.assertEqual([json.loads(l)["kind"] for l in path.read_text().splitlines()],
                                 ["request", "response", "error"])
                with self.assertRaisesRegex(SmokeClientError, "already_failed"):
                    client.get_completion("question")

    def test_invalid_judgment_does_not_become_a_score(self):
        values = [dict(score=True, explanation="bad"), dict(score=float("nan"), explanation="bad"),
                  dict(score=float("inf"), explanation="bad"), dict(score=-0.1, explanation="bad"),
                  dict(score=1.1, explanation="bad"), dict(explanation="missing"),
                  dict(score=0), dict(score=0.5, explanation=" ")]
        for value in values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                client = StrictAnthropicClient(api_key="fixture", trace_path=Path(directory)/"trace",
                    transport=lambda *_, value=value: response(json.dumps(value)))
                with self.assertRaises(SmokeClientError):
                    client.get_json_completion("judge")

    def test_real_judged_zero_is_valid(self):
        client = self.client(response('{"score":0,"explanation":"Wrong answer"}'))
        self.assertEqual(client.get_json_completion("judge")["score"], 0)
        self.assertEqual(client.summary()["completed_calls"], 1)

    def test_invalid_usage_or_extra_costs_are_rejected(self):
        variants = [None, {}, {"input_tokens": True, "output_tokens": 1},
                    {"input_tokens": -1, "output_tokens": 1},
                    {"input_tokens": 200001, "output_tokens": 1},
                    {"input_tokens": 1, "output_tokens": 1025},
                    {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 1},
                    {"input_tokens": 1, "output_tokens": 1, "service_tier": "priority"},
                    {"input_tokens": 1, "output_tokens": 1, "unknown_charge": 0}]
        for usage in variants:
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as directory:
                client = StrictAnthropicClient(api_key="fixture", trace_path=Path(directory)/"trace",
                    transport=lambda *_, usage=usage: response(usage=usage))
                with self.assertRaises(SmokeClientError):
                    client.get_completion("question")
                self.assertTrue(client.summary()["billing_uncertain"])

    def test_normal_api_usage_metadata_is_preserved(self):
        normal = {"input_tokens": 10, "output_tokens": 20,
                  "inference_geo": "global", "speed": "standard", "service_tier": "standard",
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                  "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
                  "server_tool_use": {"web_fetch_requests": 0, "web_search_requests": 0},
                  "output_tokens_details": {"thinking_tokens": 0}}
        nullable = {key: value if key in ("input_tokens", "output_tokens") else None
                    for key, value in normal.items()}
        for usage in (normal, nullable):
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "trace"
                client = StrictAnthropicClient(api_key="fixture", trace_path=path,
                    transport=lambda *_, usage=usage: response(usage=usage))
                client.get_completion("question")
                records = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(records[1]["usage"], usage)
                self.assertEqual(Decimal(client.summary()["known_usage_cost_usd"]), Decimal("0.00033"))

    def test_nonstandard_or_unknown_nested_metadata_is_rejected(self):
        metadata = [("inference_geo", "us"), ("speed", "fast"), ("service_tier", "priority"),
                    ("cache_creation_input_tokens", True), ("cache_read_input_tokens", 1),
                    ("cache_creation", {"ephemeral_1h_input_tokens": 1}),
                    ("cache_creation", {"unknown_cache_tokens": 0}),
                    ("server_tool_use", {"web_search_requests": 1}),
                    ("server_tool_use", {"web_fetch_requests": False}),
                    ("server_tool_use", {"unknown_tool_requests": 0}),
                    ("output_tokens_details", {"thinking_tokens": 1}),
                    ("output_tokens_details", {"unknown_tokens": 0})]
        for key, value in metadata:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                usage = {"input_tokens": 10, "output_tokens": 20, key: value}
                client = StrictAnthropicClient(api_key="fixture", trace_path=Path(directory)/"trace",
                    transport=lambda *_, usage=usage: response(usage=usage))
                with self.assertRaises(SmokeClientError):
                    client.get_completion("question")
                self.assertTrue(client.summary()["billing_uncertain"])

    def test_refusals_truncation_tools_and_model_substitution_are_rejected(self):
        updates = [{"stop_reason": "max_tokens"}, {"stop_reason": "refusal"},
                   {"stop_details": {"type": "refusal"}},
                   {"content": [{"type": "tool_use", "name": "fixture"}]},
                   {"model": "different-model"}, {"service_tier": "priority"}]
        for update in updates:
            with self.subTest(update=update), tempfile.TemporaryDirectory() as directory:
                client = StrictAnthropicClient(api_key="fixture", trace_path=Path(directory)/"trace",
                    transport=lambda *_, update=update: response(**update))
                with self.assertRaises(SmokeClientError):
                    client.get_completion("question")

    def test_timeout_is_not_retried_and_exception_text_never_reaches_trace(self):
        attempts = []

        def fail(*_):
            attempts.append(1)
            raise TimeoutError("fixture-secret-key https://private-key.example")

        client = StrictAnthropicClient(api_key="fixture-secret-key", trace_path=self.path, transport=fail)
        with self.assertRaisesRegex(SmokeClientError, "transport_failure"):
            client.get_completion("question")
        with self.assertRaises(SmokeClientError):
            client.get_completion("question")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(Decimal(client.summary()["reserved_cost_usd"]), RESERVATION_USD)
        self.assertTrue(client.summary()["billing_uncertain"])
        self.assertNotIn("fixture-secret-key", self.path.read_text())
        self.assertNotIn("private-key.example", self.path.read_text())

    def test_cost_and_call_ceiling_reject_before_transport(self):
        self.assertEqual(RESERVATION_USD, Decimal("0.61536"))
        self.assertEqual(RESERVATION_USD * 6, Decimal("3.69216"))
        client = self.client(max_cost_usd=Decimal("0.60"))
        with self.assertRaisesRegex(SmokeClientError, "approval_limit"):
            client.get_completion("question")
        self.assertEqual(self.calls, [])
        self.assertEqual(client.summary()["attempted_calls"], 0)
        with tempfile.TemporaryDirectory() as directory:
            client = StrictAnthropicClient(api_key="fixture", trace_path=Path(directory)/"trace",
                                            max_calls=1, transport=lambda *_: response())
            client.get_completion("question")
            with self.assertRaisesRegex(SmokeClientError, "approval_limit"):
                client.get_completion("question")
            self.assertEqual(client.summary()["attempted_calls"], 1)

    def test_http_error_records_status_without_provider_body_or_secret(self):
        def fail(*_):
            raise urllib.error.HTTPError("https://fixture-secret-key.example", 401,
                                         "fixture-secret-key", {}, None)
        client = StrictAnthropicClient(api_key="fixture-secret-key", trace_path=self.path, transport=fail)
        with self.assertRaisesRegex(SmokeClientError, "http_401"):
            client.get_completion("question")
        self.assertEqual(self.records()[-1]["error_code"], "http_401")
        self.assertNotIn("fixture-secret-key", self.path.read_text())

    def test_authorization_file_is_exclusive_and_missing_key_does_not_consume_it(self):
        with self.assertRaises(ValueError):
            StrictAnthropicClient(api_key="", trace_path=self.path)
        self.assertFalse(self.path.exists())
        self.path.write_text("prior authorization evidence\n")
        with self.assertRaises(FileExistsError):
            self.client()
        self.assertEqual(self.path.read_text(), "prior authorization evidence\n")
        for maximum in (0, 6, float("nan"), float("inf")):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                StrictAnthropicClient(api_key="fixture", trace_path=self.path, max_cost_usd=maximum)

    def test_transport_has_fixed_host_version_no_redirects_and_one_attempt(self):
        class FakeResponse(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *_): self.close()

        class Opener:
            def open(inner, request, timeout):
                self.calls.append(request)
                self.assertEqual(timeout, 90)
                return FakeResponse(json.dumps(response()).encode())

        with patch.object(client_module.urllib.request, "build_opener", return_value=Opener()) as build:
            actual = _transport({"model": MODEL}, "fixture-secret-key")
        self.assertEqual(actual["model"], MODEL)
        self.assertEqual(len(self.calls), 1)
        request = self.calls[0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("Anthropic-version"), "2023-06-01")
        self.assertIsInstance(build.call_args.args[0], _NoRedirects)
        with self.assertRaisesRegex(SmokeClientError, "redirect_rejected"):
            _NoRedirects().redirect_request(None, None, 302, "redirect", {}, "https://other.example")


if __name__ == "__main__":
    unittest.main()
