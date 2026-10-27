"""Compose + render the 4 cyberpunk loops and the rain ambience. Original compositions (CC0 / own work)."""
import json, subprocess, sys, re, os
import numpy as np
from synth import *
import synth

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'public', 'audio'); os.makedirs(OUT, exist_ok=True)
import tempfile
TMP = os.path.join(tempfile.gettempdir(), 'music_render'); os.makedirs(TMP, exist_ok=True)

def mixdown(tr, sends):
    """sends: {bus: (gain, reverb_send, delay_send)} ; returns stereo"""
    return sum(tr.buses[b] * g for b, (g, *_r) in sends.items() if b in tr.buses)

# =====================================================================================
def neon_highway():
    """Synthwave / retrowave, 108 BPM, A minor"""
    tr = Track(108, 48); sb = tr.beat / 4
    prog = [('Am', [57, 60, 64, 67], 33), ('F', [53, 57, 60, 64], 29), ('C', [55, 60, 64, 67], 36), ('G', [55, 59, 62, 67], 31),
            ('Am', [57, 60, 64, 67], 33), ('F', [53, 57, 60, 65], 29), ('Dm', [57, 60, 62, 65], 38), ('E', [56, 59, 64, 68], 28)]
    lead_ph = [[(0, 1.5, 76), (1.5, .5, 74), (2, 1, 72), (3, 1, 69)], [(0, 3, 72), (3, .5, 74), (3.5, .5, 76)],
               [(0, 1.5, 79), (1.5, .5, 76), (2, 2, 76)], [(0, 1, 74), (1, 1, 72), (2, 2, 71)],
               [(0, 1.5, 76), (1.5, .5, 74), (2, 1, 72), (3, 1, 76)], [(0, 2, 81), (2, 1, 79), (3, 1, 77)],
               [(0, 1.5, 77), (1.5, .5, 76), (2, 2, 74)], [(0, 2, 71), (2, 2, 68)]]
    kicks = []
    for bar in range(48):
        name, ch, root = prog[bar % 8]
        full = 8 <= bar < 32 or bar >= 40
        intro = bar < 8; brk = 32 <= bar < 40
        # pads
        tr.add('pad', tr.pos(bar), pad(ch, tr.beat * 4, attack=0.25, release=0.9, fc=1800 if not brk else 1200), gain=0.32)
        # arp 16ths
        arp = [ch[0] + 12, ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 24, ch[3] + 12, ch[1] + 12, ch[2] + 12]
        open_ = min(1.0, (bar + 1) / 8) if intro else (0.6 if brk else 1.0)
        for s in range(16):
            tr.add('arp', tr.pos(bar, s / 4), pluck(arp[s % 8], sb * 0.9, 500, 900 + 4200 * open_, 0.12), pan=0.35 * np.sin(s * 0.8), gain=0.16)
        # bass: 8th octave pump
        if not intro or bar >= 4:
            if brk:
                tr.add('bass', tr.pos(bar), bass(root + 12, tr.beat * 3.8, 150, 500, 0.4, 0.8), gain=0.4)
            else:
                for e in range(8):
                    m = root + 12 if e % 2 == 0 else root + 24
                    tr.add('bass', tr.pos(bar, e / 2), bass(m, tr.beat / 2 * 0.85, 200, 1600, 0.09, 0.7), gain=0.33)
        # drums
        if full or (intro and bar >= 4):
            for b in range(4):
                tr.add('kick', tr.pos(bar, b), kick(0.5, 46, 160, 0.32), gain=0.9); kicks.append(tr.pos(bar, b))
        if full:
            for b in (1, 3): tr.add('snare', tr.pos(bar, b), snare(0.5, 190, 0.16), gain=0.55)
            if bar % 8 == 7:  # fill
                for s in range(8): tr.add('snare', tr.pos(bar, 2 + s / 4), snare(0.25, 200, 0.08), gain=0.18 + 0.05 * s)
        if full or bar >= 4:
            for e in range(8):
                o = e % 2 == 1
                tr.add('hat', tr.pos(bar, e / 2), hat(0.05, open_=o and full), pan=0.25, gain=0.12 if o else 0.07)
        # lead
        if 24 <= bar < 32 or bar >= 40 or brk:
            for (b, d, m) in lead_ph[bar % 8]:
                mm = m - 12 if brk else m
                tr.add('lead', tr.pos(bar, b), lead(mm, d * tr.beat * 0.95, 3000 if not brk else 1800, 0.18), gain=0.22)
    duck = sidechain(tr.N, kicks, 0.55, 0.28)[:, None]
    for b in ('pad', 'arp', 'bass'): tr.buses[b] *= duck if b != 'arp' else (0.5 + 0.5 * duck)
    dry = tr.buses['pad'] + tr.buses['arp'] + tr.buses['bass'] + tr.buses['kick'] + tr.buses['snare'] * 0.8 + tr.buses['hat'] + tr.buses['lead']
    wet = reverb(tr.buses['pad'] * 0.5 + tr.buses['snare'] * 0.9 + tr.buses['lead'] * 0.5 + tr.buses['arp'] * 0.3, 2.8, 5500, 0.03)
    dly = delay(tr.buses['lead'] * 0.5 + tr.buses['arp'] * 0.25, tr.beat * 0.75, 0.38, 5, 3500)
    return tr, dry + 0.35 * wet + 0.35 * dly

