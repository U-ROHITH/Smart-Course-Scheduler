from urllib.parse import urlencode
from datetime import datetime, timedelta


def seconds_to_hms(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f'{h}h {m}m {s}s' if h else f'{m}m {s}s'


def gcal_event_link(title: str, start_dt: datetime, end_dt: datetime, description: str = '') -> str:
    """
    Build a Google Calendar pre-filled event URL.
    No OAuth or API key required — opens directly in the user's browser.

    Example output:
      https://calendar.google.com/calendar/render?action=TEMPLATE
        &text=Python+Course+%E2%80%94+Study+Session
        &dates=20260323T090000Z%2F20260323T110000Z
        &details=Total%3A+2h+0m%0A%0A%E2%80%A2+...
    """
    fmt = '%Y%m%dT%H%M%SZ'
    params = {
        'action': 'TEMPLATE',
        'text': title,
        'dates': f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}",
        'details': description,
    }
    return 'https://calendar.google.com/calendar/render?' + urlencode(params)


def attach_gcal_links(schedule: list[dict], playlist_title: str = '') -> None:
    """
    Mutate each day (and each video item within it) in-place by adding a
    'gcal_link' key — a pre-filled Google Calendar URL.

    Day event  : covers the full study block (09:00 UTC → 09:00 + total_sec).
    Video event: sequential 1-minute-buffered slots within the same block.
    """
    DAY_START_HOUR = 9  # 09:00 UTC

    for day in schedule:
        day_start = datetime.strptime(day['date'], '%Y-%m-%d').replace(hour=DAY_START_HOUR)
        day_end   = day_start + timedelta(seconds=day['total_sec'])

        # ── Day-level link ────────────────────────────────────────────────────
        day_title = (f"{playlist_title} — Study Session" if playlist_title
                     else "Study Session")

        desc_lines = []
        for v in day['videos']:
            if v.get('part') is not None:
                desc_lines.append(
                    f"• {v['title']} (Part {v['part']}/{v['total_parts']} — {v['duration_str']})"
                )
            else:
                desc_lines.append(f"• {v['title']} ({v['duration_str']})")
        day_desc = f"Total: {day['total_str']}\n\n" + '\n'.join(desc_lines)

        day['gcal_link'] = gcal_event_link(day_title, day_start, day_end, day_desc)

        # ── Per-video links (sequential slots within the day block) ───────────
        cursor = day_start
        for v in day['videos']:
            v_end = cursor + timedelta(seconds=v['duration_sec'])

            if v.get('part') is not None:
                v_title = f"{v['title']} — Part {v['part']}/{v['total_parts']}"
            else:
                v_title = v['title']

            if playlist_title:
                v_title = f"{playlist_title} · {v_title}"

            v['gcal_link'] = gcal_event_link(
                v_title, cursor, v_end,
                description=f"Duration: {v['duration_str']}",
            )
            cursor = v_end
