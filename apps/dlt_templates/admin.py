from django.contrib import admin
from .models import DLTTemplate, TemplateVariable


class TemplateVariableInline(admin.TabularInline):
    model = TemplateVariable
    extra = 1
    fields = ('position', 'name', 'sample_value')
    ordering = ('position',)


@admin.register(DLTTemplate)
class DLTTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'dlt_template_id', 'header_sender_id', 'category', 'department', 'variable_count', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'department', 'header_sender_id')
    search_fields = ('name', 'dlt_template_id', 'entity_id', 'header_sender_id', 'template_content')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [TemplateVariableInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TemplateVariable)
class TemplateVariableAdmin(admin.ModelAdmin):
    list_display = ('template', 'position', 'name', 'sample_value')
    list_filter = ('template',)
    search_fields = ('template__name', 'name', 'sample_value')
    ordering = ('template', 'position')
