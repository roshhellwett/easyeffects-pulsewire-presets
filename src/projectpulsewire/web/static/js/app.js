/**
 * ProjectPulsewire Studio - Clean & Calm SPA Frontend Controller
 */

const API_BASE = '/api';

const state = {
  activeTab: 'dashboard',
  status: {},
  presets: [],
  presetCategories: {},
  activePresetCategory: 'All',
  presetSearch: '',
  selectedPresets: new Set(),
  
  irsList: [],
  irsCategories: {},
  activeIrsCategory: 'All',
  irsSearch: '',
  selectedIrs: new Set(),
  
  audioStack: {},
  updates: {},
  loading: false,
};

// ==========================================
// Toast Notifications
// ==========================================
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  const icon = type === 'success' ? '✓' : type === 'error' ? '!' : 'ℹ';
  toast.innerHTML = `
    <span style="font-weight: 700; font-size: 0.95rem;">${icon}</span>
    <div style="flex: 1; font-size: 0.84rem; font-weight: 500; line-height: 1.4;">${message}</div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.2s ease';
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

// ==========================================
// API Helpers
// ==========================================
async function apiGet(endpoint, params = {}) {
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') query.append(k, v);
  }
  const url = `${API_BASE}${endpoint}${query.toString() ? '?' + query.toString() : ''}`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API GET error on ${endpoint}:`, err);
    throw err;
  }
}

async function apiPost(endpoint, data = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.message || json.error || `HTTP ${res.status}`);
    }
    return json;
  } catch (err) {
    console.error(`API POST error on ${endpoint}:`, err);
    throw err;
  }
}

// ==========================================
// Navigation & Tab Switching
// ==========================================
function switchTab(tabId) {
  state.activeTab = tabId;
  
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });

  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === `tab-${tabId}`);
  });

  // Clear batch selections
  state.selectedPresets.clear();
  state.selectedIrs.clear();
  updateBatchBar();

  if (tabId === 'dashboard') loadDashboard();
  else if (tabId === 'presets') loadPresets();
  else if (tabId === 'irs') loadIRS();
  else if (tabId === 'stack') loadAudioStack();
  else if (tabId === 'settings') loadSettings();
  else if (tabId === 'guide') loadGuide();
}

// ==========================================
// Dashboard View
// ==========================================
async function loadDashboard() {
  try {
    const status = await apiGet('/status');
    state.status = status;

    // Update Status Pill
    const pwStatus = document.getElementById('pw-status-pill');
    if (pwStatus) {
      pwStatus.innerHTML = status.pipewire_running
        ? '<div class="pulse-dot"></div> PipeWire Active'
        : '<div class="pulse-dot" style="background:#f59e0b;box-shadow:0 0 6px #f59e0b"></div> Audio Standby';
    }

    // Hero stats
    document.getElementById('stat-presets').textContent = `${status.presets_installed} / ${status.presets_total}`;
    document.getElementById('stat-irs').textContent = `${status.irs_installed} / ${status.irs_total}`;
    document.getElementById('stat-source').textContent = status.active_source.replace('presets', '').toUpperCase();
    document.getElementById('stat-ee-ver').textContent = status.easyeffects_version || 'Ready';

    // Nav badges
    const pBadge = document.getElementById('badge-presets');
    if (pBadge) pBadge.textContent = status.presets_total;
    const iBadge = document.getElementById('badge-irs');
    if (iBadge) iBadge.textContent = status.irs_total;

    // Update banner
    const updateBanner = document.getElementById('update-notification-card');
    if (updateBanner) {
      if (status.has_update) {
        updateBanner.style.display = 'flex';
        document.getElementById('latest-ver-text').textContent = status.latest_version;
      } else {
        updateBanner.style.display = 'none';
      }
    }
  } catch (err) {
    showToast('Failed to load system status', 'error');
  }
}

