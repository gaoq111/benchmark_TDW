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
         

def pipeline(port, display, output_path, name, cameras, screen_size, render_quality, scene, object, object_position, custom_position, size):
    print(f"Launching TDW server on port {port}, display {display}")
    start_tdw_server(display, port)

    c = None
    try:
        c = Controller(port=port, launch_build=False)
    except Exception as e:
        raise e

    print(f"Images will be saved to: {os.path.join(output_path, name)}")

    for camera_id in cameras:
        print(f"Camera: {camera_id}")
        camera_id = camera_id.lower()
        camera = get_cameras(camera_id)
        c.add_ons.append(camera)
    capture = ImageCapture(avatar_ids=cameras, path=os.path.join(output_path, name), png=True)
    c.add_ons.append(capture)

    # General rendering configurations
    commands = [{"$type": "set_screen_size", "width": screen_size[0], "height": screen_size[1]}, 
                {"$type": "set_render_quality", "render_quality": render_quality},
                ]
    
    if scene is None:
        commands.append(c.get_add_scene("empty_scene"))
    else:
        commands.append(c.get_add_scene(scene))

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
    
    position = custom_position if custom_position is not None else get_position(object_position) if type(object_position) != list else [get_position(pos) for pos in object_position]
    if (type(object) != list) & (type(size) != list) & (type(position)[0] != list):
        make_objects(c, [object], [position], [size], special_lib)
    elif (type(object) == list) & (type(size) == list) & (type(position[0]) == list) and (len(object) == len(position) == len(size)):
        make_objects(c, object, position, size, special_lib)
    else: 
        print(type(object), type(size), position)
        print((type(object) == list) & (type(size) == list) & (type(position) == list))
        print((len(object) == len(position) == len(size)))
        print('invent a good error warning later')


    c.communicate(commands)

    c.communicate({"$type": "terminate"})

#pipeline(1071, ":4", DEFAULT_OUTPUT_PATH, "image_capture", ['top', 'left', 'right', 'front', 'back'], (512, 512), 5, None, 'prim_sphere', 'center', None, 1)
pipeline(1071, ":4", DEFAULT_OUTPUT_PATH, "relative_positions", ['top', 'left', 'right', 'front', 'back'], (512, 512), 5, None, ['prim_sphere', 'prim_sphere'], ['right', 'left'], None, [1, 2])