from django.db import models

# Create your models here.
class User(models.Model):
    slack_username = models.CharField(db_index=True, max_length=128)
    profile = models.TextField()

class UserRecommendation(models.Model):
    user = models.ForeignKey(User)
    link = models.CharField(db_index=True, max_length=255)
    description = models.CharField(max_length=512, blank=True)
    gracenote_id = models.CharField(max_length=255, blank=True, null=True)
    likes = models.PositiveIntegerField()
    dislikes = models.PositiveIntegerField()
    timestamp = models.DateTimeField()

class UserLikeDislike(models.Model):
    user = models.ForeignKey(User)
    rec = models.ForeignKey(UserRecommendation)
    like = models.BooleanField()
    timestamp = models.DateTimeField()