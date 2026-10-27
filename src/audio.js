// Optional background music + rain ambience (Web Audio). Starts only after a user gesture; choice saved in localStorage.
export const TRACKS = [
  { id: 'neon_highway', zh: '霓虹高速', en: 'Neon Highway', style: '合成波 Synthwave' },
  { id: 'rain_runner', zh: '雨夜银翼', en: 'Rain Runner', style: '银翼氛围 Blade-Runner ambient' },
  { id: 'darknet_pulse', zh: '暗网脉冲', en: 'Darknet Pulse', style: '暗黑合成 Darksynth / industrial' },
  { id: 'lofi_rain', zh: '雨窗低保真', en: 'Lo-fi Rain Window', style: '低保真 Lo-fi chill' },
];
const LS = 'cyberpunk.audio.v1';

export function createAudio() {
  const st = { track: TRACKS[0].id, on: false, volume: 70, rain: false };
  try { Object.assign(st, JSON.parse(localStorage.getItem(LS) || '{}')); } catch (_) { /* ignore */ }
  if (!TRACKS.some((t) => t.id === st.track)) st.track = TRACKS[0].id;
  const save = () => { try { localStorage.setItem(LS, JSON.stringify(st)); } catch (_) { /* private mode */ } };

  let ctx = null, master, musicBus, rainBus, analyser, freq, manifest = null;
  let cur = null, rainNode = null, req = 0;
  const offsets = {}, buffers = {};
  let pendingResume = st.on || st.rain;

  // ---------------------------------------------------------------- UI refs
  const $ = (id) => document.getElementById(id);
  const btn = $('musicbtn'), panel = $('music'), sel = $('m-track'), playB = $('m-play'), nextB = $('m-next'),
    vol = $('m-vol'), volV = $('m-volv'), rainC = $('m-rain'), status = $('m-status');
  sel.innerHTML = `<option value="off">关闭 Off</option>` + TRACKS.map((t) => `<option value="${t.id}">${t.zh} ${t.en} · ${t.style}</option>`).join('');
  const meta = (id) => TRACKS.find((t) => t.id === id);
  function render(msg) {
    const t = meta(st.track);
    sel.value = st.on ? st.track : 'off';
    playB.textContent = cur ? '⏸' : '▶'; playB.title = cur ? '暂停 Pause (M)' : '播放 Play (M)';
    vol.value = st.volume; volV.textContent = st.volume;
    rainC.checked = st.rain;
    btn.innerHTML = `♪ 音乐 Music: <b>${st.on ? t.zh : '关 Off'}</b>${pendingResume ? ' <small>· 点击继续 tap to resume</small>' : ''}`;
    btn.classList.toggle('on', !!cur);
    status.textContent = msg || (cur ? `▶ ${t.zh} ${t.en} — ${t.style}` : st.on ? `⏸ ${t.zh} ${t.en}` : '音乐已关闭 Music off');
  }

  // ---------------------------------------------------------------- engine
  function ensureCtx() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext; ctx = new AC();
      master = ctx.createGain(); master.gain.value = gainFor(st.volume);
      musicBus = ctx.createGain(); analyser = ctx.createAnalyser(); analyser.fftSize = 256; analyser.smoothingTimeConstant = 0.6; analyser.minDecibels = -75; analyser.maxDecibels = -15;
      freq = new Uint8Array(analyser.frequencyBinCount);
      musicBus.connect(analyser); analyser.connect(master);
      rainBus = ctx.createGain(); rainBus.gain.value = 0.9; rainBus.connect(master);
      master.connect(ctx.destination);
      window.__audioCtx = ctx;
    }
    if (ctx.state !== 'running') ctx.resume().catch(() => {});
    pendingResume = false;
    return ctx;
  }
  const gainFor = (v) => Math.pow(v / 100, 2) * 1.0;
  async function getManifest() {
    if (!manifest) manifest = await (await fetch('./audio/manifest.json')).json();
    return manifest;
  }
  function load(id) {
    if (!buffers[id]) {
      buffers[id] = (async () => {
        const m = (await getManifest())[id];
        const res = await fetch('./' + m.file);
        if (!res.ok) throw new Error(`HTTP ${res.status} for ${m.file}`);
        const ab = await res.arrayBuffer();
        const buf = await new Promise((ok, bad) => ctx.decodeAudioData(ab, ok, bad));
        return { buf, m };
      })();
      buffers[id].catch(() => { delete buffers[id]; });
    }
    return buffers[id];
  }
  function startLoop(buf, m, bus, offset, fade) {
    const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
    src.loopStart = m.loopStart; src.loopEnd = m.loopEnd;
    const g = ctx.createGain(); const now = ctx.currentTime;
    g.gain.setValueAtTime(0, now); g.gain.linearRampToValueAtTime(1, now + fade);
    src.connect(g).connect(bus);
    const L = m.loopEnd - m.loopStart;
    src.start(now, m.loopStart + ((offset % L) + L) % L);
    return { src, g, t0: now, off: offset, L };
  }
  function stopLoop(n, fade = 0.8) {
    if (!n) return;
    const now = ctx.currentTime;
    n.g.gain.cancelScheduledValues(now); n.g.gain.setValueAtTime(n.g.gain.value, now); n.g.gain.linearRampToValueAtTime(0, now + fade);
    n.src.stop(now + fade + 0.05);
  }
  const posOf = (n) => (n.off + ctx.currentTime - n.t0) % n.L;

  async function playTrack(id, offset = offsets[id] || 0) {
    ensureCtx();
    const my = ++req;
    st.track = id; st.on = true; save(); render('加载中… Loading ' + meta(id).en);
    try {
      const { buf, m } = await load(id);
      if (my !== req) return;               // superseded by a newer request
      if (cur) { offsets[cur.id] = posOf(cur); stopLoop(cur, 1.2); }
      cur = startLoop(buf, m, musicBus, offset, 1.2); cur.id = id;
      render();
    } catch (e) { console.warn('music load failed', e); render('加载失败 Load failed'); }
  }
  function pause() {
    req++;
    if (cur) { offsets[cur.id] = posOf(cur); stopLoop(cur, 0.5); cur = null; }
    render();
  }
  function off() { pause(); st.on = false; save(); render(); }
  function togglePlay() { if (cur) { pause(); st.on = false; save(); render(); } else playTrack(st.track); }
  function next() {
    const i = TRACKS.findIndex((t) => t.id === st.track);
    const id = TRACKS[(i + 1) % TRACKS.length].id;
    offsets[id] = 0; playTrack(id, 0);
  }
  async function setRain(on) {
    st.rain = on; save(); render();
    if (!on) { if (rainNode) { stopLoop(rainNode, 1.5); rainNode = null; } return; }
    ensureCtx();
    if (rainNode) return;
    try {
      const { buf, m } = await load('rain');
      if (!st.rain || rainNode) return;
      rainNode = startLoop(buf, m, rainBus, Math.random() * 40, 2.5);
    } catch (e) { console.warn('rain load failed', e); }
  }
  function setVolume(v) {
    st.volume = v; save(); render();
    if (ctx) master.gain.setTargetAtTime(gainFor(v), ctx.currentTime, 0.05);
  }

  // ---------------------------------------------------------------- UI wiring
  const blur = (e) => e.currentTarget.blur && e.currentTarget.blur();
  btn.onclick = (e) => { blur(e); panel.classList.toggle('hidden'); if (pendingResume) resume(); };
  sel.onchange = () => { const v = sel.value; sel.blur(); if (v === 'off') off(); else { offsets[v] = 0; playTrack(v, 0); } };
  playB.onclick = (e) => { blur(e); togglePlay(); };
  nextB.onclick = (e) => { blur(e); next(); };
  vol.oninput = () => setVolume(+vol.value);
  vol.onchange = () => vol.blur();
  rainC.onchange = () => { rainC.blur(); setRain(rainC.checked); };
  addEventListener('keydown', (e) => {
    if (e.repeat || /INPUT|SELECT|TEXTAREA/.test(e.target?.tagName || '')) return;
    if (e.code === 'KeyM') togglePlay();
    else if (e.code === 'KeyN') next();
  });
  // restore a saved "on" state on the first user gesture (autoplay policy)
  function resume() {
    if (!pendingResume) return;
    pendingResume = false;
    if (st.on) playTrack(st.track); if (st.rain) setRain(true);
    render();
  }
  const gesture = (e) => {
    if (e.type === 'keydown' && (e.code === 'KeyM' || e.code === 'KeyN')) { pendingResume = false; if (st.rain) setRain(true); return; }
    if (e.target && panel.contains(e.target)) return;   // panel controls handle themselves
    resume();
  };
  for (const ev of ['pointerup', 'keydown', 'touchend']) addEventListener(ev, gesture, { capture: true });
  render();

  // ---------------------------------------------------------------- audio-reactive level (cheap: 128-bin analyser)
  let env = 0, slow = -1, lastT = 0;
  function pulse() {
    const now = performance.now(), dt = Math.min(0.25, lastT ? (now - lastT) / 1000 : 0.016); lastT = now;
    if (!cur || !analyser) { env *= Math.exp(-dt / 0.25); slow = -1; return env; }
    analyser.getByteFrequencyData(freq);
    const low = (freq[1] + freq[2] + freq[3]) / 765;          // ~170-700 Hz
    if (slow < 0) slow = low;                                  // seed average, no start-up flash
    slow += (low - slow) * (1 - Math.exp(-dt / 1.5));          // ~1.5 s running mean
    const hit = Math.max(0, low - slow) * 3.5;
    env = Math.max(hit, env * Math.exp(-dt / 0.22));           // fast attack, ~0.2 s release
    window.__beat = Math.min(1, env); return window.__beat;
  }
  window.__music = { get state() { return { ...st, playing: !!cur, ctx: ctx ? ctx.state : 'none', current: cur ? cur.id : null, rainPlaying: !!rainNode }; }, next, togglePlay };
  return { pulse };
}
