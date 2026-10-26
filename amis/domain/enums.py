"""Fixed enumerations from CONTEXT.md and the AMIS build spec."""

from enum import Enum


class RequestStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    DROPPED = "dropped"
    EXPIRED = "expired"
    SATISFIED_BY_ARCHIVE = "satisfied_by_archive"


class ActionStatus(str, Enum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"


class ActionKind(str, Enum):
    IMAGING = "imaging"
    DOWNLINK = "downlink"


class EventType(str, Enum):
    REQUEST_SATISFIED_BY_ARCHIVE = "REQUEST_SATISFIED_BY_ARCHIVE"
    CLOUD_BLOCK = "CLOUD_BLOCK"
    BATTERY_DROP = "BATTERY_DROP"
    EMERGENCY_TASK = "EMERGENCY_TASK"
    COMMUNICATION_OUTAGE = "COMMUNICATION_OUTAGE"
    SATELLITE_UNAVAILABLE = "SATELLITE_UNAVAILABLE"


class PlanChangeType(str, Enum):
    SATISFIED_BY_ARCHIVE = "SATISFIED_BY_ARCHIVE"
    UNCHANGED = "UNCHANGED"
    MOVED = "MOVED"
    INSERTED = "INSERTED"
    DROPPED = "DROPPED"
    COMPLETED = "COMPLETED"


class ReasonCode(str, Enum):
    SATISFIED_BY_ARCHIVE = "SATISFIED_BY_ARCHIVE"
    WINDOW_INVALIDATED = "WINDOW_INVALIDATED"
    INSUFFICIENT_BATTERY = "INSUFFICIENT_BATTERY"
    INSUFFICIENT_STORAGE = "INSUFFICIENT_STORAGE"
    DEADLINE_VIOLATION = "DEADLINE_VIOLATION"
    TIME_OVERLAP = "TIME_OVERLAP"
    SATELLITE_UNAVAILABLE = "SATELLITE_UNAVAILABLE"
    DISPLACED_BY_COMPETING_REQUEST = "DISPLACED_BY_COMPETING_REQUEST"
    ALTERNATIVE_WINDOW_AVAILABLE = "ALTERNATIVE_WINDOW_AVAILABLE"
    NO_ALTERNATIVE_WINDOW = "NO_ALTERNATIVE_WINDOW"
    NO_OBSERVATION_WINDOW = "NO_OBSERVATION_WINDOW"
    REQUEST_UNCHANGED = "REQUEST_UNCHANGED"
    # In the SRD 6 minimum vocabulary but previously missing here: the
    # correct cause for a request that entered the pool after the
    # previous plan (an emergency request) and was scheduled in this
    # one. Without it, compare_plans had no way to describe an insertion
    # honestly and fell back to ALTERNATIVE_WINDOW_AVAILABLE, which
    # asserts a cause (a freed window) that did not happen (GAP-10).
    HIGHER_PRIORITY_TASK_INSERTED = "HIGHER_PRIORITY_TASK_INSERTED"
    REBALANCED_FOR_REQUESTER_SHARE = "REBALANCED_FOR_REQUESTER_SHARE"
