"""Conservative, persistent dispatch accounting for explicitly capped live runs."""
from __future__ import annotations

LIVE_BUDGET_VERSION = "acceptance-ledger-v2"


def budget_capabilities() -> dict[str, bool]:
    """Safety claims checked by the in-process live-run preflight."""
    return {
        "request_cap": True,
        "cost_reservation": True,
        "unknown_outcome_halts": True,
        "no_automatic_retry": True,
    }

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

INPUT_PER_MILLION=.40
OUTPUT_PER_MILLION=1.60


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


# A live acceptance run refuses an unknown configured model rather than
# guessing pricing.  This is deliberately separate from model selection.
MODEL_PRICING: dict[str, ModelPricing] = {
    "gpt-4.1-mini": ModelPricing(INPUT_PER_MILLION, OUTPUT_PER_MILLION),
}

def usd(input_tokens:int, output_tokens:int)->float:
    return input_tokens*INPUT_PER_MILLION/1_000_000 + output_tokens*OUTPUT_PER_MILLION/1_000_000
def reserve(text_characters:int, image_count:int, max_output_tokens:int, image_tokens:int=10_000)->float:
    return usd(text_characters//2 + image_count*image_tokens, max_output_tokens)
def consumed(dispatches:list[dict])->float:
    return sum(float(x.get('estimated_upper_cost_usd',0)) for x in dispatches)
def eligible(dispatches:list[dict], batch:int, cap:int, budget:float, next_cost:float)->bool:
    attempted={x['batch'] for x in dispatches if x.get('status') in {'SUCCEEDED','FAILED','OUTCOME_UNKNOWN','DISPATCH_STARTED'}}
    return batch not in attempted and len(dispatches)<cap and consumed(dispatches)+next_cost<=budget


class AcceptanceDispatchLedger:
    """One-run, no-retry guard for a user-authorized acceptance exercise.

    Every request is first written as ``DISPATCH_STARTED`` with an unrecoverable
    reservation.  An exception leaves the event ``OUTCOME_UNKNOWN``: no code
    path silently retries it, because the provider may have received it.
    """
    def __init__(self, path: Path, *, run_id: str, model: str, request_cap: int = 5,
                 budget_cap_usd: float = .15) -> None:
        if model not in MODEL_PRICING:
            raise RuntimeError(f"No verified pricing configuration for configured model {model!r}")
        self.path, self.run_id, self.model = path, run_id, model
        self.request_cap, self.budget_cap_usd = request_cap, budget_cap_usd
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            if self.data.get("run_id") != run_id or self.data.get("model") != model:
                raise RuntimeError("dispatch ledger identity does not match requested acceptance run")
        else:
            self.data = {"schema_version": "live-acceptance-ledger-v1", "run_id": run_id,
                         "model": model, "request_cap": request_cap,
                         "budget_cap_usd": budget_cap_usd, "dispatches": []}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def dispatches(self) -> list[dict[str, Any]]:
        return self.data["dispatches"]

    def _pricing(self) -> ModelPricing:
        return MODEL_PRICING[self.model]

    def _halted_by_prior_failure(self) -> str | None:
        """Return the previous fail-stop state, if the run cannot continue."""
        for item in self.dispatches:
            if item.get("status") in {"OUTCOME_UNKNOWN", "COMPLETED_INVALID_RESPONSE"}:
                return str(item["status"])
        return None

    def _estimate(self, input_characters: int, output_limit: int) -> tuple[int, float]:
        # A conservative, deliberately simple bound used before dispatch.
        input_tokens = (max(input_characters, 0) + 1) // 2
        price = self._pricing()
        cost = input_tokens * price.input_per_million / 1_000_000 + output_limit * price.output_per_million / 1_000_000
        return input_tokens, cost

    def call(self, *, dispatch_id: str, stage: str, input_text: str, input_token_ceiling: int,
             output_token_ceiling: int, invoke: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        # An uncertain request may have reached the provider.  This is a
        # run-wide fail-stop, not merely a same-dispatch retry guard.
        prior_failure = self._halted_by_prior_failure()
        if prior_failure:
            raise RuntimeError(f"live acceptance halted after prior {prior_failure} dispatch; operator resolution is required")
        if len(input_text) == 0:
            raise RuntimeError(f"{stage} has no input evidence; refusing dispatch")
        estimated_input, reservation = self._estimate(len(input_text), output_token_ceiling)
        if estimated_input > input_token_ceiling:
            raise RuntimeError(f"{stage} input ceiling exceeded ({estimated_input} > {input_token_ceiling})")
        previous = next((item for item in self.dispatches if item["dispatch_id"] == dispatch_id), None)
        if previous:
            if previous["status"] == "SUCCEEDED":
                raise RuntimeError(f"{stage} was already dispatched; checkpoint must be loaded instead")
            raise RuntimeError(f"{stage} has prior {previous['status']} outcome; refusing automatic redispatch")
        if len(self.dispatches) >= self.request_cap:
            raise RuntimeError("live acceptance request cap exhausted")
        committed = sum(float(item.get("actual_cost_usd", item.get("reserved_cost_usd", 0)))
                        if item.get("status") == "SUCCEEDED" else float(item.get("reserved_cost_usd", 0))
                        for item in self.dispatches)
        if committed + reservation > self.budget_cap_usd:
            raise RuntimeError(f"live acceptance budget cap would be exceeded ({committed + reservation:.6f} > {self.budget_cap_usd:.2f})")
        event = {"dispatch_id": dispatch_id, "stage": stage, "status": "DISPATCH_STARTED",
                 "started_at": datetime.now(timezone.utc).isoformat(), "model": self.model,
                 "input_token_ceiling": input_token_ceiling, "output_token_ceiling": output_token_ceiling,
                 "estimated_input_tokens": estimated_input, "reserved_cost_usd": reservation}
        self.dispatches.append(event); self._save()
        try:
            response = invoke()
            metadata = response.get("_response_metadata", {}) if isinstance(response, dict) else {}
            input_tokens = metadata.get("input_tokens")
            output_tokens = metadata.get("output_tokens")
            price = self._pricing()
            actual = (input_tokens or 0) * price.input_per_million / 1_000_000 + (output_tokens or 0) * price.output_per_million / 1_000_000
            event.update({"status": "SUCCEEDED", "ended_at": datetime.now(timezone.utc).isoformat(),
                          "request_id": metadata.get("request_id"), "actual_input_tokens": input_tokens,
                          "actual_output_tokens": output_tokens, "actual_cost_usd": actual,
                          "reconciled_cost_usd": actual})
            metadata.update({"dispatch_id": dispatch_id, "execution": "ONLINE",
                             "reserved_cost_usd": reservation, "actual_cost_usd": actual})
            response["_response_metadata"] = metadata
            self._save()
            return response
        except Exception as exc:
            # Parsing can fail *after* the provider returned a response.  It
            # must still fail-stop, but is not an uncertain network dispatch.
            known_response = bool(getattr(exc, "response_received", False))
            event.update({"status": "COMPLETED_INVALID_RESPONSE" if known_response else "OUTCOME_UNKNOWN",
                          "ended_at": datetime.now(timezone.utc).isoformat(),
                          "error_type": type(exc).__name__, "error": str(exc)[:500]})
            if known_response:
                event["error_category"] = getattr(exc, "category", "INVALID_RESPONSE")
                metadata = getattr(exc, "response_metadata", None)
                if isinstance(metadata, dict):
                    event["response_metadata"] = metadata
            self._save()
            raise
