// Game-style controls: view modes, Minecraft-creative movement, AABB collision, mobile joystick, FPS meter.
import * as THREE from 'three';

const MODES = ['orbit', 'fp', 'tp', 'cine'];
const MODE_LABEL = { orbit: '环绕 Orbit', fp: '第一人称 First-person', tp: '第三人称 Third-person', cine: '电影巡航 Cinematic' };
const MAX_H = 400, BOUNDS = { x0: -480, x1: 480, z0: -760, z1: 310 };
const DOUBLE_TAP_MS = 300;
const SPEC = {
  fp: { r: 0.35, h: 1.8, eye: 1.65, walk: 6, run: 13, fly: 16, boost: 48, vfly: 10, vboost: 28, jump: 8 },
  tp: { r: 1.3, h: 1.4, eye: 0, walk: 10, run: 24, fly: 26, boost: 70, vfly: 14, vboost: 36, jump: 9 },
};
const GRAVITY = 26;

export function createGame({ camera, canvas, controls, scene, renderer, cine }) {
  // ---------------------------------------------------------------- state
  let mode = 'orbit';
  let boxes = [];
  fetch('./colliders.json').then((r) => r.json()).then((b) => { boxes = b; }).catch((e) => console.warn('colliders', e));
  const pl = { pos: new THREE.Vector3(), vel: new THREE.Vector3(), yaw: 0, pitch: 0, fly: false, ground: false, sprintToggle: false, bank: 0 };
  const keys = new Set();
  let lastSpace = 0, jumpReq = 0;   // jumpReq = timestamp of a buffered jump press
  const joy = { x: 0, y: 0, up: false, down: false };
  let car = null;

  // ---------------------------------------------------------------- HUD
  const viewBtn = document.getElementById('view');
  const modeTag = document.getElementById('modetag');
  const hints = document.getElementById('keys');
  const fpsEl = document.getElementById('fps');
  const touchUI = document.getElementById('touch');
  const isTouch = matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window;

  function stateText() {
    if (mode !== 'fp' && mode !== 'tp') return '';
    const s = pl.fly ? '✈ 飞行 Flying' : '🚶 行走 Walking';
    return `${s}${sprinting() ? ' · ⚡ 冲刺 Boost' : ''} · ${pl.pos.y.toFixed(0)} m`;
  }
  function updateHud() {
    viewBtn.innerHTML = `视角 View: <b>${MODE_LABEL[mode]}</b> <kbd>V</kbd>`;
    document.body.dataset.mode = mode;
    touchUI.classList.toggle('show', isTouch && (mode === 'fp' || mode === 'tp'));
  }

  // ---------------------------------------------------------------- collision
  function hit(x, y, z, r, h) {
    for (let i = 0; i < boxes.length; i++) {
      const b = boxes[i];
      if (x + r > b[0] && x - r < b[3] && z + r > b[2] && z - r < b[5] && y + h > b[1] && y < b[4]) return b;
    }
    return null;
  }
  function unstick(S) {
    for (let k = 0; k < 30; k++) { const b = hit(pl.pos.x, pl.pos.y, pl.pos.z, S.r, S.h); if (!b) return; pl.pos.y = b[4] + 0.01; }
  }
  function moveAxis(S, axis, d) {
    if (!d) return;
    const p = pl.pos; p[axis] += d;
    const b = hit(p.x, p.y, p.z, S.r, S.h);
    if (!b) return;
    if (axis === 'x') { p.x = d > 0 ? b[0] - S.r - 1e-3 : b[3] + S.r + 1e-3; pl.vel.x = 0; }
    else if (axis === 'z') { p.z = d > 0 ? b[2] - S.r - 1e-3 : b[5] + S.r + 1e-3; pl.vel.z = 0; }
    else if (d < 0) { p.y = b[4]; pl.vel.y = 0; pl.ground = true; }
    else { p.y = b[1] - S.h - 1e-3; pl.vel.y = 0; }
  }

  // ---------------------------------------------------------------- mode switching
  const _d = new THREE.Vector3();
  function enterPlayer(from) {
    if (from === 'orbit' || from === 'cine') {
      camera.getWorldDirection(_d);
      pl.yaw = Math.atan2(-_d.x, -_d.z);
      pl.pitch = THREE.MathUtils.clamp(Math.asin(_d.y), -1.2, 1.2);
      pl.pos.copy(camera.position); pl.pos.y = Math.max(0, pl.pos.y - 1.65);
      pl.vel.set(0, 0, 0);
      pl.fly = pl.pos.y > 30;   // near street level: drop down and walk; high up: stay airborne
    }
    unstick(SPEC[mode]);
  }
  function setMode(m) {
    const prev = mode; mode = m;
    if (prev === 'cine' && m !== 'cine') cine.set(false);
    controls.enabled = m === 'orbit';
    if (m === 'cine') cine.set(true);
    if (m === 'fp' || m === 'tp') enterPlayer(prev);
    if (m === 'orbit' || m === 'cine') { if (document.pointerLockElement) document.exitPointerLock(); }
    if (m === 'orbit' && prev !== 'orbit') {
      camera.getWorldDirection(_d);
      controls.target.copy(camera.position).addScaledVector(_d, 40);
      if (controls.target.y < 0) controls.target.y = 0;
      controls.update();
    }
    if (car) car.visible = m === 'tp';
    updateHud();
  }
  const cycle = () => setMode(MODES[(MODES.indexOf(mode) + 1) % MODES.length]);
  viewBtn.onclick = (e) => { e.currentTarget.blur(); cycle(); };

  // ---------------------------------------------------------------- input
  const sprinting = () => pl.sprintToggle || keys.has('ControlLeft') || keys.has('ControlRight');
  const GAME_KEYS = new Set(['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight']);
  addEventListener('keydown', (e) => {
    if (/INPUT|SELECT|TEXTAREA/.test(e.target?.tagName || '')) return;
    const playing = mode === 'fp' || mode === 'tp';
    if (playing && GAME_KEYS.has(e.code)) e.preventDefault();
    if (playing && e.ctrlKey && /^(Key[WASDR]|Arrow)/.test(e.code)) e.preventDefault(); // Ctrl+S/D/A/R etc. (Ctrl+W can't be blocked -> beforeunload guard below)
    keys.add(e.code);
    if (e.repeat) return;
    switch (e.code) {
      case 'KeyV': cycle(); break;
      case 'KeyH': hints.classList.toggle('hidden'); break;
      case 'KeyF': fpsEl.classList.toggle('hidden'); break;
      case 'KeyR': if (playing) pl.sprintToggle = !pl.sprintToggle; break;
      case 'Space': if (playing) spacePress(); break;
    }
  });
  addEventListener('keyup', (e) => keys.delete(e.code));
  // Ctrl+W (sprint + forward) would close the tab: ask before leaving while in a player mode
  addEventListener('beforeunload', (e) => { if (mode === 'fp' || mode === 'tp') { e.preventDefault(); e.returnValue = ''; } });
  addEventListener('blur', () => keys.clear());

  function spacePress() {
    const now = performance.now();
    if (now - lastSpace < DOUBLE_TAP_MS) {
      pl.fly = !pl.fly; lastSpace = 0; jumpReq = 0;
      if (pl.fly) { pl.vel.y = Math.max(pl.vel.y, 3); pl.ground = false; }
    } else { lastSpace = now; if (!pl.fly) jumpReq = now; }
  }

  // pointer lock (desktop) + drag-to-look fallback (touch / no lock)
  canvas.addEventListener('click', () => {
    if ((mode === 'fp' || mode === 'tp') && !isTouch && !document.pointerLockElement && canvas.requestPointerLock) {
      try { const p = canvas.requestPointerLock(); if (p && p.catch) p.catch(() => {}); } catch (_) { /* unsupported */ }
    }
  });
  document.addEventListener('pointerlockchange', () => document.body.classList.toggle('locked', !!document.pointerLockElement));
  const look = (dx, dy, k) => { pl.yaw -= dx * k; pl.pitch = THREE.MathUtils.clamp(pl.pitch - dy * k, -1.5, 1.5); };
  document.addEventListener('mousemove', (e) => {
    if (document.pointerLockElement === canvas) look(e.movementX, e.movementY, 0.0022);
  });
  let drag = null;
  canvas.addEventListener('pointerdown', (e) => { if (mode === 'fp' || mode === 'tp') drag = { id: e.pointerId, x: e.clientX, y: e.clientY }; });
  canvas.addEventListener('pointermove', (e) => {
    if (!drag || drag.id !== e.pointerId || document.pointerLockElement) return;
    look(e.clientX - drag.x, e.clientY - drag.y, e.pointerType === 'touch' ? 0.005 : 0.003);
    drag.x = e.clientX; drag.y = e.clientY;
  });
  const endDrag = (e) => { if (drag && drag.id === e.pointerId) drag = null; };
  canvas.addEventListener('pointerup', endDrag); canvas.addEventListener('pointercancel', endDrag);

  // on-screen joystick + buttons (touch)
  const stick = document.getElementById('stick'), knob = stick.querySelector('i');
  let stickId = null;
  const stickMove = (e) => {
    const r = stick.getBoundingClientRect(), R = r.width / 2;
    let dx = e.clientX - (r.left + R), dy = e.clientY - (r.top + R);
    const l = Math.hypot(dx, dy); if (l > R) { dx *= R / l; dy *= R / l; }
    joy.x = dx / R; joy.y = -dy / R;
    knob.style.transform = `translate(${dx}px, ${dy}px)`;
  };
  stick.addEventListener('pointerdown', (e) => { stickId = e.pointerId; try { stick.setPointerCapture(e.pointerId); } catch (_) {} stickMove(e); });
  stick.addEventListener('pointermove', (e) => { if (e.pointerId === stickId) stickMove(e); });
  const stickEnd = (e) => { if (e.pointerId !== stickId) return; stickId = null; joy.x = joy.y = 0; knob.style.transform = ''; };
  stick.addEventListener('pointerup', stickEnd); stick.addEventListener('pointercancel', stickEnd);
  const hold = (id, prop, onDown) => {
    const el = document.getElementById(id);
    el.addEventListener('pointerdown', (e) => { e.preventDefault(); joy[prop] = true; onDown && onDown(); });
    for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) el.addEventListener(ev, () => { joy[prop] = false; });
  };
  hold('t-up', 'up', () => { if (!pl.fly) jumpReq = performance.now(); });
  hold('t-down', 'down');
  document.getElementById('t-fly').onclick = () => { pl.fly = !pl.fly; if (pl.fly) { pl.vel.y = 3; pl.ground = false; } };
  document.getElementById('t-boost').onclick = (e) => { pl.sprintToggle = !pl.sprintToggle; e.currentTarget.classList.toggle('on', pl.sprintToggle); };

  // ---------------------------------------------------------------- player car (third person)
  function setCar(template, glowMat) {
    car = template.clone(true);
    car.traverse((o) => { if (o.isMesh && /Thruster|Underglow/.test(o.name)) o.material = glowMat; });
    car.rotation.order = 'YZX'; car.visible = mode === 'tp';
    scene.add(car);
  }

  // ---------------------------------------------------------------- physics
  const _f = new THREE.Vector3(), _r = new THREE.Vector3(), _w = new THREE.Vector3();
  function physics(dt) {
    const S = SPEC[mode];
    const k = (c) => keys.has(c);
    const fwd = (k('KeyW') || k('ArrowUp') ? 1 : 0) - (k('KeyS') || k('ArrowDown') ? 1 : 0) + joy.y;
    const side = (k('KeyD') || k('ArrowRight') ? 1 : 0) - (k('KeyA') || k('ArrowLeft') ? 1 : 0) + joy.x;
    const up = k('Space') || joy.up, down = k('ShiftLeft') || k('ShiftRight') || joy.down;
    const boost = sprinting();

    _f.set(-Math.sin(pl.yaw), 0, -Math.cos(pl.yaw));
    _r.set(Math.cos(pl.yaw), 0, -Math.sin(pl.yaw));
    _w.set(0, 0, 0).addScaledVector(_f, fwd).addScaledVector(_r, side);
    if (_w.lengthSq() > 1) _w.normalize();
    const speed = pl.fly ? (boost ? S.boost : S.fly) : (boost ? S.run : S.walk);
    _w.multiplyScalar(speed);
    // smooth accel / decel (exponential approach)
    const acc = 1 - Math.exp(-dt * (pl.fly ? 3.5 : (pl.ground ? 10 : 2.5)));
    pl.vel.x += (_w.x - pl.vel.x) * acc;
    pl.vel.z += (_w.z - pl.vel.z) * acc;
    if (pl.fly) {
      const vt = ((up ? 1 : 0) - (down ? 1 : 0)) * (boost ? S.vboost : S.vfly);
      pl.vel.y += (vt - pl.vel.y) * (1 - Math.exp(-dt * 5));
    } else {
      if (jumpReq && pl.ground) { pl.vel.y = S.jump; pl.ground = false; jumpReq = 0; }
      pl.vel.y -= GRAVITY * dt;
    }
    if (jumpReq && performance.now() - jumpReq > 250) jumpReq = 0;   // short jump buffer

    // integrate with sub-steps (no tunnelling through thin walls)
    const wasGround = pl.ground; pl.ground = false;
    const n = Math.max(1, Math.ceil(Math.max(Math.abs(pl.vel.x), Math.abs(pl.vel.y), Math.abs(pl.vel.z)) * dt / (S.r * 0.9)));
    const h = dt / n;
    for (let i = 0; i < n; i++) {
      moveAxis(S, 'x', pl.vel.x * h);
      moveAxis(S, 'z', pl.vel.z * h);
      moveAxis(S, 'y', pl.vel.y * h);
      if (pl.pos.y <= 0) { pl.pos.y = 0; if (pl.vel.y < 0) pl.vel.y = 0; pl.ground = true; }
    }
    if (!pl.ground && !pl.fly && wasGround && pl.vel.y <= 0) {
      // keep contact when standing still on a roof edge / ground (probe 5 cm down)
      if (pl.pos.y <= 0.0001 || hit(pl.pos.x, pl.pos.y - 0.05, pl.pos.z, S.r, S.h)) pl.ground = true;
    }
    if (pl.pos.y > MAX_H) { pl.pos.y = MAX_H; pl.vel.y = Math.min(0, pl.vel.y); }
    pl.pos.x = THREE.MathUtils.clamp(pl.pos.x, BOUNDS.x0, BOUNDS.x1);
    pl.pos.z = THREE.MathUtils.clamp(pl.pos.z, BOUNDS.z0, BOUNDS.z1);
    // Shift-landing: touching ground (street or roof) while descending in flight -> walk
    if (pl.fly && pl.ground && down) pl.fly = false;
    return side;
  }

  // ---------------------------------------------------------------- camera
  const _look = new THREE.Vector3(), _tgt = new THREE.Vector3(), _cp = new THREE.Vector3(), _e = new THREE.Euler(0, 0, 0, 'YXZ');
  let tpCam = null;
  function camFP() {
    camera.position.set(pl.pos.x, pl.pos.y + SPEC.fp.eye, pl.pos.z);
    _e.set(pl.pitch, pl.yaw, 0); camera.quaternion.setFromEuler(_e);
  }
  function camTP(dt, side) {
    const hover = 0.9 + (pl.fly ? 0 : 0.15 * Math.sin(performance.now() / 300));
    _tgt.set(pl.pos.x, pl.pos.y + hover, pl.pos.z);
    if (car) {
      pl.bank += (THREE.MathUtils.clamp(side * 0.35, -0.35, 0.35) - pl.bank) * Math.min(1, dt * 4);
      const pitchCar = THREE.MathUtils.clamp(pl.vel.y * 0.025, -0.3, 0.3);
      car.position.copy(_tgt);
      car.rotation.set(pl.bank, pl.yaw + Math.PI / 2, pitchCar);
    }
    _look.set(-Math.sin(pl.yaw) * Math.cos(pl.pitch), Math.sin(pl.pitch), -Math.cos(pl.yaw) * Math.cos(pl.pitch));
    const focus = _cp.copy(_tgt); focus.y += 1.6;
    const want = new THREE.Vector3().copy(focus).addScaledVector(_look, -11); want.y += 1.5;
    // pull camera in if a building is between car and camera
    const seg = new THREE.Vector3().subVectors(want, focus);
    for (let i = 1; i <= 12; i++) {
      const p = new THREE.Vector3().copy(focus).addScaledVector(seg, i / 12);
      if (hit(p.x, p.y - 0.3, p.z, 0.3, 0.6)) { want.copy(focus).addScaledVector(seg, Math.max(0, (i - 1.5) / 12)); break; }
    }
    if (want.y < 0.5) want.y = 0.5;
    if (!tpCam) tpCam = want.clone();
    tpCam.lerp(want, 1 - Math.exp(-dt * 10));
    camera.position.copy(tpCam);
    camera.lookAt(focus.addScaledVector(_look, 8));
  }

  function update(dt) {
    if (mode !== 'fp' && mode !== 'tp') { tpCam = null; return false; }
    const side = physics(dt);
    if (mode === 'fp') camFP(); else camTP(dt, side);
    modeTag.textContent = stateText();
    return true;
  }

  // ---------------------------------------------------------------- FPS meter
  renderer.info.autoReset = false;
  let fAcc = 0, fN = 0, msAcc = 0, last = performance.now();
  function beginFrame() { renderer.info.reset(); }
  function endFrame() {
    const now = performance.now(), d = now - last; last = now;
    fAcc += d; fN++; msAcc += d;
    if (fAcc >= 500) {
      const fps = (fN * 1000) / fAcc, ms = msAcc / fN, inf = renderer.info.render;
      fpsEl.innerHTML = `<b>${fps.toFixed(0)}</b> FPS<span>${ms.toFixed(1)} ms · ${inf.calls} draws · ${(inf.triangles / 1000).toFixed(0)}k tris</span>`;
      fpsEl.className = fpsEl.className.replace(/\b(good|ok|bad)\b/g, '').trim() + ' ' + (fps >= 50 ? 'good' : fps >= 28 ? 'ok' : 'bad');
      window.__fps = fps; fAcc = 0; fN = 0; msAcc = 0;
    }
  }

  updateHud();
  // test/debug hook
  window.__game = { get mode() { return mode; }, setMode, pl, get boxes() { return boxes.length; } };
  return { update, setMode, setCar, beginFrame, endFrame, get mode() { return mode; } };
}
