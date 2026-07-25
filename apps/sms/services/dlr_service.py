import logging
from django.utils import timezone
from apps.logs.models import SMSLog
from apps.sms.models import SMSQueue, SMSStatusChoices
from .gateway_service import SMSGatewayService

logger = logging.getLogger('apps.sms')


class DLRService:
    """
    Service responsible for querying delivery status from the SMS Gateway and synchronizing SMSLog & SMSQueue records.
    """

    @staticmethod
    def sync_dlr_status_for_message(gateway_message_id: str) -> bool:
        """
        Fetches delivery status from Gateway DLR API and updates corresponding SMSLog & SMSQueue records.
        """
        if not gateway_message_id:
            return False

        gateway_service = SMSGatewayService()
        dlr_res = gateway_service.fetch_dlr(gateway_message_id)

        if not dlr_res.success:
            logger.warning(f"DLR_SYNC_FAILED | Failed to fetch DLR for message '{gateway_message_id}': {dlr_res.error_message}")
            return False

        status_str = dlr_res.dlr_status
        now = timezone.now()

        # Update SMSLog
        logs_updated = SMSLog.objects.filter(gateway_message_id=gateway_message_id).update(
            dlr_status=status_str,
            dlr_timestamp=now,
            status=SMSStatusChoices.DELIVERED if status_str == 'DELIVRD' else (SMSStatusChoices.FAILED if status_str in ('REJECTD', 'UNDELIV') else SMSStatusChoices.SENT)
        )

        # Update SMSQueue if present
        queue_updated = SMSQueue.objects.filter(gateway_message_id=gateway_message_id).update(
            status=SMSStatusChoices.DELIVERED if status_str == 'DELIVRD' else (SMSStatusChoices.FAILED if status_str in ('REJECTD', 'UNDELIV') else SMSStatusChoices.SENT)
        )

        logger.info(f"DLR_SYNC_SUCCESS | Message ID: '{gateway_message_id}' -> DLR Status: '{status_str}' (Logs updated: {logs_updated}, Queue updated: {queue_updated})")
        return True
