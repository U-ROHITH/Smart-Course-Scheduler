// ─────────────────────────────────────────────────────────────────────────────
//  Smart Course Scheduler — client-side engine
//  Psychology layer: tracks behaviour in localStorage, drives personalisation.
// ─────────────────────────────────────────────────────────────────────────────

// ── Behaviour store (persists across visits) ──────────────────────────────────
const BEH_KEY = 'scs_behaviour';

function loadBehaviour() {
  try { return JSON.parse(localStorage.getItem(BEH_KEY)) || {}; } catch { return {}; }
}

function saveBehaviour(b) {
  localStorage.setItem(BEH_KEY, JSON.stringify(b));
}

function updateBehaviour(patch) {
  saveBehaviour({ ...loadBehaviour(), ...patch });
}

// ── State ─────────────────────────────────────────────────────────────────────
let totalVideoSec      = 0;    // used for live pace insight
let videoCount         = 0;
let currentVideos      = [];   // full video list from last fetchPlaylist response
let currentPlaylistTitle = ''; // playlist title for ICS generation
let currentSchedule    = [];   // schedule from last generateSchedule response

// ── DOM helpers ───────────────────────────────────────────────────────────────
const $    = id => document.getElementById(id);
const show = id => $(id).classList.remove('hidden');
const hide = id => $(id).classList.add('hidden');

function showError(id, msg) { const el=$(id); el.textContent=msg; el.classList.remove('hidden'); }
function clearError(id) { $(id).classList.add('hidden'); }

function clampHours(input) {
  const val = parseFloat(input.value);
  if (!isNaN(val) && val > 24) input.value = 24;
  if (!isNaN(val) && val < 0)  input.value = 0;
}

function setLoading(btnId, loading, text) {
  const btn = $(btnId);
  btn.disabled = loading;
  btn.innerHTML = loading ? `<span class="spinner"></span>${text}` : text;
}

// ── On page load ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const b = loadBehaviour();

  // Increment visit counter
  const visits = (b.visits || 0) + 1;
  updateBehaviour({ visits });

  // Returning user greeting
  if (visits > 1) {
    const chip = $('welcome-chip');
    const msg = b.lastScheduleDate
      ? `👋 Welcome back! Last schedule: ${b.lastScheduleDate}`
      : `👋 Welcome back! Visit #${visits}`;
    chip.textContent = msg;
    chip.classList.remove('hidden');
  }

  // Restore saved preferences
  if (b.weekdayHours) $('weekday-hours').value = b.weekdayHours;
  if (b.weekendHours) $('weekend-hours').value = b.weekendHours;
  if (b.lastUrl)      $('playlist-url').value  = b.lastUrl;

  // Enter key on URL input
  $('playlist-url').addEventListener('keydown', e => {
    if (e.key === 'Enter') fetchPlaylist();
  });

  // Live pace updates when hours change
  ['weekday-hours','weekend-hours'].forEach(id => {
    $(id).addEventListener('input', updatePaceInsight);
  });
});

