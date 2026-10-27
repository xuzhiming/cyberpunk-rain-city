# Music & audio credits / 配乐与音效版权

All music and ambience in `public/audio/` are **original works**, procedurally
synthesised from scratch for this project by `music/synth.py` + `music/tracks.py`
(numpy/scipy oscillators, filters, drum synthesis, reverb; mastered with ffmpeg
to -16 LUFS). No samples, loops or third-party recordings are used.

本项目 `public/audio/` 中的全部配乐与环境音均为原创，由 `music/tracks.py`
程序化合成（无任何采样或第三方素材）。

| File | Title | Style | BPM | Loop |
|---|---|---|---|---|
| neon_highway.mp3 | 霓虹高速 Neon Highway | Synthwave 合成波 | 108 | 106.7 s |
| rain_runner.mp3 | 雨夜银翼 Rain Runner | Blade-Runner-style ambient 银翼氛围 | 64 | 90 s |
| darknet_pulse.mp3 | 暗网脉冲 Darknet Pulse | Darksynth / industrial 暗黑合成 | 120 | 96 s |
| lofi_rain.mp3 | 雨窗低保真 Lo-fi Rain Window | Lo-fi chill 低保真 | 78 | 98.5 s |
| rain_ambience.mp3 | 雨声与城市环境 Rain & city ambience | Ambience 环境音 | – | 40 s |

License: **CC0 1.0 Universal** (public domain dedication) —
https://creativecommons.org/publicdomain/zero/1.0/
Regenerate: `PYTHONHASHSEED=0 python music/tracks.py`
