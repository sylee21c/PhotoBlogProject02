"""Paste/adapt this into the WSGI file shown by PythonAnywhere's Web tab.

Set these values for your own account. Do not commit the deployed secret key.
"""
import os
import sys

PROJECT = '/home/YOUR_USERNAME/PhotoBlogProject02/PhotoBlogServer'
sys.path.insert(0, PROJECT)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = '0'
os.environ['DJANGO_SECRET_KEY'] = 'REPLACE_WITH_A_LONG_RANDOM_PRIVATE_VALUE'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'YOUR_USERNAME.pythonanywhere.com'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = 'https://YOUR_USERNAME.pythonanywhere.com'
if 'YOUR_USERNAME' in PROJECT or os.environ['DJANGO_SECRET_KEY'].startswith('REPLACE_'):
    raise RuntimeError('Configure the account path, domain and private secret before deployment.')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
