import os
from dotenv import load_dotenv

load_dotenv()

# Default to dev settings if not specified
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