# =====================================================================================
def rain_runner():
    """Blade-Runner-style ambient, 64 BPM, D minor, CS-80 brass pads + FM bells"""
    tr = Track(64, 24); bar_s = tr.beat * 4
    prog = [([50, 53, 57, 60, 64], 38), ([46, 53, 57, 62, 64], 34), ([43, 50, 58, 65, 69], 31), ([45, 52, 57, 62, 67], 33)]
    for i in range(12):
        ch, root = prog[i % 4]; bar = i * 2
        if i % 4 == 3:  # A7sus4 -> A7
            tr.add('pad', tr.pos(bar), brass(ch, bar_s * 0.98, 1.4, 2.8), gain=0.5)
            tr.add('pad', tr.pos(bar + 1), brass([45, 52, 55, 61, 64], bar_s, 1.0, 3.0), gain=0.5)
        else:
            tr.add('pad', tr.pos(bar), brass(ch, bar_s * 2, 1.6, 3.0), gain=0.55)
        n = int(bar_s * 2.3 * SR); t = np.arange(n) / SR
        tr.add('sub', tr.pos(bar), sine(mtof(root - 12), n) * adsr(n, 1.5, 1, 0.9, 1.5, int(bar_s * 2 * SR)), gain=0.38)
        if i % 2 == 0: tr.add('boom', tr.pos(bar), boom(5, 32), gain=0.45)
    # sparse FM bells (D minor pentatonic), deterministic random
    r = np.random.default_rng(11); pent = [62, 65, 67, 69, 72, 74, 77, 79, 81]
    for bar in range(24):
        for e in range(8):
            if r.random() < (0.22 if bar % 4 else 0.35):
                tr.add('bell', tr.pos(bar, e / 2), bell(r.choice(pent) + 12 * (r.random() < 0.3), 3.0, 2.5, 3.5), pan=r.uniform(-0.6, 0.6), gain=0.16 * r.uniform(0.5, 1))
    # slow Vangelis-like lead in bars 8..23
    mel = [(0, 0, 6, 69), (1, 2, 2, 67), (2, 0, 4, 65), (3, 0, 4, 64), (4, 0, 6, 62), (5, 2, 2, 64), (6, 0, 8, 61),
           (8, 0, 6, 69), (9, 2, 2, 72), (10, 0, 4, 70), (11, 0, 4, 69), (12, 0, 6, 67), (13, 2, 2, 65), (14, 0, 8, 64)]
    for (b, be, d, m) in mel:
        tr.add('lead', tr.pos(8 + b, be), lead(m, d * tr.beat, 2400, 0.22, 'saw', 1.2, 0.05), gain=0.2)
    # wind / city texture: band-passed noise with periodic sweep
    N = tr.N; w = np.stack([noise(N), noise(N)], 1)
    w = circ(lambda v: bp(v, 300, 1800, 2), w) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * np.arange(N) / N))[:, None]
    tr.bus('wind')[:] = w * 0.02
    dry = tr.buses['pad'] + tr.buses['sub'] + tr.buses['boom'] * 0.6 + tr.buses['bell'] * 0.6 + tr.buses['lead'] + tr.buses['wind']
    wet = reverb(tr.buses['pad'] * 0.6 + tr.buses['bell'] + tr.buses['lead'] * 0.8 + tr.buses['boom'], 6.5, 4500, 0.06, seed=3)
    dly = delay(tr.buses['bell'] + tr.buses['lead'] * 0.4, tr.beat * 0.75, 0.45, 6, 3000)
    return tr, dry + 0.55 * wet + 0.4 * dly

