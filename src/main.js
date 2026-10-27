import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { createGame } from './game.js';
import { createAudio } from './audio.js';

// ------------------------------------------------------------------ quality
const params = new URLSearchParams(location.search);
const autoLow = matchMedia('(pointer: coarse)').matches || Math.min(innerWidth, innerHeight) < 600;
const LOW = params.get('q') ? params.get('q') === 'low' : autoLow;
const Q = LOW
  ? { dpr: Math.min(devicePixelRatio, 1.25), rain: 3500, bloomScale: 0.5, reflector: false, cars: 9, lights: 3 }
  : { dpr: Math.min(devicePixelRatio, 1.5), rain: 14000, bloomScale: 1.0, reflector: true, cars: 15, lights: 8 };
document.getElementById('qlabel').textContent = LOW ? 'Low 低' : 'High 高';
document.getElementById('quality').onclick = () => {
  params.set('q', LOW ? 'high' : 'low'); location.search = params.toString();
};

// Blender (Z-up) -> three (Y-up)
const B = (x, y, z) => new THREE.Vector3(x, z, -y);

// ------------------------------------------------------------------ renderer / scene
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Q.dpr);
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.75;

const scene = new THREE.Scene();
const FOG = new THREE.Color(0x140a26);
scene.background = new THREE.Color(0x06040d);
scene.fog = new THREE.FogExp2(FOG, 0.0058);

const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.3, 2500);
camera.position.copy(B(-3, -100, 3.2));
const controls = new OrbitControls(camera, canvas);
controls.target.copy(B(0, -40, 12));
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.5 - 0.02;
controls.maxDistance = 900;
controls.update();

// environment: dark room with neon panels -> coloured reflections on wet/metal surfaces
{
  const env = new THREE.Scene();
  env.background = new THREE.Color(0x0a0614);
  const panel = (c, i, pos, rot) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(4, 1.5), new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(i), side: THREE.DoubleSide }));
    m.position.set(...pos); m.rotation.set(...rot); env.add(m);
  };
  panel(0xff2aa8, 6, [-5, 1, 0], [0, Math.PI / 2, 0]);
  panel(0x00e5ff, 6, [5, 1.5, 0], [0, -Math.PI / 2, 0]);
  panel(0x7a2cff, 4, [0, 1, -5], [0, 0, 0]);
  panel(0xff7a1a, 3, [0, 2, 5], [0, Math.PI, 0]);
  panel(0x3a2a66, 1.5, [0, 5, 0], [Math.PI / 2, 0, 0]);
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromScene(env, 0.04).texture;
  pm.dispose();
}
scene.add(new THREE.HemisphereLight(0x6a4aa8, 0x0a0812, 0.18));

