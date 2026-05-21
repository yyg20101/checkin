from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal


ResultStatus = Literal["success", "failed", "skipped"]


@dataclass(frozen=True)
class CheckinResult:
    status: ResultStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str, details: dict[str, Any] | None = None) -> "CheckinResult":
        return cls(status="success", message=message, details=details or {})

    @classmethod
    def failed(cls, message: str, details: dict[str, Any] | None = None) -> "CheckinResult":
        return cls(status="failed", message=message, details=details or {})

    @classmethod
    def skipped(cls, message: str, details: dict[str, Any] | None = None) -> "CheckinResult":
        return cls(status="skipped", message=message, details=details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }

    def to_summary_line(self) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"[CHECKIN_SUMMARY] {payload}"
