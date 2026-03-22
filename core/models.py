from django.db import models
from django.contrib.auth.models import User

from core.utils import seconds_to_hms


class Playlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists')
    playlist_id = models.CharField(max_length=100)   # YouTube playlist ID
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=500, blank=True)
    video_count = models.IntegerField(default=0)
    total_duration_sec = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def total_duration_str(self):
        return seconds_to_hms(self.total_duration_sec)

    def __str__(self):
        return self.title or self.playlist_id


class Video(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='videos')
    youtube_id = models.CharField(max_length=20)
    title = models.CharField(max_length=500)
    duration_sec = models.IntegerField(default=0)
    position = models.IntegerField(default=0)  # order within playlist

    class Meta:
        ordering = ['position']

    def duration_str(self):
        return seconds_to_hms(self.duration_sec)

    def __str__(self):
        return self.title


class StudySchedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedules')
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='schedules')
    weekday_hours = models.FloatField()
    weekend_hours = models.FloatField()
    start_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def total_days(self):
        return self.days.count()

    def total_videos(self):
        return sum(d.videos.count() for d in self.days.all())

    def __str__(self):
        return f"Schedule for '{self.playlist}' from {self.start_date}"


class ScheduleDay(models.Model):
    schedule = models.ForeignKey(StudySchedule, on_delete=models.CASCADE, related_name='days')
    date = models.DateField()
    total_sec = models.IntegerField(default=0)
    order = models.IntegerField(default=0)
    videos = models.ManyToManyField(Video, through='ScheduleDayVideo', related_name='schedule_days')

    class Meta:
        ordering = ['order']

    def total_str(self):
        return seconds_to_hms(self.total_sec)

    def day_name(self):
        return self.date.strftime('%A, %B %d %Y')

    def is_weekend(self):
        return self.date.weekday() >= 5

    def __str__(self):
        return str(self.date)


class ScheduleDayVideo(models.Model):
    """Through table: preserves video order within a day."""
    day = models.ForeignKey(ScheduleDay, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ['position']