# =====================================================================================
def darknet_pulse():
    """Darksynth / industrial, 120 BPM, E minor (harmonic)"""
    tr = Track(120, 48)
    prog = [([40, 47, 52, 55], 28), ([40, 47, 52, 55], 28), ([36, 43, 48, 52], 24), ([36, 43, 48, 52], 24),
            ([45, 48, 52, 57], 33), ([45, 48, 52, 57], 33), ([47, 51, 54, 59], 35), ([47, 51, 54, 59], 35)]
    mel = [[71, 76, 79, 78], [(76, 4)], [72, 76, 79, 76], [(72, 4)], [69, 72, 76, 74], [(72, 2), (71, 2)], [75, 78, 71, 75], [(78, 4)]]
    kicks = []
    N = tr.N; lfo_fc = 500 + 2600 * (0.5 + 0.5 * np.sin(2 * np.pi * 12 * np.arange(N) / N - np.pi / 2))
    for bar in range(48):
        ch, root = prog[bar % 8]
        intro = bar < 8; brk = 32 <= bar < 40; full = not intro and not brk
        tr.add('drone', tr.pos(bar), pad(ch, tr.beat * 4, 0.05, 0.6, 900, 0.25, 7), gain=0.28)
        if not brk or bar >= 36:
            for s in range(16):
                m = root + 12 + (12 if s % 4 == 2 else 0)
                acc = 1.0 if s % 2 == 1 else 0.7
                tr.add('bass', tr.pos(bar, s / 4), bass(m, tr.beat / 4 * 0.8, 220, 2500, 0.05, 0.5, 2.5) * acc, gain=0.3)
        if full or (intro and bar >= 4):
            for b in range(4): tr.add('kick', tr.pos(bar, b), kick(0.45, 44, 190, 0.28, 0.4, 2.5), gain=0.95); kicks.append(tr.pos(bar, b))
        if full:
            for b in (1, 3): tr.add('clap', tr.pos(bar, b), clap(0.35) + 0.6 * snare(0.35, 210, 0.1), gain=0.45)
            if bar % 2 == 1: tr.add('metal', tr.pos(bar, 3.5), metal(0.8, 310), pan=-0.4, gain=0.18)
            if bar % 8 == 7:
                for s in range(4): tr.add('metal', tr.pos(bar, 2 + s / 2), metal(0.4, 180 + 40 * s), pan=0.4 - 0.25 * s, gain=0.15)
        for s in range(16):
            if full or (s % 2 == 0 and (bar >= 2 or brk)):
                tr.add('hat', tr.pos(bar, s / 4), hat(0.04), pan=0.3, gain=(0.1 if s % 4 == 2 else 0.05))
        if 24 <= bar < 32 or bar >= 40 or (brk and bar >= 34):
            for i, nt in enumerate(mel[bar % 8]):
                m, d = (nt, 1) if isinstance(nt, int) else nt
                b0 = i if isinstance(nt, int) else sum(x[1] for x in mel[bar % 8][:i])
                tr.add('lead', tr.pos(bar, b0), lead(m, d * tr.beat * 0.92, 2600, 0.12, 'square', 0.15, 0.12), gain=0.2)
        if bar == 39:  # riser
            n = int(tr.beat * 4 * SR); t = np.arange(n) / n
            tr.add('fx', tr.pos(bar), hp(noise(n), 1500) * t ** 2 * 0.25)
    tr.buses['bass'] = sweep_lp(tr.buses['bass'], lfo_fc)
    duck = sidechain(N, kicks, 0.7, 0.22)[:, None]
    tr.buses['drone'] *= duck; tr.buses['bass'] *= (0.35 + 0.65 * duck)
    dry = sum(tr.buses[b] for b in ('drone', 'bass', 'kick', 'clap', 'metal', 'hat', 'lead', 'fx'))
    wet = reverb(tr.buses['clap'] * 0.6 + tr.buses['metal'] + tr.buses['lead'] * 0.5 + tr.buses['drone'] * 0.3, 2.2, 6000, 0.02, seed=5)
    dly = delay(tr.buses['lead'] * 0.6 + tr.buses['metal'] * 0.4, tr.beat * 0.75, 0.35, 4, 4000)
    return tr, sat(dry, 1.15) + 0.3 * wet + 0.3 * dly