// ------------------------------------------------------------------ procedural textures
function windowTexture() {
  const S = 512, n = 8, c = document.createElement('canvas'); c.width = c.height = S;
  const g = c.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, S, S);
  const pal = ['#ffbf73', '#ffd9a8', '#9fd8ff', '#c9e6ff', '#2fe6ff', '#ff4fd0', '#ffa94d'];
  const cs = S / n;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const x = i * cs + cs * 0.18, y = j * cs + cs * 0.22, w = cs * 0.64, h = cs * 0.56;
    if (Math.random() < 0.42) {
      const col = pal[Math.floor(Math.random() * pal.length)];
      g.globalAlpha = 0.45 + Math.random() * 0.55; g.fillStyle = col; g.fillRect(x, y, w, h);
      if (Math.random() < 0.3) { g.globalAlpha = 0.5; g.fillStyle = '#000'; g.fillRect(x, y + h * 0.5, w, h * 0.5); } // blinds
    } else { g.globalAlpha = 1; g.fillStyle = '#05070b'; g.fillRect(x, y, w, h); }
  }
  g.globalAlpha = 1;
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
function puddleTexture() {
  const S = 512, c = document.createElement('canvas'); c.width = c.height = S;
  const g = c.getContext('2d'); g.fillStyle = 'rgb(222,222,222)'; g.fillRect(0, 0, S, S);
  for (let k = 0; k < 320; k++) {
    const x = Math.random() * S, y = Math.random() * S, r = 6 + Math.random() * 34;
    const gr = g.createRadialGradient(x, y, 0, x, y, r);
    gr.addColorStop(0, 'rgba(15,15,15,0.95)'); gr.addColorStop(0.7, 'rgba(30,30,30,0.6)'); gr.addColorStop(1, 'rgba(222,222,222,0)');
    g.fillStyle = gr; g.beginPath(); g.ellipse(x, y, r * (1 + Math.random()), r, Math.random() * 3, 0, 7); g.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(8, 10);
  return t;
}

// ------------------------------------------------------------------ materials
const NEON = { magenta: 0xff0a8c, cyan: 0x00d9ff, purple: 0x7a14ff, orange: 0xff5a05, pink: 0xff2650, green: 0x1aff5a };
const basic = (hex, k) => new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(k) });
const winTex = windowTexture();
const MATS = {
  Building_Windows: new THREE.MeshStandardMaterial({ color: 0x14131c, roughness: 0.42, metalness: 0.65,
    emissive: 0xffffff, emissiveMap: winTex, emissiveIntensity: 1.1, envMapIntensity: 0.5 }),
  RoofMetal: new THREE.MeshStandardMaterial({ color: 0x101016, roughness: 0.4, metalness: 0.8, envMapIntensity: 0.4 }),
  WetSidewalk: new THREE.MeshStandardMaterial({ color: 0x07070b, roughness: 0.3, metalness: 0.2, envMapIntensity: 0.2 }),
  CarPaint: new THREE.MeshStandardMaterial({ color: 0x1b1b26, roughness: 0.22, metalness: 0.9, envMapIntensity: 1.5 }),
  CarGlass: new THREE.MeshStandardMaterial({ color: 0x0b1a2a, roughness: 0.04, metalness: 1.0, envMapIntensity: 2.0 }),
  Headlight: basic(0xe6f0ff, 5), Taillight: basic(0xff1008, 4), LaneLine: basic(0x00b8ff, 1.0),
  StreetLamp: basic(0xff8c40, 2.5),
};
for (const [k, hex] of Object.entries(NEON)) { MATS['Neon_' + k] = basic(hex, 2.2); MATS['NeonSoft_' + k] = basic(hex, 0.9); }

