/**
 * AI Course Generator — Frontend Application (Ollama-Powered)
 * Handles form submission, API calls, and course rendering.
 * Architecture: Weekly outline → Daily breakdown → Day details
 */

const API_BASE = 'http://localhost:8000';

// ─── State ───────────────────────────────────────────────────
let currentCourse = null;

// ─── DOM References ──────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const pages = {
    landing: $('#landing'),
    loading: $('#loading'),
    courseView: $('#courseView'),
};

// ─── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadOllamaModels();
    checkOllamaStatus();
});

// ─── Event Listeners ─────────────────────────────────────────
function setupEventListeners() {
    // Form submit
    $('#courseForm').addEventListener('submit', handleGenerate);

    // Tabs
    $$('.tab').forEach((tab) => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Back button
    $('#backBtn').addEventListener('click', () => showPage('landing'));
}

// ─── Ollama Status Check ─────────────────────────────────────
async function checkOllamaStatus() {
    const dot = $('#statusDot');
    const text = $('#statusText');

    try {
        const response = await fetch(`${API_BASE}/api/health`);
        const data = await response.json();

        if (data.ollama && data.ollama.status === 'connected') {
            dot.classList.add('connected');
            dot.classList.remove('disconnected');
            text.textContent = 'Ollama Connected';
        } else {
            dot.classList.add('disconnected');
            dot.classList.remove('connected');
            text.textContent = 'Ollama Disconnected';
        }
    } catch (e) {
        dot.classList.add('disconnected');
        dot.classList.remove('connected');
        text.textContent = 'Backend Offline';
    }
}

// ─── Load Ollama Models ──────────────────────────────────────
async function loadOllamaModels() {
    const select = $('#model');

    try {
        const response = await fetch(`${API_BASE}/api/models`);
        if (!response.ok) throw new Error('Failed to load models');

        const data = await response.json();
        const models = data.models || [];

        select.innerHTML = '';

        if (models.length === 0) {
            select.innerHTML = '<option value="">No models found</option>';
            $('#modelHint').textContent = 'Run: ollama pull deepseek-r1:1.5b';
            return;
        }

        models.forEach((m) => {
            const opt = document.createElement('option');
            opt.value = m.name;
            const sizeMB = m.size ? `${(m.size / 1e9).toFixed(1)}GB` : '';
            opt.textContent = `${m.name}${sizeMB ? ` (${sizeMB})` : ''}`;
            select.appendChild(opt);
        });

        $('#modelHint').textContent = `${models.length} model${models.length > 1 ? 's' : ''} available locally`;
    } catch (e) {
        select.innerHTML = '<option value="">⚠ Cannot connect to backend</option>';
        $('#modelHint').textContent = 'Make sure the backend server is running on port 8000';
    }
}

// ─── Generate Course (Weekly Outline) ────────────────────────
async function handleGenerate(e) {
    e.preventDefault();

    const goal = $('#goal').value.trim();
    const model = $('#model').value || null;

    if (!goal) {
        showToast('Please enter a learning goal');
        return;
    }

    if (!model) {
        showToast('Please select an Ollama model');
        return;
    }

    // Show loading
    showPage('loading');
    animateLoadingSteps();

    try {
        const response = await fetch(`${API_BASE}/api/generate/outline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal, model }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error: ${response.status}`);
        }

        currentCourse = await response.json();
        currentCourse.requestParams = { goal, model };

        renderCourse(currentCourse);
        showPage('courseView');
        showToast('Course outline generated! Click weeks to load daily breakdown.', false);
    } catch (error) {
        console.error('Generate failed:', error);
        showToast(error.message || 'Failed to generate course. Is Ollama running?');
        showPage('landing');
    }
}

