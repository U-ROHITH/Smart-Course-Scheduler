"""
Schedule generation service.

Key guarantees:
  1. STRICT PLAYLIST ORDER — videos are always scheduled in their original sequence.
     No video ever jumps ahead of another.
  2. SPLIT LONG VIDEOS — if a video is longer than the daily budget it is divided
     into timed parts (Part 1/3, Part 2/3, Part 3/3) so every minute is accounted
     for without dropping or reordering anything.
  3. ZERO-DURATION VIDEOS — skipped entirely (deleted/private videos in a playlist
     often come back with duration 0 from the API).
  4. MAX-DAY GUARD — caps at 730 days; returns a `truncated` flag if hit so the
     caller can surface a warning to the user.
"""
import math
from datetime import timedelta, date

from core.utils import seconds_to_hms


# Absolute upper bound on schedule length.
# 730 days ≈ 2 years; an 8-hour video with a 1-minute/day budget would need
# 480 days, well within this limit.
MAX_DAYS = 730


def build_schedule(
    videos: list[dict],
    weekday_hours: float,
    weekend_hours: float,
    start_date: date,
) -> list[dict]:
    """
    Args:
        videos: original playlist order, each dict has:
                youtube_id, title, duration_sec, duration_str, position
        weekday_hours / weekend_hours: available hours per day (0–24)
        start_date: first calendar day

    Returns:
        list of day dicts:
            date        str  "YYYY-MM-DD"
            day_name    str  "Monday, March 23 2026"
            videos      list of item dicts (see below)
            total_sec   int
            total_str   str
            has_splits  bool  True if any video in this day is a split part
            truncated   bool  True on the LAST day when MAX_DAYS was hit
                              (only present when truncation occurred)

        Each item dict:
            youtube_id   str
            title        str
            duration_sec int   (duration of THIS segment only)
            duration_str str
            part         int | None   None = full video; N = Nth chunk
            total_parts  int | None   total chunks this video was split into
    """
    if not videos:
        return []

    # ── Pre-process: cast durations to int, skip 0-duration entries ───────────
    valid_videos = []
    for v in videos:
        dur = int(v.get('duration_sec') or 0)
        if dur <= 0:
            continue  # deleted / private video — no watchable content
        valid_videos.append({**v, 'duration_sec': dur})

    if not valid_videos:
        return []

    # ── Convert budgets to whole seconds ──────────────────────────────────────
    weekday_budget_sec = max(0, int(weekday_hours * 3600))
    weekend_budget_sec = max(0, int(weekend_hours * 3600))

    schedule   = []
    current    = start_date
    days_tried = 0

    video_idx           = 0
    video_remaining_sec = valid_videos[0]['duration_sec']

    # Tracks the last part-number emitted for each split video.
    # {youtube_id: last_part_number_emitted}
    part_tracker: dict[str, int] = {}

    while video_idx < len(valid_videos):
        if days_tried >= MAX_DAYS:
            # Safety cap: annotate the final scheduled day and stop.
            if schedule:
                schedule[-1]['truncated'] = True
            break

        is_weekend = current.weekday() >= 5
        budget_sec = weekend_budget_sec if is_weekend else weekday_budget_sec
        days_tried += 1

        if budget_sec <= 0:
            # This day type has zero availability — skip without counting toward MAX_DAYS limit
            days_tried -= 1
            current += timedelta(days=1)
            continue

        day_items: list[dict] = []
        used_sec = 0

        # ── Fill this day strictly in order ───────────────────────────────────
        while video_idx < len(valid_videos) and used_sec < budget_sec:
            v                = valid_videos[video_idx]
            vid_id           = v['youtube_id']
            remaining_budget = budget_sec - used_sec

            # Defensive: remaining should never go negative, but guard anyway
            video_remaining_sec = max(0, video_remaining_sec)

            if video_remaining_sec == 0:
                # Edge case: remaining was zeroed out — advance to next video
                video_idx += 1
                if video_idx < len(valid_videos):
                    video_remaining_sec = valid_videos[video_idx]['duration_sec']
                continue

            if video_remaining_sec <= remaining_budget:
                # ── Entire remaining segment fits today ────────────────────────
                current_part = part_tracker.get(vid_id, 0)
                day_items.append({
                    'youtube_id':   vid_id,
                    'title':        v['title'],
                    'duration_sec': video_remaining_sec,
                    'duration_str': seconds_to_hms(video_remaining_sec),
                    # If this video was ever split, this final chunk gets the
                    # next part number; otherwise it's a whole-video (None).
                    'part':        current_part + 1 if current_part > 0 else None,
                    'total_parts': None,  # filled in post-pass
                })
                used_sec += video_remaining_sec

                video_idx += 1
                if video_idx < len(valid_videos):
                    video_remaining_sec = valid_videos[video_idx]['duration_sec']

            else:
                # ── Video doesn't fit — take what the budget allows ────────────
                new_part = part_tracker.get(vid_id, 0) + 1
                part_tracker[vid_id] = new_part

                day_items.append({
                    'youtube_id':   vid_id,
                    'title':        v['title'],
                    'duration_sec': remaining_budget,
                    'duration_str': seconds_to_hms(remaining_budget),
                    'part':        new_part,
                    'total_parts': None,  # filled in post-pass
                })
                used_sec            += remaining_budget
                video_remaining_sec -= remaining_budget
                break  # day is full

        if day_items:
            schedule.append({
                'date':      current.strftime('%Y-%m-%d'),
                'day_name':  current.strftime('%A, %B %d %Y'),
                'videos':    day_items,
                'total_sec': used_sec,
                'total_str': seconds_to_hms(used_sec),
                'has_splits': False,  # updated in post-pass
            })

        current += timedelta(days=1)

    # ── Post-pass: compute total_parts for every split video ──────────────────
    # The highest part number emitted for a video = total number of parts.
    total_parts_map: dict[str, int] = {}
    for day in schedule:
        for item in day['videos']:
            if item['part'] is not None:
                vid_id = item['youtube_id']
                total_parts_map[vid_id] = max(
                    total_parts_map.get(vid_id, 0),
                    item['part'],
                )

    for day in schedule:
        for item in day['videos']:
            if item['part'] is not None:
                item['total_parts'] = total_parts_map[item['youtube_id']]
        day['has_splits'] = any(v['part'] is not None for v in day['videos'])

    return schedule