# =====================================================================================
def lofi_rain():
    """Lo-fi hip-hop chill, 78 BPM swung, Dm9 - G13 - Cmaj9 - A7b13"""
    tr = Track(78, 32); SW = 0.62  # swing ratio for 8ths
    sw = lambda e: (e // 2) + (SW if e % 2 else 0)  # e = 8th index -> beats
    chords = [([53, 57, 60, 64], 38), ([53, 57, 59, 64], 43), ([52, 55, 59, 62], 36), ([55, 61, 65, 70], 45)]
    walk = {38: [38, 41, 43, 45], 43: [43, 41, 40, 38], 36: [36, 40, 43, 44], 45: [45, 44, 43, 40]}
    r = np.random.default_rng(23)
    for bar in range(32):
        ch, root = chords[bar % 4]
        # EP comping: beat 1 (long), "and of 2" (mid), beat 4 (short)
        for (b, d, v) in ((0, 1.6, 0.85), (sw(3), 1.0, 0.6), (3, 0.6, 0.5)):
            for i, m in enumerate(ch):
                tr.add('ep', tr.pos(bar, b) + int(i * 0.012 * SR), epiano(m, d * tr.beat, v * r.uniform(0.85, 1)), pan=-0.2 + 0.13 * i, gain=0.14)
        # bass (soft sine/tri pluck), walking on beat 4
        bl = walk[root]
        for (b, d, m) in ((0, 1.8, bl[0]), (sw(3), 0.9, bl[1] if bar % 2 else bl[0]), (3, 0.9, bl[3] if bar % 2 else bl[2])):
            n = int((d * tr.beat + 0.2) * SR); f = mtof(m)
            y = (sine(f, n) + 0.25 * tri(f, n) + 0.1 * sine(2 * f, n)) * adsr(n, 0.01, 0.4, 0.6, 0.08, int(d * tr.beat * SR))
            tr.add('bass', tr.pos(bar, b), y, gain=0.42)
        # drums (boom bap)
        intro = bar < 2
        if not intro:
            for b in (0, sw(3) + 0.0 if bar % 2 else 2.5, 2.5 if bar % 2 else sw(5)):
                tr.add('kick', tr.pos(bar, b), kick(0.4, 50, 90, 0.22, 0.05, 1.2), gain=0.6)
            for b in (1, 3): tr.add('snare', tr.pos(bar, b + 0.02), snare(0.35, 200, 0.09, 0.6, 5000), gain=0.35)
            if r.random() < 0.5: tr.add('snare', tr.pos(bar, sw(7)), snare(0.2, 220, 0.05, 0.5, 4000), gain=0.08)
        for e in range(8):
            tr.add('hat', tr.pos(bar, sw(e)), hat(0.035), pan=0.3, gain=(0.09 if e % 2 == 0 else 0.05) * r.uniform(0.7, 1.1))
    # melody (glassy EP) bars 8-15 and 24-31
    mel = [(0, 0, 1, 72), (0, 1, 0.5, 74), (0, 1.62, 1.4, 77), (1, 0, 1.5, 76), (1, 2, 1, 74), (2, 0, 2, 71), (2, 2.62, 1, 74),
           (3, 0, 1, 73), (3, 1, 2.5, 69), (4, 0, 1, 72), (4, 1.62, 1.4, 77), (5, 0, 1, 79), (5, 1, 1, 77), (5, 2, 1.5, 74),
           (6, 0, 1.5, 76), (6, 2, 1.5, 79), (7, 0, 3, 76)]
    for start in (8, 24):
        for (b, be, d, m) in mel: tr.add('mel', tr.pos(start + b, be), epiano(m + 12, d * tr.beat, 0.55), pan=0.15, gain=0.12)
    N = tr.N
    drums = (tr.buses['kick'] + tr.buses['snare'] + tr.buses['hat'])
    drums = circ(lambda v: lp(v, 5500, 2), sat(drums, 1.6))
    music = tr.buses['ep'] + tr.buses['bass'] + tr.buses['mel'] * 0.9
    wet = reverb(tr.buses['ep'] * 0.4 + tr.buses['mel'] + tr.buses['snare'] * 0.4, 1.8, 3500, 0.02, seed=9)
    dly = delay(tr.buses['mel'], tr.beat * 0.75, 0.3, 3, 2500)
    mix = music + drums + 0.3 * wet + 0.25 * dly
    mix = circ_wow(mix, 1.4, 64)
    mix = circ(lambda v: lp(v, 6500, 2), mix)
    # vinyl: hiss + crackle
    hiss = circ(lambda v: bp(v, 2000, 9000), np.stack([noise(N), noise(N)], 1)) * 0.004
    crack = np.zeros((N, 2)); idx = r.integers(0, N, int(N / SR * 9))
    for i in idx:
        L = 40; k = min(L, N - i); s = r.standard_normal(L) * np.exp(-np.arange(L) / 6) * r.uniform(0.02, 0.09)
        crack[i:i + k, int(r.random() < 0.5)] += s[:k]
    return tr, mix + hiss + circ(lambda v: hp(v, 800), crack)

# =====================================================================================
def rain_ambience():
    """40 s seamless rain + city ambience loop"""
    N = SR * 40; t = np.arange(N) / SR
    wn = np.stack([noise(N), noise(N)], 1)
    rain = circ(lambda v: lp(hp(v, 400, 2), 7000, 2), wn)
    mod = (0.8 + 0.2 * np.sin(2 * np.pi * 3 * t / 40))[:, None]
    rain *= mod * 0.06
    # heavier "on the roof" layer
    roof = circ(lambda v: bp(v, 150, 900, 2), np.stack([noise(N), noise(N)], 1)) * 0.05
    # droplets
    drops = np.zeros((N, 2)); r = np.random.default_rng(5)
    for i in r.integers(0, N, 2600):
        L = 700; tt = np.arange(L) / SR; f = r.uniform(1500, 5000)
        s = np.sin(2 * np.pi * f * tt * (1 + 0.6 * tt * 40)) * np.exp(-tt * r.uniform(200, 500)) * r.uniform(0.01, 0.07)
        p = r.uniform(0, 1); k = min(L, N - i)
        drops[i:i + k, 0] += s[:k] * (1 - p); drops[i:i + k, 1] += s[:k] * p
    # distant city: brown-ish rumble + passing car swells
    brown = np.cumsum(noise(N)); brown -= np.linspace(brown[0], brown[-1], N); brown /= np.abs(brown).max()
    city = circ(lambda v: lp(v, 140, 2), brown[:, None] * np.ones((1, 2))) * 0.12
    for c0, pan_dir in ((6, 1), (19, -1), (31, 1)):
        L = SR * 7; tt = np.arange(L) / L; sw_ = np.sin(np.pi * tt) ** 2
        car = bp(noise(L), 200, 1400) * sw_ * 0.05
        p = 0.5 + 0.45 * pan_dir * (tt * 2 - 1)
        s = int(c0 * SR); idx = (s + np.arange(L)) % N
        drops[idx, 0] += car * (1 - p); drops[idx, 1] += car * p
    # thunder
    L = SR * 9; tt = np.arange(L) / SR
    th = lp(noise(L), 110, 2) * (np.exp(-tt / 2.5) * (1 - np.exp(-tt * 3))) * 0.8 + lp(noise(L), 400) * np.exp(-tt * 4) * 0.1
    idx = (int(24 * SR) + np.arange(L)) % N; drops[idx] += th[:, None] * [0.9, 1.0]
    return rain + roof + drops + city

# =====================================================================================
def lufs(wav):
    o = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', wav, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', o)[-1]); P = float(re.findall(r'Peak:\s+(-?[\d.inf]+) dBFS', o)[-1])
    return I, P

