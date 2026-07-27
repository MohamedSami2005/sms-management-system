from django.contrib import admin
from .models import SMSGatewayConfig


@admin.register(SMSGatewayConfig)
class SMSGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ('provider_name', 'default_sender_id', 'request_method', 'is_active', 'updated_at')
    list_filter = ('is_active', 'request_method')
    search_fields = ('provider_name', 'api_url', 'default_sender_id', 'default_entity_id')
    ordering = ('-is_active', '-created_at')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

    fieldsets = (
        ('Provider Profile', {
            'fields': ('provider_name', 'is_active', 'default_sender_id', 'default_entity_id')
        }),
        ('API Endpoints', {
            'fields': ('api_url', 'balance_api_url', 'dlr_api_url', 'request_method', 'route_id', 'response_format')
        }),
        ('Authentication', {
            'fields': ('api_key', 'username', 'password')
        }),
        ('Advanced Request Specs', {
            'classes': ('collapse',),
            'fields': ('http_headers', 'param_mapping')
        }),
        ('Audit Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
