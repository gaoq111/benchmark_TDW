from utils import *
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.backend.paths import EXAMPLE_CONTROLLER_OUTPUT_PATH
from tdw.librarian import ModelLibrarian

import argparse
import os
import subprocess
import psutil
import time
import numpy as np
import json

import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

base_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_PATH = os.path.join(base_dir, "images")

# Initiate a tdw server:
# DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port 1071
# The server might exit when there are errors in executing the commands 
# "y" is the vertical axis in the setting

def start_tdw_server(display=":4", port=1071):
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process

# Color:
def colourToRGBA(colour):
    mapping = {
        "blue": dict(r=0, g=0, b=1, a=1),
        "green": dict(r=0, g=1, b=0, a=1),
        "red": dict(r=1, g=0, b=0, a=1),
        "yellow": dict(r=1, g=1, b=0, a=1),
        "cyan": dict(r=0, g=1, b=1, a=1),
        "purple": dict(r=1, g=0, b=1, a=1),
        "white": dict(r=1, g=1, b=1, a=1),
    }
    return mapping[colour]

# Shape:
shape_dict = {
    "sphere": "prim_sphere",
    "cube": "prim_cube",
    "cylinder": "prim_cyl",
    "cone": "prim_cone",
}

def get_cameras(camera_id):
    camera_views = {"top": {"x": 0, "z": 0, "y": 2.5},
                    "left": {"x": -2.5, "z": 0, "y": 0.2},
                    "right": {"x": 2.5, "z": 0, "y": 0.2},
                    "front": {"x": 0, "z": -2.5, "y": 0.2},
                    "back": {"x": 0, "z": 2.5, "y": 0.2},}
    return ThirdPersonCamera(position=camera_views[camera_id],
                                avatar_id=camera_id,
                                look_at={"x": 0, "z": 0, "y": 0,})

def get_position(pos_name):
    positions = {'center': [0,0,0],
                    'top':[0,0,1],
                    'right':[1,0,0],
                    'bottom':[0,0,-1],
                    'left':[-1,0,0],}
    return positions[pos_name]           

# Metadata         
metadata_path = "./metadata.json"
metadata_list = []

def main(args):

    print(f"Launching TDW server on port {args.port}, display {args.display}")
    start_tdw_server(args.display, args.port)

    c = None
    try:
        c = Controller(port=args.port, launch_build=False)
    except Exception as e:
        raise e

    print(f"Images will be saved to: {os.path.join(args.output_path, args.name)}")

    for camera_id in args.cameras:
        print(f"Camera: {camera_id}")
        camera_id = camera_id.lower()
        camera = get_cameras(camera_id)
        c.add_ons.append(camera)
    capture = ImageCapture(avatar_ids=args.cameras, path=os.path.join(args.output_path, args.name), png=True)
    c.add_ons.append(capture)

    # General rendering configurations
    commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]}, 
                {"$type": "set_render_quality", "render_quality": args.render_quality},
                ]
    
    if args.scene is None:
        commands.append(c.get_add_scene("empty_scene"))
    else:
        commands.append(c.get_add_scene(args.scene))

    # select the library
    librarian = ModelLibrarian("models_special.json")
    special_lib = []
    for record in librarian.records:
        special_lib.append(record.name)
    
    # Material library
    #mat = args.material if type(args.material) == list else [args.material]

    #for m in mat:
    #    if m != None:
    #        commands.extend([c.get_add_material(m, library = "materials_high.json")])
    
    # main loop to make objects
    def make_objects(c, object, position, size, special_lib, color):
        '''if custom_position is None:
            x, y, z = get_position(object_position)
        else:
            x, y, z = custom_position'''
        for i in range(len(object)):
            object_id = c.get_unique_id()
            x, y, z = position[i]

            o = shape_dict[object[i]] if object[i] in shape_dict.keys() else object[i]

            if o in special_lib:
                    lib = "models_special.json"
            else:
                    lib = "models_core.json"
            
            #print({"x": size[i], "y": size[i], "z": size[i]})

            # get the object
            model_record = ModelLibrarian(lib).get_record(o)
            #print(object[i], position[i], size[i], lib)
            commands.extend(c.get_add_physics_object(model_name=o,
                                                    library=lib,
                                                        position={"x": x,  "y": y, "z": z},
                                                        rotation={"x": 0, "y": 0, "z": 0},
                                                        scale_factor={"x": size[i], "y": size[i], "z": size[i]},
                                                        object_id=object_id))
            #print(material[i])
            #if material[i] != None:
            #    commands.extend(TDWUtils.set_visual_material(c=c, 
            #                                    substructure=record.substructure,
            #                                    material= material[i], 
            #                                    object_id=object_id))
            #    commands.extend([{"$type": "set_visual_material",
            #                                            "material_index": 0,
            #                                            "material_name": material[i],
            #                                            "id": object_id}])
            
            commands.append({"$type": "set_color",
                        "color": colourToRGBA(color[i]),
                        "id": object_id})

    if args.custom_position != None:
        position = [[float(i) for i in j[1:len(j) - 1].split(",")] for j in args.custom_position] if ((type(args.custom_position) == list) and (len(args.custom_position) > 1)) else [[float(i) for i in args.custom_position[0][1:len(args.custom_position[0]) - 1].split(",")]] 
    else:
        position = [get_position(args.object_position)] if type(args.object_position) != list else [get_position(pos) for pos in args.object_position]
    #print(position, args.custom_position)

    #print(len(position))

    # if there is only one object + its attributes
    if ((type(args.object) != list) or (len(args.object) == 1)) & ((type(args.size) != list) or (len(args.size) == 1)) & (len(position) == 1):
        # convert all attributes to list so they can be looped
        obj = args.object if type(args.object) == list else [args.object]
        size = args.size if type(args.size) == list else [args.size]
        color = args.color if type(args.color) == list else [args.color]
        #material = args.material if type(args.material) == list else [args.material]
        make_objects(c, obj, position, size, special_lib, color)
    # multiple objects + their attributes
    elif (type(args.object) == list) & (type(args.size) == list) and (len(args.object) == len(position) == len(args.size)):
        # if there is only one color, all objects are the same color
        color = args.color if type(args.color) == list else len(object) * [args.color]
        #material = args.material if type(args.material) == list else len(object) * [args.material]
        make_objects(c, args.object, position, args.size, special_lib, color)
    # if there is a difference in the # of objects and # of attributes
    else:     
        print('Make sure that size, object, material, and object_position/custom_position are the same length')
    
    metadata = {
                                "source": [f"{os.path.join(args.output_path, args.name)}"],
                                "sizes": args.size,
                                "background": args.scene,
                                "colors": args.color,
                                "obj_names": args.object,
                                "positions" : position
    }

    metadata_list.append(metadata)  

    
    # write metadata to json
    with open(metadata_path, 'w') as json_file:
        json.dump(metadata_list, json_file, indent=4)

    c.communicate(commands)

    c.communicate({"$type": "terminate"})