function billboardMaterial(c1, c2, kind) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uC1: { value: new THREE.Color(c1) }, uC2: { value: new THREE.Color(c2) }, uKind: { value: kind } },
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `
      uniform float uTime, uKind; uniform vec3 uC1, uC2; varying vec2 vUv;
      float h(float n){ return fract(sin(n)*43758.5453); }
      void main(){
        vec2 u=vUv; float t=uTime; float v;
        if(uKind<0.5){ v = 0.5+0.5*sin(u.y*18.0 - t*3.0 + sin(u.x*6.0+t)*2.0); }
        else if(uKind<1.5){ float d=length(u-0.5); v = 0.5+0.5*sin(d*40.0 - t*4.0); }
        else if(uKind<2.5){ float row=floor(u.y*10.0); v = step(0.5, fract(u.x*3.0 + t*(0.3+h(row)) + h(row*7.0))); }
        else { vec2 g=abs(fract(u*vec2(8.,5.)+vec2(t*.2,0.))-.5); v = smoothstep(.42,.5,max(g.x,g.y)) + 0.35*sin(t*2.+u.x*9.); }
        vec3 col = mix(uC1, uC2, clamp(v,0.,1.));
        col *= 0.75 + 0.25*sin(u.y*300.0);                      // scanlines
        col *= 0.85 + 0.15*step(0.97, h(floor(t*12.0)));          // flicker
        float edge = step(0.96, max(abs(u.x-.5),abs(u.y-.5))*2.0);
        gl_FragColor = vec4(col*1.1 + edge*uC2*1.5, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
}
const BB = {
  BB_Billboard_A: billboardMaterial(NEON.magenta, NEON.cyan, 0),
  BB_Billboard_B: billboardMaterial(NEON.orange, NEON.purple, 1),
  BB_Billboard_C: billboardMaterial(NEON.cyan, NEON.pink, 2),
  BB_Billboard_D: billboardMaterial(NEON.purple, NEON.green, 3),
};

// ------------------------------------------------------------------ ground (wet, reflective)
const puddles = puddleTexture();
const groundGeo = new THREE.PlaneGeometry(1000, 1100);
const groundCenter = B(0, 224, 0);
if (Q.reflector) {
  const refl = new Reflector(groundGeo, {
    clipBias: 0.003, color: 0x6c6c78,
    textureWidth: Math.round(innerWidth * Q.dpr * 0.6), textureHeight: Math.round(innerHeight * Q.dpr * 0.6),
  });
  refl.rotation.x = -Math.PI / 2; refl.position.copy(groundCenter); refl.position.y = -0.002;
  scene.add(refl);
  // semi-transparent asphalt over the mirror: puddles (dark in alphaMap) stay mirror-like
  const overlay = new THREE.Mesh(groundGeo, new THREE.MeshStandardMaterial({
    color: 0x0b0b10, roughness: 0.45, metalness: 0.3, transparent: true, alphaMap: puddles, opacity: 0.95, depthWrite: true,
  }));
  overlay.rotation.x = -Math.PI / 2; overlay.position.copy(groundCenter); overlay.position.y = 0.004;
  scene.add(overlay);
} else {
  const g = new THREE.Mesh(groundGeo, new THREE.MeshPhongMaterial({
    color: 0x07070b, specular: 0x3a3a48, shininess: 90, specularMap: puddles,
  }));
  g.rotation.x = -Math.PI / 2; g.position.copy(groundCenter);
  scene.add(g);
}

// coloured street lights along the avenue
const lightCols = [NEON.magenta, NEON.cyan, NEON.purple, NEON.orange];
for (let i = 0; i < Q.lights; i++) {
  const L = new THREE.PointLight(lightCols[i % 4], LOW ? 90 : 150, 60, 2);
  L.position.copy(B(i % 2 ? 8 : -8, -100 + i * 45, 6));
  scene.add(L);
}

// ------------------------------------------------------------------ rain (GPU-animated line streaks)
function makeRain(count, box, len, speed, opacity) {
  const pos = new Float32Array(count * 6), end = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) {
    const x = Math.random() * box.x, y = Math.random() * box.y, z = Math.random() * box.z;
    pos.set([x, y, z, x, y, z], i * 6); end[i * 2 + 1] = 1;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aEnd', new THREE.BufferAttribute(end, 1));
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uCenter: { value: new THREE.Vector3() }, uBox: { value: box }, uLen: { value: len }, uSpeed: { value: speed }, uOpacity: { value: opacity } },
    vertexShader: `
      uniform float uTime, uLen, uSpeed; uniform vec3 uCenter, uBox; attribute float aEnd; varying float vA; varying float vD;
      void main(){
        vec3 p = position; p.y -= uTime*uSpeed; p.x += uTime*uSpeed*0.06;
        p = mod(p - uCenter + uBox*0.5, uBox) - uBox*0.5 + uCenter;
        p.y += aEnd*uLen; p.x -= aEnd*uLen*0.06;
        vA = aEnd; vec4 mv = viewMatrix*vec4(p,1.); vD = -mv.z;
        gl_Position = projectionMatrix*mv;
      }`,
    fragmentShader: `uniform float uOpacity; varying float vA; varying float vD;
      void main(){ float a = uOpacity*(0.25+0.75*vA)*smoothstep(1.0,4.0,vD)*(1.0-smoothstep(25.0,45.0,vD));
        gl_FragColor = vec4(vec3(0.62,0.74,1.0)*a, a); }`,
  });
  const lines = new THREE.LineSegments(g, m);
  lines.frustumCulled = false;
  scene.add(lines);
  return m;
}
const rain = makeRain(Q.rain, new THREE.Vector3(70, 50, 70), 0.9, 20, 0.55);

// ------------------------------------------------------------------ searchlights
const beamMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  uniforms: { uColor: { value: new THREE.Color() } },
  vertexShader: `varying float vH; varying vec3 vN; varying vec3 vV;
    void main(){ vH = uv.y; vN = normalize(normalMatrix*normal); vec4 mv = modelViewMatrix*vec4(position,1.); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
  fragmentShader: `uniform vec3 uColor; varying float vH; varying vec3 vN; varying vec3 vV;
    void main(){ float f = pow(abs(dot(vN,vV)), 2.0); float a = f*(1.0-vH)*0.09; gl_FragColor = vec4(uColor*a, a); }`,
});
const beams = [];
for (const [x, y, c] of [[-60, 140, 0x3fd6ff], [80, 230, 0xff3aa8], [-160, 260, 0x9a5cff], [30, 330, 0x3fd6ff]]) {
  const geo = new THREE.ConeGeometry(16, 420, 24, 1, true); geo.translate(0, -210, 0); geo.rotateX(Math.PI);
  const m = beamMat.clone(); m.uniforms.uColor.value = new THREE.Color(c);
  const mesh = new THREE.Mesh(geo, m); mesh.position.copy(B(x, y, 1));
  scene.add(mesh); beams.push(mesh);
}

