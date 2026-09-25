"""Fixed enumerations from CONTEXT.md and the AMIS build spec."""

from enum import Enum


class RequestStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    DROPPED = "dropped"
    EXPIRED = "expired"


class ActionStatus(str, Enum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"


class EventType(str, Enum):
    CLOUD_BLOCK = "CLOUD_BLOCK"
    BATTERY_DROP = "BATTERY_DROP"
    EMERGENCY_TASK = "EMERGENCY_TASK"
    COMMUNICATION_OUTAGE = "COMMUNICATION_OUTAGE"
    SATELLITE_UNAVAILABLE = "SATELLITE_UNAVAILABLE"


class PlanChangeType(str, Enum):
    UNCHANGED = "UNCHANGED"
    MOVED = "MOVED"
    INSERTED = "INSERTED"
    DROPPED = "DROPPED"
    COMPLETED = "COMPLETED"


class ReasonCode(str, Enum):
    WINDOW_INVALIDATED = "WINDOW_INVALIDATED"
    INSUFFICIENT_BATTERY = "INSUFFICIENT_BATTERY"
    INSUFFICIENT_STORAGE = "INSUFFICIENT_STORAGE"
    DEADLINE_VIOLATION = "DEADLINE_VIOLATION"
    TIME_OVERLAP = "TIME_OVERLAP"
    SATELLITE_UNAVAILABLE = "SATELLITE_UNAVAILABLE"
    DISPLACED_BY_COMPETING_REQUEST = "DISPLACED_BY_COMPETING_REQUEST"
    ALTERNATIVE_WINDOW_AVAILABLE = "ALTERNATIVE_WINDOW_AVAILABLE"
    NO_ALTERNATIVE_WINDOW = "NO_ALTERNATIVE_WINDOW"
    REQUEST_UNCHANGED = "REQUEST_UNCHANGED"
    # In the SRD 6 minimum vocabulary but previously missing here: the
    # correct cause for a request that entered the pool after the
    # previous plan (an emergency request) and was scheduled in this
    # one. Without it, compare_plans had no way to describe an insertion
    # honestly and fell back to ALTERNATIVE_WINDOW_AVAILABLE, which
    # asserts a cause (a freed window) that did not happen (GAP-10).
    HIGHER_PRIORITY_TASK_INSERTED = "HIGHER_PRIORITY_TASK_INSERTED"
