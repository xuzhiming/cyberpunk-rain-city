"""
Flying-car animation for the cyberpunk city (Blender 4.5, headless).

  blender -b cyberpunk_city.blend -P animate_city.py -- [--samples 24] [--pct 100]
          [--res 1280x720] [--frames 1-216] [--render] [--out DIR]

Loads the static city (cyberpunk_city.blend, left unchanged), adds:
  * spline flight paths + banking for all 15 hover cars (hero car HoverCar_00)
  * a chase camera (Cam_Chase) following the hero down the neon avenue, past the
    NEO TOKYO sign, then rising into a partial aerial reveal
  * falling (animated) rain streaks replacing the static rain
  * motion blur, animation-friendly Cycles settings
Saves cyberpunk_city_anim.blend; with --render renders the PNG sequence to anim/.
"""
import bpy, math, random, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else True
    return default
OUT = arg("--out", os.getcwd())
SAMPLES = int(arg("--samples", 12))
PCT = int(arg("--pct", 100))
RX, RY = (int(v) for v in arg("--res", "1280x720").split("x"))
FPS = 24
F0, F1 = 1, 216                         # 9.0 s @ 24 fps
fr = arg("--frames", f"{F0}-{F1}")
RF0, RF1 = (int(v) for v in fr.split("-"))
random.seed(42)

scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = F0, F1
N = F1 - F0 + 1

