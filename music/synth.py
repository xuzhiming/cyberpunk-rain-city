"""Tiny offline synth engine (numpy/scipy). Everything is rendered CIRCULARLY so each track loops seamlessly:
notes/tails that run past the loop end wrap to the start, and reverbs/delays/bus filters are circular too."""
import numpy as np
from scipy.signal import butter, sosfilt
SR = 44100
rng = np.random.default_rng(7)

def mtof(m): return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)

# ---------------------------------------------------------------- oscillators
def phase(freq, n, ph0=0.0):
    inc = np.broadcast_to(np.asarray(freq, float), (n,)) / SR
    return (ph0 + np.cumsum(inc)) % 1.0, inc

def saw(freq, n, ph0=None):
    ph, dt = phase(freq, n, rng.random() if ph0 is None else ph0)
    y = 2 * ph - 1
    m = ph < dt; x = ph[m] / dt[m]; y[m] -= x + x - x * x - 1
    m = ph > 1 - dt; x = (ph[m] - 1) / dt[m]; y[m] -= x * x + x + x + 1
    return y

def square(freq, n, pw=0.5):
    p0 = rng.random()
    return 0.5 * (saw(freq, n, p0) - saw(freq, n, (p0 + pw) % 1))

def sine(freq, n, ph0=0.0):
    ph, _ = phase(freq, n, ph0); return np.sin(2 * np.pi * ph)

def tri(freq, n):
    ph, _ = phase(freq, n, rng.random()); return 4 * np.abs(ph - 0.5) - 1

def supersaw(freq, n, voices=5, detune=0.12):
    out = np.zeros(n)
    for i in range(voices):
        c = (i - (voices - 1) / 2) / max(1, (voices - 1) / 2) * detune  # semitones
        out += saw(freq * 2 ** (c / 12), n)
    return out / np.sqrt(voices)

def noise(n): return rng.standard_normal(n)

# ---------------------------------------------------------------- filters
def _sos(kind, fc, order=2):
    if kind == 'band':
        lo, hi = fc; hi = min(hi, SR * 0.45)
        return butter(order, [lo, hi], 'band', fs=SR, output='sos')
    return butter(order, min(fc, SR * 0.45), kind, fs=SR, output='sos')
def lp(x, fc, order=2): return sosfilt(_sos('low', fc, order), x, axis=0)
def hp(x, fc, order=2): return sosfilt(_sos('high', fc, order), x, axis=0)
def bp(x, lo, hi, order=2): return sosfilt(_sos('band', (lo, hi), order), x, axis=0)

def circ(fn, x, pad=SR * 2):
    """apply a stateful filter circularly (pre-roll with the loop's own tail)"""
    y = fn(np.concatenate([x[-pad:], x], axis=0)); return y[pad:]

def sweep_lp(x, fcs, block=512, pad=SR):
    """time-varying 2-pole lowpass along axis 0 (circular pre-roll); fcs = cutoff per sample"""
    xp = np.concatenate([x[-pad:], x], axis=0); fp = np.concatenate([fcs[-pad:], fcs])
    y = np.empty_like(xp); zi = np.zeros((1, 2) + xp.shape[1:])
    for s in range(0, len(xp), block):
        sos = _sos('low', float(fp[s]), 2)
        y[s:s + block], zi = sosfilt(sos, xp[s:s + block], axis=0, zi=zi)
    return y[pad:]

# ---------------------------------------------------------------- envelopes
def adsr(n, a=0.005, d=0.1, s=0.7, r=0.2, gate=None):
    """gate = held length in samples; release starts after gate; total len n"""
    gate = n if gate is None else gate
    t = np.arange(n) / SR
    env = np.where(t < a, t / max(a, 1e-6), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-6)))
    tg = gate / SR
    lvl = env[min(gate, n - 1)]
    rel = lvl * np.exp(-(t - tg) / max(r, 1e-6))
    return np.where(t < tg, env, rel)

def expdec(n, tau): return np.exp(-np.arange(n) / SR / tau)

