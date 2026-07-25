from django.contrib import admin
from .models import SMSBatch, SMSQueue


@admin.register(SMSBatch)
class SMSBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_name', 'user', 'department', 'template', 'total_records', 'processed_records', 'successful_count', 'failed_count', 'status', 'created_at')
    list_filter = ('status', 'department', 'created_at')
    search_fields = ('file_name', 'user__username', 'template__name')
    ordering = ('-created_at',)
    readonly_fields = ('total_records', 'processed_records', 'successful_count', 'failed_count', 'started_at', 'completed_at', 'created_at', 'updated_at', 'created_by', 'updated_by')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SMSQueue)
class SMSQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'mobile_number', 'user', 'department', 'template', 'status', 'credit_units', 'gateway_message_id', 'scheduled_at', 'sent_at')
    list_filter = ('status', 'department', 'credit_units', 'scheduled_at')
    search_fields = ('mobile_number', 'gateway_message_id', 'user__username', 'message_content')
    ordering = ('scheduled_at', '-id')
    readonly_fields = ('created_at', 'updated_at', 'sent_at', 'gateway_response_raw')
