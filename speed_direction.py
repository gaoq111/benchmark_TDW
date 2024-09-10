from utils import *
from consts import COLORS
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
import random
import math
import numpy as np


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

def generate_coordinates(vision_boundary, size, n=6):
    coordinates = []
    def is_overlapping(new_coord, existing_coords, min_distance):
        """Check if the new coordinate is within the minimum distance from any existing coordinate."""
        for coord in existing_coords:
            distance = ((new_coord[0] - coord[0]) ** 2 + 
                        (new_coord[1] - coord[1]) ** 2 + 
                        (new_coord[2] - coord[2]) ** 2) ** 0.5
            if distance < min_distance:
                return True
        return False

    min_distance = size + 0.2

    while len(coordinates) < n:
        x_range = vision_boundary['x']
        z_range = vision_boundary['z']
        y = vision_boundary['y']

        x = random.uniform(x_range[0], x_range[1])
        z = random.uniform(z_range[0], z_range[1])
        new_coord = (x, y, z)

        if not is_overlapping(new_coord, coordinates, min_distance):
            coordinates.append(new_coord)

    return coordinates

#TODO: add feature where we can give a list of object to choose from and weights
def generate_objects(n=6):
    object_names = random.choices(['prim_sphere', 'prim_cube'], weights=[0.5,0.5], k=n)
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

def distance(p1, p2):
    """Calculate the Euclidean distance between two points."""
    return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

def check_line_of_sight(p1, p2, objects, radius):
    """
    Check if there is a clear path (line of sight) between two points without intersecting other objects.
    
    :param p1: The start point (last object).
    :param p2: The target point (potential destination).
    :param objects: A list of objects, represented as (x, y) coordinates.
    :param radius: The radius of the objects (assuming they are circular).
    :return: True if the line-of-sight is clear, False if it intersects any object.
    """
    for obj in objects:
        if obj == p1 or obj == p2:
            continue

        # Calculate distance from the line segment to the object
        # Parametric equation of a line segment: (1 - t) * p1 + t * p2, where t ∈ [0, 1]
        t = np.dot(np.array(p2) - np.array(p1), np.array(obj) - np.array(p1)) / np.dot(np.array(p2) - np.array(p1), np.array(p2) - np.array(p1))
        t = max(0, min(1, t))
        closest_point = (1 - t) * np.array(p1) + t * np.array(p2)
        
        # check if the closest point is within the radius
        if distance(closest_point, obj) < radius:
            return False

    return True

def determine_possible_moves(last_object, objects, radius):
    """
    Determine which objects the last object can move to without crossing other objects.
    
    :param last_object: The coordinates of the last object (x, y).
    :param objects: A list of other objects' coordinates.
    :param radius: The radius of the objects.
    :return: A list of possible destination coordinates.
    """
    possible_moves = []
    for obj in objects:
        if obj == last_object:
            continue
        if check_line_of_sight(last_object, obj, objects, radius):
            possible_moves.append(obj)
    return possible_moves

def is_tuple_close(t1, t2, tolerance=1e-9):
    """Compare two tuples element-wise with a tolerance."""
    return all(math.isclose(a, b, abs_tol=tolerance) for a, b in zip(t1, t2))

def find_tuple_in_list(t, lst, tolerance=1e-4):
    """Find the index of a tuple in a list using element-wise comparison with tolerance."""
    for i, item in enumerate(lst):
        if is_tuple_close(t, item, tolerance):
            return i
    return -1

def start_tdw_server(display=":4", port=1072):
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process
        

def main(args):
    server_process = start_tdw_server(display=":4", port=1075)

    try:
        # Launch TDW Build
        c = Controller(port=1075, launch_build=False)

        start_time = time.time()
        output_path = args.output_path  #EXAMPLE_CONTROLLER_OUTPUT_PATH.joinpath("image_capture")
        # task_name = args.name

        # read the camera and object configs
        with open('scene_settings.yaml', 'r') as file:
            congfig = yaml.safe_load(file)
        camera_config = congfig[args.scene]['camera']
        vision_boundary = congfig[args.scene]['vision_boundary']

        # general rendering configurations
        commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]}, 
                    {"$type": "set_render_quality", "render_quality": args.render_quality},
                    ]
        
        # initialize background
        commands.append(c.get_add_scene(args.scene))
        
        # select the library
        librarian = ModelLibrarian("models_special.json")
        special_lib = []
        for record in librarian.records:
            special_lib.append(record.name)
        # check library TODO: check list of objects
        if args.object in special_lib:
            lib = "models_special.json"
        else:
            lib = "models_core.json"

        # generate n coordinates, objects, and colors
        n = 6
        coordinates = generate_coordinates(vision_boundary, args.size, n=n)
        objects = generate_objects(n=n)
        colors = generate_colors(COLORS, n=n)

        # get the object and set location
        model_records = []
        object_ids = []
        for i in range(n):
            object_id = c.get_unique_id()
            object_ids.append(object_id)
            model_record = ModelLibrarian(lib).get_record(objects[i])
            model_records.append(model_record)

            x, y, z = coordinates[i]
            commands.extend(c.get_add_physics_object(model_name=objects[i],
                                                    library=lib,
                                                    position={"x": x,  "y": y, "z": z},
                                                    scale_factor={"x": args.size, "y": args.size, "z": args.size},
                                                    gravity=False,
                                                    default_physics_values=False,
                                                    object_id=object_id))

            # # Change material of object if provided
            # if args.material is not None:
            #     commands.append(c.get_add_material(material_name=args.material))
            #     # Set all of the object's visual materials.
            #     commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=args.material, object_id=object_id))
                
            # set color
            color_name, color_value = colors[i]
            r, g, b = color_value
            commands.append({"$type": "set_color", "color": {"r": r, "g": g, "b": b, "a": 1.0}, "id": object_id})

        c.communicate(commands)

        movable_obejct_id = object_ids[-1]
        start = coordinates[-1]
        start_object = objects[-1]
        start_color = colors[-1]
        possible_destinations = determine_possible_moves(start, coordinates, args.size)
        destination = random.sample(possible_destinations, 1)
        destination = destination[0]
        destination_index = find_tuple_in_list(destination, coordinates)
        destination_object = objects[destination_index]
        destination_color = colors[destination_index]

        # if task_name is not None
        filtered_start_object = start_object.split("_")[1]
        filtered_end_object = destination_object.split("_")[1]
        task_name = f"{start_color[0]}_{filtered_start_object}-{destination_color[0]}_{filtered_end_object}"
        output_path = os.path.join(output_path, task_name)

        # Camera specifying
        for camera_id in args.cameras:
            camera_id = camera_id.lower()
            camera = get_cameras(camera_id, camera_config)
            c.add_ons.append(camera)
        capture = ImageCapture(avatar_ids=args.cameras, path=output_path, png=True)
        c.add_ons.append(capture)

        start_xz = [start[0], start[2]]
        end_xz = [destination[0], destination[2]]
        coordinates = generate_line_coords(start_point=start_xz, end_point=end_xz, num_points=30)
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
# python speed_direction.py --output "/data/shared/sim/benchmark/benchmark_TDW/image_capture/speed_direction" --cameras top --name test
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
    parser.add_argument("--object", type=str, default="prim_sphere") #TODO: multiple objects
    parser.add_argument("--size", type=float, default=0.25, help="Scale of the object") #TODO: multiple sizes
    # # Task Name
    # parser.add_argument("--name", type=str, default=None, help="The name of the task.")
    # Material
    parser.add_argument("--material", type=str, default=None, help="The material of the object.")

    args = parser.parse_args()

    main(args)