// ─── Loading Animation ──────────────────────────────────────
function animateLoadingSteps() {
    const steps = ['step1', 'step2', 'step3', 'step4'];
    const messages = [
        'Analyzing your learning goal...',
        'Planning 6-month curriculum...',
        'Organizing weekly modules...',
        'Finalizing the roadmap...',
    ];

    let i = 0;
    steps.forEach(s => {
        $(`#${s}`).className = 'step';
        $(`#${s}`).textContent = messages[i];
    });

    const interval = setInterval(() => {
        if (i >= steps.length) {
            clearInterval(interval);
            return;
        }
        if (i > 0) {
            $(`#${steps[i - 1]}`).classList.remove('active');
            $(`#${steps[i - 1]}`).classList.add('done');
        }
        $(`#${steps[i]}`).classList.add('active');
        $('#loadingStatus').textContent = messages[i];
        i++;
    }, 1500);
}

// ─── Render Course ───────────────────────────────────────────
function renderCourse(course) {
    // Header
    const weeks = course.weeks || [];
    let headerHtml = `
    <h1 class="course-title">${escHtml(course.title)}</h1>
    <p class="course-desc">${escHtml(course.description)}</p>
    <div class="course-meta">
      <span class="meta-badge">📅 ${weeks.length} weeks</span>
      <span class="meta-badge">📚 ${course.classes?.length || weeks.length} modules</span>
      <span class="meta-badge">⏱ ~${weeks.length * 5} learning days</span>
    </div>
  `;

    // Prerequisites
    if (course.prerequisites && course.prerequisites.length > 0) {
        headerHtml += `
        <div class="prerequisites-section">
            <h3 class="prereq-title">📋 Prerequisites & Basics</h3>
            <ul class="prereq-list">
                ${course.prerequisites.map(p => `<li>${escHtml(p)}</li>`).join('')}
            </ul>
        </div>
        `;
    }

    $('#courseHeader').innerHTML = headerHtml;

    renderWeeklyTimeline(weeks);
}

// ─── Render Weekly Timeline ──────────────────────────────────
function renderWeeklyTimeline(weeks) {
    if (!weeks || weeks.length === 0) {
        $('#timelineContent').innerHTML =
            '<p style="color:var(--text-muted)">No timeline data available.</p>';
        return;
    }

    // Group weeks into months (4 weeks per month)
    let html = '<div class="timeline">';

    const monthNames = ['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6', 'Month 7'];

    const totalMonths = Math.ceil(weeks.length / 4);
    for (let m = 0; m < totalMonths; m++) {
        const monthWeeks = weeks.slice(m * 4, (m + 1) * 4);

        html += `
        <div class="timeline-month">
            <div class="timeline-month-title">${monthNames[m] || `Month ${m + 1}`}</div>
            ${monthWeeks.map(week => renderWeekCard(week)).join('')}
        </div>
        `;
    }

    html += '</div>';
    $('#timelineContent').innerHTML = html;
}

function renderWeekCard(week) {
    const focusClass = week.focus || 'theory';
    const isExpanded = week._expanded || false;
    const isLoading = week._loading || false;

    let conceptsHtml = '';
    if (week.concepts && week.concepts.length > 0) {
        conceptsHtml = `
        <div class="day-concepts">
            ${week.concepts.map(c => `<span class="concept-tag">${escHtml(c)}</span>`).join('')}
        </div>
        `;
    }

    let daysHtml = '';
    if (isExpanded && week._days) {
        daysHtml = `
        <div class="week-days-breakdown">
            ${week._days.map(day => renderDayCard(day, week.week)).join('')}
        </div>
        `;
    } else if (isLoading) {
        daysHtml = '<div class="week-days-breakdown"><div class="spinner-small">Loading daily breakdown...</div></div>';
    }

    return `
    <div class="timeline-day week-card ${isExpanded ? 'expanded' : ''}" 
         id="week-${week.week}">
        <div class="day-header" onclick="toggleWeekExpand(${week.week})" style="cursor:pointer">
            <span class="day-number">Week ${week.week}</span>
            <span class="day-type ${focusClass}">${focusClass}</span>
            <span class="day-status" style="font-size:0.8em; opacity:0.7">
                ${isExpanded ? '▲ Collapse' : '▼ Click to expand days'}
            </span>
        </div>
        <div class="day-title">${escHtml(week.title)}</div>
        ${conceptsHtml}
        ${daysHtml}
    </div>
    `;
}

