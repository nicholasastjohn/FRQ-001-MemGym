"""Strict, bounded direct-Anthropic client for a small engineering smoke run.

No retries, endpoint overrides, tools, caching or model substitutions are used.
The caller owns the fresh run directory and must supply an authorized API key.
Cost reservations use the model's full input context, not a tokenizer estimate.
"""

from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.request


MODEL = "claude-sonnet-4-5-20250929"
SONNET46_MODEL = "claude-sonnet-4-6"
ENDPOINT = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MAX_INPUT_TOKENS = 200000
MAX_OUTPUT_TOKENS = 1024
INPUT_USD_PER_MILLION = Decimal("3")
OUTPUT_USD_PER_MILLION = Decimal("15")
RESERVATION_USD = (MAX_INPUT_TOKENS * INPUT_USD_PER_MILLION
                   + MAX_OUTPUT_TOKENS * OUTPUT_USD_PER_MILLION) / Decimal(1000000)


class SmokeClientError(RuntimeError):
    """An intentionally non-sensitive failure code; no provider error body."""


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SmokeClientError("redirect_rejected")


def _transport(payload, api_key):
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "anthropic-version": API_VERSION})
    # A fresh opener does not follow redirects or install a retrying SDK.
    opener = urllib.request.build_opener(_NoRedirects())
    with opener.open(request, timeout=90) as response:
        return json.loads(response.read(2 * 1024 * 1024))


def _object(text):
    """Read one JSON object, including a single trailing object after prose.

    Real responses can explain their reasoning before the requested JSON. Keep
    that raw response in the trace; this parser only recovers the contract. More
    than one competing JSON output is ambiguous and must not be cherry-picked;
    inline citation arrays inside prose are not alternative outputs.
    """
    if not isinstance(text, str):
        raise SmokeClientError("malformed_json")
    text = text.strip()
    try:
        value = json.loads(text, parse_constant=lambda _: None)
    except ValueError:
        value = None
    else:
        if isinstance(value, dict):
            return value
        raise SmokeClientError("non_object_json")
    candidate_text = text[:-3].rstrip() if text.endswith("```") else text
    decoder = json.JSONDecoder(parse_constant=lambda _: None)
    containers = []
    index = 0
    while index < len(candidate_text):
        if candidate_text[index] not in "{[":
            index += 1
            continue
        try:
            candidate, end = decoder.raw_decode(candidate_text, index)
        except ValueError:
            index += 1
            continue
        containers.append((candidate, index, end))
        index = end  # Nested objects inside one complete container are not alternatives.
    objects = [item for item in containers if isinstance(item[0], dict)]
    competing_arrays = []
    for item in containers:
        candidate, start, end = item
        if not isinstance(candidate, list):
            continue
        line_start = candidate_text.rfind("\n", 0, start) + 1
        line_end = candidate_text.find("\n", end)
        if line_end < 0:
            line_end = len(candidate_text)
        if not candidate_text[line_start:start].strip() and not candidate_text[end:line_end].strip():
            competing_arrays.append(item)
    # Inline references such as Document[36] are prose citations, not alternate
    # JSON outputs. A standalone JSON array still competes with another output.
    if len(objects) + len(competing_arrays) > 1:
        raise SmokeClientError("ambiguous_json")
    if not objects:
        if containers and not candidate_text[containers[-1][2]:].strip():
            raise SmokeClientError("non_object_json")
        raise SmokeClientError("malformed_json")
    if candidate_text[objects[0][2]:].strip():
        raise SmokeClientError("malformed_json")
    return objects[0][0]


