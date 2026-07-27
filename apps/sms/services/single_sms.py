import logging
from typing import Tuple, Dict, Any

from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.dlt_templates.models import DLTTemplate
from apps.users.models import Department
from apps.logs.models import SMSLog
from apps.sms.models import SMSStatusChoices
from .gateway_service import SMSGatewayService
from .dto import SMSPayload, GatewayResult

logger = logging.getLogger('apps.sms')


class SingleSMSService:
    """
    Business service handling single SMS validation, dynamic variable interpolation,
    gateway API dispatching, and audit logging persistence.
    """

    @classmethod
    def process_and_send(
        cls,
        user: CustomUser,
        mobile_number: str,
        template: DLTTemplate,
        variable_values: Dict[str, str],
        department: Department = None
    ) -> Tuple[bool, SMSLog, GatewayResult]:

        dept = department or user.department

        # 1. Render final interpolated text message
        final_message_text = template.preview_message(variable_values)
        
        # 2. Calculate SMS credit units
        credit_units = DLTTemplate.calculate_sms_credits(final_message_text)

        # 3. Build DTO payload for SMSGatewayService
        payload = SMSPayload(
            mobile_number=mobile_number,
            message_text=final_message_text,
            dlt_template_id=template.dlt_template_id,
            entity_id=template.entity_id,
            header_sender_id=template.header_sender_id
        )

        # 4. Dispatch via SMSGatewayService
        gateway_service = SMSGatewayService()
        gw_result = gateway_service.send_single(payload)

        # 5. Determine dispatch status
        status = SMSStatusChoices.SENT if gw_result.success else SMSStatusChoices.FAILED

        # 6. Save immutable SMSLog entry
        log_entry = SMSLog.objects.create(
            user=user,
            department=dept,
            template=template,
            mobile_number=mobile_number,
            message_content=final_message_text,
            status=status,
            credit_units=credit_units,
            gateway_message_id=gw_result.gateway_message_id,
            gateway_status_code=str(gw_result.status_code or ''),
            gateway_response_raw=gw_result.raw_response or gw_result.error_message
        )

        logger.info(
            f"SINGLE_SMS_DISPATCH | User: '{user.username}' | Mobile: '{mobile_number}' | "
            f"Template ID: '{template.dlt_template_id}' | Status: '{status}' | GW Msg ID: '{gw_result.gateway_message_id}'"
        )

        return gw_result.success, log_entry, gw_result
