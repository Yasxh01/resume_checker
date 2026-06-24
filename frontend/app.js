/* ============================================================
   app.js — RecruitIQ Frontend Application
   ============================================================
   Complete UI logic for:
   - Theme toggle (dark/light)
   - JD template loader
   - Candidate card management
   - PDF upload
   - Weight sliders with auto-normalization
   - Pipeline execution via FastAPI
   - Animated score counters
   - Radar charts (Chart.js)
   - Bias flag rendering
   - Side-by-side comparison modal
   - CSV export
   ============================================================ */

'use strict';

// ============================================================
// CONFIGURATION
// ============================================================
// Config
const API_BASE = '';

// Layer metadata: label, color, key
const LAYERS = [
  { key: 'score_l1', label: '🧠 Semantic', color: '#7c6ff7', shortLabel: 'Semantic' },
  { key: 'score_l2', label: '🗂️ Taxonomy', color: '#00d4aa', shortLabel: 'Taxonomy' },
  { key: 'score_l3', label: '📅 Experience', color: '#f79a1e', shortLabel: 'Experience' },
  { key: 'score_l4', label: '💼 Projects', color: '#e91e8c', shortLabel: 'Projects' },
  { key: 'score_l5', label: '🐙 GitHub', color: '#3b9eff', shortLabel: 'GitHub' },
];

const WEIGHT_DEFAULTS = [8, 7, 6, 5, 4];
const RANK_MEDALS = ['🥇', '🥈', '🥉'];

// ============================================================
// STATE
// ============================================================
let state = {
  theme: 'dark',
  jdTemplates: {},
  candidates: [],
  weights: [...WEIGHT_DEFAULTS],
  lastResults: null,
  resultsCurrentPage: 1,
  resultsItemsPerPage: 10,
  tableCurrentPage: 1,
  tableItemsPerPage: 10,
  radarCharts: {},
  currentPage: 1,
  itemsPerPage: 10,
};

// ============================================================
// DOM HELPERS
// ============================================================
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function show(el) { if (el) el.style.display = ''; }
function hide(el) { if (el) el.style.display = 'none'; }

function autoExtractMetadata(c) {
  if (!c.resume_text) return;
  const text = c.resume_text;

  // 1. GitHub Username
  const githubMatch = text.match(/(?:github\.com\/|github:? )([a-zA-Z0-9-]+)/i);
  if (githubMatch && githubMatch[1]) c.github_username = githubMatch[1].trim();

  // 2. Years of Experience (Smarter Heuristic)
  // First try direct mention
  const expMatch = text.match(/(\d+)\+?\s*years?(?:\s*of)?\s*experience/i);
  if (expMatch && expMatch[1]) {
    c.years_of_experience = parseInt(expMatch[1], 10);
  } else {
    // Fallback: Estimate from date ranges (e.g. 2018 - 2023)
    const years = [...text.matchAll(/(?:20|19)\d{2}/g)].map(m => parseInt(m[0], 10));
    if (years.length >= 2) {
      const minYear = Math.min(...years);
      const maxYear = Math.max(...years, new Date().getFullYear());
      // Sanity check
      if (maxYear - minYear > 0 && maxYear - minYear < 40) {
        c.years_of_experience = maxYear - minYear;
      } else {
        c.years_of_experience = 0;
      }
    } else {
      c.years_of_experience = 0; // Default
    }
  }

  // 3. Skills Extraction
  const commonSkills = ["Python", "JavaScript", "React", "Node.js", "Java", "C++", "SQL", "Docker", "Kubernetes", "AWS", "Machine Learning", "Data Analysis", "Go", "Rust", "Ruby on Rails", "Angular", "Vue.js", "MongoDB", "PostgreSQL", "Redis", "TypeScript", "HTML", "CSS", "C#", ".NET", "PHP", "Swift", "Kotlin", "Spring", "Django", "Flask", "Express", "GCP", "Azure"];
  const foundSkills = new Set(c.skills || []);

  commonSkills.forEach(skill => {
    const escapedSkill = skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (new RegExp(`\\b${escapedSkill}\\b`, 'i').test(text)) {
      foundSkills.add(skill);
    }
  });
  c.skills = Array.from(foundSkills);

  // 4. Projects Text (Robust Heuristic)
  // Look for "Projects", "Personal Projects", "Open Source", etc.
  const projectsMatch = text.match(/(?:(?:Personal\s+|Academic\s+)?Projects?|Open Source)(?:\s*:|\n|)[ \t]*([\s\S]{10,800}?)(?=\n\s*(?:(?:Professional\s+|Work\s+)?Experience|Education|Skills|Languages|Certifications|Work History|Employment|Career|$))/i);
  
  if (projectsMatch && projectsMatch[1]) {
    let pText = projectsMatch[1].trim();
    if (pText.length > 500) pText = pText.substring(0, 500) + '...';
    c.projects_text = pText;
  } else {
    // If we can't cleanly extract a section, grab a slice containing "project" context.
    // Use [\s\S] instead of . so it crosses line breaks!
    const fallbackMatch = text.match(/[\s\S]{0,150}project[\s\S]{0,400}/i);
    if (fallbackMatch) {
      c.projects_text = fallbackMatch[0].trim() + '...';
    } else {
      // Ultimate fallback: Just grab the last 400 characters of the resume
      c.projects_text = text.length > 400 ? text.slice(-400) : text;
    }
  }
}

function logProgress(msg, color = '') {
  const log = $('#progressLog');
  if (!log) return;
  const line = document.createElement('div');
  line.className = 'progress-log-line';
  line.textContent = msg;
  if (color) line.style.color = color;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

function setProgress(pct) {
  const fill = $('#progressBarFill');
  if (fill) fill.style.width = Math.min(pct, 100) + '%';
}

// ============================================================
// THEME TOGGLE
// ============================================================
function initTheme() {
  const saved = localStorage.getItem('recruitiq-theme') || 'dark';
  applyTheme(saved);

  $('#themeToggle').addEventListener('click', () => {
    applyTheme(state.theme === 'dark' ? 'light' : 'dark');
  });
}

function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  $('#themeIcon').textContent = theme === 'dark' ? '🌙' : '☀️';
  $('#footerMode').textContent = theme === 'dark' ? '🌙 Dark Mode' : '☀️ Light Mode';
  localStorage.setItem('recruitiq-theme', theme);

  // Re-render radar charts with new theme colours
  Object.values(state.radarCharts).forEach(chart => {
    if (chart) {
      const gridColor = theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
      const tickColor = theme === 'dark' ? '#8b92b8' : '#5a6080';
      chart.options.scales.r.grid.color = gridColor;
      chart.options.scales.r.ticks.color = tickColor;
      chart.options.scales.r.pointLabels.color = tickColor;
      chart.update();
    }
  });
}