// ==========================================
// EQ Presets Hub
// ==========================================
async function loadPresets() {
  const container = document.getElementById('presets-grid');
  if (!container) return;

  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-tertiary);">Loading presets...</div>`;

  try {
    const data = await apiGet('/presets', {
      category: state.activePresetCategory === 'All' ? '' : state.activePresetCategory,
      search: state.presetSearch,
    });

    state.presets = data.presets;
    state.presetCategories = data.categories;

    renderPresetCategoryPills(data.categories);
    renderPresetCards(data.presets);
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--accent-rose);">Failed to load presets: ${err.message}</div>`;
  }
}

function renderPresetCategoryPills(categories) {
  const pillsContainer = document.getElementById('preset-category-pills');
  if (!pillsContainer) return;

  let html = `<button class="pill-btn ${state.activePresetCategory === 'All' ? 'active' : ''}" onclick="filterPresetCategory('All')">All</button>`;
  
  for (const [cat, count] of Object.entries(categories)) {
    const isActive = state.activePresetCategory === cat;
    html += `<button class="pill-btn ${isActive ? 'active' : ''}" onclick="filterPresetCategory('${cat}')">${cat} <span style="opacity:0.6">(${count})</span></button>`;
  }

  pillsContainer.innerHTML = html;
}

function filterPresetCategory(cat) {
  state.activePresetCategory = cat;
  loadPresets();
}

function renderPresetCards(presets) {
  const container = document.getElementById('presets-grid');
  if (!container) return;

  if (presets.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-tertiary);">No presets match your search.</div>`;
    return;
  }

  container.innerHTML = presets.map(p => {
    const isSelected = state.selectedPresets.has(p.name);
    const pluginsHtml = p.plugins_order.slice(0, 4).map(name => `<span class="plugin-pill">${name}</span>`).join('');
    const extraPlugins = p.plugins_order.length > 4 ? `<span class="plugin-pill">+${p.plugins_order.length - 4}</span>` : '';

    return `
      <div class="card ${p.installed ? 'installed' : ''}" id="card-preset-${encodeURIComponent(p.name)}">
        <div class="card-top">
          <div class="card-title-group">
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
              <span class="badge-tag">${p.category}</span>
              ${p.installed ? '<span class="badge-tag badge-installed">Installed</span>' : ''}
            </div>
            <h3 class="card-title">${p.name}</h3>
          </div>
          <input type="checkbox" class="checkbox-custom" ${isSelected ? 'checked' : ''} onchange="togglePresetSelection('${escapeQuotes(p.name)}', this.checked)">
        </div>

        <div class="plugin-chain-pills">
          ${pluginsHtml}
          ${extraPlugins}
        </div>

        <div class="card-footer">
          <button class="btn btn-secondary btn-sm" onclick="previewPreset('${escapeQuotes(p.name)}')">
            Inspect
          </button>
          <div class="card-actions">
            ${p.installed 
              ? `<button class="btn btn-danger btn-sm" onclick="removeSinglePreset('${escapeQuotes(p.name)}')">Uninstall</button>`
              : `<button class="btn btn-primary btn-sm" onclick="installSinglePreset('${escapeQuotes(p.name)}')">Install</button>`
            }
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function togglePresetSelection(name, checked) {
  if (checked) state.selectedPresets.add(name);
  else state.selectedPresets.delete(name);
  updateBatchBar();
}

async function installSinglePreset(name) {
  try {
    const res = await apiPost('/presets/install', { name });
    showToast(res.message || `Installed '${name}'`, 'success');
    loadPresets();
    loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function removeSinglePreset(name) {
  try {
    const res = await apiPost('/presets/remove', { name });
    showToast(res.message || `Removed '${name}'`, 'success');
    loadPresets();
    loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function installAllUninstalledPresets() {
  try {
    const res = await apiPost('/presets/install', { all_uninstalled: true });
    showToast(res.message || 'All presets installed', 'success');
    loadPresets();
    loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Preset Detail & Signal Chain Modal
async function previewPreset(name) {
  try {
    const detail = await apiGet(`/presets/${encodeURIComponent(name)}`);
    const modal = document.getElementById('preset-modal');
    const content = document.getElementById('preset-modal-body');

    let chainHtml = '<div class="chain-diagram">';
    detail.plugins_order.forEach((p, idx) => {
      chainHtml += `<div class="chain-node"><span>🎛</span> ${p}</div>`;
      if (idx < detail.plugins_order.length - 1) {
        chainHtml += `<span class="chain-arrow">→</span>`;
      }
    });
    chainHtml += '</div>';

    content.innerHTML = `
      <div class="modal-header">
        <div>
          <span class="badge-tag">${detail.source}</span>
          <h2 style="font-size:1.35rem; font-weight:700; margin-top:4px;">${detail.name}</h2>
          <p style="color:var(--text-secondary); font-size:0.82rem;">${detail.filename}</p>
        </div>
        <button class="modal-close-btn" onclick="closeModal('preset-modal')">&times;</button>
      </div>

      <div style="margin-top:12px;">
        <h4 style="font-size:0.82rem; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:0.05em; font-weight:600;">Plugin Signal Chain (${detail.plugins_order.length} Blocks)</h4>
        ${chainHtml}
      </div>

      <div style="margin-top:20px; display:flex; gap:10px; justify-content:flex-end;">
        <button class="btn btn-secondary btn-sm" onclick="closeModal('preset-modal')">Close</button>
        ${detail.installed
          ? `<button class="btn btn-danger btn-sm" onclick="removeSinglePreset('${escapeQuotes(detail.name)}'); closeModal('preset-modal');">Remove Preset</button>`
          : `<button class="btn btn-primary btn-sm" onclick="installSinglePreset('${escapeQuotes(detail.name)}'); closeModal('preset-modal');">Install to EasyEffects</button>`
        }
      </div>
    `;

    modal.classList.add('active');
  } catch (err) {
    showToast('Failed to load preset detail', 'error');
  }
}

// ==========================================
// IRS Convolver Hub
// ==========================================
async function loadIRS() {
  const container = document.getElementById('irs-grid');
  if (!container) return;

  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-tertiary);">Loading IRS convolution files...</div>`;

  try {
    const data = await apiGet('/irs', {
      category: state.activeIrsCategory === 'All' ? '' : state.activeIrsCategory,
      search: state.irsSearch,
    });

    state.irsList = data.irs;
    state.irsCategories = data.categories;

    renderIrsCategoryPills(data.categories);
    renderIrsCards(data.irs);
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--accent-rose);">Failed to load IRS: ${err.message}</div>`;
  }
}

