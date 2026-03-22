"""
ICS (iCalendar) file generator.
Produces a valid RFC 5545 calendar file from a schedule list.
Works for every calendar app: Google Calendar, Apple Calendar, Outlook, etc.
No OAuth, no API keys, no verification required.
"""
import hashlib
from datetime import datetime, timedelta


def _esc(text: str) -> str:
    """Escape ICS text values per RFC 5545."""
    return text.replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('\n', r'\n')


def _fold(line: str) -> str:
    """Fold lines longer than 75 octets (RFC 5545 §3.1)."""
    result = []
    while len(line.encode('utf-8')) > 75:
        result.append(line[:75])
        line = ' ' + line[75:]
    result.append(line)
    return '\r\n'.join(result)


def build_ics(schedule: list[dict], playlist_title: str = '') -> str:
    """
    Args:
        schedule : list of day dicts from build_schedule()
        playlist_title : used in event summaries

    Returns:
        ICS file content as a string.
    """
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Smart Course Scheduler//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_esc(playlist_title or "Study Schedule")}',
        'X-WR-TIMEZONE:UTC',
    ]

    for day in schedule:
        day_date   = day['date']             # "YYYY-MM-DD"
        total_sec  = day['total_sec']
        videos     = day['videos']

        # Start at 09:00 UTC, end = start + total_sec
        start_dt = datetime.strptime(day_date, '%Y-%m-%d').replace(hour=9)
        end_dt   = start_dt + timedelta(seconds=total_sec)

        dtstart  = start_dt.strftime('%Y%m%dT%H%M%SZ')
        dtend    = end_dt.strftime('%Y%m%dT%H%M%SZ')
        dtstamp  = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

        # Unique ID for this event
        uid_seed = f"scs-{day_date}-{'-'.join(v['youtube_id'] for v in videos)}"
        uid = hashlib.md5(uid_seed.encode()).hexdigest() + '@smartcoursescheduler'

        # Summary line
        summary = f"Study: {len(videos)} video{'s' if len(videos) != 1 else ''} — {day['total_str']}"
        if playlist_title:
            summary = f"{playlist_title} · {summary}"

        # Description: bullet list of videos with part labels for splits
        desc_lines = []
        for v in videos:
            if v.get('part') is not None:
                label = f"• {v['title']} (Part {v['part']}/{v['total_parts']} — {v['duration_str']})"
            else:
                label = f"• {v['title']} ({v['duration_str']})"
            desc_lines.append(label)
        description = f"Total: {day['total_str']}\\n\\n" + '\\n'.join(_esc(l) for l in desc_lines)

        lines += [
            'BEGIN:VEVENT',
            _fold(f'UID:{uid}'),
            f'DTSTAMP:{dtstamp}',
            f'DTSTART:{dtstart}',
            f'DTEND:{dtend}',
            _fold(f'SUMMARY:{_esc(summary)}'),
            _fold(f'DESCRIPTION:{description}'),
            'END:VEVENT',
        ]

    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'
