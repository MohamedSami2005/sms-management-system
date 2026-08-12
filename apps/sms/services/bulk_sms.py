import time
import logging
from typing import List, Dict, Any, Tuple

from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.users.models import Department, Staff
from apps.dlt_templates.models import DLTTemplate
from apps.sms.models import SMSBatch, SMSStatusChoices
from apps.logs.models import SMSLog
from .single_sms import SingleSMSService
from .field_mapper import StaffFieldMapper

logger = logging.getLogger('apps.sms')


class BulkSMSService:
    """
    Personalized Bulk Staff SMS Engine.
    Iterates over selected staff recipients, resolves mapped database fields & static values
    individually per recipient using StaffFieldMapper, and dispatches via SingleSMSService.
    """

    @classmethod
    def execute_bulk_dispatch(
        cls,
        user: CustomUser,
        staff_user_ids: List[int],
        template: DLTTemplate,
        mapping_config: Dict[str, Dict[str, str]],
        department: Department = None,
        existing_batch: SMSBatch = None,
        excel_rows: List[Dict[str, Any]] = None
    ) -> Tuple[SMSBatch, Dict[str, Any]]:
        """
        Loops through all selected staff members or imported Excel rows, generates personalized interpolated text per recipient,
        and dispatches via SingleSMSService.
        """
        start_time = time.time()
        dept = department or user.department

        if excel_rows is not None:
            recipients = excel_rows
            total_count = len(excel_rows)
        else:
            recipients = list(Staff.objects.filter(id__in=staff_user_ids).select_related('department'))
            if not recipients:
                recipients = list(CustomUser.objects.filter(id__in=staff_user_ids).select_related('department'))
            total_count = len(recipients)

        # 1. Create or reuse SMSBatch tracking record
        if existing_batch:
            batch = existing_batch
            if not batch.started_at:
                batch.started_at = timezone.now()
                batch.save(update_fields=['started_at'])
        else:
            file_label = f"Bulk Excel - {template.name}" if excel_rows is not None else f"Personalized Bulk SMS - {template.name}"
            batch = SMSBatch.objects.create(
                user=user,
                department=dept,
                template=template,
                file_name=f"{file_label} ({total_count} Recipients)",
                total_records=total_count,
                processed_records=0,
                successful_count=0,
                failed_count=0,
                status=SMSStatusChoices.PROCESSING,
                started_at=timezone.now()
            )

        logger.info(f"PERSONALIZED_BULK_START | Batch #{batch.id} | Initiator: '{user.username}' | Recipients: {total_count} | Template: '{template.name}'")

        failure_reasons = []
        total_credits_used = 0

        # 2. Personalized Sequential Loop over Recipients (Staff or Excel Row Dicts)
        for recipient in recipients:
            if isinstance(recipient, dict):
                mobile = (recipient.get('__normalized_mobile') or '').strip()
                staff_name = recipient.get('__normalized_name', 'Excel Recipient')
            elif isinstance(recipient, Staff):
                mobile = (recipient.mobile_number or '').strip()
                staff_name = recipient.name
            else:
                mobile = (getattr(recipient, 'phone_number', '') or '').strip()
                staff_name = recipient.get_full_name() or recipient.username

            if not mobile:
                batch.failed_count += 1
                batch.processed_records += 1
                batch.save(update_fields=['failed_count', 'processed_records'])
                failure_reasons.append(f"{staff_name}: Missing mobile number")
                logger.warning(f"PERSONALIZED_SMS_SKIP | Recipient '{staff_name}' missing phone number.")
                continue

            try:
                # Resolve recipient-specific personalized variables
                personalized_vars = StaffFieldMapper.resolve_all_variables(recipient, mapping_config)

                # Call SingleSMSService.process_and_send()
                success, log_entry, gw_result = SingleSMSService.process_and_send(
                    user=user,
                    mobile_number=mobile,
                    template=template,
                    variable_values=personalized_vars,
                    department=dept
                )

                # Associate log entry with this SMSBatch
                log_entry.batch = batch
                log_entry.save(update_fields=['batch'])

                total_credits_used += log_entry.credit_units

                if success:
                    batch.successful_count += 1
                else:
                    batch.failed_count += 1
                    err_msg = gw_result.error_message or "Gateway response failed"
                    failure_reasons.append(f"{staff_name} ({mobile}): {err_msg}")

            except Exception as e:
                batch.failed_count += 1
                failure_reasons.append(f"{staff_name} ({mobile}): Exception - {str(e)}")
                logger.error(f"PERSONALIZED_SMS_ERR | Exception sending to '{mobile}': {str(e)}")

            batch.processed_records += 1
            batch.save(update_fields=['processed_records', 'successful_count', 'failed_count'])

        # 3. Finalize SMSBatch Status
        exec_time = round(time.time() - start_time, 2)
        batch.completed_at = timezone.now()
        batch.status = SMSStatusChoices.SENT if batch.failed_count == 0 else (SMSStatusChoices.DELIVERED if batch.successful_count > 0 else SMSStatusChoices.FAILED)
        batch.save(update_fields=['completed_at', 'status'])

        success_pct = round((batch.successful_count / total_count * 100), 1) if total_count > 0 else 0.0

        summary = {
            'batch_id': batch.id,
            'total_selected': total_count,
            'successful_count': batch.successful_count,
            'failed_count': batch.failed_count,
            'execution_time_seconds': exec_time,
            'total_credits_used': total_credits_used,
            'success_percentage': success_pct,
            'failure_reasons': failure_reasons
        }

        logger.info(
            f"PERSONALIZED_BULK_COMPLETE | Batch #{batch.id} | Sent: {batch.successful_count}/{total_count} | "
            f"Failed: {batch.failed_count} | Time: {exec_time}s | Credits: {total_credits_used}"
        )

        return batch, summary
