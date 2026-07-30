from django.contrib import admin
from .models import SMSLog


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'mobile_number', 'status', 'user', 'department', 'template', 'credit_units', 'gateway_message_id', 'dlr_status', 'created_at')
    list_filter = ('status', 'dlr_status', 'department', 'created_at')
    search_fields = ('mobile_number', 'gateway_message_id', 'message_content', 'user__username')
    ordering = ('-created_at',)
    readonly_fields = (
        'user', 'department', 'template', 'batch', 'mobile_number',
        'message_content', 'status', 'credit_units', 'gateway_message_id',
        'gateway_status_code', 'gateway_response_raw', 'dlr_status',
        'dlr_timestamp', 'created_at', 'updated_at'
    )

    def has_add_permission(self, request):
        # Audit logs are immutable and created only via system services
        return False

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete log entries if necessary
        return request.user.is_superuser