// ── Step 1: Fetch playlist ────────────────────────────────────────────────────
async function fetchPlaylist() {
  const url = $('playlist-url').value.trim();
  clearError('fetch-error');
  hide('playlist-section');
  hide('availability-section');
  hide('timetable-section');
  hide('calendar-section');
  totalVideoSec = 0;
  videoCount = 0;

  if (!url) { showError('fetch-error', 'Please enter a YouTube playlist URL.'); return; }

  setLoading('fetch-btn', true, 'Fetching...');

  try {
    const resp = await fetch('/fetch-playlist/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await resp.json();

    if (!resp.ok) { showError('fetch-error', data.error || 'Something went wrong.'); return; }

    totalVideoSec        = data.total_sec;
    videoCount           = data.count;
    currentVideos        = data.videos;
    currentPlaylistTitle = data.title || '';

    // Save to behaviour store
    updateBehaviour({
      lastUrl: url,
      totalFetches: (loadBehaviour().totalFetches || 0) + 1,
    });

    renderPlaylistSection(data);
    advanceStepper(1);
    show('playlist-section');
    show('availability-section');
    $('start-date').value = todayStr();
    updatePaceInsight();
    $('playlist-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch {
    showError('fetch-error', 'Network error. Is the server running?');
  } finally {
    setLoading('fetch-btn', false, 'Analyse →');
  }
}

function renderPlaylistSection(data) {
  // Title
  $('playlist-title').textContent = data.title || 'Playlist Overview';

  // Stats
  $('stat-videos').textContent   = data.count;
  $('stat-duration').textContent = data.total_str;
  const avgSec = Math.round(data.total_sec / data.count);
  $('stat-avg').textContent = secToHms(avgSec);

  // Psychological analysis
  $('playlist-insight').innerHTML = analysePlaylist(data);

  // Video list
  const list = $('video-list');
  list.innerHTML = '';
  data.videos.forEach((v, i) => {
    const row = document.createElement('div');
    row.className = 'video-row';
    row.innerHTML = `
      <span class="idx">${i + 1}</span>
      <span class="title">${escHtml(v.title)}</span>
      <span class="dur">${v.duration_str}</span>
    `;
    list.appendChild(row);
  });
}

// ── Psychological playlist analysis ──────────────────────────────────────────
function analysePlaylist({ count, total_sec }) {
  const hours = total_sec / 3600;
  const avgMin = Math.round(total_sec / count / 60);

  // Content density
  let density, densityIcon;
  if (count < 10)       { density = 'focused, tight course';       densityIcon = '🎯'; }
  else if (count < 25)  { density = 'well-scoped playlist';        densityIcon = '📚'; }
  else if (count < 60)  { density = 'comprehensive curriculum';    densityIcon = '🗂️'; }
  else                  { density = 'deep, ambitious series';      densityIcon = '🏔️'; }

  // Learning style from avg video length
  let style;
  if (avgMin < 5)       style = 'Bite-sized lessons — perfect for daily micro-habits.';
  else if (avgMin < 12) style = 'Medium-length videos — great for focused, single-topic sessions.';
  else if (avgMin < 25) style = 'Long-form content — you\'ll want dedicated, distraction-free blocks.';
  else                  style = 'Deep-dive lectures — high cognitive load. Build in short breaks.';

  // Commitment framing
  let commitment;
  if (hours < 2)        commitment = 'Quick win — you could knock this out in a weekend.';
  else if (hours < 8)   commitment = 'A solid short course. A week of consistent effort finishes it.';
  else if (hours < 20)  commitment = 'Proper course material. A regular schedule is your best friend here.';
  else                  commitment = 'This is a serious commitment. Consistent daily sessions are essential.';

  return `${densityIcon} <strong>${count} videos</strong> — a ${density}. Avg length: <strong>${avgMin} min</strong>.<br>
    💡 ${style}<br>⚡ ${commitment}`;
}

// ── Live pace insight (updates on hour input change) ─────────────────────────
function updatePaceInsight() {
  if (!totalVideoSec) return;

  const wd = parseFloat($('weekday-hours').value) || 0;
  const we = parseFloat($('weekend-hours').value) || 0;
  const dailySec = ((wd * 5) + (we * 2)) / 7 * 3600;  // avg daily seconds

  if (dailySec <= 0) {
    $('pace-bar').textContent = '⚠️ Set at least some available hours to see your pace estimate.';
    return;
  }

  const days  = Math.ceil(totalVideoSec / dailySec);
  const weeks = Math.ceil(days / 7);

  // Learner type
  const avgDailyH = dailySec / 3600;
  const { type, emoji } = getLearnerType(avgDailyH);

  // Finish date estimate
  const finish = new Date();
  finish.setDate(finish.getDate() + days);
  const finishStr = finish.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  $('pace-bar').innerHTML =
    `${emoji} <strong>${type}</strong> — At this pace you'll finish in ` +
    `<strong>${days} day${days===1?'':'s'}</strong> (${weeks} week${weeks===1?'':'s'}), ` +
    `estimated by <strong>${finishStr}</strong>.`;
}

function getLearnerType(avgHoursPerDay) {
  if (avgHoursPerDay < 0.5) return { type: 'Micro-Learner',    emoji: '🌱' };
  if (avgHoursPerDay < 1)   return { type: 'Steady Learner',   emoji: '🚶' };
  if (avgHoursPerDay < 2)   return { type: 'Dedicated Student',emoji: '📖' };
  if (avgHoursPerDay < 4)   return { type: 'Power Learner',    emoji: '🚀' };
  return                           { type: 'Speed Runner',     emoji: '⚡' };
}

// ── Step 2: Generate schedule ─────────────────────────────────────────────────
async function generateSchedule() {
  clearError('schedule-error');
  hide('timetable-section');
  hide('calendar-section');

  const weekdayHours = parseFloat($('weekday-hours').value);
  const weekendHours = parseFloat($('weekend-hours').value);
  const startDate    = $('start-date').value;

  if (isNaN(weekdayHours) || isNaN(weekendHours)) {
    showError('schedule-error', 'Please enter valid numbers for available hours.'); return;
  }
  if (weekdayHours < 0 || weekendHours < 0) {
    showError('schedule-error', 'Hours cannot be negative.'); return;
  }
  if (weekdayHours > 24 || weekendHours > 24) {
    showError('schedule-error', 'Hours per day cannot exceed 24. There are only 24 hours in a day!'); return;
  }
  if (!startDate) {
    showError('schedule-error', 'Please choose a start date.'); return;
  }
  if (weekdayHours === 0 && weekendHours === 0) {
    showError('schedule-error', 'You need at least some available hours per day.'); return;
  }

  setLoading('schedule-btn', true, 'Building your schedule…');

  try {
    const resp = await fetch('/generate-schedule/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        weekday_hours: weekdayHours,
        weekend_hours: weekendHours,
        start_date:    startDate,
        videos:        currentVideos,
      }),
    });
    const data = await resp.json();

    if (!resp.ok) { showError('schedule-error', data.error || 'Something went wrong.'); return; }

    // Save preferences
    const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    updateBehaviour({
      weekdayHours,
      weekendHours,
      schedulesGenerated: (loadBehaviour().schedulesGenerated || 0) + 1,
      lastScheduleDate: today,
    });

    currentSchedule = data.schedule;
    renderTimetable(data.schedule, weekdayHours, weekendHours);
    advanceStepper(2);
    show('timetable-section');
    show('calendar-section');
    showStickyCalBar(data.schedule);
    launchConfetti();

    if (data.truncated) {
      showError('schedule-error',
        '⚠️ Your schedule is very long — only the first 730 days are shown. ' +
        'Try increasing your daily hours to fit the full playlist.'
      );
    }

    $('timetable-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch {
    showError('schedule-error', 'Network error. Is the server running?');
  } finally {
    setLoading('schedule-btn', false, 'Generate My Schedule →');
  }
}

