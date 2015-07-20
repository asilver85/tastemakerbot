# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user_recs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userrecommendation',
            name='is_youtube',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
    ]
