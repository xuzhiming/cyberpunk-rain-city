"""
Procedural cyberpunk rainy city for Blender 4.5 (headless).

Usage:
  blender -b -P build_city.py -- [--render street|aerial|both|none] [--samples N]
          [--pct 100] [--out DIR] [--glb]
Builds the scene, saves cyberpunk_city.blend in --out and optionally renders.
"""
import bpy, bmesh, math, random, sys, os, time
from mathutils import Vector, Euler

# ---------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else True
    return default
RENDER = arg("--render", "none")
SAMPLES = int(arg("--samples", 96))
PCT = int(arg("--pct", 100))
OUT = arg("--out", os.getcwd())
EXPORT_GLB = bool(arg("--glb", False))
os.makedirs(OUT, exist_ok=True)

random.seed(2077)

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "CyberpunkCity"

def coll(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c
C_GROUND, C_BLD, C_NEON, C_CARS, C_RAIN, C_FX = (coll(n) for n in
    ("Streets", "Buildings", "Neon", "FlyingCars", "Rain", "Atmosphere"))

# ---------------------------------------------------------------- mesh helpers
def box_verts(cx, cy, cz, sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    v = [(cx + dx * hx, cy + dy * hy, cz + dz * hz)
         for dz in (-1, 1) for dy in (-1, 1) for dx in (-1, 1)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return v, f

class MeshBuilder:
    """Accumulate many boxes/quads into one mesh (fast, few objects)."""
    def __init__(self):
        self.v, self.f, self.mi = [], [], []
    def box(self, c, s, mat_index=0):
        v, f = box_verts(*c, *s)
        o = len(self.v)
        self.v += v
        self.f += [tuple(i + o for i in q) for q in f]
        self.mi += [mat_index] * len(f)
    def quad(self, pts, mat_index=0):
        o = len(self.v)
        self.v += pts
        self.f.append((o, o + 1, o + 2, o + 3))
        self.mi.append(mat_index)
    def build(self, name, mats, collection, smooth=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.mi)
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.update()
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        return ob

def box_obj(name, c, s, mat, collection, rot=None):
    mb = MeshBuilder()
    mb.box((0, 0, 0), s)
    ob = mb.build(name, [mat], collection)
    ob.location = c
    if rot:
        ob.rotation_euler = rot
    return ob

# ---------------------------------------------------------------- materials
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out

def emission_mat(name, color, strength):
    m, nt, out = new_mat(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (*color, 1)
    return m

def math_node(nt, op, a=None, b=None, va=0.0, vb=0.0):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for idx, src, val in ((0, a, va), (1, b, vb)):
        if src is not None:
            nt.links.new(src, n.inputs[idx])
        else:
            n.inputs[idx].default_value = val
    return n.outputs[0]

NEON = {
    "magenta": (1.0, 0.02, 0.55),
    "cyan":    (0.0, 0.85, 1.0),
    "purple":  (0.45, 0.05, 1.0),
    "orange":  (1.0, 0.35, 0.02),
    "pink":    (1.0, 0.15, 0.3),
    "green":   (0.1, 1.0, 0.35),
}
NEON_MATS = {k: emission_mat("Neon_" + k, c, 18.0) for k, c in NEON.items()}
NEON_SOFT = {k: emission_mat("NeonSoft_" + k, c, 5.0) for k, c in NEON.items()}
MAIN_NEON = ["magenta", "cyan", "purple", "orange", "magenta", "cyan", "pink", "green"]

def building_material():
    m, nt, out = new_mat("Building_Windows")
    N = nt.nodes
    geo = N.new("ShaderNodeNewGeometry")
    oi = N.new("ShaderNodeObjectInfo")
    sp = N.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Position"], sp.inputs[0])
    sn = N.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Normal"], sn.inputs[0])
    # window grid coordinates
    u = math_node(nt, "DIVIDE", math_node(nt, "ADD", sp.outputs[0], sp.outputs[1]), None, vb=1.6)
    v = math_node(nt, "DIVIDE", sp.outputs[2], None, vb=3.3)
    fu = math_node(nt, "FRACT", u); fv = math_node(nt, "FRACT", v)
    mu = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", fu, None, vb=0.18),
                   math_node(nt, "LESS_THAN", fu, None, vb=0.82))
    mv = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", fv, None, vb=0.28),
                   math_node(nt, "LESS_THAN", fv, None, vb=0.82))
    vert = math_node(nt, "LESS_THAN", math_node(nt, "ABSOLUTE", sn.outputs[2]), None, vb=0.5)
    above = math_node(nt, "GREATER_THAN", sp.outputs[2], None, vb=4.5)  # no windows at street level
    mask = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", mu, mv), math_node(nt, "MULTIPLY", vert, above))
    cell = N.new("ShaderNodeCombineXYZ")
    nt.links.new(math_node(nt, "FLOOR", u), cell.inputs[0])
    nt.links.new(math_node(nt, "FLOOR", v), cell.inputs[1])
    nt.links.new(math_node(nt, "MULTIPLY", oi.outputs["Random"], None, vb=137.0), cell.inputs[2])
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"
    nt.links.new(cell.outputs[0], wn.inputs["Vector"])
    lit = math_node(nt, "GREATER_THAN", wn.outputs["Value"], None, vb=0.62)
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (1.0, 0.72, 0.42, 1)    # warm
    el[1].position = 0.45; el[1].color = (0.55, 0.85, 1.0, 1)   # cool white-blue
    e = el.new(0.75); e.color = (0.1, 0.9, 1.0, 1)              # cyan
    e = el.new(0.9); e.color = (1.0, 0.2, 0.8, 1)               # magenta
    sepc = N.new("ShaderNodeSeparateColor"); nt.links.new(wn.outputs["Color"], sepc.inputs[0])
    nt.links.new(sepc.outputs[0], ramp.inputs[0])
    bright = math_node(nt, "ADD", math_node(nt, "MULTIPLY", sepc.outputs[1], None, vb=2.0), None, vb=0.6)
    strength = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", mask, lit), bright)
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    # dark facade, slightly varied per object
    fac_ramp = N.new("ShaderNodeValToRGB")
    fac_ramp.color_ramp.elements[0].color = (0.012, 0.013, 0.02, 1)
    fac_ramp.color_ramp.elements[1].color = (0.05, 0.045, 0.06, 1)
    nt.links.new(oi.outputs["Random"], fac_ramp.inputs[0])
    nt.links.new(fac_ramp.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.5
    # glass windows are glossier than the concrete frame
    rough = math_node(nt, "SUBTRACT", None, math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", mu, mv), None, vb=0.3), va=0.45)
    nt.links.new(rough, bsdf.inputs["Roughness"])
    nt.links.new(ramp.outputs[0], bsdf.inputs["Emission Color"])
    nt.links.new(strength, bsdf.inputs["Emission Strength"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m

def wet_ground_material(name, base, dry_rough, scale):
    m, nt, out = new_mat(name)
    N = nt.nodes
    tc = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")         # puddle mask: white = puddle
    ramp.color_ramp.elements[0].position = 0.48
    ramp.color_ramp.elements[1].position = 0.53
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    rmix = N.new("ShaderNodeMapRange")
    rmix.inputs["To Min"].default_value = dry_rough
    rmix.inputs["To Max"].default_value = 0.015
    nt.links.new(ramp.outputs[0], rmix.inputs["Value"])
    nt.links.new(rmix.outputs[0], bsdf.inputs["Roughness"])
    cmix = N.new("ShaderNodeMix"); cmix.data_type = "RGBA"
    cmix.inputs["A"].default_value = (*base, 1)
    cmix.inputs["B"].default_value = (base[0] * 0.35, base[1] * 0.35, base[2] * 0.4, 1)
    nt.links.new(ramp.outputs[0], cmix.inputs["Factor"])
    nt.links.new(cmix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.6
    # fine asphalt grain bump outside puddles
    n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 60.0
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    bump = N.new("ShaderNodeBump")
    inv = math_node(nt, "SUBTRACT", None, ramp.outputs[0], va=1.0)
    nt.links.new(math_node(nt, "MULTIPLY", inv, None, vb=0.15), bump.inputs["Strength"])
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m

def billboard_material(name, c1, c2, kind):
    m, nt, out = new_mat(name)
    N = nt.nodes
    tc = N.new("ShaderNodeTexCoord")
    if kind == "wave":
        t = N.new("ShaderNodeTexWave"); t.inputs["Scale"].default_value = 1.5
        t.inputs["Distortion"].default_value = 6.0
    elif kind == "magic":
        t = N.new("ShaderNodeTexMagic"); t.inputs["Scale"].default_value = 0.8
        t.turbulence_depth = 3
    else:
        t = N.new("ShaderNodeTexVoronoi"); t.inputs["Scale"].default_value = 1.2
    nt.links.new(tc.outputs["Object"], t.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    e = ramp.color_ramp.elements.new(0.5); e.color = (0.02, 0.0, 0.05, 1)
    out_sock = t.outputs["Fac"] if "Fac" in t.outputs else t.outputs["Distance"]
    nt.links.new(out_sock, ramp.inputs[0])
    em = N.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 7.0
    nt.links.new(ramp.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m

def trail_material(name, color, strength):
    """Emission fading along local -X (trail mesh spans x in [-1, 0])."""
    m, nt, out = new_mat(name)
    N = nt.nodes
    tc = N.new("ShaderNodeTexCoord")
    sp = N.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sp.inputs[0])
    fade = math_node(nt, "POWER", math_node(nt, "ADD", sp.outputs[0], None, vb=1.0), None, vb=2.0)
    em = N.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1)
    nt.links.new(math_node(nt, "MULTIPLY", fade, None, vb=strength), em.inputs["Strength"])
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    nt.links.new(fade, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m

MAT_BLD = building_material()
MAT_ROAD = wet_ground_material("WetAsphalt", (0.018, 0.018, 0.022), 0.28, 0.08)
MAT_WALK = wet_ground_material("WetSidewalk", (0.04, 0.04, 0.045), 0.32, 0.25)
MAT_ROOF = bpy.data.materials.new("RoofMetal"); MAT_ROOF.use_nodes = True
pb = MAT_ROOF.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1); pb.inputs["Metallic"].default_value = 0.8
pb.inputs["Roughness"].default_value = 0.35
MAT_CARBODY = bpy.data.materials.new("CarPaint"); MAT_CARBODY.use_nodes = True
pb = MAT_CARBODY.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.04, 0.04, 0.05, 1); pb.inputs["Metallic"].default_value = 0.9
pb.inputs["Roughness"].default_value = 0.15
pb.inputs["Coat Weight"].default_value = 1.0
MAT_GLASS = bpy.data.materials.new("CarGlass"); MAT_GLASS.use_nodes = True
pb = MAT_GLASS.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.02, 0.03, 0.05, 1); pb.inputs["Roughness"].default_value = 0.05
pb.inputs["Metallic"].default_value = 1.0
MAT_HEAD = emission_mat("Headlight", (0.85, 0.92, 1.0), 60.0)
MAT_TAIL = emission_mat("Taillight", (1.0, 0.03, 0.02), 40.0)
MAT_TRAIL_R = trail_material("Trail_Red", (1.0, 0.05, 0.05), 6.0)
MAT_TRAIL_W = trail_material("Trail_White", (0.7, 0.85, 1.0), 6.0)
MAT_TRAIL_C = trail_material("Trail_Cyan", (0.0, 0.8, 1.0), 6.0)
MAT_LANE = emission_mat("LaneLine", (0.0, 0.7, 1.0), 4.0)
MAT_LAMP = emission_mat("StreetLamp", (1.0, 0.55, 0.25), 25.0)
BILLBOARDS = [
    billboard_material("Billboard_A", NEON["magenta"], NEON["cyan"], "wave"),
    billboard_material("Billboard_B", NEON["orange"], NEON["purple"], "magic"),
    billboard_material("Billboard_C", NEON["cyan"], NEON["pink"], "voronoi"),
    billboard_material("Billboard_D", NEON["purple"], NEON["green"], "wave"),
]

# ---------------------------------------------------------------- city layout
P = 56.0          # block pitch
BLOCK = 40.0      # block size (street width = 16 m)
AVE_HALF = 12.0   # main avenue (x = 0) is 24 m wide
IX = range(-5, 5)     # block columns -> centers (i+0.5)*P
JY = range(-3, 11)    # block rows
SIDEWALK = 3.5

ground = box_obj("Road_Ground", (0, 4 * P, -0.1), (16 * P, 20 * P, 0.2), MAT_ROAD, C_GROUND)

walk = MeshBuilder()
lanes = MeshBuilder()
bld_mb_roofs = MeshBuilder()
neon_mb = {k: MeshBuilder() for k in NEON}
neon_soft_mb = {k: MeshBuilder() for k in NEON}
lamp_mb = MeshBuilder()
buildings = []
facade_targets = []   # (building_obj_info) for signs

def block_bounds(i, j):
    cx, cy = (i + 0.5) * P, (j + 0.5) * P
    x0, x1 = cx - BLOCK / 2, cx + BLOCK / 2
    y0, y1 = cy - BLOCK / 2, cy + BLOCK / 2
    # widen main avenue at x = 0
    if i == -1: x1 = min(x1, -AVE_HALF)
    if i == 0:  x0 = max(x0, AVE_HALF)
    return x0, x1, y0, y1

def dist_to_center(x, y):
    return math.hypot(x, y - 3 * P)

landmarks = {(-2, 4), (1, 6), (-1, 8), (3, 2), (2, 9), (-4, 6)}

for i in IX:
    for j in JY:
        x0, x1, y0, y1 = block_bounds(i, j)
        # sidewalk slab
        walk.box(((x0 + x1) / 2, (y0 + y1) / 2, 0.075), (x1 - x0, y1 - y0, 0.15))
        bx0, bx1, by0, by1 = x0 + SIDEWALK, x1 - SIDEWALK, y0 + SIDEWALK, y1 - SIDEWALK
        on_avenue = i in (-1, 0)
        if (i, j) in landmarks:
            lots = [(bx0, bx1, by0, by1)]
        else:
            nx = random.choice([2, 2, 3]); ny = random.choice([2, 3, 3])
            xs = sorted([bx0, bx1] + [random.uniform(bx0 + 5, bx1 - 5) for _ in range(nx - 1)])
            ys = sorted([by0, by1] + [random.uniform(by0 + 5, by1 - 5) for _ in range(ny - 1)])
            lots = [(xs[a], xs[a + 1], ys[b], ys[b + 1]) for a in range(nx) for b in range(ny)]
        for (lx0, lx1, ly0, ly1) in lots:
            gap = 0.8
            lx0 += gap; lx1 -= gap; ly0 += gap; ly1 -= gap
            if lx1 - lx0 < 3 or ly1 - ly0 < 3:
                continue
            cx, cy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
            d = dist_to_center(cx, cy)
            centrality = max(0.15, 1.0 - d / 320.0)
            if (i, j) in landmarks:
                h = random.uniform(190, 280)
            else:
                h = 12 + random.lognormvariate(3.3, 0.55) * centrality * 1.6
                h = min(h, 150)
            sx, sy = lx1 - lx0, ly1 - ly0
            # stacked tiers (setbacks) for taller buildings
            tiers = 1 if h < 50 else (2 if h < 120 else 4)
            z = 0.0
            tier_h = [h * f for f in ([1.0] if tiers == 1 else ([0.6, 0.4] if tiers == 2 else [0.38, 0.27, 0.2, 0.15]))]
            mb = MeshBuilder()
            csx, csy = sx, sy
            for k, th in enumerate(tier_h):
                mb.box((0, 0, z + th / 2), (csx, csy, th))
                # glowing edge band at top of each tier
                if random.random() < (0.9 if (i, j) in landmarks else 0.45):
                    col = random.choice(MAIN_NEON)
                    t = 0.35
                    zz = z + th - 0.6
                    for (ox, oy, ex, ey) in ((0, csy / 2 + 0.05, csx + 0.2, t), (0, -csy / 2 - 0.05, csx + 0.2, t),
                                             (csx / 2 + 0.05, 0, t, csy + 0.2), (-csx / 2 - 0.05, 0, t, csy + 0.2)):
                        neon_mb[col].box((cx + ox, cy + oy, zz), (ex, ey, t))
                z += th
                csx *= random.uniform(0.7, 0.85); csy *= random.uniform(0.7, 0.85)
            ob = mb.build(f"Building_{i}_{j}_{len(buildings)}", [MAT_BLD], C_BLD)
            ob.location = (cx, cy, 0)
            buildings.append(ob)
            # rooftop details
            for _ in range(random.randint(0, 3)):
                rx = cx + random.uniform(-csx / 2, csx / 2); ry = cy + random.uniform(-csy / 2, csy / 2)
                bld_mb_roofs.box((rx, ry, z + 1.5), (random.uniform(1, 4), random.uniform(1, 4), 3))
            if (i, j) in landmarks:   # antenna spire with beacon
                bld_mb_roofs.box((cx, cy, z + 20), (0.8, 0.8, 40))
                neon_mb["pink"].box((cx, cy, z + 40.5), (1.6, 1.6, 1.6))
                # vertical neon strips running up the corners
                col = random.choice(["cyan", "magenta", "purple"])
                for sxs in (-1, 1):
                    for sys_ in (-1, 1):
                        neon_mb[col].box((cx + sxs * (sx / 2 + 0.1), cy + sys_ * (sy / 2 + 0.1), tier_h[0] / 2),
                                         (0.4, 0.4, tier_h[0]))
            facade_targets.append((cx, cy, sx, sy, h, on_avenue, i))

walk.build("Sidewalks", [MAT_WALK], C_GROUND)
bld_mb_roofs.build("RoofDetails", [MAT_ROOF], C_BLD)

# lane markings (cyan glowing dashes) and street lamps along main avenue + cross streets
for y in [y * 6.0 for y in range(-30, 110)]:
    for x in (-4.0, 0.0, 4.0):
        if x == 0.0:
            lanes.box((x, y, 0.01), (0.15, 6.0, 0.02))
        elif int(y / 6) % 2 == 0:
            lanes.box((x, y, 0.01), (0.12, 3.0, 0.02))
for y in [y * 14.0 for y in range(-12, 45)]:
    for side in (-1, 1):
        x = side * (AVE_HALF - 1.0)
        lamp_mb.box((x, y, 3.5), (0.15, 0.15, 7.0))
        lamp_mb.box((x - side * 0.8, y, 7.0), (1.8, 0.25, 0.15))
        neon_soft_mb["orange"].box((x - side * 1.4, y, 6.85), (0.6, 0.3, 0.1))
lanes.build("LaneLines", [MAT_LANE], C_GROUND)
lamp_mb.build("StreetLampPoles", [MAT_ROOF], C_GROUND)

# ---------------------------------------------------------------- neon signs & billboards
TEXTS = ["NEON", "CYBER", "2077", "BAR", "HOTEL", "SYNTH", "NOODLE", "RAMEN", "OPEN", "ZERO", "TECH", "LOVE",
         "DRINK", "GRID", "VOID", "NOVA", "SUSHI", "ARCADE"]

def facade_point(cx, cy, sx, sy, side):
    """Return (position on facade, outward normal, tangent) for facade side 0..3."""
    if side == 0:  return Vector((cx + sx / 2, cy, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), sy
    if side == 1:  return Vector((cx - sx / 2, cy, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), sx and sy
    if side == 2:  return Vector((cx, cy + sy / 2, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)), sx
    return Vector((cx, cy - sy / 2, 0)), Vector((0, -1, 0)), Vector((1, 0, 0)), sx

def add_text(txt, loc, normal, size, mat, vertical=False):
    cu = bpy.data.curves.new("txt_" + txt, "FONT")
    cu.body = txt if not vertical else "\n".join(txt)
    cu.size = size
    cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.extrude = 0.03
    ob = bpy.data.objects.new("Sign_" + txt, cu)
    ob.data.materials.append(mat)
    C_NEON.objects.link(ob)
    ob.location = loc
    # text lies in XY facing +Z; rotate to face along `normal`
    rz = math.atan2(normal.y, normal.x) + math.pi / 2
    ob.rotation_euler = (math.pi / 2, 0, rz)
    return ob

bb_count = 0
for (cx, cy, sx, sy, h, on_avenue, i) in facade_targets:
    sides = [0, 1, 2, 3]
    if on_avenue:
        ave_side = 1 if i == 0 else 0      # facade facing x = 0
        n_signs = random.randint(4, 8)
    else:
        ave_side = None
        n_signs = random.randint(0, 3) if random.random() < 0.7 else 0
    for s in range(n_signs):
        side = ave_side if (ave_side is not None and random.random() < 0.85) else random.choice(sides)
        base, nrm, tan, width = facade_point(cx, cy, sx, sy, side)
        col = random.choice(MAIN_NEON)
        off = random.uniform(-width / 2 + 1, width / 2 - 1) if width > 2.5 else 0
        p = base + tan * off
        kind = random.random()
        if kind < 0.45:
            # vertical blade sign sticking out of the facade
            z0 = random.uniform(4, min(28, max(6, h * 0.5)))
            hh = random.uniform(4, 11)
            c = p + nrm * 0.9
            sz = (0.25 if abs(nrm.x) < 0.5 else 1.6, 1.6 if abs(nrm.x) < 0.5 else 0.25, hh)
            sz = (1.6, 0.25, hh) if abs(nrm.x) > 0.5 else (0.25, 1.6, hh)
            neon_soft_mb[col].box((c.x, c.y, z0 + hh / 2), sz)
            # bright border tubes
            col2 = random.choice(MAIN_NEON)
            for dz in (0, hh):
                neon_mb[col2].box((c.x + nrm.x * 0.15, c.y + nrm.y * 0.15, z0 + dz),
                                  (sz[0] + 0.1, sz[1] + 0.1, 0.12))
            if random.random() < 0.6:
                t = add_text(random.choice(TEXTS)[:6], (c.x + nrm.x * 0.2, c.y + nrm.y * 0.2, z0 + hh / 2),
                             tan if random.random() < 0.5 else -tan, 1.0, NEON_MATS[col2], vertical=True)
                t.rotation_euler.z = math.atan2(nrm.y, nrm.x) + (0 if random.random() < 0.5 else math.pi)  # readable from the street
        elif kind < 0.8:
            # horizontal neon strip / storefront band
            z = random.choice([3.2, 3.4, random.uniform(5, min(40, max(6, h - 2)))])
            L = min(width - 0.5, random.uniform(3, 12))
            c = p + nrm * 0.15
            sz = (0.15, L, 0.18) if abs(nrm.x) > 0.5 else (L, 0.15, 0.18)
            neon_mb[col].box((c.x, c.y, z), sz)
            if z < 4 and random.random() < 0.7:   # glowing shop window under the band
                sz2 = (0.08, L, 2.4) if abs(nrm.x) > 0.5 else (L, 0.08, 2.4)
                neon_soft_mb[random.choice(["orange", "pink", "cyan", "purple"])].box((c.x, c.y, 1.6), sz2)
        else:
            # flat text sign on facade
            z = random.uniform(5, min(35, max(7, h - 3)))
            add_text(random.choice(TEXTS), (p.x + nrm.x * 0.2, p.y + nrm.y * 0.2, z), nrm,
                     random.uniform(1.2, 2.6), NEON_MATS[col])
    # billboards: big emissive screens on taller buildings
    if h > 35 and random.random() < (0.55 if on_avenue else 0.18):
        side = ave_side if ave_side is not None else random.choice(sides)
        base, nrm, tan, width = facade_point(cx, cy, sx, sy, side)
        w = min(width * 0.8, random.uniform(8, 16)); hh = w * random.uniform(0.5, 1.4)
        z = random.uniform(12, max(13, min(h - hh - 2, 70)))
        c = base + nrm * 0.3
        mb = MeshBuilder()
        if abs(nrm.x) > 0.5:
            mb.box((0, 0, 0), (0.2, w, hh))
        else:
            mb.box((0, 0, 0), (w, 0.2, hh))
        mat = random.choice(BILLBOARDS)
        bb = mb.build(f"Billboard_{bb_count}", [mat], C_NEON)
        bb.location = (c.x, c.y, z + hh / 2)
        # neon frame
        fc = random.choice(MAIN_NEON)
        for dz in (-hh / 2, hh / 2):
            sz = (0.3, w + 0.4, 0.25) if abs(nrm.x) > 0.5 else (w + 0.4, 0.3, 0.25)
            neon_mb[fc].box((c.x + nrm.x * 0.1, c.y + nrm.y * 0.1, z + hh / 2 + dz), sz)
        bb_count += 1

# a few big free-standing holographic signs over the avenue
for k, (y, z, txt, col) in enumerate([(-40, 14, "NEO TOKYO", "cyan"), (30, 24, "KABUKI", "magenta"),
                                      (110, 30, "ZAIBATSU", "orange"), (220, 45, "NIGHT CITY", "purple")]):
    t = add_text(txt, (0, y, z), Vector((0, -1, 0)), 3.2, NEON_MATS[col])
    neon_soft_mb[col].box((0, y + 0.3, z), (len(txt) * 2.2, 0.1, 4.5))

for k in NEON:
    if neon_mb[k].v:
        o = neon_mb[k].build("NeonTubes_" + k, [NEON_MATS[k]], C_NEON)
    if neon_soft_mb[k].v:
        o = neon_soft_mb[k].build("NeonPanels_" + k, [NEON_SOFT[k]], C_NEON)

# ---------------------------------------------------------------- flying cars
def flying_car(name, loc, heading_deg, trail=None, scale=1.0, glow="cyan"):
    root = bpy.data.objects.new(name, None)
    C_CARS.objects.link(root)
    root.location = loc
    root.rotation_euler = (math.radians(random.uniform(-3, 3)), math.radians(random.uniform(-4, 4)),
                           math.radians(heading_deg))
    root.scale = (scale,) * 3
    def part(nm, c, s, mat):
        o = box_obj(name + "_" + nm, c, s, mat, C_CARS)
        o.parent = root
        return o
    body = part("Body", (0, 0, 0), (4.8, 2.1, 0.7), MAT_CARBODY)
    bev = body.modifiers.new("bevel", "BEVEL"); bev.width = 0.18; bev.segments = 3
    cab = part("Cabin", (-0.3, 0, 0.55), (2.4, 1.7, 0.55), MAT_GLASS)
    bev = cab.modifiers.new("bevel", "BEVEL"); bev.width = 0.2; bev.segments = 3
    # hover pods
    for sx in (1.6, -1.6):
        for sy in (1.15, -1.15):
            pod = part("Pod", (sx, sy, -0.2), (1.0, 0.5, 0.35), MAT_CARBODY)
            part("Thruster", (sx, sy, -0.39), (0.7, 0.3, 0.05), NEON_MATS[glow])
    part("HeadL", (2.42, 0.7, 0.05), (0.06, 0.45, 0.14), MAT_HEAD)
    part("HeadR", (2.42, -0.7, 0.05), (0.06, 0.45, 0.14), MAT_HEAD)
    part("Tail", (-2.42, 0, 0.1), (0.06, 1.9, 0.12), MAT_TAIL)
    part("Underglow", (0, 0, -0.36), (3.6, 1.2, 0.03), NEON_SOFT[glow])
    if trail:
        L = trail
        for yy in (0.8, -0.8):
            mb = MeshBuilder(); mb.box((-0.5, 0, 0), (1.0, 1.0, 1.0))
            tr = mb.build(name + "_Trail", [MAT_TRAIL_R], C_CARS)
            tr.parent = root
            tr.location = (-2.5, yy, 0.1)
            tr.scale = (L, 0.12, 0.08)
            tr.visible_shadow = False
    # headlight beam (spot light, lights up rain + fog)
    sp = bpy.data.lights.new(name + "_Beam", "SPOT")
    sp.energy = 4000; sp.spot_size = math.radians(30); sp.spot_blend = 0.6
    sp.color = (0.8, 0.9, 1.0)
    so = bpy.data.objects.new(name + "_Beam", sp); C_CARS.objects.link(so)
    so.parent = root; so.location = (2.6, 0, 0)
    so.rotation_euler = (0, math.radians(100), 0)  # point forward (+X) and slightly down
    return root

cars = [
    ((-4, -55, 7.5), 92, 28, 1.0, "cyan"),
    ((3.5, -78, 4.5), 97, 22, 1.0, "magenta"),
    ((5, -20, 12.0), -88, 40, 1.0, "magenta"),
    ((-2, 20, 18.0), 95, 50, 1.0, "purple"),
    ((6, 60, 26.0), -80, 60, 1.0, "cyan"),
    ((-8, 120, 34.0), 90, 70, 1.0, "orange"),
    ((3, 200, 48.0), -95, 0, 1.0, "magenta"),
    ((40, 40, 60.0), 10, 80, 1.0, "cyan"),
    ((-60, 90, 75.0), -30, 90, 1.0, "magenta"),
    ((-120, -20, 45.0), 60, 80, 1.0, "purple"),
    ((90, 160, 95.0), 180, 100, 1.0, "orange"),
    ((-30, 260, 110.0), 0, 0, 1.0, "cyan"),
    ((-150, 120, 85.0), 90, 90, 1.0, "magenta"),
    ((60, -60, 55.0), 135, 70, 1.0, "cyan"),
    ((-90, 200, 130.0), -45, 0, 1.0, "purple"),
]
for n, (loc, hd, tr, sc, gl) in enumerate(cars):
    flying_car(f"HoverCar_{n:02d}", loc, hd, trail=tr if tr else None, scale=sc, glow=gl)

# sky traffic lanes: streams of tiny light dots far away
traffic = {"white": MeshBuilder(), "red": MeshBuilder()}
for lane in range(10):
    z = random.uniform(70, 160)
    ang = random.uniform(0, math.pi)
    ox, oy = random.uniform(-150, 150), random.uniform(0, 350)
    d = Vector((math.cos(ang), math.sin(ang), 0))
    for k in range(40):
        t = random.uniform(-300, 300)
        p = Vector((ox, oy, z)) + d * t
        key = "white" if k % 2 == 0 else "red"
        traffic[key].box(tuple(p), (0.8, 0.8, 0.4))
traffic["white"].build("SkyTraffic_Head", [MAT_HEAD], C_CARS)
traffic["red"].build("SkyTraffic_Tail", [MAT_TAIL], C_CARS)

# ---------------------------------------------------------------- rain (thin emissive-transparent streaks)
m, nt, out = new_mat("Rain")
tr = nt.nodes.new("ShaderNodeBsdfTransparent")
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
em.inputs["Strength"].default_value = 1.2
gl = nt.nodes.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.0
add = nt.nodes.new("ShaderNodeAddShader")
nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(gl.outputs[0], add.inputs[1])
mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs[0].default_value = 0.3
nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(add.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs["Surface"])
MAT_RAIN = m

def rain_volume(name, center, size, count, length, width, wind=(0.08, 0.03)):
    mb = MeshBuilder()
    cx, cy, cz = center; sx, sy, sz = size
    for _ in range(count):
        x = cx + random.uniform(-sx / 2, sx / 2)
        y = cy + random.uniform(-sy / 2, sy / 2)
        z = cz + random.uniform(-sz / 2, sz / 2)
        L = length * random.uniform(0.6, 1.4)
        dx, dy = wind[0] * L, wind[1] * L
        a = random.uniform(0, math.pi)
        w = width * random.uniform(0.6, 1.2)
        ox, oy = math.cos(a) * w / 2, math.sin(a) * w / 2
        # two crossed quads so streaks are visible from any direction
        mb.quad([(x - ox, y - oy, z), (x + ox, y + oy, z), (x + ox + dx, y + oy + dy, z + L), (x - ox + dx, y - oy + dy, z + L)])
        mb.quad([(x + oy, y - ox, z), (x - oy, y + ox, z), (x - oy + dx, y + ox + dy, z + L), (x + oy + dx, y - ox + dy, z + L)])
    ob = mb.build(name, [MAT_RAIN], C_RAIN)
    ob.visible_shadow = False
    ob.visible_diffuse = False
    ob.visible_volume_scatter = False
    return ob

rain_volume("Rain_Street", (0, -60, 11), (26, 90, 22), 9000, 0.6, 0.01)
rain_volume("Rain_Aerial", (-120, -150, 100), (220, 220, 140), 3000, 3.5, 0.05)
rain_volume("Rain_City", (0, 150, 60), (500, 500, 120), 5000, 2.5, 0.03)

# splash ripples in puddles near street camera: tiny bright rings (flat discs)
spl = MeshBuilder()
for _ in range(600):
    x = random.uniform(-11, 11); y = random.uniform(-90, -10)
    r = random.uniform(0.04, 0.12)
    spl.box((x, y, 0.012), (r, r, 0.004))
splash = spl.build("RainSplashes", [MAT_RAIN], C_RAIN)

# ---------------------------------------------------------------- fog / mist volume
m, nt, out = new_mat("CityFog")
N = nt.nodes
geo = N.new("ShaderNodeNewGeometry")
sp = N.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Position"], sp.inputs[0])
falloff = math_node(nt, "MAXIMUM", math_node(nt, "SUBTRACT", None,
                    math_node(nt, "DIVIDE", sp.outputs[2], None, vb=70.0), va=1.0), None, vb=0.0)
dens = math_node(nt, "ADD", math_node(nt, "MULTIPLY", falloff, None, vb=0.022), None, vb=0.0035)
vol = N.new("ShaderNodeVolumePrincipled")
vol.inputs["Color"].default_value = (0.7, 0.72, 0.9, 1)
vol.inputs["Anisotropy"].default_value = 0.35
nt.links.new(dens, vol.inputs["Density"])
nt.links.new(vol.outputs[0], out.inputs["Volume"])
fog = box_obj("Fog_Volume", (0, 150, 110), (900, 1000, 220), m, C_FX)
fog.visible_shadow = False

# searchlights sweeping up through the fog
for (x, y, col, tilt) in [(-60, 140, (0.2, 0.8, 1.0), 12), (80, 230, (1.0, 0.2, 0.7), -15),
                          (-160, 260, (0.6, 0.3, 1.0), 20), (30, 330, (0.2, 0.8, 1.0), -8)]:
    L = bpy.data.lights.new("Searchlight", "SPOT")
    L.energy = 3.0e6; L.spot_size = math.radians(6); L.spot_blend = 0.3; L.color = col
    L.shadow_soft_size = 0.5
    o = bpy.data.objects.new("Searchlight", L); C_FX.objects.link(o)
    o.location = (x, y, 2)
    o.rotation_euler = (math.radians(tilt), math.radians(tilt * 0.6), 0)   # pointing up

# coloured fill lights at street level to tint the fog & wet road
for (y, x, col) in [(-30, -9, (1.0, 0.1, 0.6)), (-5, 9, (0.1, 0.8, 1.0)), (25, -9, (0.6, 0.2, 1.0)),
                    (60, 9, (1.0, 0.4, 0.05)), (100, -9, (0.1, 0.8, 1.0)), (150, 9, (1.0, 0.1, 0.6))]:
    L = bpy.data.lights.new("NeonFill", "AREA")
    L.energy = 4000; L.size = 6; L.color = col
    o = bpy.data.objects.new("NeonFill", L); C_FX.objects.link(o)
    o.location = (x, y, 6)
    o.rotation_euler = (0, math.radians(-90 if x > 0 else 90), 0)

# ---------------------------------------------------------------- world: dark night sky with polluted glow
world = bpy.data.worlds.new("NightSky"); scene.world = world
world.use_nodes = True
wnt = world.node_tree; wnt.nodes.clear()
wout = wnt.nodes.new("ShaderNodeOutputWorld")
bg = wnt.nodes.new("ShaderNodeBackground")
tc = wnt.nodes.new("ShaderNodeTexCoord")
sepw = wnt.nodes.new("ShaderNodeSeparateXYZ"); wnt.links.new(tc.outputs["Generated"], sepw.inputs[0])
ramp = wnt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.06, 0.02, 0.08, 1)
ramp.color_ramp.elements[1].position = 0.35; ramp.color_ramp.elements[1].color = (0.002, 0.002, 0.008, 1)
wnt.links.new(sepw.outputs[2], ramp.inputs[0])
wnt.links.new(ramp.outputs[0], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 1.0
wnt.links.new(bg.outputs[0], wout.inputs["Surface"])

# ---------------------------------------------------------------- cameras
def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

cd = bpy.data.cameras.new("Cam_Street"); cd.lens = 20; cd.sensor_width = 36
cd.dof.use_dof = False
cam_street = bpy.data.objects.new("Cam_Street", cd); scene.collection.objects.link(cam_street)
cam_street.location = (-3.0, -95.0, 2.2)
look_at(cam_street, (1.5, 40.0, 20.0))

ca = bpy.data.cameras.new("Cam_Aerial"); ca.lens = 30; ca.clip_end = 3000
cam_aerial = bpy.data.objects.new("Cam_Aerial", ca); scene.collection.objects.link(cam_aerial)
cam_aerial.location = (-230.0, -230.0, 150.0)
look_at(cam_aerial, (10.0, 130.0, 25.0))
cd.clip_end = 3000
scene.camera = cam_street

# ---------------------------------------------------------------- render settings
scene.render.engine = "CYCLES"
cy = scene.cycles
cy.device = "CPU"
cy.samples = SAMPLES
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.02
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 6; cy.diffuse_bounces = 2; cy.glossy_bounces = 3
cy.transmission_bounces = 2; cy.volume_bounces = 0; cy.transparent_max_bounces = 12
cy.caustics_reflective = False; cy.caustics_refractive = False
cy.blur_glossy = 1.0
cy.sample_clamp_indirect = 10.0
cy.volume_step_rate = 4.0
cy.volume_max_steps = 256
cy.light_sampling_threshold = 0.01
scene.render.resolution_x = 1920; scene.render.resolution_y = 1080
scene.render.resolution_percentage = PCT
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.threads_mode = "AUTO"
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Punchy"
except Exception:
    pass
scene.view_settings.exposure = 0.3

# compositor: bloom / fog glow for neon
scene.use_nodes = True
ct = scene.node_tree; ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers")
glare = ct.nodes.new("CompositorNodeGlare"); glare.glare_type = "FOG_GLOW"
for k, v in (("Threshold", 1.0), ("Strength", 0.6), ("Size", 0.7), ("Saturation", 1.2)):
    if k in glare.inputs:
        glare.inputs[k].default_value = v
glare.quality = "HIGH"
comp = ct.nodes.new("CompositorNodeComposite")
ct.links.new(rl.outputs["Image"], glare.inputs["Image"])
ct.links.new(glare.outputs["Image"], comp.inputs["Image"])

# ---------------------------------------------------------------- save / export / render
blend_path = os.path.join(OUT, "cyberpunk_city.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
print("SAVED", blend_path, "objects:", len(bpy.data.objects))

if EXPORT_GLB:
    glb = os.path.join(OUT, "cyberpunk_city.glb")
    # rain/fog are not meaningful in glTF -> exclude them
    for ob in list(C_RAIN.objects) + list(C_FX.objects):
        ob.hide_set(True) if ob.name in bpy.context.view_layer.objects else None
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_visible=True,
                              export_apply=True, export_lights=False, export_cameras=True)
    for ob in list(C_RAIN.objects) + list(C_FX.objects):
        ob.hide_set(False)
    print("EXPORTED", glb)

def do_render(cam, fname):
    scene.camera = cam
    scene.render.filepath = os.path.join(OUT, fname)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {fname} in {time.time() - t0:.1f}s")

if RENDER in ("street", "both"):
    do_render(cam_street, arg("--name_street", "render_street.png"))
if RENDER in ("aerial", "both"):
    do_render(cam_aerial, arg("--name_aerial", "render_aerial.png"))
