# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('slack_username', models.CharField(max_length=128, db_index=True)),
                ('profile', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='UserLikeDislike',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('like', models.BooleanField()),
                ('timestamp', models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name='UserRecommendation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('link', models.CharField(max_length=255, db_index=True)),
                ('description', models.CharField(max_length=512, blank=True)),
                ('gracenote_id', models.CharField(max_length=255, null=True, blank=True)),
                ('likes', models.PositiveIntegerField()),
                ('dislikes', models.PositiveIntegerField()),
                ('timestamp', models.DateTimeField()),
                ('user', models.ForeignKey(to='user_recs.User')),
            ],
        ),
        migrations.AddField(
            model_name='userlikedislike',
            name='rec',
            field=models.ForeignKey(to='user_recs.UserRecommendation'),
        ),
        migrations.AddField(
            model_name='userlikedislike',
            name='user',
            field=models.ForeignKey(to='user_recs.User'),
        ),
    ]
