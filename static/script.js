const state = {
  source: 'spotify',
  tracks: [],
  youtube: { title: '', video: [], audio: [] },
  kind: 'video',
  selectedFormat: null,
  ytPlaylist: { title: '', videos: [] },
  ytpKind: 'video',
};

const els = {
  tabs: document.querySelectorAll('.tab'),
  urlInput: document.getElementById('urlInput'),
  fetchBtn: document.getElementById('fetchBtn'),
  errorBanner: document.getElementById('errorBanner'),
  trackSection: document.getElementById('trackSection'),
  trackList: document.getElementById('trackList'),
  trackCount: document.getElementById('trackCount'),
  youtubeSection: document.getElementById('youtubeSection'),
  videoTitle: document.getElementById('videoTitle'),
  qualityList: document.getElementById('qualityList'),
  kindBtns: document.querySelectorAll('[data-kind]'),
  ytPlaylistSection: document.getElementById('ytPlaylistSection'),
  ytPlaylistTitle: document.getElementById('ytPlaylistTitle'),
  ytPlaylistCount: document.getElementById('ytPlaylistCount'),
  ytPlaylistVideoList: document.getElementById('ytPlaylistVideoList'),
  ytpKindBtns: document.querySelectorAll('[data-ytp-kind]'),
  resolutionRow: document.getElementById('resolutionRow'),
  resolutionSelect: document.getElementById('resolutionSelect'),
  sizeEstimate: document.getElementById('sizeEstimate'),
  downloadBtn: document.getElementById('downloadBtn'),
  stopBtn: document.getElementById('stopBtn'),
  openFolderBtn: document.getElementById('openFolderBtn'),
  progressFill: document.getElementById('progressFill'),
  progressText: document.getElementById('progressText'),
  logBox: document.getElementById('logBox'),
};

let sizeScanInterval = null;

function showError(msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove('hidden');
}
function clearError() {
  els.errorBanner.classList.add('hidden');
  els.errorBanner.textContent = '';
}

function setButtonLoading(btn, loading) {
  btn.querySelector('.btn-label').classList.toggle('hidden', loading);
  btn.querySelector('.spinner').classList.toggle('hidden', !loading);
  btn.disabled = loading;
}

function resetResults() {
  state.tracks = [];
  state.youtube = { title: '', video: [], audio: [] };
  state.selectedFormat = null;
  state.ytPlaylist = { title: '', videos: [] };

  if (sizeScanInterval) clearInterval(sizeScanInterval);
  els.sizeEstimate.textContent = '';
  els.sizeEstimate.classList.remove('scanning');

  els.trackSection.classList.add('hidden');
  els.youtubeSection.classList.add('hidden');
  els.ytPlaylistSection.classList.add('hidden');
  els.trackList.innerHTML = '';
  els.qualityList.innerHTML = '';
  els.ytPlaylistVideoList.innerHTML = '';
  els.downloadBtn.disabled = true;
  els.progressFill.style.width = '0%';
  els.progressText.textContent = '0%';
}

const placeholders = {
  spotify: 'Paste a playlist link here…',
  gaana: 'Paste a playlist link here…',
  youtube: 'Paste a single YouTube video link…',
  youtube_playlist: 'Paste a YouTube playlist link here…',
};

// ---------------- tabs ----------------
els.tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    els.tabs.forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    state.source = tab.dataset.source;
    els.urlInput.placeholder = placeholders[state.source] || 'Paste a link here…';
    resetResults();
    clearError();
  });
});

els.kindBtns.forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-kind]').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    state.kind = btn.dataset.kind;
    state.selectedFormat = null;
    els.downloadBtn.disabled = true;
    renderQualityList();
  });
});

els.ytpKindBtns.forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-ytp-kind]').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    state.ytpKind = btn.dataset.ytpKind;
    els.resolutionRow.classList.toggle('hidden', state.ytpKind === 'audio');
    startSizeScan();
  });
});

