import json
from datetime import datetime

from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from googleapiclient.errors import HttpError

from core.services.youtube import fetch_playlist as yt_fetch, extract_playlist_id
from core.services.scheduler import build_schedule
from core.services.ics import build_ics
from core.utils import seconds_to_hms


# ─── Pages ────────────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'index.html')


# ─── API: fetch playlist ──────────────────────────────────────────────────────

@csrf_exempt
def fetch_playlist(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    data = json.loads(request.body)
    url = data.get('url', '').strip()

    if not url:
        return JsonResponse({'error': 'Please enter a playlist URL.'}, status=400)

    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return JsonResponse({'error': 'Invalid YouTube playlist URL. Make sure it contains "list=..."'}, status=400)

    api_key = settings.YOUTUBE_API_KEY
    if not api_key or api_key == 'your_youtube_api_key_here':
        return JsonResponse({'error': 'YouTube API key not configured.'}, status=500)

    cache_key = f'playlist:{playlist_id}'
    cached = cache.get(cache_key)

    if cached:
        result = cached
    else:
        try:
            result = yt_fetch(playlist_id, api_key)
        except HttpError as e:
            if e.status_code == 404:
                return JsonResponse({
                    'error': 'Playlist not found. It may be private, unlisted, or the URL is incorrect. '
                             'Only public playlists are supported.'
                }, status=400)
            if e.status_code == 403:
                return JsonResponse({
                    'error': 'Access denied by YouTube API. Ensure the YouTube Data API v3 is enabled in Google Cloud Console.'
                }, status=500)
            return JsonResponse({'error': f'YouTube API error ({e.status_code}): {e.reason}'}, status=500)
        except Exception as e:
            return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

        if not result['videos']:
            return JsonResponse({'error': 'Playlist is empty or not publicly accessible.'}, status=400)

        cache.set(cache_key, result)

    total_sec = sum(v['duration_sec'] for v in result['videos'])

    request.session['playlist_data'] = {
        'title': result['title'],
        'videos': result['videos'],
        'total_sec': total_sec,
    }
    request.session.modified = True

    return JsonResponse({
        'playlist_id': playlist_id,
        'title': result['title'],
        'videos': result['videos'],
        'total_sec': total_sec,
        'total_str': seconds_to_hms(total_sec),
        'count': len(result['videos']),
        'cached': bool(cached),
    })


# ─── API: generate schedule ───────────────────────────────────────────────────

@csrf_exempt
def generate_schedule(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    data = json.loads(request.body)
    start_date_str = data.get('start_date', '').strip()

    try:
        weekday_hours = float(data.get('weekday_hours', 1))
        weekend_hours = float(data.get('weekend_hours', 2))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Hours must be numbers.'}, status=400)

    if not start_date_str:
        return JsonResponse({'error': 'Please provide a start date.'}, status=400)
    if weekday_hours < 0 or weekend_hours < 0:
        return JsonResponse({'error': 'Hours cannot be negative.'}, status=400)
    if weekday_hours > 24 or weekend_hours > 24:
        return JsonResponse({'error': 'Hours per day cannot exceed 24.'}, status=400)
    if weekday_hours == 0 and weekend_hours == 0:
        return JsonResponse({'error': 'You need at least some available hours per day.'}, status=400)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format.'}, status=400)

    playlist_data = request.session.get('playlist_data')
    if not playlist_data:
        return JsonResponse({'error': 'No playlist loaded. Please fetch a playlist first.'}, status=400)

    videos = playlist_data['videos']
    for v in videos:
        v['duration_str'] = seconds_to_hms(v['duration_sec'])

    schedule = build_schedule(videos, weekday_hours, weekend_hours, start_date)

    if not schedule:
        return JsonResponse({'error': 'Could not build a schedule. Check your hours and start date.'}, status=400)

    truncated = any(day.get('truncated') for day in schedule)

    request.session['schedule'] = schedule
    request.session.modified = True

    return JsonResponse({'schedule': schedule, 'truncated': truncated})


# ─── ICS download ─────────────────────────────────────────────────────────────

def download_ics(request):
    """
    Returns the study schedule as a .ics file.
    Works with Google Calendar, Apple Calendar, Outlook — no OAuth required.
    """
    schedule = request.session.get('schedule')
    if not schedule:
        return render(request, 'error.html', {
            'message': 'No schedule found. Please generate a schedule first.'
        })

    playlist_data = request.session.get('playlist_data', {})
    playlist_title = playlist_data.get('title', 'Study Schedule')

    ics_content = build_ics(schedule, playlist_title)

    filename = 'study-schedule.ics'
    response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