# ---------------------------------------------------------------- mixing
class Track:
    def __init__(self, bpm, bars, beats_per_bar=4):
        self.bpm = bpm; self.beat = 60 / bpm; self.bars = bars
        self.N = int(round(bars * beats_per_bar * self.beat * SR)); self.bpb = beats_per_bar
        self.buses = {}
    def bus(self, name):
        if name not in self.buses: self.buses[name] = np.zeros((self.N, 2))
        return self.buses[name]
    def pos(self, bar, beat=0.0): return int(round((bar * self.bpb + beat) * self.beat * SR))
    def add(self, name, start, sig, pan=0.0, gain=1.0):
        b = self.bus(name)
        if sig.ndim == 1:
            l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            sig = np.stack([sig * l * 1.4142, sig * r * 1.4142], 1)
        sig = sig * gain
        start %= self.N; n = len(sig)
        while n > 0:
            k = min(n, self.N - start)
            b[start:start + k] += sig[:k]; sig = sig[k:]; n -= k; start = 0

def circ_conv(x, ir):
    """circular convolution of stereo x (N,2) with stereo ir (M,2)"""
    N = len(x); out = np.empty_like(x)
    for c in range(2):
        h = np.zeros(N); m = min(len(ir), N); h[:m] = ir[:m, c]
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c]) * np.fft.rfft(h), N)
    return out

def reverb(x, t60=2.5, damp=6000, predelay=0.02, width=1.0, seed=1):
    r = np.random.default_rng(seed); M = int(t60 * 1.2 * SR)
    t = np.arange(M) / SR; env = np.exp(-6.91 * t / t60)
    ir = np.stack([r.standard_normal(M), r.standard_normal(M)], 1)
    ir = lp(ir, damp, 1) * env[:, None]
    ir[:, 1] = width * ir[:, 1] + (1 - width) * ir[:, 0]
    pd = int(predelay * SR); ir = np.concatenate([np.zeros((pd, 2)), ir])
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return circ_conv(x, ir)

def delay(x, time, fb=0.4, taps=6, damp=4000, pingpong=True):
    d = int(time * SR); y = np.zeros_like(x); cur = x.copy()
    for k in range(1, taps + 1):
        cur = circ(lambda v: lp(v, damp, 1), cur, SR // 2) * fb
        sh = np.roll(cur, d * k, axis=0) if False else np.roll(cur, d, axis=0)
        cur = sh
        y += cur[:, ::-1] if (pingpong and k % 2) else cur
    return y

def sidechain(N, starts, depth=0.6, length=0.25):
    g = np.ones(N); L = int(length * SR); t = np.linspace(0, 1, L)
    shape = 1 - depth * (1 - t) ** 2
    for s in starts:
        s %= N; k = min(L, N - s); g[s:s + k] *= shape[:k]
        if k < L: g[:L - k] *= shape[k:]
    return g

def sat(x, drive=1.5): return np.tanh(x * drive) / np.tanh(drive)

# ---------------------------------------------------------------- drums
def kick(dur=0.5, f0=48, f1=150, decay=0.35, click=0.25, drive=1.6):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 + f1 * np.exp(-t * 32)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    y += click * hp(noise(n), 3000) * np.exp(-t * 300)
    return sat(y, drive)

def snare(dur=0.4, tone=185, decay=0.12, nmix=0.8, bright=7000):
    n = int(dur * SR); t = np.arange(n) / SR
    y = 0.6 * sine(tone, n) * np.exp(-t * 22) + 0.3 * sine(tone * 1.6, n) * np.exp(-t * 30)
    y += nmix * bp(noise(n), 900, bright) * np.exp(-t / decay)
    return sat(y, 1.2)

def clap(dur=0.35):
    n = int(dur * SR); t = np.arange(n) / SR; env = np.zeros(n)
    for o in (0, 0.011, 0.022):
        k = int(o * SR); env[k:] += np.exp(-(t[:n - k]) * 140) * 0.7
    env += np.exp(-t * 16) * 0.5
    return bp(noise(n), 1000, 5000) * env

def hat(dur=0.06, open_=False):
    n = int((0.35 if open_ else dur) * SR); t = np.arange(n) / SR
    y = hp(noise(n), 7000, 2) + 0.5 * hp(square(5400, n) * square(7900, n), 6000)
    return y * np.exp(-t * (9 if open_ else 55))

def metal(dur=0.6, f=320):
    n = int(dur * SR); t = np.arange(n) / SR
    m = sine(f * 1.414, n) * 6 * np.exp(-t * 6)
    y = np.sin(2 * np.pi * f * t + m) * np.exp(-t * 5) + 0.3 * hp(noise(n), 3000) * np.exp(-t * 40)
    return y

def boom(dur=4.0, f=34):
    n = int(dur * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * np.cumsum(f + 40 * np.exp(-t * 6)) / SR) * np.exp(-t / 1.2)
    y += 0.5 * lp(noise(n), 200) * np.exp(-t / 0.8)
    return sat(y, 1.3)

# ---------------------------------------------------------------- instruments
def pad(notes, dur, attack=0.4, release=1.2, fc=2200, detune=0.14, voices=5):
    n = int((dur + release * 3) * SR); g = int(dur * SR); y = np.zeros(n)
    for m in notes: y += supersaw(mtof(m), n, voices, detune)
    y = lp(y, fc, 2) * adsr(n, attack, 0.5, 0.85, release, g)
    return y / max(1, len(notes)) ** 0.5

def brass(notes, dur, attack=1.2, release=2.5, fc0=500, fc1=2600, vib=0.08):
    """CS-80-ish: detuned saws, slow filter swell (crossfade dark->bright), vibrato"""
    n = int((dur + release * 3) * SR); g = int(dur * SR); t = np.arange(n) / SR
    lfo = 2 ** (vib / 12 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 1.5, 0, 1))
    y = np.zeros(n)
    for m in notes:
        f = mtof(m) * lfo
        y += saw(f, n) + saw(f * 1.006, n) + 0.5 * square(f * 0.5, n, 0.35)
    env = adsr(n, attack, 1.0, 0.8, release, g)
    swell = np.clip(env, 0, 1) ** 1.5
    y = lp(y, fc0) * (1 - swell) + lp(y, fc1) * swell
    return y * env / max(1, len(notes)) ** 0.5 * 0.5