els.resolutionSelect.addEventListener('change', () => {
  startSizeScan();
});

// ---------------- fetch ----------------
els.fetchBtn.addEventListener('click', async () => {
  const url = els.urlInput.value.trim();
  if (!url) {
    showError('Please paste a link first.');
    return;
  }
  clearError();
  resetResults();
  setButtonLoading(els.fetchBtn, true);

  try {
    const res = await fetch('/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: state.source, url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Something went wrong.');

    if (data.type === 'playlist') {
      state.tracks = data.tracks;
      renderTrackList();
    } else if (data.type === 'youtube') {
      state.youtube = { title: data.title, video: data.video_formats, audio: data.audio_formats };
      els.videoTitle.textContent = data.title;
      els.youtubeSection.classList.remove('hidden');
      renderQualityList();
    } else if (data.type === 'youtube_playlist') {
      state.ytPlaylist = { title: data.title, videos: data.videos };
      renderYtPlaylist();
    }
  } catch (err) {
    showError(err.message);
  } finally {
    setButtonLoading(els.fetchBtn, false);
  }
});

function renderTrackList() {
  els.trackList.innerHTML = '';
  state.tracks.forEach((t) => {
    const li = document.createElement('li');
    li.textContent = t;
    els.trackList.appendChild(li);
  });
  els.trackCount.textContent = `${state.tracks.length} tracks`;
  els.trackSection.classList.remove('hidden');
  els.downloadBtn.disabled = state.tracks.length === 0;
}

function renderQualityList() {
  const options = state.youtube[state.kind] || [];
  els.qualityList.innerHTML = '';
  options.forEach((opt, idx) => {
    const li = document.createElement('li');
    li.textContent = opt.label;
    li.addEventListener('click', () => {
      [...els.qualityList.children].forEach((c) => c.classList.remove('selected'));
      li.classList.add('selected');
      state.selectedFormat = opt;
      els.downloadBtn.disabled = false;
    });
    els.qualityList.appendChild(li);
  });
}