function renderDayCard(day, weekNum) {
    const isLoaded = day._loaded || false;
    const globalDay = (weekNum - 1) * 7 + day.day;

    let conceptsHtml = '';
    if (day.concepts && day.concepts.length > 0) {
        conceptsHtml = `
        <div class="day-concepts" style="margin-top:4px">
            ${day.concepts.map(c => `<span class="concept-tag">${escHtml(c)}</span>`).join('')}
        </div>
        `;
    }

    let contentHtml = '';
    if (isLoaded) {
        contentHtml = `<div class="day-content-area">${renderDayContent(day)}</div>`;
    }

    return `
    <div class="timeline-day day-in-week ${isLoaded ? 'loaded' : ''}" 
         id="day-${weekNum}-${day.day}"
         onclick="loadDayContent(${weekNum}, ${day.day})" 
         style="cursor:pointer; margin-left: 16px; border-left: 2px solid var(--border-color); padding-left: 12px;">
        <div class="day-header">
            <span class="day-number" style="font-size:0.75rem">Day ${day.day}</span>
            <span class="day-type ${day.task_type || 'theory'}" style="font-size:0.65rem">${day.task_type || 'theory'}</span>
            ${!isLoaded ? '<span class="day-status" style="font-size:0.7em; opacity:0.6">Load details →</span>' : ''}
        </div>
        <div class="day-title" style="font-size:0.85rem">${escHtml(day.title)}</div>
        ${conceptsHtml}
        ${contentHtml}
    </div>
    `;
}

// ─── Toggle Week Expansion (Lazy Load Days) ──────────────────
async function toggleWeekExpand(weekNum) {
    const weeks = currentCourse.weeks;
    const weekIndex = weeks.findIndex(w => w.week === weekNum);
    if (weekIndex === -1) return;

    const week = weeks[weekIndex];

    // If already expanded, collapse
    if (week._expanded) {
        week._expanded = false;
        renderWeeklyTimeline(weeks);
        return;
    }

    // If days not loaded yet, fetch them
    if (!week._days) {
        week._loading = true;
        renderWeeklyTimeline(weeks);

        try {
            const params = currentCourse.requestParams;
            const response = await fetch(`${API_BASE}/api/generate/week`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    goal: params.goal,
                    week_number: week.week,
                    week_title: week.title,
                    concepts: week.concepts || [],
                    model: params.model,
                }),
            });

            if (!response.ok) throw new Error('Failed to load week details');

            const data = await response.json();
            week._days = data.days || [];
            week._loading = false;
            week._expanded = true;
        } catch (error) {
            console.error(error);
            week._loading = false;
            showToast('Failed to load week details. Click to retry.');
        }
    } else {
        week._expanded = true;
    }

    renderWeeklyTimeline(weeks);
}

// ─── Load Day Content (Lazy Load Details) ────────────────────
async function loadDayContent(weekNum, dayNum) {
    // Stop event from also triggering the week toggle
    event.stopPropagation();

    const week = currentCourse.weeks.find(w => w.week === weekNum);
    if (!week || !week._days) return;

    const day = week._days.find(d => d.day === dayNum);
    if (!day || day._loaded) return;

    const dayEl = $(`#day-${weekNum}-${dayNum}`);
    if (!dayEl) return;

    dayEl.innerHTML += '<div class="spinner-small" style="margin-top:8px">Loading content...</div>';

    try {
        const params = currentCourse.requestParams;
        const response = await fetch(`${API_BASE}/api/generate/day`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                goal: params.goal,
                day_title: day.title,
                day_number: (weekNum - 1) * 7 + dayNum,
                duration_minutes: day.duration_minutes || 60,
                task_type: day.task_type || 'theory',
                model: params.model,
            }),
        });

        if (!response.ok) throw new Error('Failed to load day details');

        const details = await response.json();
        Object.assign(day, details);
        day._loaded = true;

        renderWeeklyTimeline(currentCourse.weeks);
    } catch (error) {
        console.error(error);
        showToast('Failed to load day details.');
    }
}