// ── Render timetable ──────────────────────────────────────────────────────────
function renderTimetable(schedule, weekdayH, weekendH) {
  // Summary stats
  const totalDays  = schedule.length;
  const totalVids  = schedule.reduce((s, d) => s + d.videos.length, 0);
  const totalSec   = schedule.reduce((s, d) => s + d.total_sec, 0);
  $('sum-days').textContent = totalDays;
  $('sum-vids').textContent = totalVids;
  $('sum-time').textContent = secToHms(totalSec);

  // Behaviour panel
  renderBehaviourPanel(weekdayH, weekendH, totalDays);

  // Group days by ISO week
  const body = $('schedule-body');
  body.innerHTML = '';

  const weeks = {};
  schedule.forEach(day => {
    const d = new Date(day.date + 'T12:00:00');
    const wk = getISOWeek(d);
    const yr = d.getFullYear();
    const key = `${yr}-W${wk}`;
    if (!weeks[key]) weeks[key] = { label: weekLabel(d), days: [] };
    weeks[key].days.push(day);
  });

  let dayIdx = 0;
  Object.values(weeks).forEach(({ label, days }) => {
    const wLabel = document.createElement('div');
    wLabel.className = 'week-label';
    wLabel.textContent = label;
    body.appendChild(wLabel);

    days.forEach(day => {
      body.appendChild(buildDayCard(day, ++dayIdx));
    });
  });
}