function renderYtPlaylist() {
  els.ytPlaylistTitle.textContent = state.ytPlaylist.title;
  els.ytPlaylistCount.textContent = `${state.ytPlaylist.videos.length} videos`;
  els.ytPlaylistVideoList.innerHTML = '';
  state.ytPlaylist.videos.forEach((v) => {
    const li = document.createElement('li');
    li.textContent = v.title;
    els.ytPlaylistVideoList.appendChild(li);
  });
  els.resolutionRow.classList.toggle('hidden', state.ytpKind === 'audio');
  els.ytPlaylistSection.classList.remove('hidden');
  els.downloadBtn.disabled = state.ytPlaylist.videos.length === 0;
  startSizeScan();
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let val = bytes;
  let i = 0;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(1)} ${units[i]}`;
}

async function startSizeScan() {
  if (sizeScanInterval) clearInterval(sizeScanInterval);
  if (!state.ytPlaylist.videos.length) return;

  els.sizeEstimate.textContent = `Scanning size for ${state.ytPlaylist.videos.length} videos…`;
  els.sizeEstimate.classList.add('scanning');

  try {
    const res = await fetch('/api/estimate-size', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        videos: state.ytPlaylist.videos,
        is_audio: state.ytpKind === 'audio',
        max_height: parseInt(els.resolutionSelect.value, 10),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not scan sizes.');

    sizeScanInterval = setInterval(async () => {
      try {
        const progRes = await fetch(`/api/progress/${data.job_id}`);
        const job = await progRes.json();
        if (!progRes.ok) throw new Error(job.error || 'Lost the size scan.');

        const sizeText = formatBytes(job.size_bytes || 0);
        if (job.done) {
          clearInterval(sizeScanInterval);
          els.sizeEstimate.classList.remove('scanning');
          const unknownNote = job.unknown_count
            ? ` (size unknown for ${job.unknown_count} video${job.unknown_count === 1 ? '' : 's'})`
            : '';
          els.sizeEstimate.textContent = `Estimated total: ~${sizeText}${unknownNote}`;
        } else {
          els.sizeEstimate.textContent = `Scanning… ~${sizeText} so far (${job.current}/${job.total})`;
        }
      } catch (err) {
        clearInterval(sizeScanInterval);
        els.sizeEstimate.classList.remove('scanning');
        els.sizeEstimate.textContent = '';
      }
    }, 700);
  } catch (err) {
    els.sizeEstimate.classList.remove('scanning');
    els.sizeEstimate.textContent = '';
  }
}

// ---------------- download ----------------
els.downloadBtn.addEventListener('click', async () => {
  clearError();
  setButtonLoading(els.downloadBtn, true);
  els.logBox.innerHTML = '';
  els.progressFill.style.width = '0%';
  els.progressText.textContent = '0%';

  try {
    let jobId;
    if (state.source === 'youtube') {
      if (!state.selectedFormat) throw new Error('Pick a quality first.');
      const res = await fetch('/api/download/youtube', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: els.urlInput.value.trim(),
          format_id: state.selectedFormat.format_id,
          is_audio: state.kind === 'audio',
          has_audio: state.selectedFormat.has_audio !== false,
          title: state.youtube.title,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Download failed to start.');
      jobId = data.job_id;
    } else if (state.source === 'youtube_playlist') {
      if (!state.ytPlaylist.videos.length) throw new Error('Fetch a playlist first.');
      const res = await fetch('/api/download/youtube-playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videos: state.ytPlaylist.videos,
          is_audio: state.ytpKind === 'audio',
          max_height: parseInt(els.resolutionSelect.value, 10),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Download failed to start.');
      jobId = data.job_id;
    } else {
      if (!state.tracks.length) throw new Error('Fetch a playlist first.');
      const res = await fetch('/api/download/playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tracks: state.tracks }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Download failed to start.');
      jobId = data.job_id;
    }

    pollProgress(jobId);
    currentJobId = jobId;
    els.stopBtn.classList.remove('hidden');
  } catch (err) {
    showError(err.message);
    setButtonLoading(els.downloadBtn, false);
  }
});

let seenLogCount = 0;
let currentJobId = null;

els.stopBtn.addEventListener('click', async () => {
  if (!currentJobId) return;
  els.stopBtn.disabled = true;
  try {
    await fetch(`/api/cancel/${currentJobId}`, { method: 'POST' });
  } catch (err) {
    showError('Could not reach the server to stop the job.');
  }
});

function pollProgress(jobId) {
  seenLogCount = 0;
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${jobId}`);
      const job = await res.json();
      if (!res.ok) throw new Error(job.error || 'Lost track of the job.');

      appendNewLogLines(job.log);

      const pct = job.total ? Math.round((job.current / job.total) * 100) : 0;
      els.progressFill.style.width = `${pct}%`;
      els.progressText.textContent = `${pct}%`;

      if (job.done) {
        clearInterval(interval);
        setButtonLoading(els.downloadBtn, false);
        els.stopBtn.classList.add('hidden');
        els.stopBtn.disabled = false;
        currentJobId = null;
      }
    } catch (err) {
      clearInterval(interval);
      showError(err.message);
      setButtonLoading(els.downloadBtn, false);
    }
  }, 900);
}

function appendNewLogLines(log) {
  for (let i = seenLogCount; i < log.length; i++) {
    const div = document.createElement('div');
    div.className = 'log-line';
    div.textContent = log[i];
    els.logBox.appendChild(div);
  }
  seenLogCount = log.length;
  els.logBox.scrollTop = els.logBox.scrollHeight;
}

// ---------------- open folder ----------------
els.openFolderBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/open-folder', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not open the folder.');
  } catch (err) {
    showError(err.message);
  }
});