// ============================================================
// API HEALTH CHECK
// ============================================================
async function checkApiHealth() {
  const dot = $('.status-dot');
  const text = $('#apiStatusText');
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      dot.classList.add('online');
      text.textContent = 'API Online';
    } else {
      throw new Error('Not OK');
    }
  } catch {
    dot.classList.add('offline');
    text.textContent = 'API Offline';
    showApiOfflineWarning();
  }
}

function showApiOfflineWarning() {
  const banner = document.createElement('div');
  banner.style.cssText = `
    background: rgba(233,30,140,0.1);
    border: 1px solid rgba(233,30,140,0.3);
    color: #e91e8c;
    padding: 0.75rem 1.5rem;
    text-align: center;
    font-size: 0.82rem;
    font-weight: 600;
  `;
  banner.innerHTML = `
    ⚠️ FastAPI backend not running.
    Start it with: <code style="background:rgba(0,0,0,0.2);padding:0.1rem 0.4rem;border-radius:4px;">
    cd backend && uvicorn main:app --reload --port 8000</code>
  `;
  document.body.insertBefore(banner, document.body.firstChild);
}

// ============================================================
// LOAD JD TEMPLATES
// ============================================================
async function loadJdTemplates() {
  try {
    const res = await fetch(`${API_BASE}/api/job-descriptions`);
    const data = await res.json();

    state.jdTemplates = data.job_descriptions;

    // Populate selector
    const sel = $('#jdSelector');
    sel.innerHTML = '';
    Object.keys(data.job_descriptions).forEach(key => {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = key;
      sel.appendChild(opt);
    });

    // Load default JD
    const defaultKey = data.default || Object.keys(data.job_descriptions)[0];
    sel.value = defaultKey;
    loadJd(defaultKey);

    // Load default candidates
    if (data.candidates && data.candidates.length) {
      state.candidates = data.candidates.map((c, i) => ({ ...c, id: i, isMinimized: true }));
      renderCandidateCards();
    }

    sel.addEventListener('change', () => loadJd(sel.value));
  } catch (err) {
    console.error('Failed to load JD templates:', err);
  }
}

function loadJd(key) {
  const jd = state.jdTemplates[key];
  if (!jd) return;
  $('#jdText').value = jd.text;
  $('#jdSkills').value = jd.required_skills.join(', ');
  $('#requiredYears').value = jd.required_years;
}

// ============================================================
// WEIGHT SLIDERS
// ============================================================
function initSliders() {
  const container = $('#sliderGroup');
  const summary = $('#weightSummary');
  container.innerHTML = '';

  LAYERS.forEach((layer, i) => {
    const item = document.createElement('div');
    item.className = 'slider-item';
    item.innerHTML = `
      <div class="slider-header">
        <span class="slider-label">${layer.label}</span>
        <span class="slider-value" id="sliderVal${i}">${state.weights[i]}</span>
      </div>
      <input type="range" min="0" max="10"
             value="${state.weights[i]}" id="slider${i}"
             style="accent-color:${layer.color}" />
    `;
    container.appendChild(item);

    $(`#slider${i}`).addEventListener('input', (e) => {
      state.weights[i] = parseInt(e.target.value);
      $(`#sliderVal${i}`).textContent = state.weights[i];
      renderWeightSummary();
    });

    $(`#slider${i}`).addEventListener('change', () => {
      if (state.lastResults) {
        recalculateScores();
      }
    });
  });

  renderWeightSummary();
}

function getNormalizedWeights() {
  const total = state.weights.reduce((a, b) => a + b, 0);
  if (total === 0) return state.weights.map(() => 0);
  return state.weights.map(w => w / total);
}

function renderWeightSummary() {
  const norm = getNormalizedWeights();
  const summary = $('#weightSummary');
  summary.innerHTML = LAYERS.map((l, i) => `
    <div class="weight-item" style="opacity: ${state.weights[i] === 0 ? 0.4 : 1}; transition: opacity 0.3s;">
      <span>${l.shortLabel}</span>
      <span>${(norm[i] * 100).toFixed(1)}%</span>
    </div>
  `).join('');
}

function recalculateScores() {
  if (!state.lastResults) return;
  const norm = getNormalizedWeights();

  // Recompute composite scores based on new weights
  state.lastResults.results.forEach(r => {
    let composite = 0;
    composite += (r.layer_scores.l1 || 0) * norm[0];
    composite += (r.layer_scores.l2 || 0) * norm[1];
    composite += (r.layer_scores.l3 || 0) * norm[2];
    composite += (r.layer_scores.l4 || 0) * norm[3];
    composite += (r.layer_scores.l5 || 0) * norm[4];
    r.composite_score = composite;
  });

  // Update state.lastResults.weights so the Weight Grid shows correctly
  state.lastResults.weights = {
    w1: norm[0],
    w2: norm[1],
    w3: norm[2],
    w4: norm[3],
    w5: norm[4]
  };

  // Resort candidates by new composite score descending
  state.lastResults.results.sort((a, b) => b.composite_score - a.composite_score);

  // Re-render the results section with updated scores and sorting
  renderResults(state.lastResults);
}

// ============================================================
// CANDIDATE CARDS & PAGINATION
// ============================================================
function initPagination() {
  $('#itemsPerPage').addEventListener('change', (e) => {
    state.itemsPerPage = e.target.value === '1000000' ? 1000000 : parseInt(e.target.value);
    state.currentPage = 1;
    renderCandidateCards();
  });

  $('#prevPageBtn').addEventListener('click', () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      renderCandidateCards();
    }
  });

  $('#nextPageBtn').addEventListener('click', () => {
    const totalPages = Math.ceil(state.candidates.length / state.itemsPerPage);
    if (state.currentPage < totalPages) {
      state.currentPage++;
      renderCandidateCards();
    }
  });
}

function initResultsPagination() {
  $('#resultsItemsPerPage').addEventListener('change', (e) => {
    state.resultsItemsPerPage = e.target.value === '1000000' ? 1000000 : parseInt(e.target.value);
    state.resultsCurrentPage = 1;
    renderRankingCards();
  });

  $('#prevResultsPageBtn').addEventListener('click', () => {
    if (state.resultsCurrentPage > 1) {
      state.resultsCurrentPage--;
      renderRankingCards();
    }
  });

  $('#nextResultsPageBtn').addEventListener('click', () => {
    const totalResults = state.lastResults?.results?.length || 0;
    const totalPages = Math.ceil(totalResults / state.resultsItemsPerPage);
    if (state.resultsCurrentPage < totalPages) {
      state.resultsCurrentPage++;
      renderRankingCards();
    }
  });
}

function initTablePagination() {
  $('#tableItemsPerPage').addEventListener('change', (e) => {
    state.tableItemsPerPage = e.target.value === '1000000' ? 1000000 : parseInt(e.target.value);
    state.tableCurrentPage = 1;
    renderScoreTable();
  });

  $('#prevTablePageBtn').addEventListener('click', () => {
    if (state.tableCurrentPage > 1) {
      state.tableCurrentPage--;
      renderScoreTable();
    }
  });

  $('#nextTablePageBtn').addEventListener('click', () => {
    const totalResults = state.lastResults?.results?.length || 0;
    const totalPages = Math.ceil(totalResults / state.tableItemsPerPage);
    if (state.tableCurrentPage < totalPages) {
      state.tableCurrentPage++;
      renderScoreTable();
    }
  });
}

