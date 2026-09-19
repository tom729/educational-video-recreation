"""Build a reusable 3D asset plate, not a finished educational video.

Run with Blender in background mode. No third-party add-ons or network required.
"""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--resolution-percent", type=int, default=100)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--render-samples", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.frames < 2 or args.fps < 1 or args.samples < 1:
        parser.error("frames >= 2, fps >= 1 and samples >= 1 are required")
    if not 1 <= args.resolution_percent <= 100:
        parser.error("resolution-percent must be between 1 and 100")
    return args


def material(name, color, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = 0.3
    return mat


def finish_part(obj, mat):
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("Readable edges", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 3
    return obj


def sleeve(name, outer, inner, height, z, mat, segments=64):
    """Closed annular mesh with an actual through-hole, not a textured solid."""
    vertices = []
    for radius, level in ((outer, -height / 2), (outer, height / 2),
                          (inner, -height / 2), (inner, height / 2)):
        vertices.extend((radius * math.cos(2 * math.pi * i / segments),
                         radius * math.sin(2 * math.pi * i / segments), level)
                        for i in range(segments))
    faces = []
    n = segments
    for i in range(n):
        j = (i + 1) % n
        faces.extend(((i, j, n + j, n + i),
                      (2 * n + j, 2 * n + i, 3 * n + i, 3 * n + j),
                      (n + i, n + j, 3 * n + j, 3 * n + i),
                      (j, i, 2 * n + i, 2 * n + j)))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = polygon.index % 4 < 2
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location.z = z
    return finish_part(obj, mat)


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_light(name, location, energy, size):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = energy
    light.shape = "DISK"
    light.size = size
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, (0, 0, 0.5))


def check_geometry(scene, parts):
    limits = [1.0, 0.0, 1.0, 0.0]
    failures = []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in parts:
            evaluated = obj.evaluated_get(depsgraph)
            points = [world_to_camera_view(scene, scene.camera,
                      evaluated.matrix_world @ Vector(corner)) for corner in evaluated.bound_box]
            for p in points:
                limits = [min(limits[0], p.x), max(limits[1], p.x),
                          min(limits[2], p.y), max(limits[3], p.y)]
            if any(not (0.1 <= p.x <= 0.9 and 0.1 <= p.y <= 0.8
                        and scene.camera.data.clip_start < p.z < scene.camera.data.clip_end)
                   for p in points):
                failures.append({"frame": frame, "object": obj.name})
    if failures:
        raise RuntimeError("Geometry exceeds camera/safe frame: " + json.dumps(failures[:10]))
    return {"all_frames_checked": scene.frame_end, "normalized_bounds": limits,
            "safe_bounds": [0.1, 0.9, 0.1, 0.8],
            "scope": "Evaluated geometry bounds only; excludes compositing, glow and text."}


def main():
    args = parse_args()
    if not bpy.app.background:
        raise RuntimeError("Run in a separate Blender --background process to protect open scenes.")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.seed = 0
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = args.resolution_percent
    scene.render.fps = args.fps
    scene.render.fps_base = 1.0
    scene.frame_start, scene.frame_end = 1, args.frames
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("StudioWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.15, 0.2, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    shell = sleeve("Housing", 0.7, 0.48, 1.4, 0, material("Blue shell", (0.035, 0.24, 0.38), 0.5))
    cap = sleeve("EndRing", 0.73, 0.32, 0.18, 0.79, material("Orange ring", (0.8, 0.25, 0.045), 0.3))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.23, depth=2.0, location=(0, 0, 0.1))
    shaft = bpy.context.object
    shaft.name = "Shaft"
    finish_part(shaft, material("Steel", (0.5, 0.58, 0.64), 0.8))

    # One key per frame makes evaluated integer frames independent of interpolation defaults.
    for frame in range(1, args.frames + 1):
        u = (frame - 1) / (args.frames - 1)
        u = min(1.0, max(0.0, (u - 0.15) / 0.7))
        eased = u * u * (3.0 - 2.0 * u)
        cap.location.z = 0.79 + 0.9 * eased
        shaft.location.z = 0.1 + 0.35 * eased
        for part in (cap, shaft):
            part.keyframe_insert(data_path="location", frame=frame)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (5, -8, 5)
    aim(camera, (0, 0, 0.7))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.5
    camera_data.clip_start, camera_data.clip_end = 0.01, 100
    scene.camera = camera
    add_light("Key", (3, -4, 6), 900, 4)
    add_light("Fill", (-3, -1, 3), 600, 3)
    add_light("Rim", (1, 4, 4), 1100, 3)

    geometry = check_geometry(scene, (shell, cap, shaft))
    scene.frame_set(1)
    (output / "frames").mkdir()
    scene.render.filepath = "//frames/frame_"
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))
    rendered = []
    if args.render_samples:
        for frame in sorted({1, (args.frames + 1) // 2, args.frames}):
            scene.frame_set(frame)
            path = output / f"sample_{frame:04d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            rendered.append(path.name)
    report = {"blender_version": bpy.app.version_string, "engine": "CYCLES", "device": "CPU",
              "fps": args.fps, "frames": args.frames, "duration_seconds": args.frames / args.fps,
              "resolution": [1080, 1920], "resolution_percent": args.resolution_percent,
              "rendered_samples": rendered, "geometry_check": geometry,
              "purpose": "Generic asset plate; not a factual product model or finished video."}
    (output / "scene-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
