"""Recorded prediction and explicit simulation policy; no runtime source lookup."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import math
from typing import Any


@dataclass(frozen=True)
class ConjunctionEvidence:
    source: str
    encounter_id: str
    matched_norad_id: int
    counterpart_norad_id: int
    tca: datetime
    miss_distance_km: float
    maximum_probability: float
    threshold: float
    policy_version: str
    pre_padding_s: float
    post_padding_s: float

    def validate(self, start: datetime, end: datetime) -> None:
        for name in ("source", "encounter_id", "policy_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"conjunction {name} must be a nonempty, trimmed string")
        if self.policy_version != "socrates-outage-v1":
            raise ValueError("unsupported conjunction policy version")
        for name in ("matched_norad_id", "counterpart_norad_id"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"conjunction {name} must be a positive integer")
        if self.matched_norad_id == self.counterpart_norad_id:
            raise ValueError("conjunction counterpart must differ from matched identity")
        for name in ("miss_distance_km", "maximum_probability", "threshold", "pre_padding_s", "post_padding_s"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"conjunction {name} must be finite")
        if self.miss_distance_km < 0 or not 0 <= self.threshold <= self.maximum_probability <= 1:
            raise ValueError("conjunction distance/probability must be ranged and qualify at the threshold")
        if self.pre_padding_s <= 0 or self.post_padding_s <= 0:
            raise ValueError("conjunction padding must be positive")
        if not isinstance(self.tca, datetime) or self.tca.utcoffset() != timedelta(0):
            raise ValueError("conjunction TCA must be UTC")
        if (start != self.tca - timedelta(seconds=self.pre_padding_s)
                or end != self.tca + timedelta(seconds=self.post_padding_s)):
            raise ValueError("conjunction interval must equal TCA minus/plus padding")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "tca": self.tca.isoformat()}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ConjunctionEvidence":
        return ConjunctionEvidence(**{**data, "tca": datetime.fromisoformat(data["tca"])})
