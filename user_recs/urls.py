from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^dime/', views.get_recommendation, name='dime'),
    url(r'^ten/', views.add_recommendation, name='ten'),
    url(r'^like/', views.like_dislike, name='like'),
    url(r'^gracenote_id/', views.add_gracenoteid, name='add_id')
]