def write_wav(path, x):
    import wave
    y = np.clip(x, -1, 1); pcm = (y * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

def master(name, x, target=-16.0, kbps=80, pad_s=1.0):
    x = x - x.mean(0)
    tmp = f'{TMP}/{name}_pre.wav'
    # measure on 2 loops so gating sees steady state
    pk = np.abs(x).max(); x = x / pk * 0.5
    write_wav(tmp, np.concatenate([x, x])); I, _ = lufs(tmp)
    g = 10 ** ((target - I) / 20); y = x * g
    # soft limiter above 0.8 (memoryless, keeps loop seamless)
    th = 0.8; a = np.abs(y); over = a > th
    y[over] = np.sign(y[over]) * (th + (1 - th) * np.tanh((a[over] - th) / (1 - th)))
    y *= 0.93
    write_wav(tmp, np.concatenate([y, y])); I2, P2 = lufs(tmp)
    corr = min(10 ** ((target - I2) / 20), 10 ** ((-1.5 - P2) / 20))   # hit target without exceeding -1.5 dBFS peak
    y *= corr; write_wav(tmp, np.concatenate([y, y])); I2, P2 = lufs(tmp)
    # padded file: [tail 1 s][loop][head 1 s] -> JS loops [pad, pad+L] (robust to MP3 decoder delay)
    p = int(pad_s * SR); padded = np.concatenate([y[-p:], y, y[:p]])
    wav = f'{TMP}/{name}.wav'; write_wav(wav, padded)
    mp3 = f'{OUT}/{name}.mp3'
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', wav, '-c:a', 'libmp3lame', '-b:a', f'{kbps}k',
                    '-metadata', f'title={name}', '-metadata', 'comment=Original procedural composition - CC0 1.0', mp3], check=True)
    print(f'{name}: loop {len(y)/SR:.2f}s  I={I2:.1f} LUFS  peak={P2:.1f} dBFS  mp3={os.path.getsize(mp3)/1e6:.2f} MB', flush=True)
    return {'file': f'audio/{name}.mp3', 'loopStart': pad_s, 'loopEnd': pad_s + len(y) / SR, 'lufs': round(I2, 1)}

if __name__ == '__main__':
    which = sys.argv[1:] or ['neon_highway', 'rain_runner', 'darknet_pulse', 'lofi_rain', 'rain']
    man_path = f'{OUT}/manifest.json'
    man = json.load(open(man_path)) if os.path.exists(man_path) else {}
    for w in which:
        synth.rng = np.random.default_rng(abs(hash(w)) % 2**32)
        if w == 'rain':
            man['rain'] = master('rain_ambience', rain_ambience(), -24.0, 64)
        else:
            tr, mix = globals()[w]()
            man[w] = master(w, mix, -16.0, 80)
            man[w]['bpm'] = tr.bpm
    json.dump(man, open(man_path, 'w'), indent=1)
