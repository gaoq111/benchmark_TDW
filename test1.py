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
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port {port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process

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
    

    def make_objects(c, object, position, size, special_lib):
        '''if custom_position is None:
            x, y, z = get_position(object_position)
        else:
            x, y, z = custom_position'''
        for i in range(len(object)):

            object_id = c.get_unique_id()
            x, y, z = position[i]

            if object[0] in special_lib:
                    lib = "models_special.json"
            else:
                    lib = "models_core.json"

            # get the object
            model_record = ModelLibrarian(lib).get_record(object[i])
            print(object[i], position[i], size[i], lib)
            commands.extend(c.get_add_physics_object(model_name=object[i],
                                                    library=lib,
                                                        position={"x": x,  "y": y, "z": z},
                                                        rotation={"x": 0, "y": 0, "z": 0},
                                                        scale_factor={"x": size[i], "y": size[i], "z": size[i]},
                                                        object_id=object_id))
            color = np.random.uniform(0, 1, 3)
            commands.append({"$type": "set_color",
                        "color": {"r": color[0], "g": color[1], "b": color[2], "a": 1.0},
                        "id": object_id})
    
    position = args.custom_position if args.custom_position is not None else get_position(args.object_position) if type(args.object_position) != list else [get_position(pos) for pos in args.object_position]
    if (type(args.object) != list) & (type(args.size) != list) & (type(position)[0] != list):
        make_objects(c, [args.object], [position], [args.size], special_lib)
    elif (type(args.object) == list) & (type(args.size) == list) & (type(position[0]) == list) and (len(args.object) == len(position) == len(args.size)):
        make_objects(c, args.object, position, args.size, special_lib)
    else: 
        print(type(args.object), type(args.size), position)
        print((type(args.object) == list) & (type(args.size) == list) & (type(position) == list))
        print((len(args.object) == len(position) == len(args.size)))
        print('invent a good error warning later')


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
    parser.add_argument("--custom_position", type=int, nargs='+', default=None, help="Set the objects inital (x,y,z) coordinates.")
    parser.add_argument("--size", type=float, nargs='+', default=1, help="Scale of the object")
    # Action
    #parser.add_argument("--action", type=str, default="circle_1", help="Format: [trajectory]_[radius]")
    # Enable Physics
    # parser.add_argument("--physics", type=bool, default=False, help="Enable Physics.")
    # Task Name
    parser.add_argument("--name", type=str, default="test", help="The name of the task.")
    # Material
    #parser.add_argument("--material", type=str, default=None, help="The material of the object.")
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