#pipeline(1071, ":4", DEFAULT_OUTPUT_PATH, "image_capture", ['top', 'left', 'right', 'front', 'back'], (512, 512), 5, None, 'prim_sphere', 'center', None, 1)
#pipeline(1071, ":4", DEFAULT_OUTPUT_PATH, "relative_positions", ['top', 'left', 'right', 'front', 'back'], (512, 512), 5, None, ['prim_sphere', 'prim_sphere'], ['right', 'left'], None, [1, 2])

# DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port 1071
# python tryout_kevin.py --output "/data/shared/sim/benchmark/tdw/image_capture/trajectory_demo" --cameras top --scene empty_scene --name circle --action circle_1
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1071, help="Port to connect to.")
    parser.add_argument("--display", type=str, default=":4", help="Display to use.")
    # Screen size
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    # Cameras
    parser.add_argument("--cameras", type=str, nargs='+', default=['top', 'front', 'back'], choices=['top', 'left', 'right', 'front', 'back'], help="Set which cameras to enable.")
    # Output Path
    parser.add_argument("--output_path", type=str, required=False, default=DEFAULT_OUTPUT_PATH, help="The path to save the outputs to.")
    # Render Quality
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")
    # Scene
    parser.add_argument("--scene", type=str, default=None, help="The Scene to initialize.")
    # Object
    parser.add_argument("--object", type=str, nargs='+', default="prim_sphere")
    parser.add_argument("--object_position", type=str, nargs='+', default="center", choices=['center', 'top', 'right', 'bottom', 'left'], help="Set the objects inital position.")
    parser.add_argument("--custom_position", type=str, nargs='+', default=None, help="Set the objects inital (x,y,z) coordinates.")
    parser.add_argument("--size", type=float, nargs='+', default=1, help="Scale of the object")
    # Color
    parser.add_argument("--color", type=str, nargs='+', default='red', help="Color of the object")
    # Action
    #parser.add_argument("--action", type=str, default="circle_1", help="Format: [trajectory]_[radius]")
    # Enable Physics
    # parser.add_argument("--physics", type=bool, default=False, help="Enable Physics.")
    # Task Name
    parser.add_argument("--name", type=str, default="test", help="The name of the task.")
    # Material
    #parser.add_argument("--material", type=str, nargs='+', default=None, help="The material of the object.")
    # Texture Scale
    #parser.add_argument("--texture_scale", type=float, default=None, help="The scale of the texture.")
    
    """
    NOTE About Texture Scale:
    It is possible to scale the textures of a material to make them appear larger or smaller with the 
    [`set_texture_scale` command](https://github.com/threedworld-mit/tdw/blob/e28687dac79ef7a2aa25cc41569154b550e3fb84/Documentation/api/command_api.md#set_texture_scale). 
    By default, texture scales are always (1, 1) but this doesn't necessarily indicate an "actual" size in real-world units. Larger values mean that the texture will be _smaller_ and repeat more often:
    """

    args = parser.parse_args()

    main(args)