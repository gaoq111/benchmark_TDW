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
import shutil
import json
from tqdm import tqdm
import copy

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
def generate_objects(object_list, n=6):
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

        output_path = args.output_path
        os.makedirs(output_path, exist_ok=True) 

        # # Add interior lighting
        # interior_lighting = InteriorSceneLighting()
        # c.add_ons.append(interior_lighting) 

        # read the camera and object configs
        with open('scene_settings.yaml', 'r') as file:
            congfig = yaml.safe_load(file)

        # Define scenes
        scenes = ["empty_scene", "monkey_physics_room", "box_room_2018", "archviz_house", "ruin", "suburb_scene_2018"]

        # Define materials
        object_materials = ["limestone_white", "glass_chopped_strands", "sand_covered_stone_ground"]

        # Define objects
        objects_set = ['prim_cube', 'prim_sphere']

        # number of objects
        num_obj = [2, 3, 4]

        # Number of data per scene
        num_data = 5

        # Define Library
        lib = "models_special.json"

        # Define Camera
        cameras = ['top']

        # Define Size
        size = 0.25

        # Define Speeds
        speeds = [1, 2, 3]

        # Initialize image info
        infos = []

        # Add CollisionManager to track object collisions
        # collision_manager = CollisionManager(enter=True, exit=True, stay=True)
        # c.add_ons.append(collision_manager)

        count = 0
        for scene in tqdm(scenes, desc="Processing scenes"):
            # interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
            for camera_id in tqdm(cameras, leave=False):
                for n in tqdm(num_obj, leave=False):
                    for material in tqdm(object_materials, leave=False):
                        for _ in tqdm(range(num_data), leave=False):
                            output_path = args.output_path

                            # Camera and vision boundary setting
                            camera_config = congfig[scene]['camera']
                            vision_boundary = congfig[scene]['vision_boundary']

                            # generate n coordinates, objects, and colors
                            coordinates = generate_coordinates(vision_boundary, size, n=n)

                            objects = generate_objects(objects_set, n=n)
                            colors = generate_colors(COLORS, n=n)

                            # all image infos in 1 scenario (multiple speeds)
                            image_infos = {}

                            for speed in speeds:
                                image_info = {}
                                image_info["speed"] = speed
                                image_info["scene"] = scene
                                image_info["camera_view"] = camera_id

                                c.add_ons.clear() 
                                c.communicate({"$type": "destroy_all_objects"})
                                objects_info = []
                                # General rendering configurations
                                commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]},
                                            {"$type": "set_render_quality", "render_quality": args.render_quality}]
                                # Initialize scene
                                commands.append(c.get_add_scene(scene))
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
                                                                            scale_factor={"x": size, "y": size, "z": size},
                                                                            gravity=False,
                                                                            default_physics_values=False,
                                                                            object_id=object_id))
                                    
                                    # set material
                                    commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=material, object_id=object_id))
                                    
                                    # set color
                                    color_name, color_value = colors[i]
                                    r, g, b = color_value
                                    commands.append({"$type": "set_color", "color": {"r": r, "g": g, "b": b, "a": 1.0}, "id": object_id})

                                for object_name, color_name in zip(objects, colors):
                                    object_name = object_name.split("_")[1]
                                    color_name = color_name[0].replace('_', ' ')
                                    object_info = {
                                                "type": object_name,
                                                "material": material,
                                                "color": color_name,
                                                "size": size}
                                    objects_info.append(object_info)

                                c.communicate(commands)

                                movable_obejct_id = object_ids[-1]
                                start = coordinates[-1]
                                start_object = objects[-1]
                                start_object = start_object.split("_")[1]
                                start_color = colors[-1]
                                start_color_name = start_color[0].replace('_', ' ')

                                image_info["moving"] = {
                                                        "type": start_object,
                                                        "material": material,
                                                        "color": start_color_name,
                                                        "size": size}

                                possible_destinations = determine_possible_moves(start, coordinates, size)
                                # skip this case if no path is available
                                if len(possible_destinations) < 1:
                                    continue

                                destination = random.sample(possible_destinations, 1)
                                destination = destination[0]
                                destination_index = find_tuple_in_list(destination, coordinates)
                                destination_object = objects[destination_index]
                                destination_color = colors[destination_index]
                                destination_color_name = destination_color[0].replace('_', ' ')
                                destination_object = destination_object.split("_")[1]

                                image_info["reference"] = {
                                                        "type": destination_object,
                                                        "material": material,
                                                        "color": destination_color_name,
                                                        "size": size}

                                # output setting
                                task_name = f"scenario_{count}/speed{speed}x"
                                output_path_speed = os.path.join(output_path, task_name)

                                # Camera specifying
                                camera_id = camera_id.lower()
                                camera = get_cameras(camera_id, camera_config)
                                c.add_ons.append(camera)

                                capture = ImageCapture(avatar_ids=[camera_id], path=output_path_speed, png=True)
                                c.add_ons.append(capture)

                                start_xz = [start[0], start[2]]
                                end_xz = [destination[0], destination[2]]
                                # Calculate the direction vector
                                direction_vector = [end_xz[0] - start_xz[0], end_xz[1] - start_xz[1]]

                                # Extend the line by doubling the distance (2 times the direction vector)
                                end_xz = [start_xz[0] + speed * direction_vector[0], start_xz[1] + speed * direction_vector[1]]

                                path_coordinates = generate_line_coords(start_point=start_xz, end_point=end_xz, num_points=30)
                                if path_coordinates is not None:
                                    for (x_d, z_d) in path_coordinates:
                                        commands= [{"$type": "teleport_object", 
                                                        "position": {"x": x_d, "z": z_d, "y": y}, 
                                                        "id": movable_obejct_id, "physics": False, "absolute": True, "use_centroid": False}]
                                        c.communicate(commands)

                                ###########################################################
                                image_info["image_path"] = f"{output_path_speed}/{camera_id}"
                                image_info["objects_info"] = objects_info

                                colors = []
                                random_colors = random.sample(list(COLORS.keys()), n)
                                for color in random_colors:
                                    sampled_color_name, sampled_color_value = (color, COLORS[color])
                                    sampled_color_value = tuple(value / 255 for value in sampled_color_value)
                                    colors.append((sampled_color_name, sampled_color_value))
                                
                                # add to all speeds dictionary
                                image_infos[speed] = copy.deepcopy(image_info)
                                ##########################################################

                            # add the image_infos to this scenario
                            infos.append(copy.deepcopy(image_infos))
                            count += 1

                            # Reset for the next loop
                            c.add_ons.clear() 
                            c.communicate({"$type": "destroy_all_objects"})
                            c.communicate(TDWUtils.create_empty_room(12, 12))
        
    finally:
        # Save object info to JSON
        output_path = args.output_path
        with open(os.path.join(output_path, "speed.json"), 'w') as f:
            json.dump(infos, f, indent=4)

        l = len(infos)
        print(f"{l} scenarios generated.")

        # Terminate the server after the job is done
        c.communicate({"$type": "terminate"})
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    random.seed(39)
    parser = argparse.ArgumentParser(description="Generate a dataset with different object configurations.")
    # Screen size
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    # Output Path
    parser.add_argument("--output_path", type=str, required=True, help="The path to save the outputs to.")
    # Render Quality
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")

    args = parser.parse_args()

    main(args)