function renderCandidateCards() {
  const grid = $('#candidatesGrid');
  grid.innerHTML = '';

  const totalPages = Math.max(1, Math.ceil(state.candidates.length / state.itemsPerPage));
  if (state.currentPage > totalPages) state.currentPage = totalPages;

  if (state.candidates.length > 0) {
    $('#paginationControls').style.display = 'flex';
    $('#pageInfo').textContent = `${state.currentPage} / ${totalPages}`;
    $('#prevPageBtn').disabled = state.currentPage === 1;
    $('#nextPageBtn').disabled = state.currentPage === totalPages;
  } else {
    hide($('#paginationControls'));
  }

  if (!state.candidates.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <span class="empty-state-icon">👥</span>
        No candidates yet. Click "Add Candidate" or "Upload PDFs" to begin.
      </div>`;
    return;
  }

  const startIdx = (state.currentPage - 1) * state.itemsPerPage;
  const endIdx = startIdx + state.itemsPerPage;
  const pageCandidates = state.candidates.slice(startIdx, endIdx);

  pageCandidates.forEach((c, idx) => {
    const i = startIdx + idx; // Absolute index in state.candidates
    const card = document.createElement('div');
    card.className = 'candidate-card';
    card.dataset.id = i;
    card.innerHTML = `
      <div class="candidate-card-header" onclick="toggleCandidate(${i})">
        
        <div style="display:flex; align-items:center; gap:1rem; flex:1;">
          <!-- Serial Number & Icon -->
          <div style="display:flex; align-items:center; justify-content:center; width:36px; height:36px; background:var(--bg-input); border-radius:8px; font-weight:700; color:var(--text-muted); font-size:0.8rem;">
            ${i + 1}
          </div>
          
          <div style="display:flex; align-items:center; justify-content:center; width:36px; height:36px; background:rgba(124,111,247,0.1); border-radius:8px; color:var(--accent-purple);">
            <i data-lucide="${c._pdfSource ? 'file-text' : 'user'}"></i>
          </div>

          <!-- Name & Meta -->
          <div>
            <div class="candidate-name" id="cName${i}" style="font-size:0.95rem;">${escHtml(c.name)}</div>
            <div class="candidate-meta" style="display:flex; gap:1rem; align-items:center; margin-top:0.2rem; font-size:0.75rem;">
              <span style="display:flex; align-items:center;"><i data-lucide="briefcase" style="width:12px;height:12px;margin-right:4px;"></i>${c.years_of_experience} yrs exp</span>
              ${c._pdfSource ? `<span style="display:flex; align-items:center; color:var(--accent-teal);"><i data-lucide="check-circle" style="width:12px;height:12px;margin-right:4px;"></i>PDF Loaded</span>` : ''}
            </div>
          </div>
        </div>

        <div style="display:flex; gap:0.5rem; align-items:center;">
          <button class="btn btn-sm" style="background:transparent; border:none; color:var(--text-muted);" title="${c.isMinimized ? 'Expand' : 'Minimize'}">
            <i data-lucide="${c.isMinimized ? 'chevron-down' : 'chevron-up'}"></i>
          </button>
          <button class="btn btn-sm" style="background:transparent; border:none; color:#e91e8c;" onclick="event.stopPropagation(); removeCandidate(${i})" title="Remove">
            <i data-lucide="trash-2"></i>
          </button>
        </div>
      </div>

      <div style="display: ${c.isMinimized ? 'none' : 'block'}; padding: 1rem; border-top: 1px solid var(--border-light);">

      <div class="candidate-upload-zone" style="display:flex; justify-content:space-between; align-items:center; padding-right:1rem;">
        <div style="flex:1; cursor:pointer;" onclick="triggerPdfUpload(${i})">
          <i data-lucide="file-text"></i>
          ${c._pdfSource ? `Loaded: ${escHtml(c._pdfSource)} (Click to replace)` : 'Upload PDF to Auto-Fill'}
        </div>
        ${c._pdfUrl ? `
        <button class="btn btn-sm" onclick="event.stopPropagation(); window.open('${c._pdfUrl}', '_blank')" style="background:var(--accent-purple); color:#fff; border:none; padding:0.2rem 0.6rem; font-size:0.8rem;">
          <i data-lucide="eye" style="width:14px;height:14px;"></i> Preview
        </button>
        ` : ''}
      </div>

      <div class="candidate-data-box">
        <div class="candidate-data-header">
          <i data-lucide="edit-3"></i> Manual Entry (Optional)
        </div>

        <div class="candidate-field">
          <label>Full Name</label>
          <input type="text" value="${escHtml(c.name)}"
                 oninput="updateCandidate(${i}, 'name', this.value)" />
        </div>

        <div class="candidate-field">
          <label>Resume Text</label>
          <textarea rows="3"
            oninput="updateCandidate(${i}, 'resume_text', this.value)"
          >${escHtml(c.resume_text)}</textarea>
        </div>

        <div class="candidate-field">
          <label>Skills (comma-separated)</label>
          <input type="text" value="${escHtml((c.skills || []).join(', '))}"
                 oninput="updateCandidate(${i}, 'skills', this.value.split(',').map(s=>s.trim()).filter(Boolean))" />
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
          <div class="candidate-field">
            <label>Years Exp.</label>
            <input type="number" min="0" max="40" value="${c.years_of_experience}"
                   oninput="updateCandidate(${i}, 'years_of_experience', parseInt(this.value)||0)" />
          </div>
          <div class="candidate-field">
            <label>GitHub Username</label>
            <input type="text" value="${escHtml(c.github_username || '')}"
                   oninput="updateCandidate(${i}, 'github_username', this.value)" />
          </div>
        </div>

        <div class="candidate-field">
          <label>Projects Text</label>
          <textarea rows="2"
            oninput="updateCandidate(${i}, 'projects_text', this.value)"
          >${escHtml(c.projects_text || '')}</textarea>
        </div>
      </div>
      </div> <!-- End collapsible wrapper -->
    `;
    grid.appendChild(card);
  });

  if (window.lucide) {
    lucide.createIcons({ root: grid });
  }
}

function toggleCandidate(idx) {
  if (state.candidates[idx]) {
    state.candidates[idx].isMinimized = !state.candidates[idx].isMinimized;
    renderCandidateCards();
  }
}

function updateCandidate(idx, field, value) {
  if (state.candidates[idx]) {
    state.candidates[idx][field] = value;
    if (field === 'name') {
      const nameEl = document.getElementById(`cName${idx}`);
      if (nameEl) nameEl.textContent = value;
    }
  }
}

function removeCandidate(idx) {
  state.candidates.splice(idx, 1);
  // Re-number remaining default candidate names sequentially
  state.candidates.forEach((c, i) => {
    if (/^Candidate \d+$/.test(c.name)) {
      c.name = `Candidate ${i + 1}`;
    }
  });
  renderCandidateCards();
}

function addCandidate() {
  state.candidates.push({
    id: Date.now(),
    name: `Candidate ${state.candidates.length + 1}`,
    resume_text: '',
    skills: [],
    years_of_experience: 0,
    projects_text: '',
    github_username: '',
    isMinimized: true, // Always minimized by default
  });
  state.currentPage = Math.max(1, Math.ceil(state.candidates.length / state.itemsPerPage));
  renderCandidateCards();
  // Scroll to bottom of grid
  const grid = $('#candidatesGrid');
  grid.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

window.removeCandidate = removeCandidate;
window.updateCandidate = updateCandidate;
window.toggleCandidate = toggleCandidate;

window.triggerPdfUpload = function (idx) {
  state._targetUploadIndex = idx;
  $('#pdfInput').click();
};

// ============================================================
// PDF UPLOAD & DRAG/DROP
// ============================================================
function initPdfUpload() {
  const btn = $('#uploadPdfBtn');
  const input = $('#pdfInput');

  btn.addEventListener('click', () => {
    state._targetUploadIndex = null;
    input.click();
  });

  const handleFiles = async (files) => {
    if (!files.length) return;

    const isTargeted = state._targetUploadIndex !== null && state._targetUploadIndex !== undefined;
    const targetBtn = isTargeted ? $(`#cUploadBtn${state._targetUploadIndex}`) : btn;

    if (targetBtn) {
      targetBtn.innerHTML = `<span class="spinner"></span> Parsing ${files.length} file(s)...`;
      if (!isTargeted) targetBtn.disabled = true;
    }

    try {
      let usedTarget = false;
      const chunkSize = 5;

      for (let i = 0; i < files.length; i += chunkSize) {
        const chunk = files.slice(i, i + chunkSize);

        const promises = chunk.map(async (file) => {
          const formData = new FormData();
          formData.append('file', file);
          const res = await fetch(`${API_BASE}/api/upload-resume`, { method: 'POST', body: formData });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Upload failed with status ${res.status}`);
          }
          const data = await res.json();
          return { file, data };
        });

        const results = await Promise.allSettled(promises);

        let hasError = false;
        let errorMsg = '';

        results.forEach((result) => {
          if (result.status === 'fulfilled') {
            const { file, data } = result.value;
            if (isTargeted && !usedTarget) {
              const c = state.candidates[state._targetUploadIndex];
              if (/^Candidate \d+$/.test(c.name)) c.name = file.name.replace('.pdf', '');
              c.resume_text = data.extracted_text;
              c._pdfSource = file.name;
              c._pdfUrl = URL.createObjectURL(file);
              autoExtractMetadata(c);
              usedTarget = true;
            } else {
              const c = {
                id: Date.now() + Math.random(),
                name: file.name.replace('.pdf', ''),
                resume_text: data.extracted_text,
                skills: [],
                years_of_experience: 0,
                projects_text: '',
                github_username: '',
                _pdfSource: file.name,
                _pdfUrl: URL.createObjectURL(file),
                isMinimized: true // Always minimized by default
              };
              autoExtractMetadata(c);
              state.candidates.push(c);
            }
          } else {
            hasError = true;
            errorMsg = result.reason.message || 'Network Error';
          }
        });

        if (hasError) {
          throw new Error(errorMsg === 'Failed to fetch' ? 'Failed to connect to backend. Is the Python server running on port 8000?' : errorMsg);
        }

        if (!isTargeted && targetBtn) {
          targetBtn.innerHTML = `<span class="spinner"></span> Parsed ${Math.min(i + chunkSize, files.length)} / ${files.length}`;
        }
        renderCandidateCards();
      }

      showToast(`✅ Successfully processed ${files.length} PDF(s)`, 'success');

      // Auto-navigate to the last page so the user sees the newly added candidates
      if (!isTargeted) {
        state.currentPage = Math.max(1, Math.ceil(state.candidates.length / state.itemsPerPage));
        renderCandidateCards();
        const grid = $('#candidatesGrid');
        grid.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }

    } catch (err) {
      showToast(`❌ PDF batch upload failed: ${err.message}`, 'error');
    } finally {
      if (!isTargeted && btn) {
        btn.innerHTML = '<i data-lucide="upload"></i> Upload PDFs';
        btn.disabled = false;
      } else if (targetBtn) {
        const c = state.candidates[state._targetUploadIndex];
        targetBtn.innerHTML = `<i data-lucide="file-text"></i> ${c && c._pdfSource ? `Loaded: ${escHtml(c._pdfSource)}` : 'Upload PDF to Auto-Fill'}`;
      }
      state._targetUploadIndex = null;
      if (window.lucide) lucide.createIcons();
      input.value = '';
    }
  };

  input.addEventListener('change', (e) => {
    handleFiles(Array.from(e.target.files));
  });

  // Global Drag & Drop functionality
  document.body.addEventListener('dragover', (e) => {
    e.preventDefault();
    document.body.classList.add('drag-active');
  });

  document.body.addEventListener('dragleave', (e) => {
    e.preventDefault();
    if (e.clientX === 0 || e.clientY === 0) { // Ensures we actually left the window
      document.body.classList.remove('drag-active');
    }
  });

  document.body.addEventListener('drop', (e) => {
    e.preventDefault();
    document.body.classList.remove('drag-active');
    const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
    if (files.length > 0) {
      state._targetUploadIndex = null; // Drag and drop is always global bulk upload
      handleFiles(files);
    } else {
      showToast('Please drop valid PDF files only.', 'error');
    }
  });
}

// ============================================================
// EVALUATION PIPELINE
// ============================================================
async function runEvaluation() {
  // Validate inputs
  if (!state.candidates.length) {
    showToast('Add at least one candidate before running.', 'error');
    return;
  }

  const jdText = $('#jdText').value.trim();
  const jdSkillsRaw = $('#jdSkills').value.trim();
  const requiredYears = parseInt($('#requiredYears').value) || 0;

  if (!jdText) {
    showToast('Please enter a job description.', 'error');
    return;
  }

  const jdSkills = jdSkillsRaw.split(',').map(s => s.trim()).filter(Boolean);

  // Build weights
  const norm = getNormalizedWeights();
  const weights = {
    w1: parseFloat((norm[0] * 100).toFixed(4)),
    w2: parseFloat((norm[1] * 100).toFixed(4)),
    w3: parseFloat((norm[2] * 100).toFixed(4)),
    w4: parseFloat((norm[3] * 100).toFixed(4)),
    w5: parseFloat((norm[4] * 100).toFixed(4)),
  };

  const validCandidates = state.candidates.filter(c => c.resume_text && c.resume_text.trim() !== '');

  if (!validCandidates.length) {
    showToast('Please add at least one candidate with a resume before running.', 'error');
    return;
  }

  // Build request body
  const body = {
    jd_text: jdText,
    jd_skills: jdSkills,
    required_years: requiredYears,
    candidates: validCandidates.map(c => ({
      name: c.name || 'Unknown',
      resume_text: c.resume_text || '',
      skills: Array.isArray(c.skills) ? c.skills : [],
      years_of_experience: c.years_of_experience || 0,
      projects_text: c.projects_text || '',
      github_username: c.github_username || '',
    })),
    weights: weights,
    generate_verdicts: $('#generateVerdicts').checked,
    gemini_api_key: $('#geminiApiKey') ? $('#geminiApiKey').value.trim() : ''
  };

  // Update UI: show progress, hide results
  const runBtn = $('#runBtn');
  runBtn.disabled = true;
  runBtn.innerHTML = `<span class="spinner"></span> Running Pipeline...`;
  hide($('#resultsSection'));

  const progressPanel = $('#progressPanel');
  show(progressPanel);
  $('#progressLog').innerHTML = '';
  setProgress(0);

  // Progress simulation steps
  const totalSteps = state.candidates.length * 5 + 2;
  let step = 0;

  function tick(msg, color) {
    step++;
    logProgress(msg, color);
    setProgress((step / totalSteps) * 95);
  }

  try {
    tick('⚙️  Initializing evaluation pipeline...');

    for (let i = 0; i < state.candidates.length; i++) {
      const name = state.candidates[i].name;
      tick(`\n🔍 Evaluating: ${name}`);
      tick(`  → 🧠 Layer 1: Neural semantic matching...`);
      tick(`  → 🗂️  Layer 2: Taxonomy & alias resolution...`);
      tick(`  → 📅 Layer 3: Experience ratio scoring...`);
      tick(`  → 💼 Layer 4: Project portfolio relevance...`);
      tick(`  → 🐙 Layer 5: GitHub behavioral API...`);
    }

    tick('\n📊 Computing composite scores & ranking...');

    // Actual API call
    const res = await fetch(`${API_BASE}/api/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    state.lastResults = data;

    setProgress(100);
    logProgress('\n✅ Pipeline complete!', '#00d4aa');

    // Render results
    setTimeout(() => {
      hide(progressPanel);
      renderResults(data);
    }, 600);

  } catch (err) {
    logProgress(`\n❌ Error: ${err.message}`, '#e91e8c');
    showToast(`Evaluation failed: ${err.message}`, 'error');
    runBtn.disabled = false;
    runBtn.innerHTML = `<i data-lucide="zap"></i> Run Evaluation Pipeline`;
    lucide.createIcons();
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = `<i data-lucide="zap"></i> Run Evaluation Pipeline`;
    lucide.createIcons();
  }
}

// ============================================================
// RENDER RESULTS
// ============================================================
function renderResults(data) {
  const section = $('#resultsSection');
  show(section);
  section.scrollIntoView({ behavior: 'smooth' });

  // Destroy old radar charts
  Object.values(state.radarCharts).forEach(c => c?.destroy());
  state.radarCharts = {};

  renderRankingCards(data.results);
  renderBiasFlags(data.bias_flags);
  renderScoreTable(data.results);
  renderWeightGrid(data.weights);
}

// ============================================================
// RANKING CARDS
// ============================================================
function renderRankingCards(overrideResults = null) {
  const container = $('#rankingCards');
  container.innerHTML = '';

  const resultsToRender = overrideResults || state.lastResults?.results || [];

  const totalPages = Math.max(1, Math.ceil(resultsToRender.length / state.resultsItemsPerPage));
  if (state.resultsCurrentPage > totalPages) state.resultsCurrentPage = totalPages;

  if (resultsToRender.length > 0) {
    $('#resultsPaginationControls').style.display = 'flex';
    $('#resultsPageInfo').textContent = `${state.resultsCurrentPage} / ${totalPages}`;
    $('#prevResultsPageBtn').disabled = state.resultsCurrentPage === 1;
    $('#nextResultsPageBtn').disabled = state.resultsCurrentPage === totalPages;
  } else {
    $('#resultsPaginationControls').style.display = 'none';
  }

  const startIdx = (state.resultsCurrentPage - 1) * state.resultsItemsPerPage;
  const endIdx = startIdx + state.resultsItemsPerPage;
  const pageResults = resultsToRender.slice(startIdx, endIdx);

  const animated = $('#animatedCounters').checked;

  pageResults.forEach((r, idx) => {
    const globalIdx = startIdx + idx; // For IDs
    const medal = RANK_MEDALS[globalIdx] || `#${globalIdx + 1}`;
    const card = document.createElement('div');
    card.className = 'ranking-card';

    const verdictHTML = r.verdict ? buildVerdictHTML(r.verdict) : '';
    const githubHTML = buildGithubHTML(r.github_data);
    const skillHTML = buildSkillHTML(r.matched_skills, r.missing_skills);

    card.innerHTML = `
      <!-- HEADER -->
      <div class="ranking-card-header" style="cursor:pointer;" onclick="const body = this.nextElementSibling; const icon = this.querySelector('.toggle-icon'); if(body.style.display === 'none'){ body.style.display = 'grid'; icon.setAttribute('data-lucide', 'chevron-up'); } else { body.style.display = 'none'; icon.setAttribute('data-lucide', 'chevron-down'); } if(window.lucide) lucide.createIcons();">
        <div class="ranking-card-left" style="display:flex; align-items:center;">
          <i data-lucide="chevron-down" class="toggle-icon" style="color:var(--text-muted); margin-right:0.5rem; width:20px;"></i>
          <span class="rank-medal">${medal}</span>
          <div>
            <div class="ranking-name">${escHtml(r.name)}</div>
            <div class="ranking-meta">
              ${r.years_of_experience} yrs exp &nbsp;·&nbsp;
              Required: ${r.required_years} yrs &nbsp;·&nbsp;
              GitHub: ${r.github_data?.status === 'success' ? r.github_data.public_repos + ' repos' : 'N/A'}
            </div>
          </div>
        </div>
        <div style="display:flex; flex-direction:column; align-items:flex-end;">
          <div class="composite-score" id="cScore${globalIdx}">0%</div>
          <div style="margin-top:0.5rem; display:flex; gap:0.5rem;">
            <button class="btn btn-sm" onclick="event.stopPropagation(); generateInterviewQuestions(${globalIdx})" title="AI Interview Guide" style="background:var(--bg-panel); border:1px solid var(--accent-teal); color:var(--accent-teal); padding:0.2rem 0.5rem; font-size:0.75rem;">
              <i data-lucide="bot" style="width:12px; height:12px;"></i> Q&A
            </button>
            ${state.candidates[globalIdx] && state.candidates[globalIdx]._pdfUrl ? `
            <button class="btn btn-sm" onclick="event.stopPropagation(); window.open('${state.candidates[globalIdx]._pdfUrl}', '_blank')" title="View PDF" style="background:var(--accent-purple); border:none; color:#fff; padding:0.2rem 0.5rem; font-size:0.75rem;">
              <i data-lucide="file-text" style="width:12px; height:12px;"></i> PDF
            </button>
            ` : ''}
          </div>
        </div>
      </div>

      <!-- BODY: Layer scores + Radar chart -->
      <div class="card-body-grid" style="display:none; padding-top:1.5rem; border-top:1px solid var(--border-light); margin-top:1rem;">
        <div>
          <!-- Layer scores -->
          <div class="layer-scores-grid">
            ${LAYERS.map((l, li) => `
              <div class="layer-score-item">
                <span class="layer-score-label">${l.shortLabel}</span>
                <span class="layer-score-value" id="lScore${globalIdx}_${li}" style="color:${l.color}">0%</span>
                <div class="score-bar">
                  <div class="score-bar-fill" id="lBar${globalIdx}_${li}" style="background:${l.color}"></div>
                </div>
              </div>
            `).join('')}
          </div>

          <!-- Composite bar -->
          <div class="composite-bar-wrap">
            <div class="composite-bar-label">
              <span>Overall Composite Score</span>
              <span id="cBarLabel${globalIdx}">0%</span>
            </div>
            <div class="composite-bar">
              <div class="composite-bar-fill" id="cBar${globalIdx}"></div>
            </div>
          </div>

          <!-- Skill explanation -->
          ${skillHTML}

          <!-- GitHub info -->
          ${githubHTML}

          <!-- LLM Verdict -->
          ${verdictHTML}
        </div>

        <!-- Radar Chart -->
        <div class="radar-wrap">
          <canvas id="radar${globalIdx}" width="240" height="240"></canvas>
        </div>
      </div>
    `;

    container.appendChild(card);

    // Animate scores
    const scoreValues = LAYERS.map(l => r[l.key]);

    if (animated) {
      animateCounter(`cScore${globalIdx}`, r.composite, '%', 1500);
      animateCounter(`cBarLabel${globalIdx}`, r.composite, '%', 1500);
      scoreValues.forEach((val, li) => {
        animateCounter(`lScore${globalIdx}_${li}`, val, '%', 1200);
      });
    } else {
      $(`#cScore${globalIdx}`).textContent = r.composite + '%';
      $(`#cBarLabel${globalIdx}`).textContent = r.composite + '%';
      scoreValues.forEach((val, li) => {
        $(`#lScore${globalIdx}_${li}`).textContent = val + '%';
      });
    }

    // Animate bars (slight delay for visual effect)
    setTimeout(() => {
      const cBar = $(`#cBar${globalIdx}`);
      if (cBar) cBar.style.width = Math.min(r.composite, 100) + '%';
      scoreValues.forEach((val, li) => {
        const lBar = $(`#lBar${globalIdx}_${li}`);
        if (lBar) lBar.style.width = Math.min(val, 100) + '%';
      });
    }, 200);

    // Render radar chart
    renderRadarChart(globalIdx, r, scoreValues);
  });
}

// ============================================================
// ANIMATED COUNTER
// ============================================================
function animateCounter(elId, target, suffix, duration) {
  const el = document.getElementById(elId);
  if (!el) return;

  const start = performance.now();
  const startVal = 0;

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = startVal + (target - startVal) * eased;
    el.textContent = current.toFixed(1) + suffix;
    if (progress < 1) requestAnimationFrame(update);
    else el.textContent = target + suffix;
  }

  requestAnimationFrame(update);
}

// ============================================================
// RADAR CHART
// ============================================================
function renderRadarChart(idx, result, scores) {
  const canvas = document.getElementById(`radar${idx}`);
  if (!canvas) return;

  const isDark = state.theme === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
  const tickColor = isDark ? '#8b92b8' : '#5a6080';

  const chart = new Chart(canvas, {
    type: 'radar',
    data: {
      labels: LAYERS.map(l => l.shortLabel),
      datasets: [{
        label: result.name,
        data: scores,
        backgroundColor: 'rgba(124,111,247,0.15)',
        borderColor: '#7c6ff7',
        borderWidth: 2,
        pointBackgroundColor: LAYERS.map(l => l.color),
        pointBorderColor: 'transparent',
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 1000, easing: 'easeOutQuart' },
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: { stepSize: 25, color: tickColor, font: { size: 9 }, backdropColor: 'transparent' },
          grid: { color: gridColor },
          pointLabels: { color: tickColor, font: { size: 10, weight: '600' } },
          angleLines: { color: gridColor },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.raw.toFixed(1)}%`
          }
        }
      },
    },
  });

  state.radarCharts[idx] = chart;
}

// ============================================================
// SKILL EXPLANATION HTML
// ============================================================
function buildSkillHTML(matched, missing) {
  if (!matched?.length && !missing?.length) return '';
  return `
    <div class="skill-explanation">
      <div>
        <div class="skill-col-title matched">✅ Matched Skills (${matched?.length || 0})</div>
        <div class="skill-tags">
          ${(matched || []).map(s => `<span class="skill-tag matched">${escHtml(s)}</span>`).join('') || '<span class="text-muted" style="font-size:0.75rem">None</span>'}
        </div>
      </div>
      <div>
        <div class="skill-col-title missing">❌ Missing Skills (${missing?.length || 0})</div>
        <div class="skill-tags">
          ${(missing || []).map(s => `<span class="skill-tag missing">${escHtml(s)}</span>`).join('') || '<span class="text-muted" style="font-size:0.75rem">None — full match!</span>'}
        </div>
      </div>
    </div>
  `;
}

// ============================================================
// GITHUB INFO HTML
// ============================================================
function buildGithubHTML(githubData) {
  if (!githubData || githubData.status !== 'success') {
    const statusMessages = {
      no_username: 'No GitHub username provided — neutral score applied.',
      not_found: 'GitHub profile not found (404).',
      rate_limited: 'GitHub API rate limit reached — neutral score applied.',
      connection_error: 'Could not connect to GitHub API.',
      timeout: 'GitHub API request timed out.',
    };
    const msg = statusMessages[githubData?.status] || 'GitHub data unavailable.';
    return `<div class="github-info"><span>🐙 ${msg}</span></div>`;
  }

  return `
    <div class="github-info">
      <span class="github-stat">🐙 <strong>${githubData.public_repos}</strong> public repos (+${githubData.repo_score} pts)</span>
      <span class="github-stat">👥 <strong>${githubData.followers}</strong> followers (+${githubData.follower_score} pts)</span>
      <span class="github-stat">⭐ GitHub Score: <strong>${githubData.score}/100</strong></span>
    </div>
  `;
}

// ============================================================
// VERDICT HTML
// ============================================================
function buildVerdictHTML(verdict) {
  if (!verdict) return '';

  const recBadge = {
    'Strong Hire': '<span class="badge badge-hire">✅ Strong Hire</span>',
    'Consider': '<span class="badge badge-consider">⚠️ Consider</span>',
    'Pass': '<span class="badge badge-pass">❌ Pass</span>',
  }[verdict.recommendation] || '';

  const sourceTag = verdict.source === 'llm'
    ? '<span style="font-size:0.65rem;color:var(--accent-purple);font-weight:700;">✨ AI VERDICT</span>'
    : '<span style="font-size:0.65rem;color:var(--text-muted);">RULE-BASED VERDICT</span>';

  return `
    <div class="verdict-box">
      <div class="verdict-header">
        <span class="verdict-label">🤖 Hiring Recommendation</span>
        <div style="display:flex;gap:0.5rem;align-items:center;">
          ${sourceTag}
          ${recBadge}
        </div>
      </div>
      <p>${escHtml(verdict.verdict)}</p>
    </div>
  `;
}

// ============================================================
// BIAS FLAGS
// ============================================================
function renderBiasFlags(flags) {
  const panel = $('#biasFlagsPanel');
  const content = $('#biasFlagsContent');

  if (!$('#showBiasFlags').checked || !flags || !flags.length) {
    hide(panel);
    return;
  }

  show(panel);
  content.innerHTML = flags.map(f => `
    <div class="bias-flag ${f.severity}">
      <span class="bias-flag-icon">${f.severity === 'warning' ? '⚠️' : 'ℹ️'}</span>
      <div>
        <div class="bias-flag-type">${escHtml(f.flag_type)}</div>
        <div class="bias-flag-candidate">${escHtml(f.candidate)}</div>
        <div class="bias-flag-message">${escHtml(f.message)}</div>
        <div class="bias-flag-rec">💡 ${escHtml(f.recommendation)}</div>
      </div>
    </div>
  `).join('');
}

// ============================================================
// SCORE TABLE
// ============================================================
function renderScoreTable(results = null) {
  const tbody = $('#scoreTableBody');
  const resultsToRender = results || state.lastResults?.results || [];

  const totalPages = Math.max(1, Math.ceil(resultsToRender.length / state.tableItemsPerPage));
  if (state.tableCurrentPage > totalPages) state.tableCurrentPage = totalPages;

  if (resultsToRender.length > 0) {
    $('#tablePaginationControls').style.display = 'flex';
    $('#tablePageInfo').textContent = `${state.tableCurrentPage} / ${totalPages}`;
    $('#prevTablePageBtn').disabled = state.tableCurrentPage === 1;
    $('#nextTablePageBtn').disabled = state.tableCurrentPage === totalPages;
  } else {
    $('#tablePaginationControls').style.display = 'none';
  }

  const startIdx = (state.tableCurrentPage - 1) * state.tableItemsPerPage;
  const endIdx = startIdx + state.tableItemsPerPage;
  const pageResults = resultsToRender.slice(startIdx, endIdx);

  tbody.innerHTML = pageResults.map((r, idx) => {
    const globalIdx = startIdx + idx;
    const medal = RANK_MEDALS[globalIdx] || `#${globalIdx + 1}`;
    const recBadge = r.verdict ? ({
      'Strong Hire': '<span class="badge badge-hire" style="font-size:0.65rem">✅ Hire</span>',
      'Consider': '<span class="badge badge-consider" style="font-size:0.65rem">⚠️ Consider</span>',
      'Pass': '<span class="badge badge-pass" style="font-size:0.65rem">❌ Pass</span>',
    }[r.verdict.recommendation] || '') : '—';

    return `
      <tr>
        <td class="rank-cell">${medal}</td>
        <td style="font-weight:700;color:var(--text-primary)">${escHtml(r.name)}</td>
        <td class="score-cell">${r.composite}%</td>
        ${LAYERS.map(l => `<td>${r[l.key]}%</td>`).join('')}
        <td>${recBadge}</td>
      </tr>
    `;
  }).join('');
}

// ============================================================
// WEIGHT GRID
// ============================================================
function renderWeightGrid(weights) {
  const grid = $('#weightGrid');
  const norm = [weights.w1, weights.w2, weights.w3, weights.w4, weights.w5];
  grid.innerHTML = LAYERS.map((l, i) => `
    <div class="weight-grid-item">
      <span class="weight-grid-label">${l.shortLabel}</span>
      <span class="weight-grid-value" style="color:${l.color}">
        ${(norm[i] * 100).toFixed(1)}%
      </span>
    </div>
  `).join('');
}

// ============================================================
// CSV EXPORT
// ============================================================
async function exportCsv() {
  if (!state.lastResults) {
    showToast('Run an evaluation first to export results.', 'error');
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/export-csv`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'candidate_rankings.csv';
    a.click();
    URL.revokeObjectURL(url);
    showToast('✅ CSV downloaded successfully!', 'success');
  } catch (err) {
    showToast(`CSV export failed: ${err.message}`, 'error');
  }
}

// ============================================================
// COMPARISON MODAL
// ============================================================
function openCompareModal() {
  if (!state.lastResults?.results?.length) {
    showToast('Run an evaluation first to compare candidates.', 'error');
    return;
  }

  const results = state.lastResults.results;
  if (results.length < 2) {
    showToast('Need at least 2 candidates to compare.', 'error');
    return;
  }

  const a = results[0];
  const b = results[1];
  const modal = $('#compareModal');
  const content = $('#compareContent');

  content.innerHTML = `
    <div class="compare-grid">
      ${[a, b].map((r, ci) => `
        <div>
          <div class="compare-col-name">
            ${RANK_MEDALS[ci] || '#' + (ci + 1)} ${escHtml(r.name)}
            <span style="font-size:0.8rem;color:var(--accent-teal);margin-left:0.5rem;">
              ${r.composite}%
            </span>
          </div>
          ${LAYERS.map((l, li) => {
    const myScore = r[l.key];
    const otherScore = (ci === 0 ? b : a)[l.key];
    const delta = myScore - otherScore;
    const deltaClass = delta > 0 ? 'delta-pos' : delta < 0 ? 'delta-neg' : 'delta-tie';
    const deltaSign = delta > 0 ? '+' : '';
    return `
              <div class="compare-row">
                <span class="compare-layer-name">${l.shortLabel}</span>
                <div style="display:flex;gap:0.5rem;align-items:center;">
                  <span class="compare-score" style="color:${l.color}">${myScore}%</span>
                  <span class="compare-delta ${deltaClass}">${deltaSign}${delta.toFixed(1)}</span>
                </div>
              </div>
            `;
  }).join('')}
          <div class="compare-row" style="margin-top:0.5rem;border-top:2px solid var(--border);padding-top:0.5rem;">
            <span class="compare-layer-name" style="font-weight:800;color:var(--text-primary)">Composite</span>
            <span class="compare-score" style="font-size:1rem;background:var(--gradient-accent);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">${r.composite}%</span>
          </div>
          ${r.verdict ? `
            <div style="margin-top:1rem;font-size:0.78rem;color:var(--text-secondary);font-style:italic;line-height:1.5;">
              "${escHtml(r.verdict.verdict)}"
            </div>
          ` : ''}
        </div>
      `).join('')}
    </div>

    <!-- Side-by-side radar comparison -->
    <div style="margin-top:1.5rem;">
      <div style="font-size:0.78rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.75rem;">
        Radar Comparison
      </div>
      <canvas id="compareRadar" height="300"></canvas>
    </div>
  `;

  show(modal);

  // Render comparison radar with both candidates
  const isDark = state.theme === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
  const tickColor = isDark ? '#8b92b8' : '#5a6080';

  new Chart(document.getElementById('compareRadar'), {
    type: 'radar',
    data: {
      labels: LAYERS.map(l => l.shortLabel),
      datasets: [
        {
          label: a.name,
          data: LAYERS.map(l => a[l.key]),
          backgroundColor: 'rgba(124,111,247,0.15)',
          borderColor: '#7c6ff7',
          borderWidth: 2,
          pointBackgroundColor: '#7c6ff7',
          pointRadius: 4,
        },
        {
          label: b.name,
          data: LAYERS.map(l => b[l.key]),
          backgroundColor: 'rgba(0,212,170,0.12)',
          borderColor: '#00d4aa',
          borderWidth: 2,
          pointBackgroundColor: '#00d4aa',
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        r: {
          min: 0, max: 100,
          ticks: { stepSize: 25, color: tickColor, font: { size: 9 }, backdropColor: 'transparent' },
          grid: { color: gridColor },
          pointLabels: { color: tickColor, font: { size: 11, weight: '600' } },
          angleLines: { color: gridColor },
        },
      },
      plugins: {
        legend: { labels: { color: tickColor, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%` } },
      },
      animation: { duration: 800 },
    },
  });
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(message, type = 'info') {
  const colors = {
    success: { bg: 'rgba(0,212,170,0.12)', border: 'rgba(0,212,170,0.3)', color: '#00d4aa' },
    error: { bg: 'rgba(233,30,140,0.12)', border: 'rgba(233,30,140,0.3)', color: '#e91e8c' },
    info: { bg: 'rgba(124,111,247,0.12)', border: 'rgba(124,111,247,0.3)', color: '#7c6ff7' },
  };
  const c = colors[type] || colors.info;

  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 9999;
    background: ${c.bg};
    border: 1px solid ${c.border};
    color: ${c.color};
    padding: 0.75rem 1.25rem;
    border-radius: 10px;
    font-size: 0.85rem;
    font-weight: 600;
    max-width: 360px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    animation: slideIn 0.3s ease;
    font-family: inherit;
    backdrop-filter: blur(8px);
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ============================================================
// UTILITY: HTML ESCAPE
// ============================================================
function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ============================================================
// EVENT LISTENERS
// ============================================================
function initEventListeners() {
  // Run button
  $('#runBtn').addEventListener('click', runEvaluation);

  // Add candidate
  $('#addCandidateBtn').addEventListener('click', addCandidate);

  // CSV export
  $('#exportCsvBtn').addEventListener('click', exportCsv);

  // Compare button
  $('#compareBtn').addEventListener('click', openCompareModal);

  // Close compare modal
  $('#closeCompareBtn').addEventListener('click', () => hide($('#compareModal')));
  $('#compareModal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) hide(e.currentTarget);
  });

  // Keyboard: close modal on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hide($('#compareModal'));
  });
}

