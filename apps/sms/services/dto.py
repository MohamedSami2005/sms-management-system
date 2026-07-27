from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class SMSPayload:
    mobile_number: str
    message_text: str
    dlt_template_id: str
    entity_id: str
    header_sender_id: str
    custom_ref: Optional[str] = None


@dataclass
class GatewayResult:
    success: bool
    gateway_message_id: Optional[str] = None
    status_code: Optional[int] = None
    raw_response: Optional[str] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    totnumber: int = 1
    totalcredit: int = 1


@dataclass
class BalanceResult:
    success: bool
    balance: str = "N/A"
    gateway_name: str = ""
    response_time_ms: float = 0.0
    raw_response: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DLRResult:
    success: bool
    gateway_message_id: str = ""
    dlr_status: str = "UNKNOWN"
    raw_response: Optional[str] = None
    error_message: Optional[str] = None