class StrictAnthropicClient:
    """Duck-typed upstream evaluator client with per-attempt cost reservation.

    `transport` is an injectable test fixture, never a CLI endpoint setting.
    Reservations remain consumed on every failure, and the client becomes failed
    after any attempted request fails. Unknown billing is never counted as zero.
    This is a single-owner sequential client, not a concurrent request scheduler.
    """

    def __init__(self, *, api_key, trace_path, max_cost_usd=Decimal("5"),
                 max_calls=6, transport=None, model=MODEL, prior_reservation_usd=Decimal("0"),
                 minimum_request_interval_seconds=0):
        try:
            maximum = Decimal(str(max_cost_usd))
            prior = Decimal(str(prior_reservation_usd))
        except Exception:
            raise ValueError("Invalid cost ceiling") from None
        if not maximum.is_finite() or not Decimal("0") < maximum <= Decimal("5"):
            raise ValueError("Cost ceiling must be positive and at most 5 USD")
        if type(max_calls) is not int or not 1 <= max_calls <= 6:
            raise ValueError("Call ceiling must be between one and six")
        if not prior.is_finite() or not Decimal("0") <= prior <= maximum:
            raise ValueError("Prior reservation must be nonnegative and within the cost ceiling")
        if model not in (MODEL, SONNET46_MODEL):
            raise ValueError("Unsupported model; no automatic substitution is permitted")
        try:
            interval = float(minimum_request_interval_seconds)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Invalid minimum request interval") from None
        if type(minimum_request_interval_seconds) is bool or not math.isfinite(interval) or not 0 <= interval <= 300:
            raise ValueError("Minimum request interval must be finite and between zero and 300 seconds")
        if not isinstance(api_key, str) or not api_key.strip() or any(c.isspace() for c in api_key):
            raise ValueError("A nonblank API key without whitespace is required")
        self.model = model
        self._settle_success = model == SONNET46_MODEL
        self._max_input_tokens = 1000000 if self._settle_success else MAX_INPUT_TOKENS
        self._reservation = (self._max_input_tokens * INPUT_USD_PER_MILLION
                             + MAX_OUTPUT_TOKENS * OUTPUT_USD_PER_MILLION) / Decimal(1000000)
        self._api_key = api_key
        self._transport = transport or _transport
        self._maximum, self._max_calls = maximum, max_calls
        self._attempted = self._completed = 0
        self._usage_accounted = 0
        self._reserved = self._known_cost = Decimal("0")
        self._prior, self._gross_reserved = prior, Decimal("0")
        self._interval, self._last_request_started = interval, None
        self._failed = False
        self._trace = Path(trace_path)
        self._trace.parent.mkdir(parents=True, exist_ok=True)
        with self._trace.open("x", encoding="utf-8"):
            pass

    def summary(self):
        return {"attempted_calls": self._attempted, "completed_calls": self._completed,
                "maximum_calls": self._max_calls, "approved_ceiling_usd": str(self._maximum),
                "reserved_cost_usd": str(self._prior + self._reserved),
                "budget_held_usd": str(self._prior + self._reserved),
                "prior_reservation_usd": str(self._prior),
                "new_run_held_usd": str(self._reserved),
                "gross_new_reservations_usd": str(self._gross_reserved),
                "per_request_reservation_usd": str(self._reservation),
                "minimum_request_interval_seconds": self._interval,
                "known_usage_cost_usd": str(self._known_cost),
                "billing_uncertain": self._prior > 0 or self._attempted != self._usage_accounted,
                "failed": self._failed, "model": self.model, "api_version": API_VERSION,
                "cost_basis": "Uncached standard input/output token rates; estimates, not invoices"}

    def _record(self, record):
        with self._trace.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()

    def _response(self, response):
        if not isinstance(response, dict) or response.get("model") != self.model:
            raise SmokeClientError("unexpected_response_model")
        if response.get("stop_reason") != "end_turn":
            raise SmokeClientError("incomplete_or_refused_response")
        if isinstance(response.get("stop_details"), dict) and response["stop_details"].get("type") == "refusal":
            raise SmokeClientError("refused_response")
        if response.get("service_tier") not in (None, "standard"):
            raise SmokeClientError("unsupported_service_tier")
        blocks = response.get("content")
        if not isinstance(blocks, list) or not blocks or any(
                not isinstance(block, dict) or block.get("type") != "text"
                or not isinstance(block.get("text"), str) for block in blocks):
            raise SmokeClientError("non_text_response")
        text = "".join(block["text"] for block in blocks)
        if not text.strip():
            raise SmokeClientError("empty_response")
        usage = response.get("usage")
        if not isinstance(usage, dict):
            raise SmokeClientError("missing_usage")
        for key in ("input_tokens", "output_tokens"):
            if type(usage.get(key)) is not int or usage[key] < 0:
                raise SmokeClientError("invalid_usage")
        if usage["input_tokens"] > self._max_input_tokens or usage["output_tokens"] > MAX_OUTPUT_TOKENS:
            raise SmokeClientError("usage_exceeds_reserved_limits")
        ordinary_metadata = {"service_tier": (None, "standard"),
                             "speed": (None, "standard"),
                             "inference_geo": (None, "global")}
        zero_nested = {
            "server_tool_use": {"web_fetch_requests", "web_search_requests"},
            "output_tokens_details": {"thinking_tokens"},
            "cache_creation": {"ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens"},
        }
        for key, value in usage.items():
            if key in ("input_tokens", "output_tokens"):
                continue
            if key in ordinary_metadata and value in ordinary_metadata[key]:
                continue
            if key in ("cache_creation_input_tokens", "cache_read_input_tokens") and (
                    value is None or type(value) is int and value == 0):
                continue
            if key in zero_nested:
                if value is None or (isinstance(value, dict) and set(value) <= zero_nested[key]
                                     and all(type(n) is int and n == 0 for n in value.values())):
                    continue
            # Reject unknown billable usage instead of assigning it a zero cost.
            raise SmokeClientError("unsupported_usage_component")
        selected = {"id": response.get("id"), "model": self.model,
                    "stop_reason": "end_turn", "content": text,
                    "usage": json.loads(json.dumps(usage, allow_nan=False))}
        if not isinstance(selected["id"], str) or not selected["id"]:
            raise SmokeClientError("missing_response_id")
        return text, selected

    def _complete(self, prompt, role, temperature):
        if self._failed:
            raise SmokeClientError("client_already_failed")
        if not isinstance(prompt, str) or not prompt.strip() or temperature != 0:
            raise SmokeClientError("unsupported_request")
        if self._attempted >= self._max_calls or self._prior + self._reserved + self._reservation > self._maximum:
            raise SmokeClientError("approval_limit_reached")
        if self._last_request_started is not None and self._interval:
            while True:
                remaining = self._last_request_started + self._interval - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 10))
        payload = {"model": self.model, "max_tokens": MAX_OUTPUT_TOKENS, "temperature": 0,
                   "service_tier": "standard_only",
                   "messages": [{"role": "user", "content": prompt}]}
        if self._settle_success:
            payload["thinking"] = {"type": "disabled"}
        if role == "judge":
            payload["system"] = "You must respond with valid JSON."
        self._attempted += 1
        self._reserved += self._reservation
        self._gross_reserved += self._reservation
        record = {"kind": "request", "call": self._attempted, "role": role,
                  "model": self.model, "api_version": API_VERSION,
                  "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "prompt_utf8_bytes": len(prompt.encode()), "max_output_tokens": MAX_OUTPUT_TOKENS,
                  "reserved_cost_usd": str(self._reservation),
                  "budget_held_usd": str(self._prior + self._reserved)}
        self._record(record)  # If recording fails, transport is never invoked.
        start = time.monotonic()
        self._last_request_started = start
        try:
            try:
                raw = self._transport(payload, self._api_key)
            except urllib.error.HTTPError as error:
                # Status alone is useful for auth/rate-limit diagnosis; the URL,
                # headers and provider error body may contain sensitive data.
                error.close()
                raise SmokeClientError(f"http_{error.code}") from None
            except Exception:
                raise SmokeClientError("transport_failure") from None
            text, selected = self._response(raw)
            cost = (selected["usage"]["input_tokens"] * INPUT_USD_PER_MILLION
                    + selected["usage"]["output_tokens"] * OUTPUT_USD_PER_MILLION) / Decimal(1000000)
            self._known_cost += cost
            self._usage_accounted += 1
            response_record = {"kind": "response", "call": self._attempted, "role": role,
                               **selected, "usage_cost_usd": str(cost),
                               "elapsed_seconds": round(time.monotonic() - start, 6)}
            self._record(response_record)
            value = _object(text)
            if role == "answer":
                if not isinstance(value.get("answer"), str) or not value["answer"].strip():
                    raise SmokeClientError("invalid_answer")
            else:
                score = value.get("score")
                if type(score) not in (float, int) or not 0 <= score <= 1 or not math.isfinite(score):
                    raise SmokeClientError("invalid_judge_score")
                if not isinstance(value.get("explanation"), str) or not value["explanation"].strip():
                    raise SmokeClientError("invalid_judge_explanation")
            release = self._reservation - cost if self._settle_success else Decimal("0")
            held_after = self._reserved - release
            if self._settle_success:
                self._record({"kind": "settlement", "call": self._attempted, "role": role,
                              "released_reservation_usd": str(release),
                              "budget_held_usd": str(self._prior + held_after)})
            self._reserved = held_after
            self._completed += 1
            return text, value
        except SmokeClientError as error:
            self._failed = True
            self._record({"kind": "error", "call": self._attempted, "role": role,
                          "error_code": error.args[0],
                          "elapsed_seconds": round(time.monotonic() - start, 6),
                          "reservation_retained": True})
            raise

    def get_completion(self, prompt, temperature=0.0):
        return self._complete(prompt, "answer", temperature)[0]

    def get_json_completion(self, prompt, response_format=None, temperature=0.0):
        # The unchanged upstream supplies its JSON schema here; strict local
        # validation enforces its score/explanation contract on returned text.
        return self._complete(prompt, "judge", temperature)[1]
