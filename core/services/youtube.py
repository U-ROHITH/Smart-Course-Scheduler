"""
YouTube Data API v3 service.
Responsible for: parsing playlist URLs, fetching video metadata.
No Django imports — pure Python.
"""
import re

import googleapiclient.discovery

from core.utils import seconds_to_hms


def extract_playlist_id(url: str) -> str | None:
    m = re.search(r'list=([A-Za-z0-9_-]+)', url)
    return m.group(1) if m else None


def _parse_iso_duration(iso: str) -> int:
    """ISO 8601 duration → total seconds. e.g. 'PT1H4M30S' → 3870"""
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def fetch_playlist(playlist_id: str, api_key: str) -> dict:
    """
    Returns:
        {
            'title': str,
            'videos': [{'youtube_id', 'title', 'duration_sec', 'duration_str', 'position'}, ...]
        }
    Raises googleapiclient.errors.HttpError on API failure.
    """
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=api_key)

    # Playlist title (1 quota unit)
    info_resp = youtube.playlists().list(part='snippet', id=playlist_id).execute()
    title = ''
    if info_resp.get('items'):
        title = info_resp['items'][0]['snippet']['title']

    videos = []
    next_page_token = None
    position_counter = 0

    while True:
        pl_resp = youtube.playlistItems().list(
            part='snippet',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        items = pl_resp.get('items', [])
        if not items:
            break

        video_ids = []
        meta: dict[str, dict] = {}
        for item in items:
            vid_id = item['snippet']['resourceId']['videoId']
            video_ids.append(vid_id)
            meta[vid_id] = {
                'title': item['snippet']['title'],
                'position': position_counter,
            }
            position_counter += 1

        # Batch duration fetch (1 quota unit per 50 videos)
        details_resp = youtube.videos().list(
            part='contentDetails',
            id=','.join(video_ids),
        ).execute()

        duration_map = {
            v['id']: _parse_iso_duration(v['contentDetails']['duration'])
            for v in details_resp.get('items', [])
        }

        for vid_id in video_ids:
            dur = duration_map.get(vid_id, 0)
            videos.append({
                'youtube_id': vid_id,
                'title': meta[vid_id]['title'],
                'duration_sec': dur,
                'duration_str': seconds_to_hms(dur),
                'position': meta[vid_id]['position'],
            })

        next_page_token = pl_resp.get('nextPageToken')
        if not next_page_token:
            break

    return {'title': title, 'videos': videos}