def pluck(m, dur=0.25, fc0=600, fc1=5000, decay=0.18, wave='saw'):
    n = int((dur + 0.4) * SR); f = mtof(m)
    y = saw(f, n) if wave == 'saw' else square(f, n, 0.3)
    e = expdec(n, decay)
    y = lp(y, fc0) * (1 - e) + lp(y, fc1) * e
    return y * adsr(n, 0.002, decay, 0.0, 0.1, int(dur * SR))

def bass(m, dur, fc0=180, fc1=1200, decay=0.12, sub=0.6, drive=1.4, wave='saw'):
    n = int((dur + 0.15) * SR); f = mtof(m)
    y = saw(f, n) if wave == 'saw' else square(f, n, 0.5)
    e = expdec(n, decay)
    y = lp(y, fc0, 2) * (1 - e) + lp(y, fc1, 2) * e
    y = y + sub * sine(f, n)
    return sat(y * adsr(n, 0.003, 0.3, 0.8, 0.05, int(dur * SR)), drive)

def lead(m, dur, fc=3200, vib=0.15, wave='saw', release=0.25, detune=0.08):
    n = int((dur + release * 4) * SR); t = np.arange(n) / SR
    lfo = 2 ** (vib / 12 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.25) / 0.4, 0, 1))
    f = mtof(m) * lfo
    if wave == 'saw': y = saw(f, n) + saw(f * 2 ** (detune / 12), n)
    else: y = square(f, n, 0.5) + 0.6 * saw(f * 2 ** (detune / 12), n)
    return lp(y, fc) * adsr(n, 0.02, 0.3, 0.75, release, int(dur * SR)) * 0.5

def bell(m, dur=2.5, index=3.0, ratio=3.5):
    n = int(dur * SR); t = np.arange(n) / SR; f = mtof(m)
    mod = np.sin(2 * np.pi * f * ratio * t) * index * np.exp(-t * 2.5)
    return np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.6) * adsr(n, 0.002, 1, 1, 1)

def epiano(m, dur, vel=1.0):
    """FM Rhodes-ish"""
    n = int((dur + 1.2) * SR); t = np.arange(n) / SR; f = mtof(m)
    idx = (1.2 + 1.5 * vel) * np.exp(-t * 3.5)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    y += 0.18 * vel * np.sin(2 * np.pi * f * 14.0 * t) * np.exp(-t * 30)   # tine
    y *= 1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)                             # tremolo
    return y * adsr(n, 0.003, 1.4, 0.35, 0.35, int(dur * SR)) * (0.5 + 0.5 * vel)

def circ_wow(x, depth_ms=1.6, cycles=40):
    """periodic pitch wobble (integer #cycles over the loop -> seamless)"""
    N = len(x); i = np.arange(N)
    d = (depth_ms / 1000 * SR) * (1 + np.sin(2 * np.pi * cycles * i / N)) / 2 + 2
    src = (i - d) % N; i0 = np.floor(src).astype(int); fr = (src - i0)[:, None]
    return x[i0] * (1 - fr) + x[(i0 + 1) % N] * fr