function buildDayCard(day, idx) {
  const d = new Date(day.date + 'T12:00:00');
  const isWeekend = d.getDay() === 0 || d.getDay() === 6;

  const card = document.createElement('div');
  card.className = `day-card ${isWeekend ? 'weekend' : 'weekday'}`;
  card.style.animationDelay = `${(idx - 1) * 30}ms`;

  const dayAbbr   = d.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase();
  const dayNum    = d.getDate();
  const monthAbbr = d.toLocaleDateString('en-US', { month: 'short' });

  // Build pills — split videos get a special dashed pill with "✂ Part N/M" label
  const pills = day.videos.map(v => {
    const isSplit = v.part !== null && v.part !== undefined;
    let pillClass = isWeekend ? 'pill weekend' : 'pill';
    if (isSplit) pillClass += ' split';

    const label = isSplit
      ? `✂ ${escHtml(truncate(v.title, 28))} · Part ${v.part}/${v.total_parts} (${v.duration_str})`
      : `${escHtml(truncate(v.title, 36))}`;

    const tooltip = isSplit
      ? `${v.title} — Part ${v.part} of ${v.total_parts} (${v.duration_str} of this session)`
      : `${v.title} (${v.duration_str})`;

    return `<span class="${pillClass}" title="${escHtml(tooltip)}">${label}</span>`;
  }).join('');

  // Split badge — shown if day has any divided video
  const splitBadge = day.has_splits
    ? `<span class="split-badge">✂ divided</span>`
    : '';

  card.innerHTML = `
    <div class="day-meta">
      <div class="day-name">${dayAbbr}</div>
      <div class="day-date">${dayNum}</div>
      <div class="day-month">${monthAbbr}</div>
    </div>
    <div class="day-body">
      <div class="day-pills">${pills}</div>
      <div class="day-footer">
        <span class="count-badge">${day.videos.length} video${day.videos.length !== 1 ? 's' : ''}</span>
        <span class="study-time">▶ ${day.total_str}</span>
        ${splitBadge}
      </div>
    </div>
  `;
  return card;
}

// ── Sticky calendar bar ───────────────────────────────────────────────────────
function showStickyCalBar(schedule) {
  const totalDays = schedule.length;
  const totalVids = schedule.reduce((s, d) => s + d.videos.length, 0);
  $('bar-text').textContent =
    `📅 ${totalDays} study day${totalDays !== 1 ? 's' : ''}, ${totalVids} video${totalVids !== 1 ? 's' : ''} — ready to sync`;
  $('sticky-cal-bar').classList.add('visible');
  document.body.classList.add('bar-visible');
}

// ── Behaviour panel ───────────────────────────────────────────────────────────
function renderBehaviourPanel(weekdayH, weekendH, totalDays) {
  const b = loadBehaviour();
  const avgH = ((weekdayH * 5) + (weekendH * 2)) / 7;
  const { type, emoji } = getLearnerType(avgH);
  const schedCount = b.schedulesGenerated || 1;

  const items = [
    { val: `${emoji} ${type}`,       lbl: 'Learner type',        isType: true },
    { val: `${schedCount}`,          lbl: 'Schedules generated'              },
    { val: `${b.visits || 1}`,       lbl: 'Total sessions'                   },
    { val: `${totalDays} days`,      lbl: 'This schedule length'             },
  ];

  $('behavior-grid').innerHTML = items.map(item => `
    <div class="b-item">
      <div class="${item.isType ? 'b-type' : 'b-val'}">${item.val}</div>
      <div class="b-lbl">${item.lbl}</div>
    </div>
  `).join('');
}

// ── Stepper ───────────────────────────────────────────────────────────────────
function advanceStepper(completedStep) {
  show('stepper');
  for (let i = 1; i <= 3; i++) {
    const stepEl = $(`step-${i}`);
    const numEl  = $(`sn-${i}`);
    stepEl.classList.remove('active', 'done');
    if (i < completedStep + 1) {
      stepEl.classList.add('done');
      numEl.textContent = '✓';
    } else if (i === completedStep + 1) {
      stepEl.classList.add('active');
      numEl.textContent = i;
    } else {
      numEl.textContent = i;
    }
  }
}

