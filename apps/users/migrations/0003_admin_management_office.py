from django.db import migrations


def create_admin_management_office(apps, schema_editor):
    Department = apps.get_model('users', 'Department')
    admin_office, _ = Department.objects.get_or_create(
        name="Admin Management",
        defaults={
            'code': 'ADMIN_MGMT',
            'description': 'Global System Administration Office',
            'is_active': True
        }
    )

    # Associate any existing users without a department to Admin Management office
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(department__isnull=True).update(department=admin_office)

    # Associate any existing DLT templates without a department to Admin Management office
    DLTTemplate = apps.get_model('dlt_templates', 'DLTTemplate')
    DLTTemplate.objects.filter(department__isnull=True).update(department=admin_office)

    # Associate any existing SMS logs without a department to Admin Management office
    SMSLog = apps.get_model('logs', 'SMSLog')
    SMSLog.objects.filter(department__isnull=True).update(department=admin_office)


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_staff'),
        ('accounts', '0001_initial'),
        ('dlt_templates', '0001_initial'),
        ('logs', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_admin_management_office, reverse_code=reverse_func),
    ]
