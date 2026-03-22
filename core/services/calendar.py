"""
Google Calendar API service.
Works with raw schedule dicts (no DB models required).
"""
import os

import google_auth_oauthlib.flow
import googleapiclient.discovery
from django.conf import settings

SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_oauth_flow() -> google_auth_oauthlib.flow.Flow:
    return google_auth_oauthlib.flow.Flow.from_client_config(
        {
            'web': {
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )


def push_schedule_to_calendar(credentials, schedule: list[dict]) -> tuple[int, list[str]]:
    """
    Creates Google Calendar events from a raw schedule list.

    Args:
        credentials: google.oauth2.credentials.Credentials
        schedule: list of day dicts from build_schedule()

    Returns:
        (created_count, error_list)
    """
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)

    created = 0
    errors = []

    for day in schedule:
        day_date = day['date']
        description = '\n'.join(
            f"• {v['title']} ({v['duration_str']})" for v in day['videos']
        )

        total_sec = day['total_sec']
        start_dt = f"{day_date}T09:00:00"
        end_h = 9 + total_sec // 3600
        end_m = (total_sec % 3600) // 60
        end_dt = f"{day_date}T{end_h:02d}:{end_m:02d}:00"

        event = {
            'summary': f"Study: {len(day['videos'])} video(s) — {day['total_str']}",
            'description': f"Total watch time: {day['total_str']}\n\n{description}",
            'start': {'dateTime': start_dt, 'timeZone': 'UTC'},
            'end': {'dateTime': end_dt, 'timeZone': 'UTC'},
        }

        try:
            service.events().insert(calendarId='primary', body=event).execute()
            created += 1
        except Exception as e:
            errors.append(str(e))

    return created, errors