// ------------------------------------------------------------------ sky traffic (distant light dots)
const sky = (() => {
  const lanes = [], N = 360, pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
  for (let l = 0; l < 12; l++) lanes.push({ o: B(-200 + Math.random() * 400, -50 + Math.random() * 500, 180 + Math.random() * 120), d: new THREE.Vector3(Math.cos(l * 1.7), 0, Math.sin(l * 1.7)), s: 15 + Math.random() * 25 });
  const items = [];
  for (let i = 0; i < N; i++) {
    const red = i % 2; items.push({ lane: lanes[i % 12], t: Math.random() * 800 - 400, dir: red ? 1 : -1 });
    const c = red ? [3, 0.2, 0.15] : [2.5, 2.6, 3]; col.set(c, i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 2.2, vertexColors: true, sizeAttenuation: true, fog: true }));
  pts.frustumCulled = false; scene.add(pts);
  return (dt) => {
    items.forEach((it, i) => {
      it.t += it.dir * it.lane.s * dt; if (it.t > 400) it.t -= 800; if (it.t < -400) it.t += 800;
      const p = it.lane.o.clone().addScaledVector(it.lane.d, it.t); p.y += it.dir * 2; pos.set([p.x, p.y, p.z], i * 3);
    });
    g.attributes.position.needsUpdate = true;
  };
})();