def smooth(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

def catmull(pts, t):
    """Uniform Catmull-Rom through pts, t in [0,1]."""
    n = len(pts) - 1
    s = max(0.0, min(0.999999, t)) * n
    i = int(s); u = s - i
    p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[min(i + 1, n)]; p3 = pts[min(i + 2, n)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)

def path_fn(ctrl, ease=None, t0=0.0, t1=1.0):
    pts = [Vector(p) for p in ctrl]
    def f(frame):
        t = (frame - F0) / (N - 1)
        t = t0 + (t1 - t0) * (ease(t) if ease else t)
        return catmull(pts, t)
    return f

def circle_fn(center, r, z, start_deg, deg_total, dz=0.0):
    c = Vector(center)
    def f(frame):
        t = (frame - F0) / (N - 1)
        a = math.radians(start_deg + deg_total * t)
        return Vector((c.x + r * math.cos(a), c.y + r * math.sin(a), z + dz * math.sin(t * math.pi)))
    return f

def ease_io(t):   # gentle accel/decel, mostly constant speed
    return 0.85 * t + 0.15 * smooth(t)

def key_car(ob, fn, bank_k=0.6, max_bank=18):
    ob.animation_data_clear()
    prev_yaw = None
    yaws = []
    poss = [fn(f) for f in range(F0 - 1, F1 + 2)]
    for k, f in enumerate(range(F0, F1 + 1)):
        p_prev, p, p_next = poss[k], poss[k + 1], poss[k + 2]
        v = (p_next - p_prev) * (FPS / 2.0)
        vh = math.hypot(v.x, v.y)
        yaw = math.atan2(v.y, v.x)
        if yaws:
            while yaw - yaws[-1] > math.pi: yaw -= 2 * math.pi
            while yaw - yaws[-1] < -math.pi: yaw += 2 * math.pi
        yaws.append(yaw)
    for k, f in enumerate(range(F0, F1 + 1)):
        p_prev, p, p_next = poss[k], poss[k + 1], poss[k + 2]
        v = (p_next - p_prev) * (FPS / 2.0)
        vh = max(0.1, math.hypot(v.x, v.y))
        yr = (yaws[min(k + 1, N - 1)] - yaws[max(k - 1, 0)]) * FPS / 2.0
        roll = max(-math.radians(max_bank), min(math.radians(max_bank), -bank_k * yr * vh / 9.81))
        pitch = -math.atan2(v.z, vh) * 0.6
        # tiny hover bob
        bob = 0.08 * math.sin(f * 0.35 + hash(ob.name) % 7)
        ob.location = (p.x, p.y, p.z + bob)
        ob.rotation_euler = (roll, pitch, yaws[k])
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# ---------------------------------------------------------------- flight paths
hero_fn = path_fn([(-2.0, -112, 6.0), (-2.5, -80, 6.5), (0.0, -40, 7.5), (-1.5, 0, 8.5), (1.0, 40, 10.0),
                   (-0.5, 80, 13.0), (0.5, 120, 18.0), (0.0, 160, 25.0), (0.5, 200, 32.0)], ease=ease_io)

paths = {
    "HoverCar_00": hero_fn,
    # avenue traffic
    "HoverCar_01": path_fn([(5.5, 230, 12), (6.0, 150, 11.5), (4.5, 60, 12.5), (6.0, -30, 11), (5.0, -130, 12)]),
    "HoverCar_02": path_fn([(-6.0, -70, 18), (-5.0, -10, 18.5), (-6.5, 50, 19.5), (-5.0, 110, 21), (-6.0, 150, 22)]),
    "HoverCar_03": path_fn([(7.0, 300, 27), (6.0, 200, 26), (7.5, 100, 28), (6.0, 0, 27), (7.0, -80, 26)]),
    "HoverCar_04": path_fn([(-4.0, 60, 33), (-5.5, 120, 34), (-4.0, 190, 36), (-5.0, 250, 38)]),
    "HoverCar_05": path_fn([(4.0, -10, 4.5), (3.0, 40, 5.0), (4.5, 100, 5.5), (3.5, 160, 6.0)]),
    # cross-street traffic
    "HoverCar_06": path_fn([(-160, 56, 22), (-60, 58, 20), (0, 56, 19), (60, 54, 20), (160, 56, 22)]),
    "HoverCar_07": path_fn([(150, 112, 30), (50, 110, 28), (0, 112, 27), (-60, 115, 29), (-170, 112, 31)]),
    "HoverCar_08": path_fn([(-140, 168, 40), (-40, 170, 38), (30, 166, 37), (140, 168, 40)]),
    # high air lanes (curved loops around landmark towers)
    "HoverCar_09": circle_fn((-112, 252), 70, 85, 180, 140, dz=8),
    "HoverCar_10": circle_fn((84, 364), 90, 110, 200, -120, dz=-10),
    "HoverCar_11": circle_fn((0, 200), 150, 70, 250, 80, dz=6),
    "HoverCar_12": circle_fn((-28, 476), 110, 125, 270, 100, dz=5),
    "HoverCar_13": circle_fn((196, 140), 60, 60, 120, -160, dz=4),
    "HoverCar_14": circle_fn((60, 300), 200, 140, 210, 60, dz=-8),
}
for name, fn in paths.items():
    ob = bpy.data.objects.get(name)
    if ob:
        key_car(ob, fn)

# hero trails: shorter and thinner so they read as light streaks close to camera
for ch in bpy.data.objects["HoverCar_00"].children:
    if "_Trail" in ch.name:
        ch.scale = (14.0, 0.05, 0.05)

# ---------------------------------------------------------------- chase camera
cd = bpy.data.cameras.new("Cam_Chase"); cd.lens = 24; cd.clip_end = 3000
cam = bpy.data.objects.new("Cam_Chase", cd); scene.collection.objects.link(cam)
END_POS = Vector((-5.0, 92.0, 52.0))
END_LOOK = Vector((6.0, 260.0, 12.0))
REVEAL0, REVEAL1 = 120, F1
for f in range(F0, F1 + 1):
    h = hero_fn(f)
    chase_pos = h + Vector((-1.8 + 0.6 * math.sin(f * 0.04), -11.0, 2.6))
    # look at a smoothed point ahead of the hero (averaging removes jitter/rotational blur)
    chase_look = sum((hero_fn(f + k) for k in range(4, 17, 3)), Vector()) / 5 + Vector((0, 4.0, 0.6))
    s = smooth((f - REVEAL0) / (REVEAL1 - REVEAL0))
    # once rising, the camera decelerates and climbs; it keeps looking at the hero
    # for a while, then towards the avenue / skyline for the aerial reveal
    pos = chase_pos.lerp(END_POS, s)
    look = chase_look.lerp(END_LOOK.lerp(h, 0.6), smooth((f - REVEAL0) / 80))
    cam.location = pos
    d = look - pos
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
# smooth out the rotation curves a bit
for fc in cam.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
scene.camera = cam

# ---------------------------------------------------------------- animated rain
for nm in ("Rain_Street", "Rain_Aerial", "Rain_City"):
    o = bpy.data.objects.get(nm)
    if o:
        o.hide_render = True; o.hide_viewport = True
MAT_RAIN = bpy.data.materials["Rain"]
rain_coll = bpy.data.collections["Rain"]
FALL = 9.0 * (N / FPS) + 2.0   # metres fallen during the clip (~9 m/s)

def rain_mesh(name, xr, yr, zr, count, length, width, wind=(0.08, 0.03)):
    v, f = [], []
    for _ in range(count):
        x = random.uniform(*xr); y = random.uniform(*yr); z = random.uniform(*zr)
        L = length * random.uniform(0.6, 1.4); dx, dy = wind[0] * L, wind[1] * L
        a = random.uniform(0, math.pi); w = width * random.uniform(0.6, 1.2)
        ox, oy = math.cos(a) * w / 2, math.sin(a) * w / 2
        o = len(v)
        v += [(x - ox, y - oy, z), (x + ox, y + oy, z), (x + ox + dx, y + oy + dy, z + L), (x - ox + dx, y - oy + dy, z + L),
              (x + oy, y - ox, z), (x - oy, y + ox, z), (x - oy + dx, y + ox + dy, z + L), (x + oy + dx, y - ox + dy, z + L)]
        f += [(o, o + 1, o + 2, o + 3), (o + 4, o + 5, o + 6, o + 7)]
    me = bpy.data.meshes.new(name); me.from_pydata(v, [], f); me.materials.append(MAT_RAIN)
    ob = bpy.data.objects.new(name, me); rain_coll.objects.link(ob)
    ob.visible_shadow = False; ob.visible_diffuse = False; ob.visible_volume_scatter = False
    # fall: linear translation, slight wind drift -> real motion blur
    for frame, zz in ((F0, 0.0), (F1, -FALL)):
        ob.location = (wind[0] * -zz, wind[1] * -zz, zz)
        ob.keyframe_insert("location", frame=frame)
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return ob

# dense fine rain along the avenue corridor the camera flies through
rain_mesh("RainAnim_Avenue", (-14, 14), (-125, 120), (0, 55 + FALL), 60000, 0.6, 0.011)
# camera rise area: coarser streaks near the end position
rain_mesh("RainAnim_Rise", (-30, 25), (20, 130), (20, 90 + FALL), 14000, 1.6, 0.03)
# sparse big streaks over the whole city for the aerial reveal
rain_mesh("RainAnim_City", (-300, 300), (-100, 500), (0, 160 + FALL), 14000, 3.0, 0.035)

# ---------------------------------------------------------------- render settings (animation budget)
r = scene.render
r.resolution_x, r.resolution_y, r.resolution_percentage = RX, RY, PCT
r.use_motion_blur = True
r.motion_blur_shutter = 0.5
r.use_persistent_data = True
cy = scene.cycles
cy.samples = SAMPLES
cy.max_bounces = 3
cy.adaptive_threshold = 0.08
cy.use_denoising = True; cy.denoiser = "OPENIMAGEDENOISE"
cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
cy.max_bounces = 3; cy.diffuse_bounces = 1; cy.glossy_bounces = 1
cy.transparent_max_bounces = 6
cy.volume_step_rate = 12.0
cy.motion_blur_position = "CENTER"
r.image_settings.file_format = "PNG"
r.image_settings.color_depth = "8"
r.image_settings.compression = 30
os.makedirs(os.path.join(OUT, "anim"), exist_ok=True)
r.filepath = os.path.join(OUT, "anim", "frame_")
scene.frame_set(F0)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "cyberpunk_city_anim.blend"), compress=True, copy=False)
print("SAVED_ANIM_BLEND")

if arg("--render", False):
    scene.frame_start, scene.frame_end = RF0, RF1
    bpy.ops.render.render(animation=True)