// ============================================================
// INIT
// ============================================================
async function init() {
  // Initialize Lucide icons
  lucide.createIcons();

  // Theme
  initTheme();

  // Sliders
  initSliders();

  // Event listeners
  initEventListeners();

  // Pagination controls
  initPagination();
  initResultsPagination();
  initTablePagination();

  // PDF upload
  initPdfUpload();

  // Auto-resize textarea
  const jdText = $('#jdText');
  if (jdText) {
    jdText.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = (this.scrollHeight) + 'px';
    });
  }

  // Check API health (non-blocking)
  checkApiHealth();

  // Load JD templates + candidates from API
  await loadJdTemplates();

  console.log('✅ RecruitIQ initialized');
}

// ============================================================
// INTERVIEW QUESTIONS MODAL LOGIC
// ============================================================
window.generateInterviewQuestions = async function (idx) {
  if (!state.lastResults || !state.lastResults.results || !state.lastResults.results[idx]) {
    console.error("Candidate not found at idx:", idx);
    return;
  }
  const candidate = state.lastResults.results[idx];
  const jdText = $('#jdText').value.trim();
  const apiKey = $('#geminiApiKey') ? $('#geminiApiKey').value.trim() : '';

  const modal = $('#interviewModal');
  const container = $('#interviewQuestionsContainer');
  
  // Show Modal and Loading Spinner
  modal.style.display = 'flex'; // Use flex for better centering
  container.innerHTML = `
    <div style="text-align:center; padding:4rem 2rem; display:flex; flex-direction:column; align-items:center;">
      <div class="spinner" style="width:40px; height:40px; border-width:3px; border-color:var(--accent-teal) transparent var(--accent-teal) transparent;"></div>
      <p style="margin-top:1.5rem; color:var(--text-primary); font-size:1.1rem; font-weight:500;">Generating Professional Interview Guide...</p>
      <p style="color:var(--text-secondary); font-size:0.9rem; margin-top:0.5rem;">Analyzing missing skills and required expertise</p>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/api/interview-questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate: candidate,
        jd_text: jdText,
        gemini_api_key: apiKey
      }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    
    let html = '';
    
    if (data.questions && data.questions.length > 0) {
      data.questions.forEach((q, i) => {
        html += `
          <div style="background:var(--bg-panel); border:1px solid var(--border); border-radius:10px; padding:1.5rem; margin-bottom:1.5rem;">
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:1rem; color:var(--accent-teal); font-weight:700;">
              <div style="background:var(--accent-teal); color:#000; width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:0.85rem;">${i+1}</div>
              ${escHtml(q.type)}
            </div>
            <p style="font-size:1.1rem; color:var(--text-primary); margin-bottom:1rem; font-weight:500;">
              "${escHtml(q.question)}"
            </p>
            <div style="background:rgba(124, 111, 247, 0.1); border-left:4px solid var(--accent-purple); padding:1rem; border-radius:4px; font-size:0.9rem;">
              <strong>Rationale:</strong> ${escHtml(q.rationale)}
            </div>
          </div>
        `;
      });
    } else {
      html = `<p>No questions generated.</p>`;
    }
    
    container.innerHTML = html;

  } catch (err) {
    container.innerHTML = `
      <div style="text-align:center; padding:3rem; color:var(--accent-pink);">
        <i data-lucide="alert-triangle" style="width:48px; height:48px; margin-bottom:1rem;"></i>
        <p>Error generating questions: ${err.message}</p>
      </div>
    `;
    lucide.createIcons();
  }
}

// Boot on DOM ready
document.addEventListener('DOMContentLoaded', init);
