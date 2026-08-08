import time
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple

from apps.common.exceptions import (
    SMSGatewayException, SMSGatewayTimeoutException, SMSGatewayAuthException,
    SMSGatewayValidationException, SMSGatewayHTTPException
)
from apps.settings_app.models import SMSGatewayConfig
from .dto import SMSPayload, GatewayResult, BalanceResult, DLRResult

logger = logging.getLogger('apps.sms')

# Draft4SMS Provider Error Code Mapping
DRAFT4SMS_ERROR_CODES = {
    '001': 'Invalid API Key',
    '002': 'Invalid Route',
    '004': 'No Message Found',
    '005': 'Invalid Schedule',
    '006': 'Invalid Date Format',
    '007': 'No Numbers',
    '008': 'Insufficient Credit',
    '009': 'Parent Less Balance',
    '010': 'Campaign Failed',
    '011': 'Message Sent Successfully',
}


class SMSGatewayService:
    """
    Production-grade SMS Gateway service strictly complying with Draft4SMS API provider specifications.
    Supports single & bulk SMS dispatch, DLR tracking, credit balance queries, API key masking,
    and configurable HTTP methods/parameters via SMSGatewayConfig.
    """

    MAX_RETRIES = 3
    DEFAULT_TIMEOUT = 10.0  # seconds

    def __init__(self, config: Optional[SMSGatewayConfig] = None):
        self.config = config or SMSGatewayConfig.get_active_config()

    def _get_active_config(self) -> SMSGatewayConfig:
        if not self.config or not self.config.is_active:
            self.config = SMSGatewayConfig.get_active_config()
            
        if not self.config:
            raise SMSGatewayValidationException("No active SMS Gateway configuration profile found. Please configure settings.")
        return self.config

    @staticmethod
    def mask_api_key(key: str) -> str:
        """Masks sensitive API key string for safe logging and UI display."""
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}****{key[-4:]}"

    def _execute_http_request(
        self,
        url: str,
        method: str,
        params_or_data: Dict[str, Any],
        headers: Dict[str, Any] = None
    ) -> Tuple[int, str, float]:
        """
        Executes HTTP request with exponential backoff retries and API key log masking.
        Returns (status_code, raw_response_text, execution_time_ms).
        """
        config = self._get_active_config()
        timeout_val = float(getattr(config, 'timeout', 10) or 10)
        request_headers = config.http_headers or {}
        if headers:
            request_headers.update(headers)

        masked_params = params_or_data.copy()
        if 'apikey' in masked_params:
            masked_params['apikey'] = self.mask_api_key(str(masked_params['apikey']))

        attempt = 0
        last_exception = None

        while attempt < self.MAX_RETRIES:
            attempt += 1
            start_time = time.time()

            try:
                logger.info(f"GATEWAY_REQ | Attempt {attempt}/{self.MAX_RETRIES} | Method: {method} | URL: {url}")
                logger.debug(f"GATEWAY_PAYLOAD | Params: {masked_params}")

                if method.upper() == 'POST':
                    response = requests.post(url, data=params_or_data, headers=request_headers, timeout=timeout_val)
                else:
                    response = requests.get(url, params=params_or_data, headers=request_headers, timeout=timeout_val)

                exec_time_ms = round((time.time() - start_time) * 1000, 2)
                status_code = response.status_code
                response_text = response.text

                logger.info(f"GATEWAY_RESP | Status: {status_code} | Execution Time: {exec_time_ms}ms")
                logger.debug(f"GATEWAY_RAW_BODY | {response_text[:500]}")

                # Retry on transient 5xx Server Errors
                if status_code >= 500:
                    logger.warning(f"GATEWAY_5XX_ERROR | Attempt {attempt} returned {status_code}. Retrying...")
                    time.sleep(2 ** (attempt - 1))  # Exponential backoff: 1s, 2s, 4s
                    continue

                if status_code in (401, 403):
                    raise SMSGatewayAuthException(
                        "SMS Gateway Authentication failed. Please check your API Key credentials.",
                        status_code=status_code,
                        response_raw=response_text
                    )

                return status_code, response_text, exec_time_ms

            except requests.Timeout as e:
                exec_time_ms = round((time.time() - start_time) * 1000, 2)
                logger.warning(f"GATEWAY_TIMEOUT | Attempt {attempt} timed out after {exec_time_ms}ms.")
                last_exception = SMSGatewayTimeoutException(
                    f"SMS Gateway request timed out after {self.DEFAULT_TIMEOUT}s.",
                    response_raw=str(e)
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(2 ** (attempt - 1))
            except requests.RequestException as e:
                exec_time_ms = round((time.time() - start_time) * 1000, 2)
                logger.error(f"GATEWAY_HTTP_ERR | Attempt {attempt} failed: {str(e)}")
                last_exception = SMSGatewayHTTPException(f"HTTP request error: {str(e)}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(2 ** (attempt - 1))

        if last_exception:
            raise last_exception
        raise SMSGatewayException(f"Gateway request failed after {self.MAX_RETRIES} attempts.")

    def send_single(self, payload: SMSPayload) -> GatewayResult:
        """
        Dispatches a single SMS complying strictly with Draft4SMS API specification.
        Endpoint: https://text.draft4sms.com/vb/apikey.php
        Required params: apikey, senderid, number, message
        Optional params: templateid, unicode, format=json
        """
        config = self._get_active_config()
        url = config.api_url or "https://text.draft4sms.com/vb/apikey.php"

        # Check Unicode encoding
        is_unicode = '1' if any(ord(c) > 127 for c in payload.message_text) else '0'

        data = {
            'apikey': config.api_key,
            'senderid': payload.header_sender_id or config.default_sender_id,
            'number': payload.mobile_number,
            'message': payload.message_text,
            'templateid': payload.dlt_template_id,
            'unicode': is_unicode,
            'format': getattr(config, 'response_format', 'json') or 'json'
        }

        try:
            status_code, raw_response, exec_time = self._execute_http_request(
                url=url,
                method=config.request_method or 'POST',
                params_or_data=data
            )

            parsed = self._parse_send_response(raw_response)
            
            return GatewayResult(
                success=parsed['success'],
                gateway_message_id=parsed['messageid'],
                status_code=status_code,
                raw_response=raw_response,
                execution_time_ms=exec_time,
                error_message=parsed['error_message'],
                totnumber=parsed['totnumber'],
                totalcredit=parsed['totalcredit']
            )

        except SMSGatewayException as e:
            return GatewayResult(
                success=False,
                status_code=getattr(e, 'status_code', None),
                raw_response=getattr(e, 'response_raw', str(e)),
                error_message=e.message
            )

    def send_bulk(self, payloads: List[SMSPayload]) -> List[GatewayResult]:
        results = []
        for payload in payloads:
            res = self.send_single(payload)
            results.append(res)
        return results

    def get_balance(self) -> BalanceResult:
        """
        Queries credit balance complying with Draft4SMS Balance API.
        Endpoint: https://text.draft4sms.com/vb/http-credit.php
        Params: apikey, route_id, format=json
        """
        config = self._get_active_config()
        url = config.balance_api_url or "https://text.draft4sms.com/vb/http-credit.php"

        data = {
            'apikey': config.api_key,
            'route_id': getattr(config, 'route_id', '1') or '1',
            'format': getattr(config, 'response_format', 'json') or 'json'
        }

        try:
            status_code, raw_response, exec_time = self._execute_http_request(
                url=url,
                method='GET',
                params_or_data=data
            )

            balance_val, total_val, error_msg = self._parse_balance_response(raw_response, config=config)
            return BalanceResult(
                success=balance_val != "N/A",
                balance=balance_val,
                total_sms_allowed=total_val,
                gateway_name=config.provider_name,
                response_time_ms=exec_time,
                raw_response=raw_response,
                error_message=error_msg
            )
        except SMSGatewayException as e:
            config_total = str(config.total_sms_allowed).strip() if config and getattr(config, 'total_sms_allowed', '') else "N/A"
            return BalanceResult(
                success=False,
                balance="N/A",
                total_sms_allowed=config_total or "N/A",
                gateway_name=config.provider_name if config else "",
                error_message=e.message
            )

    def fetch_dlr(self, gateway_message_id: str) -> DLRResult:
        """
        Queries Delivery Report complying with Draft4SMS DLR API.
        Endpoint: https://text.draft4sms.com/vb/http-dlr.php
        Params: apikey, msgid, format=json
        """
        config = self._get_active_config()
        url = config.dlr_api_url or "https://text.draft4sms.com/vb/http-dlr.php"

        data = {
            'apikey': config.api_key,
            'msgid': gateway_message_id,
            'format': getattr(config, 'response_format', 'json') or 'json'
        }

        try:
            status_code, raw_response, exec_time = self._execute_http_request(
                url=url,
                method='GET',
                params_or_data=data
            )

            dlr_status = self._parse_dlr_response(raw_response)
            return DLRResult(
                success=True,
                gateway_message_id=gateway_message_id,
                dlr_status=dlr_status,
                raw_response=raw_response
            )
        except SMSGatewayException as e:
            return DLRResult(
                success=False,
                gateway_message_id=gateway_message_id,
                dlr_status="UNKNOWN",
                error_message=e.message
            )

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests API endpoint connectivity and response latency (ms).
        """
        config = self._get_active_config()
        start = time.time()
        try:
            res = self.get_balance()
            return {
                'success': res.success,
                'status_code': 200 if res.success else 400,
                'response_time_ms': res.response_time_ms,
                'gateway_name': config.provider_name,
                'balance': res.balance,
                'raw_response': res.raw_response[:200] if res.raw_response else res.error_message
            }
        except SMSGatewayException as e:
            exec_time = round((time.time() - start) * 1000, 2)
            return {
                'success': False,
                'status_code': getattr(e, 'status_code', None),
                'response_time_ms': exec_time,
                'gateway_name': config.provider_name,
                'error_message': e.message
            }

    @staticmethod
    def _parse_send_response(raw_response: str) -> Dict[str, Any]:
        """
        Parses Draft4SMS Send SMS JSON response.
        Success Example:
        {"status": "Success", "code": "011", "messageid": "12345", "totnumber": 1, "totalcredit": 1, "description": "Message Sent Successfully"}
        """
        try:
            data = json.loads(raw_response)
            status = str(data.get('status', '')).strip()
            code = str(data.get('code', '')).strip()
            msg_id = str(data.get('messageid') or data.get('msgid') or '').strip()
            totnumber = int(data.get('totnumber', 1))
            totalcredit = int(data.get('totalcredit', 1))
            desc = str(data.get('description') or data.get('message') or '')

            is_success = (status.lower() == 'success' or code == '011')

            if is_success:
                return {
                    'success': True,
                    'messageid': msg_id or "GW_" + str(int(time.time())),
                    'totnumber': totnumber,
                    'totalcredit': totalcredit,
                    'error_message': None
                }
            else:
                # Map error code to human readable description
                code_desc = DRAFT4SMS_ERROR_CODES.get(code, desc or f"Gateway Error Code {code}")
                return {
                    'success': False,
                    'messageid': None,
                    'totnumber': 0,
                    'totalcredit': 0,
                    'error_message': f"Provider Code [{code}]: {code_desc}"
                }
        except Exception:
            # Fallback for plain text provider responses
            if 'success' in raw_response.lower() or '011' in raw_response:
                return {'success': True, 'messageid': "GW_" + str(int(time.time())), 'totnumber': 1, 'totalcredit': 1, 'error_message': None}
            return {'success': False, 'messageid': None, 'totnumber': 0, 'totalcredit': 0, 'error_message': f"Invalid provider response: {raw_response[:200]}"}

    @staticmethod
    def _parse_balance_response(raw_response: str, config: Optional[SMSGatewayConfig] = None) -> Tuple[str, str, Optional[str]]:
        """
        Parses Draft4SMS Balance API response.
        Returns (balance_val, total_allowed_val, error_message).
        """
        config_total = str(config.total_sms_allowed).strip() if config and getattr(config, 'total_sms_allowed', '') else ""
        try:
            data = json.loads(raw_response)
            balance_val = "N/A"
            if 'balance' in data:
                balance_val = str(data['balance'])
            elif 'credits' in data:
                balance_val = str(data['credits'])
            elif data.get('status', '').lower() == 'success':
                balance_val = str(data.get('credit', '10000'))

            total_val = str(data.get('total_allowed') or data.get('total_credits') or data.get('total') or data.get('allocated') or config_total or "N/A")

            if balance_val != "N/A":
                return balance_val, total_val, None

            code = str(data.get('code', ''))
            desc = DRAFT4SMS_ERROR_CODES.get(code, data.get('description', 'Failed to fetch balance'))
            return "N/A", config_total or "N/A", f"Code [{code}]: {desc}"
        except Exception:
            return "N/A", config_total or "N/A", "Failed to parse balance response"

    @staticmethod
    def _parse_dlr_response(raw_response: str) -> str:
        """Parses Draft4SMS DLR status response."""
        raw_upper = raw_response.upper()
        if 'DELIVERED' in raw_upper or 'DELIVRD' in raw_upper:
            return 'DELIVRD'
        elif 'SUBMITTED' in raw_upper or 'SENT' in raw_upper:
            return 'SUBMITTED'
        elif 'FAILED' in raw_upper:
            return 'FAILED'
        elif 'REJECTED' in raw_upper or 'REJECTD' in raw_upper:
            return 'REJECTED'
        return 'UNKNOWN'
