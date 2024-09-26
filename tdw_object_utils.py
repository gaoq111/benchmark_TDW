import os
import sys

import yaml
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import List
from interface import ObjectType, AVAILABLE_CAMERA_POS

from tdw.add_ons.image_capture import ImageCapture
from tdw.add_ons.third_person_camera import ThirdPersonCamera

import numpy as np

SELECTED_SCENES = ["box_room_2018", "empty_scene", "monkey_physics_room", "ruin", "suburb_scene_2018"]
SELECTED_MATERIALS = ["concrete_raw_damaged", "iron_rusty", "plastic_base", "wood_american_chestnut"] #"leather_bull",
SELECTED_OBJECTS = [
    "prim_cone",
    "prim_sphere",
    "prim_cube",
    "prim_cyl",
]
SELECTED_SIZES = [0.1, 0.2, 0.4]
SELECTED_TEXTURES = [0.1, 0.5, 1.0]
SELECTED_COLORS = {
    "red": {
        "r": 1, "g": 0, "b": 0, "a": 1
    },
    "green": {
        "r": 0, "g": 1, "b": 0, "a": 1
    },
    "blue": {
        "r": 0, "g": 0, "b": 1, "a": 1
    },
    "yellow": {
        "r": 1, "g": 1, "b": 0, "a": 1
    },
    "purple": {
        "r": 1, "g": 0, "b": 1, "a": 1
    },
    "orange": {
        "r": 1, "g": 0.5, "b": 0, "a": 1
    },
    "brown": {
        "r": 0.5, "g": 0.25, "b": 0, "a": 1
    },
    "gray": {
        "r": 0.5, "g": 0.5, "b": 0.5, "a": 1
    },
    "black": {
        "r": 0, "g": 0, "b": 0, "a": 1
    },
    "white": {
        "r": 1, "g": 1, "b": 1, "a": 1
    },
    "transparent": {
        "r": 1, "g": 1, "b": 1, "a": 0.5
    },
}

def array_to_transform(array):
    return {"x": array[0], "y": array[1], "z": array[2]}

def numpy_to_python(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [numpy_to_python(item) for item in obj]
    else:
        return obj


def get_cameras(camera_position: str, scene: str):
    # read the camera and object configs
    with open('/data/shared/sim/benchmark/benchmark_TDW/scene_settings.yaml', 'r') as file:
        config = yaml.safe_load(file)[scene]['camera']
    return ThirdPersonCamera(position=config[camera_position],
                                avatar_id=camera_position,
                                look_at=config["look_at"])


def get_camera_views(motion, camera_view: List[str]):
    """
    We need to filter the camera view based on the motion of the object,
    for example, if the object is moving forward, we need to filter the camera view to exclude the front and back view, since the object's motion is in the same direction
    """
    
    if motion == "forward":
        return list(filter(lambda x: x != "front" and x != "back", camera_view))
    elif motion == "backward":
        return list(filter(lambda x: x != "front" and x != "back", camera_view))
    elif motion == "left":
        return list(filter(lambda x: x != "right" and x != "left", camera_view))
    elif motion == "right":
        return list(filter(lambda x: x != "left" and x != "right", camera_view))
    else:
        return camera_view

def add_cameras(c, camera_ids, output_pth, scene):
    for cam in camera_ids:
        c.add_ons.append(get_cameras(cam, scene))
    capture = ImageCapture(avatar_ids=camera_ids, path=output_pth, png=True)
    c.add_ons.append(capture)

def format_dict_to_string(d:dict):
    res = ""
    for key, value in d.items():
        res += f"{key}={value},"
    return res

def get_object_id(object_type:ObjectType):
    TEMPLATE = "{model_name}_pos={position}_rot={rotation}_scale={scale_factor}_texture_scale={texture_scale}_material={material}_color={color}"
    res = TEMPLATE.format(model_name=object_type.model_name,
                          position=format_dict_to_string(object_type.position),
                          rotation=format_dict_to_string(object_type.rotation),
                          scale_factor=format_dict_to_string(object_type.scale_factor),
                          texture_scale=object_type.texture_scale,
                          material=object_type.material,
                          color=format_dict_to_string(object_type.color))
    return res

def get_object_shape_id(object_type:ObjectType):
    TEMPLATE = "{model_name}_texture_scale={texture_scale}_material={material}_color={color}"
    res = TEMPLATE.format(model_name=object_type.model_name,
                          texture_scale=object_type.texture_scale,
                          material=object_type.material,
                          color=format_dict_to_string(object_type.color))
    return res

def get_scene(scene_name):
    if scene_name not in SELECTED_SCENES:
        raise ValueError(f"Scene {scene_name} not found in AVAILABLE_SCENES")
    return scene_name

def get_position(scene: str, x_range: tuple, y_range: tuple, z_range: tuple):
    with open('/data/shared/sim/benchmark/benchmark_TDW/scene_settings.yaml', 'r') as file:
        config = yaml.safe_load(file)[scene]['object']['center']
    x, y, z = config
    position={"x": x + np.random.uniform(x_range[0], x_range[1]), "y": y +np.random.uniform(y_range[0], y_range[1]), "z": z + np.random.uniform(z_range[0], z_range[1])}
    return position

def get_position_with_offset(scene: str, x_range: tuple, y_range: tuple, z_range: tuple, offset):
    with open('/data/shared/sim/benchmark/benchmark_TDW/scene_settings.yaml', 'r') as file:
        config = yaml.safe_load(file)[scene]['object']['center']
    x, y, z = config
    position={"x": x + np.random.uniform(x_range[0], x_range[1]) + offset, "y": y +np.random.uniform(y_range[0], y_range[1]), "z": z + np.random.uniform(z_range[0], z_range[1]) + offset}
    return position
