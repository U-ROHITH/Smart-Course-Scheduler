from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('fetch-playlist/', views.fetch_playlist, name='fetch_playlist'),
    path('generate-schedule/', views.generate_schedule, name='generate_schedule'),
    path('download-ics/', views.download_ics, name='download_ics'),
]
