from utils import *
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.backend.paths import EXAMPLE_CONTROLLER_OUTPUT_PATH
from tdw.librarian import ModelLibrarian

from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.output_data import OutputData, FieldOfView
from tdw.add_ons.third_person_camera import ThirdPersonCamera

import argparse
import os
import time
import yaml
import subprocess

# Initiate a tdw server:
# The server might exit when there are errors in executing the commands 
# "y" is the vertical axis in the setting

#Todo:
# 1. Better image write_out method, in tdw_physics, they write images to hfd5 files
# 2. Multiprocess tdw servers

#[Optional]: using python subprocess to initiate the server on-the-fly with a customized port


# function should change camera location based on scene, especially "archivz_house"
def get_cameras(camera_id, camera_config):
    return ThirdPersonCamera(position=camera_config[camera_id],
                            avatar_id=camera_id,
                            look_at=camera_config['look_at'],)

def get_position(pos_name, object_config):
    return object_config[pos_name]                    

def get_action_coordinates(action, center):
    if action is None:
        return None
    else:
        traj, num = action.split("_")
        if traj == 'circle':
            radius = float(num)
            return generate_circle_coords(num_points=30, radius=radius, center=center)
        if traj == 'square':
            side_length = float(num)
            return generate_square_coords(num_points=30, side_length=side_length)
        if traj == 'triangle':
            side_length = float(num)
            return generate_triangle_coords(num_points=30, side_length=side_length)

def start_tdw_server(display=":4", port=1071):
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process
        

def main(args):
    server_process = start_tdw_server(display=":4", port=1072)

    try:
        # Launch TDW Build
        c = Controller(port=1072, launch_build=False)

        start_time = time.time()
        output_path = args.output_path  #EXAMPLE_CONTROLLER_OUTPUT_PATH.joinpath("image_capture")
        task_name = args.name
        print(f"Images will be saved to: {os.path.join(output_path, task_name)}")

        # read the camera and object configs
        with open('scene_settings.yaml', 'r') as file:
            congfig = yaml.safe_load(file)
        camera_config = congfig[args.scene]['camera']
        object_config = congfig[args.scene]['object']

        # Camera specifying
        for camera_id in args.cameras:
            camera_id = camera_id.lower()
            camera = get_cameras(camera_id, camera_config)
            c.add_ons.append(camera)
        capture = ImageCapture(avatar_ids=args.cameras, path=os.path.join(output_path, task_name), png=True)
        c.add_ons.append(capture)

        object_id = c.get_unique_id()

        # General rendering configurations
        commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]}, 
                    {"$type": "set_render_quality", "render_quality": args.render_quality},
                    ]
        
        #Initialize background
        commands.append(c.get_add_scene(args.scene))

        # get location
        if args.custom_position is None:
            x, y, z = get_position(args.object_position, object_config)
        else:
            x, y, z = args.custom_position
        # x, y, z = get_position(args.object_position, object_config)
        center = get_position('center', object_config)
        center = [center[0], center[2]]
        
        # select the library
        librarian = ModelLibrarian("models_special.json")
        special_lib = []
        for record in librarian.records:
            special_lib.append(record.name)
        if args.object in special_lib:
            lib = "models_special.json"
        else:
            lib = "models_core.json"

        # get the object
        model_record = ModelLibrarian(lib).get_record(args.object)
        commands.extend(c.get_add_physics_object(model_name=args.object,
                                                library=lib,
                                                position={"x": x,  "y": y, "z": z},
                                                scale_factor={"x": args.size, "y": args.size, "z": args.size},
                                                gravity=False,
                                                default_physics_values=False,
                                                object_id=object_id))

        # set color
        if args.color is not None:
            r, g, b = args.color
            commands.append({"$type": "set_color", "color": {"r": r, "g": g, "b": b, "a": 1.0}, "id": object_id})
        c.communicate(commands)

        # Change material of object if provided
        if args.material is not None:
            commands = [c.get_add_material(material_name=args.material)]
            # Set all of the object's visual materials.
            commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=args.material, object_id=object_id))
        c.communicate(commands)

        # Get coordinates for motion trajectory
        coordinates = get_action_coordinates(args.action, center)
        if coordinates is not None:
            for (x_d, z_d) in coordinates:
                commands= [{"$type": "teleport_object", 
                                "position": {"x": x_d, "z": z_d, "y": y}, 
                                "id": object_id, "physics": False, "absolute": True, "use_centroid": False}]
                c.communicate(commands)
        
        end_time = time.time()

        # Calculate elapsed time
        elapsed_time = end_time - start_time
        print(f"Completed. Total time: {elapsed_time:.4f} seconds")
        
    finally:
        # Terminate the server after the job is done
        c.communicate({"$type": "terminate"})
        server_process.terminate()
        server_process.wait()

# DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port=1071
# python trajectory.py --output "/data/shared/sim/benchmark/tdw/image_capture/test" --cameras top --name test2 --action circle_1 --size 0.3
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Screen size
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    # Cameras
    parser.add_argument("--cameras", type=str, nargs='+', default=['top'], choices=['top', 'left', 'right', 'front', 'back'], help="Set which cameras to enable.")
    # Output Path
    parser.add_argument("--output_path", type=str, required=True, help="The path to save the outputs to.")
    # Render Quality
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")
    # Scene
    parser.add_argument("--scene", type=str, default="empty_scene", help="The Scene to initialize.")
    # Object
    parser.add_argument("--object", type=str, default="prim_sphere")
    parser.add_argument("--object_position", type=str, default="center", choices=['center', 'top', 'right', 'bottom', 'left'], help="Set the objects inital position.")
    parser.add_argument("--custom_position", type=float, nargs='+', default=None, help="Set the objects inital (x,y,z) coordinates.")
    parser.add_argument("--size", type=float, default=0.25, help="Scale of the object")
    parser.add_argument("--color", type=float, nargs='+', default=None, help="Color of the object (RGB)")
    # Action
    parser.add_argument("--action", type=str, default=None, help="Format: [trajectory]_[radius]")
    # Task Name
    parser.add_argument("--name", type=str, default="test", help="The name of the task.")
    # Material
    parser.add_argument("--material", type=str, default=None, help="The material of the object.")

    args = parser.parse_args()

    main(args)