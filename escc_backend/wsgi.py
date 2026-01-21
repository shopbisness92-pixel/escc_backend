<<<<<<< HEAD
"""
WSGI config for escc_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'escc_backend.settings')

application = get_wsgi_application()

app = application

=======
"""
WSGI config for escc_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'escc_backend.settings')

application = get_wsgi_application()

app = application

>>>>>>> db10e5ef20a7e0293aa4275ab1c6357019f9d8ee
