from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^dime/', views.get_recommendation, name='dime'),
    url(r'^ten/', views.add_recommendation, name='ten'),
    url(r'^like/', views.like_dislike, name='like'),
    url(r'^gracenote_id/', views.add_gracenoteid, name='add_id'),
    url(r'^tracksearch/(?P<rec_id>[0-9]+)', views.track_search, name='track_search'),
    url(r'^trackname/', views.track_name_search, name='track_name_search'),
    url(r'^trackinfo/', views.track_info, name='track_info'),
    url(r'^userchart/', views.top_tastemakers, name='top_tastemakers')
]