// ------------------------------------------------------------------ flying cars
function streetLoop(xA, xB, yA, yB, z, r = 9) {
  const C = [[xA, yA], [xA, yB], [xB, yB], [xB, yA]], pts = [];
  for (let i = 0; i < 4; i++) {
    const p = C[i], a = C[(i + 3) % 4], b = C[(i + 1) % 4];
    const din = new THREE.Vector2(p[0] - a[0], p[1] - a[1]).normalize(), dout = new THREE.Vector2(b[0] - p[0], b[1] - p[1]).normalize();
    pts.push(B(p[0] - din.x * r, p[1] - din.y * r, z), B(p[0] + dout.x * r * 0.3 - din.x * r * 0.3, p[1] + dout.y * r * 0.3 - din.y * r * 0.3, z), B(p[0] + dout.x * r, p[1] + dout.y * r, z));
  }
  return new THREE.CatmullRomCurve3(pts, true, 'centripetal');
}
// all loops follow the street grid (streets are building-free at any height); avenue heights avoid the hanging signs
const CAR_DEFS = [
  [-4, -56, -112, 448, 8, 26, 'cyan'], [4, 56, 560, -56, 18, 22, 'magenta'], [-3, -112, 0, 336, 36, 30, 'purple'],
  [5, 112, -56, 504, 9, 24, 'orange'], [56, 168, 0, 392, 60, 28, 'cyan'], [-56, -168, 56, 448, 90, 32, 'magenta'],
  [-112, 112, 112, 280, 120, 34, 'purple'], [-168, 0, -112, 560, 75, 26, 'cyan'], [-224, 224, -56, 560, 150, 38, 'orange'],
  [3, 168, 112, 448, 55, 27, 'pink'], [-4, -224, 280, -112, 24, 23, 'green'], [168, -56, 168, 504, 105, 30, 'cyan'],
  [-3, 112, 392, 0, 70, 29, 'magenta'], [112, 224, -112, 336, 42, 25, 'purple'], [-280, -112, 0, 504, 130, 33, 'orange'],
];
const cars = [];
const trailMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, fog: false });
function makeTrail(color) {
  const M = 40, g = new THREE.BufferGeometry();
  const pos = new Float32Array(M * 2 * 3), col = new Float32Array(M * 2 * 3), idx = [];
  for (let i = 0; i < M - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  g.setIndex(idx); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const mesh = new THREE.Mesh(g, trailMat); mesh.frustumCulled = false; scene.add(mesh);
  return { mesh, pos, col, hist: [], M, color: new THREE.Color(color) };
}
function updateTrail(tr, p) {
  tr.hist.unshift(p.clone()); if (tr.hist.length > tr.M) tr.hist.pop();
  for (let i = 0; i < tr.M; i++) {
    const q = tr.hist[Math.min(i, tr.hist.length - 1)], f = Math.pow(1 - i / tr.M, 2) * 2.5;
    tr.pos.set([q.x, q.y + 0.07, q.z, q.x, q.y - 0.07, q.z], i * 6);
    tr.col.set([tr.color.r * f, tr.color.g * f, tr.color.b * f, tr.color.r * f, tr.color.g * f, tr.color.b * f], i * 6);
  }
  tr.mesh.geometry.attributes.position.needsUpdate = true; tr.mesh.geometry.attributes.color.needsUpdate = true;
}

function setupCars(template) {
  template.traverse((o) => { if (o.isMesh) { o.castShadow = false; } });
  CAR_DEFS.slice(0, Q.cars).forEach(([xA, xB, yA, yB, z, speed, glow], i) => {
    const curve = streetLoop(xA, xB, yA, yB, z);
    const car = template.clone(true);
    car.traverse((o) => { if (o.isMesh && /Thruster|Underglow/.test(o.name)) o.material = MATS[(/Thruster/.test(o.name) ? 'Neon_' : 'NeonSoft_') + glow]; });
    car.rotation.order = 'YZX';
    scene.add(car);
    cars.push({ car, curve, len: curve.getLength(), speed, u: Math.random(), bank: 0, z,
      trails: [makeTrail(0xff1a10), makeTrail(0xff1a10)], tailL: new THREE.Vector3(-2.55, 0.1, 0.8), tailR: new THREE.Vector3(-2.55, 0.1, -0.8) });
  });
}
const _t = new THREE.Vector3(), _t2 = new THREE.Vector3(), _p = new THREE.Vector3();
function updateCars(dt, time) {
  for (const c of cars) {
    c.u = (c.u + c.speed * dt / c.len) % 1;
    c.curve.getPointAt(c.u, _p);
    c.curve.getTangentAt(c.u, _t); c.curve.getTangentAt((c.u + 0.004) % 1, _t2);
    const yaw = Math.atan2(-_t.z, _t.x);
    const turn = Math.atan2(_t.x * _t2.z - _t.z * _t2.x, _t.dot(_t2));       // signed yaw change
    const target = THREE.MathUtils.clamp(turn * 25, -0.45, 0.45);
    c.bank += (target - c.bank) * Math.min(1, dt * 3);
    c.car.position.copy(_p); c.car.position.y += Math.sin(time * 1.7 + c.z) * 0.15;
    c.car.rotation.set(c.bank, yaw, Math.sin(time * 1.1 + c.z) * 0.02);
    c.car.updateMatrixWorld();
    updateTrail(c.trails[0], c.car.localToWorld(c.tailL.clone()));
    updateTrail(c.trails[1], c.car.localToWorld(c.tailR.clone()));
  }
}

// ------------------------------------------------------------------ cinematic fly-through
const flyPath = new THREE.CatmullRomCurve3([
  B(-3, -130, 3.5), B(0, -60, 6), B(2, 0, 9), B(-2, 70, 13), B(0, 140, 22), B(-8, 200, 40), B(-50, 260, 90),
  B(-150, 300, 150), B(-250, 160, 170), B(-220, -60, 120), B(-110, -170, 55), B(-30, -180, 10),
], true, 'centripetal');
const CITY_CENTER = B(0, 250, 40);
let flying = false, flyT = 0;
const FLY_DURATION = 45;
const flyBtn = document.getElementById('fly');
function setFly(on) {
  flying = on; flyBtn.classList.toggle('on', on);
  flyBtn.textContent = on ? '■ 停止巡航 Stop' : '▶ 自动巡航 Fly-through';
  controls.enabled = !on;
  if (!on) { controls.target.copy(camera.position).add(camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(40)); controls.update(); }
}
flyBtn.onclick = (e) => { e.currentTarget.blur(); game.setMode(flying ? 'orbit' : 'cine'); };
function updateFly(dt) {
  flyT = (flyT + dt / FLY_DURATION) % 1;
  const p = flyPath.getPointAt(flyT), ahead = flyPath.getPointAt((flyT + 0.02) % 1);
  const k = THREE.MathUtils.smoothstep(p.y, 25, 110);
  ahead.y -= 2; const look = ahead.lerp(CITY_CENTER, k * 0.85);
  camera.position.lerp(p, Math.min(1, dt * 4));
  const m = new THREE.Matrix4().lookAt(camera.position, look, new THREE.Vector3(0, 1, 0));
  camera.quaternion.slerp(new THREE.Quaternion().setFromRotationMatrix(m), Math.min(1, dt * 3));
}

// ------------------------------------------------------------------ game controls (view modes, WASD, FPS)
const game = createGame({ camera, canvas, controls, scene, renderer, cine: { set: setFly } });
const music = createAudio();

// ------------------------------------------------------------------ post-processing
const composer = new EffectComposer(renderer);
composer.setPixelRatio(Q.dpr);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.75, 0.45, 0.9);
const origSize = bloom.setSize.bind(bloom);
bloom.setSize = (w, h) => origSize(Math.max(1, Math.round(w * Q.bloomScale)), Math.max(1, Math.round(h * Q.bloomScale)));
composer.addPass(bloom);
composer.addPass(new OutputPass());
composer.setSize(innerWidth, innerHeight);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight);
});