function renderIrsCategoryPills(categories) {
  const pillsContainer = document.getElementById('irs-category-pills');
  if (!pillsContainer) return;

  let html = `<button class="pill-btn ${state.activeIrsCategory === 'All' ? 'active' : ''}" onclick="filterIrsCategory('All')">All</button>`;
  
  for (const [cat, count] of Object.entries(categories)) {
    const isActive = state.activeIrsCategory === cat;
    html += `<button class="pill-btn ${isActive ? 'active' : ''}" onclick="filterIrsCategory('${cat}')">${cat} <span style="opacity:0.6">(${count})</span></button>`;
  }

  pillsContainer.innerHTML = html;
}

function filterIrsCategory(cat) {
  state.activeIrsCategory = cat;
  loadIRS();
}

function renderIrsCards(irsList) {
  const container = document.getElementById('irs-grid');
  if (!container) return;

  if (irsList.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-tertiary);">No IRS files found.</div>`;
    return;
  }

  container.innerHTML = irsList.map(irs => {
    const isSelected = state.selectedIrs.has(irs.name);

    return `
      <div class="card ${irs.installed ? 'installed' : ''}" id="card-irs-${encodeURIComponent(irs.name)}">
        <div class="card-top">
          <div class="card-title-group">
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
              <span class="badge-tag">${irs.category}</span>
              <span style="font-size:0.72rem; color:var(--text-dim); font-family:var(--font-mono);">${irs.size_formatted}</span>
              ${irs.installed ? '<span class="badge-tag badge-installed">Installed</span>' : ''}
            </div>
            <h3 class="card-title">${irs.name}</h3>
          </div>
          <input type="checkbox" class="checkbox-custom" ${isSelected ? 'checked' : ''} onchange="toggleIrsSelection('${escapeQuotes(irs.name)}', this.checked)">
        </div>

        <p class="card-desc">${irs.use_guide}</p>

        <div class="card-footer">
          <button class="btn btn-secondary btn-sm" onclick="previewIRS('${escapeQuotes(irs.name)}')">
            Profile
          </button>
          <div class="card-actions">
            ${irs.installed 
              ? `<button class="btn btn-danger btn-sm" onclick="removeSingleIRS('${escapeQuotes(irs.name)}')">Uninstall</button>`
              : `<button class="btn btn-primary btn-sm" onclick="installSingleIRS('${escapeQuotes(irs.name)}')">Install</button>`
            }
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function toggleIrsSelection(name, checked) {
  if (checked) state.selectedIrs.add(name);
  else state.selectedIrs.delete(name);
  updateBatchBar();
}

async function installSingleIRS(name) {
  try {
    const res = await apiPost('/irs/install', { name });
    showToast(res.message || `Installed IRS '${name}'`, 'success');
    loadIRS();
    loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function removeSingleIRS(name) {
  try {
    const res = await apiPost('/irs/remove', { name });
    showToast(res.message || `Removed IRS '${name}'`, 'success');
    loadIRS();
    loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function installAllUninstalledIRS() {
  try {
    const res = await apiPost('/irs/install', { all_uninstalled: true });
    showToast(res.message || 'All IRS files installed', 'success');
    loadIRS();
    loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function previewIRS(name) {
  try {
    const detail = await apiGet(`/irs/${encodeURIComponent(name)}`);
    const modal = document.getElementById('preset-modal');
    const content = document.getElementById('preset-modal-body');

    content.innerHTML = `
      <div class="modal-header">
        <div>
          <span class="badge-tag">${detail.category}</span>
          <h2 style="font-size:1.35rem; font-weight:700; margin-top:4px;">${detail.name}</h2>
          <p style="color:var(--text-secondary); font-size:0.82rem;">${detail.filename} (${detail.size_formatted})</p>
        </div>
        <button class="modal-close-btn" onclick="closeModal('preset-modal')">&times;</button>
      </div>

      <div style="background:var(--bg-card); border:1px solid var(--border-subtle); padding:14px 16px; border-radius:var(--radius-sm); margin:14px 0;">
        <h4 style="color:var(--accent-primary); margin-bottom:4px; font-size:0.85rem; font-weight:600;">Category Purpose</h4>
        <p style="font-size:0.85rem; color:var(--text-secondary); line-height:1.5;">${detail.category_desc}</p>
      </div>

      <div style="background:var(--bg-card); border:1px solid var(--border-subtle); padding:14px 16px; border-radius:var(--radius-sm); margin:14px 0;">
        <h4 style="color:var(--accent-purple); margin-bottom:4px; font-size:0.85rem; font-weight:600;">Acoustic Tuning Recommendation</h4>
        <p style="font-size:0.85rem; color:var(--text-secondary); line-height:1.5;">${detail.use_guide}</p>
      </div>

      <div style="margin-top:20px; display:flex; gap:10px; justify-content:flex-end;">
        <button class="btn btn-secondary btn-sm" onclick="closeModal('preset-modal')">Close</button>
        ${detail.installed
          ? `<button class="btn btn-danger btn-sm" onclick="removeSingleIRS('${escapeQuotes(detail.name)}'); closeModal('preset-modal');">Remove IRS</button>`
          : `<button class="btn btn-primary btn-sm" onclick="installSingleIRS('${escapeQuotes(detail.name)}'); closeModal('preset-modal');">Install to Convolver</button>`
        }
      </div>
    `;

    modal.classList.add('active');
  } catch (err) {
    showToast('Failed to load IRS detail', 'error');
  }
}

// ==========================================
// Floating Batch Toolbar Actions
// ==========================================
function updateBatchBar() {
  const bar = document.getElementById('batch-bar');
  const countEl = document.getElementById('batch-count-text');
  if (!bar || !countEl) return;

  const count = state.activeTab === 'presets' ? state.selectedPresets.size : state.selectedIrs.size;

  if (count > 0) {
    countEl.textContent = `${count} ${state.activeTab === 'presets' ? 'preset(s)' : 'file(s)'} selected`;
    bar.classList.add('active');
  } else {
    bar.classList.remove('active');
  }
}

async function handleBatchInstall() {
  if (state.activeTab === 'presets') {
    const names = Array.from(state.selectedPresets);
    if (!names.length) return;
    try {
      const res = await apiPost('/presets/install', { names });
      showToast(res.message, 'success');
      state.selectedPresets.clear();
      updateBatchBar();
      loadPresets();
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  } else if (state.activeTab === 'irs') {
    const names = Array.from(state.selectedIrs);
    if (!names.length) return;
    try {
      const res = await apiPost('/irs/install', { names });
      showToast(res.message, 'success');
      state.selectedIrs.clear();
      updateBatchBar();
      loadIRS();
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
}

async function handleBatchRemove() {
  if (state.activeTab === 'presets') {
    const names = Array.from(state.selectedPresets);
    if (!names.length) return;
    try {
      const res = await apiPost('/presets/remove', { names });
      showToast(res.message, 'success');
      state.selectedPresets.clear();
      updateBatchBar();
      loadPresets();
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  } else if (state.activeTab === 'irs') {
    const names = Array.from(state.selectedIrs);
    if (!names.length) return;
    try {
      const res = await apiPost('/irs/remove', { names });
      showToast(res.message, 'success');
      state.selectedIrs.clear();
      updateBatchBar();
      loadIRS();
      loadDashboard();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
}

function selectAllVisible() {
  if (state.activeTab === 'presets') {
    state.presets.forEach(p => state.selectedPresets.add(p.name));
    renderPresetCards(state.presets);
  } else if (state.activeTab === 'irs') {
    state.irsList.forEach(i => state.selectedIrs.add(i.name));
    renderIrsCards(state.irsList);
  }
  updateBatchBar();
}

function clearAllSelections() {
  state.selectedPresets.clear();
  state.selectedIrs.clear();
  if (state.activeTab === 'presets') renderPresetCards(state.presets);
  else if (state.activeTab === 'irs') renderIrsCards(state.irsList);
  updateBatchBar();
}

// ==========================================
// Audio Stack & Diagnostics
// ==========================================
async function loadAudioStack() {
  const container = document.getElementById('stack-table-body');
  if (!container) return;

  container.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:30px; color:var(--text-tertiary);">Running system diagnostics...</td></tr>`;

  try {
    const data = await apiGet('/audio-stack');
    state.audioStack = data;

    document.getElementById('distro-name-badge').textContent = `${data.distro_name} (${data.distro_family})`;

    container.innerHTML = data.packages.map(pkg => `
      <tr>
        <td>
          <div style="font-weight:600; color:var(--text-primary);">${pkg.name}</div>
          <div style="font-size:0.78rem; color:var(--text-tertiary);">${pkg.description}</div>
        </td>
        <td>
          <span class="badge-tag" style="${pkg.critical ? 'color:var(--accent-primary); border-color:var(--border-highlight);' : ''}">${pkg.critical ? 'Critical' : 'Recommended'}</span>
        </td>
        <td>
          <span style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text-secondary);">${pkg.pkg_name}</span>
        </td>
        <td>
          ${pkg.installed 
            ? '<span style="color:var(--accent-success); font-weight:600; font-size:0.82rem;">Installed</span>' 
            : '<span style="color:var(--text-dim); font-weight:500; font-size:0.82rem;">Missing</span>'
          }
        </td>
      </tr>
    `).join('');

    const cmdBox = document.getElementById('install-cmd-box');
    const cmdText = document.getElementById('install-cmd-text');
    if (data.install_command) {
      cmdBox.style.display = 'flex';
      cmdText.textContent = data.install_command;
    } else {
      cmdBox.style.display = 'none';
    }
  } catch (err) {
    showToast('Failed to run audio stack diagnostics', 'error');
  }
}

async function triggerInstallAudioStack() {
  try {
    showToast('Installing dependencies (requires sudo)...', 'info');
    const res = await apiPost('/audio-stack/install');
    showToast(res.message, res.success ? 'success' : 'error');
    loadAudioStack();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function copyCommandToClipboard() {
  const text = document.getElementById('install-cmd-text').textContent;
  navigator.clipboard.writeText(text);
  showToast('Copied install command', 'success');
}

// ==========================================
// Settings & Source Switcher
// ==========================================
async function loadSettings() {
  const status = await apiGet('/status');
  state.status = status;

  document.getElementById('current-pkg-version').textContent = status.version;
  document.getElementById('setting-presets-path').textContent = status.presets_dir;
  document.getElementById('setting-convolver-path').textContent = status.convolver_dir;

  const select = document.getElementById('source-select');
  if (select) {
    select.value = status.active_source;
  }
}

async function handleSourceChange(newSource) {
  try {
    const res = await apiPost('/presets/source', { source: newSource });
    showToast(res.message, 'success');
    loadDashboard();
    loadSettings();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function triggerPackageUpgrade() {
  try {
    showToast('Upgrading projectpulsewire from PyPI...', 'info');
    const res = await apiPost('/updates/upgrade');
    if (res.success) {
      showToast('Upgrade successful. Please restart the server.', 'success', 5000);
    } else {
      showToast(`Upgrade failed: ${res.message}`, 'error');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function shutdownServer() {
  if (confirm('Stop the local web server?')) {
    try {
      await apiPost('/server/shutdown');
      document.body.innerHTML = `
        <div style="display:flex; height:100vh; align-items:center; justify-content:center; flex-direction:column; background:#090b10; color:#f8fafc; font-family:sans-serif;">
          <h2 style="font-weight:600; margin-bottom:8px;">Server Stopped</h2>
          <p style="color:#64748b; font-size:0.9rem;">You can close this browser tab.</p>
        </div>
      `;
    } catch (e) {
      showToast('Server stop requested', 'info');
    }
  }
}

// ==========================================
// IRS Guide View
// ==========================================
async function loadGuide() {
  try {
    const data = await apiGet('/guide/irs');
    const container = document.getElementById('guide-categories-grid');
    if (container) {
      container.innerHTML = data.categories.map(cat => `
        <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:16px;">
          <h4 style="color:var(--accent-primary); margin-bottom:4px; font-size:0.9rem; font-weight:600;">${cat.name}</h4>
          <p style="font-size:0.82rem; color:var(--text-secondary); line-height:1.5;">${cat.description}</p>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error('Failed to load guide:', err);
  }
}

// Utility
function escapeQuotes(str) {
  return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  // Debounced search
  const presetSearchInput = document.getElementById('preset-search-input');
  if (presetSearchInput) {
    let timeout;
    presetSearchInput.addEventListener('input', (e) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        state.presetSearch = e.target.value;
        loadPresets();
      }, 200);
    });
  }

  const irsSearchInput = document.getElementById('irs-search-input');
  if (irsSearchInput) {
    let timeout;
    irsSearchInput.addEventListener('input', (e) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        state.irsSearch = e.target.value;
        loadIRS();
      }, 200);
    });
  }

  // Modal backdrop dismiss
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });

  // Initial load
  loadDashboard();
});
