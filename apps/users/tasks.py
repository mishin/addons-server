from datetime import datetime
import os
import random

from django.conf import settings
from django.contrib.auth.models import User as DjangoUser
from django.db import IntegrityError
from django.db import connection, transaction

import commonware.log
from celery.decorators import task
from easy_thumbnails import processors
from PIL import Image

from . import cron
from amo.utils import slugify
from users.models import UserProfile

task_log = commonware.log.getLogger('z.task')


@task
def delete_photo(dst):
    task_log.info('[1@None] Deleting photo: %s.' % dst)

    if not dst.startswith(settings.USERPICS_PATH):
        task_log.error("Someone tried deleting something they shouldn't: %s"
                       % dst)
        return

    try:
        os.remove(dst)
    except Exception, e:
        task_log.error("Error deleting userpic: %s" % e)


@task
def resize_photo(src, dst):
    """Resizes userpics to 200x200"""
    task_log.info('[1@None] Resizing photo: %s' % dst)

    try:
        im = Image.open(src)
        im = processors.scale_and_crop(im, (200, 200))
        im.save(dst)
        os.remove(src)
    except Exception, e:
        task_log.error("Error saving userpic: %s" % e)


@task(rate_limit='3/m')
def fix_users_with_photos(ids):
    """Temporary code, see bug 596477.  Delete me after 5.12."""
    task_log.info('[%s@%s] Adding photo flag to users' %
                  (len(ids), fix_users_with_photos.rate_limit))
    cursor = connection.cursor()

    query = "UPDATE users SET picture_type='image/png' WHERE id IN(%s)"
    query = query % ','.join([str(i) for i in ids])
    cursor.execute(query)
    transaction.commit_unless_managed()