// ------------------------------------------------------------------ load city
const bar = document.getElementById('progress'), ltext = document.getElementById('ltext');
const GLB_SIZE_HINT = 1.25e6;
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
loader.load('./city.glb', (gltf) => {
  const root = gltf.scene;
  const template = root.getObjectByName('CarTemplate');
  template.removeFromParent();
  root.traverse((o) => {
    if (!o.isMesh) return;
    if (o.name === 'Road_Ground' || o.parent?.name === 'Road_Ground') { o.visible = false; return; }
    const owner = o.name.startsWith('BB_') ? o.name : o.parent?.name;
    if (BB[o.name] || BB[owner]) { o.material = BB[o.name] || BB[owner]; return; }
    const mn = o.material?.name;
    if (MATS[mn]) o.material = MATS[mn];
  });
  template.traverse((o) => { if (o.isMesh && MATS[o.material?.name]) o.material = MATS[o.material.name]; });
  scene.add(root);
  setupCars(template);
  game.setCar(template, MATS.Neon_cyan);
  bar.style.width = '100%'; ltext.textContent = 'Ready 100%';
  setTimeout(() => document.getElementById('loader').classList.add('done'), 300);
  window.__ready = true;
  if (params.has('fly')) game.setMode('cine');
  else if (params.get('view')) game.setMode(params.get('view'));
}, (e) => {
  const total = e.lengthComputable && e.total ? e.total : GLB_SIZE_HINT;
  const pct = Math.min(99, Math.round((e.loaded / total) * 100));
  bar.style.width = pct + '%'; ltext.textContent = `Loading… ${pct}%`;
}, (err) => { ltext.textContent = 'Load error: ' + err.message; console.error(err); });

// ------------------------------------------------------------------ loop
const clock = new THREE.Timer();
let time = params.has('t') ? parseFloat(params.get('t')) : 0;
function frame() {
  clock.update(); const dt = Math.min(clock.getDelta(), 0.05);
  time += dt;
  rain.uniforms.uTime.value = time;
  rain.uniforms.uCenter.value.copy(camera.position).add(new THREE.Vector3(0, 12, 0));
  for (const m of Object.values(BB)) m.uniforms.uTime.value = time;
  beams.forEach((b, i) => { b.rotation.set(Math.sin(time * 0.3 + i) * 0.25, 0, Math.cos(time * 0.23 + i * 2) * 0.25); });
  sky(dt);
  updateCars(dt, time);
  if (flying) updateFly(dt);
  else if (!game.update(dt)) { controls.update(); if (camera.position.y < 0.8) camera.position.y = 0.8; }
  const beat = music.pulse();                                   // audio-reactive: bloom breathes with the kick
  bloom.strength = 0.75 + 0.35 * beat;
  game.beginFrame();
  composer.render();
  game.endFrame();
  requestAnimationFrame(frame);
}
frame();
