from utils import generate_square_coords, generate_circle_coords, generate_triangle_coords
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

from tqdm import tqdm
from consts import COLORS

import argparse
import os
import time
import yaml
import subprocess
import random
import json
import copy

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

def generate_objects(object_list, n=1):
    object_names = random.choices(object_list, k=n)
    return object_names

def generate_colors(colors, n=6):
    """
    Select the number of colors from a given dictionary.

    :param colors: The colors dictionary.
    :param n: The number of colors to select.
    :return: A list of tuples: [ ('Color1', (r1, g1, b1)),  ('Color2', (r2, g2, b2)), ...]
    """
    processed_colors = []
    selected_colors = random.sample(list(colors.items()), n)
    for color in selected_colors:
        color_name, color_value = color
        color_new_value = tuple(value / 255 for value in color_value)
        processed_colors.append((color_name, color_new_value))
    return processed_colors                  

def get_action_coordinates(action, radius, center):
    if action is None:
        return None
    else:
        if action == 'circle':
            radius = float(radius)
            return generate_circle_coords(num_points=30, radius=radius, center=center)
        if action == 'square':
            side_length = float(radius)
            return generate_square_coords(num_points=30, side_length=side_length, center=center)
        if action == 'triangle':
            side_length = float(radius)
            return generate_triangle_coords(num_points=30, side_length=side_length, center=center)

def start_tdw_server(display=":4", port=1072):
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process
        

def main(args):
    server_process = start_tdw_server(display=":4", port=1073)

    try:
        # Launch TDW Build
        c = Controller(port=1073, launch_build=False)

        output_path = args.output_path
        os.makedirs(output_path, exist_ok=True) 

        # read the camera and object configs
        with open('scene_settings.yaml', 'r') as file:
            congfig = yaml.safe_load(file)

        # Define scenes
        scenes = ["empty_scene", "monkey_physics_room", "box_room_2018", "archviz_house", "ruin", "suburb_scene_2018"]

        # Define materials
        object_materials = ["limestone_white", "glass_chopped_strands", "sand_covered_stone_ground"]

        # Define objects
        object_list = ['prim_cube', 'prim_sphere']
        
        # Define Trajectories
        trajactories = ['circle', 'triangle', 'square']

        # Define Trajectory Radius
        radius = [0.3, 0.6, 1, 1.2]

        # Define Library
        lib = "models_special.json"

        # Define Camera
        cameras = ['top']

        # Define Size
        size = 0.25

        # Initialize image info
        images_info = []

        # Number of data per scene
        num_data = 10

        count = 0

        for scene in tqdm(scenes, desc="Processing scenes"):
            for camera_id in tqdm(cameras, leave=False):
                for material in tqdm(object_materials, leave=False):
                    for traj in tqdm(trajactories, leave=False):
                        for traj_radius in tqdm(radius, leave=False):
                            for _ in tqdm(range(num_data), leave=False):
                                image_info = {}
                                output_path = args.output_path

                                # Camera and vision boundary setting
                                camera_config = congfig[scene]['camera']
                                object_config = congfig[scene]['object']
                                # General rendering configurations
                                commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]},
                                            {"$type": "set_render_quality", "render_quality": args.render_quality}]

                                # Initialize scene
                                commands.append(c.get_add_scene(scene))

                                # generate n objects, and colors
                                n = 1
                                initial_pos = get_position('right', object_config)
                                object_center = get_position('center', object_config)
                                object_center = [object_center[0], object_center[2]] # x-z plane
                                objects = generate_objects(object_list, n=n)
                                colors = generate_colors(COLORS, n=n)

                                # get the object and set location
                                model_records = []
                                object_ids = []
            
                                object_id = c.get_unique_id()
                                object_ids.append(object_id)
                                model_record = ModelLibrarian(lib).get_record(objects[0])
                                model_records.append(model_record)

                                x, y, z = initial_pos
                                commands.extend(c.get_add_physics_object(model_name=objects[0],
                                                                        library=lib,
                                                                        position={"x": x,  "y": y, "z": z},
                                                                        scale_factor={"x": size, "y": size, "z": size},
                                                                        gravity=False,
                                                                        default_physics_values=False,
                                                                        object_id=object_id))
                                # set material
                                commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=material, object_id=object_id))

                                # set color
                                color_name, color_value = colors[0]
                                r, g, b = color_value
                                commands.append({"$type": "set_color", "color": {"r": r, "g": g, "b": b, "a": 1.0}, "id": object_id})

                                c.communicate(commands)

                                object = objects[0]
                                object = object.split("_")[1]
                                color = colors[0]
                                color_name = color[0]
                                color_name = color_name.replace('_', ' ')
                                image_info["object"] = {
                                                    "type": object,
                                                    "material": material,
                                                    "color": color_name,
                                                    "size": size}

                                # output setting
                                task_name = f"scenario_{count}_{material}_{traj}_{traj_radius}"
                                output_path = os.path.join(output_path, task_name)

                                # Camera specifying
                                camera_id = camera_id.lower()
                                camera = get_cameras(camera_id, camera_config)
                                c.add_ons.append(camera)

                                capture = ImageCapture(avatar_ids=[camera_id], path=output_path, png=True)
                                c.add_ons.append(capture)

                                # Get coordinates for motion trajectory
                                coordinates = get_action_coordinates(traj, traj_radius, object_center)
                                if coordinates is not None:
                                    for (x_d, z_d) in coordinates:
                                        commands= [{"$type": "teleport_object", 
                                                        "position": {"x": x_d, "z": z_d, "y": y}, 
                                                        "id": object_id, "physics": False, "absolute": True, "use_centroid": False}]
                                        c.communicate(commands)

                                image_info["image_path"] = f"{output_path}/{camera_id}"
                                image_info["scene"] = scene
                                image_info["camera_view"] = camera_id
                                image_info["trajectory"] = traj
                                image_info["radius"] = traj_radius

                                images_info.append(copy.deepcopy(image_info))
                                count += 1

                                # Reset for the next loop
                                c.add_ons.clear() 
                                c.communicate({"$type": "destroy_all_objects"})
                                c.communicate(TDWUtils.create_empty_room(12, 12))

    finally:
        # Save object info to JSON
        output_path = args.output_path
        with open(os.path.join(output_path, "trajectory.json"), 'w') as f:
            json.dump(images_info, f, indent=4)

        l = len(images_info)
        print(f"{l} scenarios generated.")

        # Terminate the server after the job is done
        c.communicate({"$type": "terminate"})
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    random.seed(39)
    parser = argparse.ArgumentParser()
    # Screen size
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    # Output Path
    parser.add_argument("--output_path", type=str, required=True, help="The path to save the outputs to.")
    # Render Quality
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")

    args = parser.parse_args()

    main(args)