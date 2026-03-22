import json
from datetime import datetime

from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
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
    url  = data.get('url', '').strip()

    if not url:
        return JsonResponse({'error': 'Please enter a playlist URL.'}, status=400)

    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return JsonResponse(
            {'error': 'Invalid YouTube playlist URL. Make sure it contains "list=..."'},
            status=400,
        )

    api_key = settings.YOUTUBE_API_KEY
    if not api_key or api_key == 'your_youtube_api_key_here':
        return JsonResponse({'error': 'YouTube API key not configured.'}, status=500)

    cache_key = f'playlist:{playlist_id}'
    cached    = cache.get(cache_key)

    if cached:
        result = cached
    else:
        try:
            result = yt_fetch(playlist_id, api_key)
        except HttpError as e:
            if e.status_code == 404:
                return JsonResponse({
                    'error': (
                        'Playlist not found. It may be private, unlisted, or the URL is '
                        'incorrect. Only public playlists are supported.'
                    )
                }, status=400)
            if e.status_code == 403:
                return JsonResponse({
                    'error': (
                        'Access denied by YouTube API. Ensure the YouTube Data API v3 '
                        'is enabled in Google Cloud Console.'
                    )
                }, status=500)
            return JsonResponse(
                {'error': f'YouTube API error ({e.status_code}): {e.reason}'},
                status=500,
            )
        except Exception as e:
            return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

        if not result['videos']:
            return JsonResponse(
                {'error': 'Playlist is empty or not publicly accessible.'},
                status=400,
            )

        cache.set(cache_key, result, timeout=60 * 60 * 24)

    total_sec = sum(v['duration_sec'] for v in result['videos'])

    return JsonResponse({
        'playlist_id': playlist_id,
        'title':       result['title'],
        'videos':      result['videos'],
        'total_sec':   total_sec,
        'total_str':   seconds_to_hms(total_sec),
        'count':       len(result['videos']),
        'cached':      bool(cached),
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
        return JsonResponse(
            {'error': 'You need at least some available hours per day.'},
            status=400,
        )

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format.'}, status=400)

    # Client sends the full videos list (returned earlier by fetch-playlist).
    # This eliminates any server-side session / persistent storage requirement.
    videos = data.get('videos')
    if not videos or not isinstance(videos, list):
        return JsonResponse(
            {'error': 'No playlist data provided. Please fetch a playlist first.'},
            status=400,
        )

    for v in videos:
        v['duration_str'] = seconds_to_hms(int(v.get('duration_sec') or 0))

    schedule = build_schedule(videos, weekday_hours, weekend_hours, start_date)

    if not schedule:
        return JsonResponse(
            {'error': 'Could not build a schedule. Check your hours and start date.'},
            status=400,
        )

    truncated = any(day.get('truncated') for day in schedule)

    return JsonResponse({'schedule': schedule, 'truncated': truncated})


# ─── ICS download ─────────────────────────────────────────────────────────────

@csrf_exempt
def download_ics(request):
    """
    Accepts the schedule as JSON in the POST body and returns a .ics file.
    No server-side storage required — client sends back what it received from
    generate-schedule.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    data           = json.loads(request.body)
    schedule       = data.get('schedule')
    playlist_title = data.get('playlist_title', 'Study Schedule')

    if not schedule:
        return JsonResponse({'error': 'No schedule provided.'}, status=400)

    ics_content = build_ics(schedule, playlist_title)

    response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="study-schedule.ics"'
    return response