// ── Confetti ──────────────────────────────────────────────────────────────────
function launchConfetti() {
  const canvas = $('confetti-canvas');
  const ctx = canvas.getContext('2d');
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.classList.remove('hidden');

  const colors = ['#6366F1','#F59E0B','#10B981','#EC4899','#3B82F6','#F97316'];
  const pieces = Array.from({ length: 80 }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * -canvas.height,
    r: Math.random() * 6 + 3,
    d: Math.random() * 80 + 20,
    color: colors[Math.floor(Math.random() * colors.length)],
    tilt: Math.random() * 10 - 5,
    tiltAngle: 0,
    tiltSpeed: Math.random() * 0.1 + 0.05,
  }));

  let frame = 0;
  const MAX = 120;

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach(p => {
      p.tiltAngle += p.tiltSpeed;
      p.y += (Math.cos(frame * 0.01) + p.d / 10 + 1) * 1.2;
      p.x += Math.sin(frame * 0.01) * 1.5;
      p.tilt = Math.sin(p.tiltAngle) * 12;

      ctx.beginPath();
      ctx.lineWidth = p.r;
      ctx.strokeStyle = p.color;
      ctx.moveTo(p.x + p.tilt + p.r / 3, p.y);
      ctx.lineTo(p.x + p.tilt, p.y + p.tilt + p.r * 1.1);
      ctx.stroke();
    });

    frame++;
    if (frame < MAX) requestAnimationFrame(draw);
    else canvas.classList.add('hidden');
  }

  draw();
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function truncate(s, n) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function secToHms(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

function getISOWeek(d) {
  const date = new Date(d.valueOf());
  const day = (date.getDay() + 6) % 7;  // Mon = 0
  date.setDate(date.getDate() - day + 3);
  const firstThursday = date.valueOf();
  date.setMonth(0, 1);
  if (date.getDay() !== 4) {
    date.setMonth(0, 1 + ((4 - date.getDay()) + 7) % 7);
  }
  return 1 + Math.ceil((firstThursday - date) / 604800000);
}

function weekLabel(d) {
  const mon = new Date(d);
  mon.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  const fmt = dd => dd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  return `Week of ${fmt(mon)} – ${fmt(sun)}`;
}

// ── Sticky calendar bar ───────────────────────────────────────────────────────
function showStickyCalBar(schedule) {
  const bar = $('sticky-cal-bar');
  const totalDays = schedule.length;
  const totalVids = schedule.reduce((s, d) => s + d.videos.length, 0);
  $('bar-text').textContent = `📅 ${totalVids} video${totalVids !== 1 ? 's' : ''} across ${totalDays} day${totalDays !== 1 ? 's' : ''} — ready to export!`;
  bar.classList.add('visible');
}

// ── ICS download (POST → blob → save) ────────────────────────────────────────
async function downloadIcs() {
  if (!currentSchedule.length) {
    alert('Please generate a schedule first.');
    return;
  }

  try {
    const resp = await fetch('/download-ics/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        schedule:       currentSchedule,
        playlist_title: currentPlaylistTitle,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.error || 'Failed to generate calendar file.');
      return;
    }

    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = 'study-schedule.ics';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    alert('Network error — could not download calendar file.');
  }
}

// ── Import guide step animations (Intersection Observer) ──────────────────────
function initImportGuideObserver() {
  const steps = document.querySelectorAll('.ig-step[data-delay]');
  if (!steps.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = parseInt(entry.target.dataset.delay, 10) || 0;
        setTimeout(() => entry.target.classList.add('visible'), delay);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  steps.forEach(step => observer.observe(step));
}

// Initialise observer once calendar section is shown
const _origShow = show;
(function patchShow() {
  const calSection = document.getElementById('calendar-section');
  if (!calSection) return;

  const sectionObserver = new MutationObserver(() => {
    if (!calSection.classList.contains('hidden')) {
      initImportGuideObserver();
      sectionObserver.disconnect();
    }
  });
  sectionObserver.observe(calSection, { attributes: true, attributeFilter: ['class'] });
})();