// ─── Render Day Content ──────────────────────────────────────
function renderDayContent(task) {
    let tocHtml = '';
    if (task.table_of_contents && task.table_of_contents.length > 0) {
        tocHtml = `
            <div class="day-toc" style="margin-top:15px; margin-bottom:15px;">
                <h5 style="margin:0 0 8px 0; color:var(--primary); font-size:0.9rem; text-transform:uppercase; letter-spacing:0.5px;">Table of Contents</h5>
                <ul style="margin:0; padding-left:20px; color:var(--text-secondary);">
                    ${task.table_of_contents.map(t => `<li style="margin-bottom:4px">${escHtml(t)}</li>`).join('')}
                </ul>
            </div>`;
    }

    return `
        <div class="day-desc">${escHtml(task.description)}</div>
        ${tocHtml}
        ${renderResources(task.resources || [])}
    `;
}



function renderResources(resources) {
    if (!resources || resources.length === 0) return '';

    const youtube = resources.filter((r) => r.source === 'youtube');
    const web = resources.filter((r) => r.source === 'web');

    let html = '';

    if (youtube.length > 0) {
        html += `
      <div class="resources-section">
        <h4>🎬 YouTube Videos</h4>
        <div class="resources-grid">
          ${youtube.map(r => `
            <a href="${escAttr(r.url)}" target="_blank" rel="noopener" class="resource-card">
              ${r.thumbnail
                ? `<img class="resource-thumb" src="${escAttr(r.thumbnail)}" alt="${escAttr(r.title)}" loading="lazy" onerror="this.style.display='none'" />`
                : '<div class="resource-thumb" style="display:flex;align-items:center;justify-content:center;font-size:2rem">🎬</div>'
            }
              <div class="resource-info">
                <div class="resource-source youtube">▶ YouTube</div>
                <div class="resource-title">${escHtml(r.title)}</div>
                ${r.description ? `<div class="resource-desc">${escHtml(r.description)}</div>` : ''}
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
    }

    if (web.length > 0) {
        html += `
      <div class="resources-section" style="margin-top:var(--space-lg)">
        <h4>🌐 Web Resources</h4>
        <div class="resources-grid">
          ${web.map(r => `
            <a href="${escAttr(r.url)}" target="_blank" rel="noopener" class="resource-card">
              <div class="resource-info">
                <div class="resource-source web">🌐 Article</div>
                <div class="resource-title">${escHtml(r.title)}</div>
                ${r.description ? `<div class="resource-desc">${escHtml(r.description)}</div>` : ''}
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
    }

    return html;
}

// ─── Class Toggle ────────────────────────────────────────────


// ─── Page Navigation ─────────────────────────────────────────
function showPage(name) {
    Object.values(pages).forEach((p) => p.classList.remove('active'));
    if (pages[name]) pages[name].classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── Tab Switching ───────────────────────────────────────────


// ─── Toast Notifications ────────────────────────────────────
function showToast(message, isError = true) {
    const toast = $('#toast');
    const icon = toast.querySelector('.toast-icon');
    const msg = toast.querySelector('.toast-message');

    icon.textContent = isError ? '⚠️' : '✅';
    msg.textContent = message;
    toast.classList.add('visible');

    setTimeout(() => toast.classList.remove('visible'), 4000);
}

// ─── Utilities ───────────────────────────────────────────────
function escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escAttr(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
