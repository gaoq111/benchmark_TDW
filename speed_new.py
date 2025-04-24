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

def generate_line_coords(start_point, end_point, num_points=30):
    """
    Generate a list of coordinates interpolated along a straight line from the start point to the end point.
    :param start_point: (x_start, z_start)
    :param end_point: (x_end, z_end)
    :param num_points: Number of interpolation points
    :return: [(x, z), (x, z), ...]
    """
    (x1, z1) = start_point
    (x2, z2) = end_point
    coords = []
    for i in range(num_points):
        t = i / (num_points - 1)
        x = x1 + (x2 - x1) * t
        z = z1 + (z2 - z1) * t
        coords.append((x, z))
    return coords

def get_cameras(camera_id, camera_config):
    return ThirdPersonCamera(position=camera_config[camera_id],
                             avatar_id=camera_id,
                             look_at=camera_config['look_at'],
                             field_of_view=70)

def generate_coordinates(vision_boundary, size, n=6):
    """
    Randomly generate n coordinates within the specified vision boundary while maintaining a minimum distance.
    """
    coordinates = []

    def is_overlapping(new_coord, existing_coords, min_distance):
        """Check if the new coordinate is too close to the existing ones."""
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

def generate_objects(object_list, n=6):
    """
    Randomly select n object names (potentially with weighting) from object_list.
    """
    object_names = random.choices(object_list, k=n)
    return object_names

def generate_colors(colors, n=6):
    """
    Randomly select n colors from the given color dictionary and return them in [(color_name, (r, g, b)), ...] format.
    """
    processed_colors = []
    selected_colors = random.sample(list(colors.items()), n)
    for color in selected_colors:
        color_name, color_value = color
        # Convert from 0-255 to 0-1
        color_new_value = tuple(value / 255 for value in color_value)
        processed_colors.append((color_name, color_new_value))
    return processed_colors

def distance(p1, p2):
    """Compute the Euclidean distance between two points on a 2D plane."""
    return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

def check_line_of_sight(p1, p2, objects, radius):
    """
    Determine whether the line between two points intersects with any objects.
    :param p1, p2: (x, z)
    :param objects: [(x, z), ...]
    :param radius: The radius of the object
    :return: True / False
    """
    for obj in objects:
        if obj == p1 or obj == p2:
            continue

        # Parametric equation of the line segment: (1 - t)*p1 + t*p2, t ∈ [0,1]
        vec_p1p2 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
        vec_p1obj = np.array([obj[0] - p1[0], obj[1] - p1[1]])
        dot_val = np.dot(vec_p1p2, vec_p1obj)
        len_sq = np.dot(vec_p1p2, vec_p1p2)
        if len_sq == 0:
            # p1 and p2 overlap
            continue
        t = dot_val / len_sq
        t = max(0, min(1, t))
        closest_point = np.array([p1[0], p1[1]]) + t * vec_p1p2

        if distance(closest_point, obj) < radius:
            return False
    return True

def determine_possible_moves(moving_object, another_moving_object, objects, radius):
    """
    Find all possible destinations to which you can move directly from last_object without being obstructed.
    """
    possible_moves = []
    for obj in objects:
        if obj == moving_object or obj == another_moving_object:
            continue
        if check_line_of_sight(moving_object, obj, objects, radius):
            possible_moves.append(obj)
    return possible_moves

def is_tuple_close(t1, t2, tolerance=1e-9):
    """Check if two tuples are approximately equal within a given tolerance."""
    return all(math.isclose(a, b, abs_tol=tolerance) for a, b in zip(t1, t2))

def find_tuple_in_list(t, lst, tolerance=1e-4):
    """Find the index of tuple t in list lst if they are approximately equal."""
    for i, item in enumerate(lst):
        if is_tuple_close(t, item, tolerance):
            return i
    return -1

def start_tdw_server(display=":4", port=1072):
    """
    Start the TDW server. Requires specifying the DISPLAY variable and port number.
    """
    # The following command is only an example. Please modify it according to the local path of your TDW executable.
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process

def main(args):
    # Start the TDW server
    server_process = start_tdw_server(display=":4", port=1078)
    try:
        c = Controller(port=1078, launch_build=False)

        output_path = args.output_path
        os.makedirs(output_path, exist_ok=True)

        with open('scene_settings.yaml', 'r') as file:
            congfig = yaml.safe_load(file)

        # Some example scenes
        # scenes = ["empty_scene", "monkey_physics_room", "box_room_2018",
        #           "archviz_house", "ruin", "suburb_scene_2018"]
        scenes = ["monkey_physics_room", "box_room_2018",
                  "archviz_house", "ruin", "suburb_scene_2018"]

        # Some example materials
        object_materials = ["limestone_white", "glass_chopped_strands", "sand_covered_stone_ground"]

        # Object names
        objects_set = ['prim_cube', 'prim_sphere']

        # Number of objects in each scene
        # num_obj = [2, 3, 4]
        num_obj = [3, 4]

        # Number of data samples to generate for each configuration
        num_data = 8

        # Name of the model library file
        lib = "models_special.json"

        # List of camera IDs
        cameras = ['top']

        # Object scale
        size = 0.1

        # Available speeds
        speeds_available = [1, 2, 4]

        # Store information for all scenarios to write into JSON later
        infos = []

        count = 0
        for scene in tqdm(scenes, desc="Processing scenes"):
            for camera_id in tqdm(cameras, leave=False, desc="Processing cameras"):
                for n in tqdm(num_obj, leave=False, desc="Processing number of objects"):
                    for material in tqdm(object_materials, leave=False, desc="Processing material"):
                        for speed1 in tqdm(speeds_available, leave=False, desc="Processing speed1"):
                            remaining_speeds = [s for s in speeds_available if s != speed1]
                            for speed2 in tqdm(remaining_speeds, leave=False, desc="Processing speed2"):
                                for _ in tqdm(range(num_data), leave=False, desc=""):
                                    # Clear all AddOns first
                                    c.add_ons.clear()
                                    # Clear the scene
                                    c.communicate({"$type": "destroy_all_objects"})

                                    # Create an empty room to avoid potential residual effects
                                    c.communicate(TDWUtils.create_empty_room(12, 12))

                                    # Create a folder: scenario_{count}
                                    task_name = f"scenario_{count}"
                                    output_path_scenario = os.path.join(output_path, task_name)
                                    os.makedirs(output_path_scenario, exist_ok=True)

                                    # Basic rendering configuration
                                    commands = [
                                        {"$type": "set_screen_size",
                                        "width": args.screen_size[0],
                                        "height": args.screen_size[1]},
                                        {"$type": "set_render_quality",
                                        "render_quality": args.render_quality}
                                    ]
                                    # Load the scene
                                    commands.append(c.get_add_scene(scene))

                                    # Read camera and vision boundary
                                    camera_config = congfig[scene]['camera']
                                    vision_boundary = congfig[scene]['vision_boundary']

                                    # Generate object positions, object categories, and colors
                                    coordinates = generate_coordinates(vision_boundary, size, n=n)
                                    objs = generate_objects(objects_set, n=n)
                                    cols = generate_colors(COLORS, n=n)

                                    # Add objects
                                    object_ids = []
                                    model_records = []
                                    for i in range(n):
                                        object_id = c.get_unique_id()
                                        object_ids.append(object_id)
                                        model_record = ModelLibrarian(lib).get_record(objs[i])
                                        model_records.append(model_record)

                                        x, y, z = coordinates[i]
                                        commands.extend(
                                            c.get_add_physics_object(
                                                model_name=objs[i],
                                                library=lib,
                                                position={"x": x, "y": y, "z": z},
                                                scale_factor={"x": size, "y": size, "z": size},
                                                gravity=False,
                                                default_physics_values=False,
                                                object_id=object_id
                                            )
                                        )
                                        # Set the material
                                        commands.extend(
                                            TDWUtils.set_visual_material(
                                                c=c,
                                                substructure=model_record.substructure,
                                                material=material,
                                                object_id=object_id
                                            )
                                        )
                                        # Set the color
                                        color_name, color_value = cols[i]
                                        r, g, b = color_value
                                        commands.append({
                                            "$type": "set_color",
                                            "color": {"r": r, "g": g, "b": b, "a": 1.0},
                                            "id": object_id
                                        })

                                    # Organize information of all static objects
                                    objects_info = []
                                    for o_name, c_name in zip(objs, cols):
                                        o_name_simple = o_name.split("_")[1]  # e.g. "cube", "sphere"
                                        color_display = c_name[0].replace('_', ' ')
                                        object_info = {
                                            "type": o_name_simple,
                                            "material": material,
                                            "color": color_display,
                                            "size": size
                                        }
                                        objects_info.append(object_info)

                                    # Execute commands to load the scene and objects
                                    c.communicate(commands)

                                    # Select two different speeds
                                    # speed1, speed2 = random.sample(speeds_available, 2)

                                    # Choose the last 2 created objects to be movable
                                    movable_object_id_1 = object_ids[-1]
                                    movable_object_id_2 = object_ids[-2]

                                    start1 = coordinates[-1]
                                    start2 = coordinates[-2]

                                    start_object1 = objs[-1]
                                    start_object2 = objs[-2]

                                    # Extract the "simplified names" and colors
                                    start_object1_simple = start_object1.split("_")[1]
                                    start_object2_simple = start_object2.split("_")[1]
                                    start_color1_name = cols[-1][0].replace('_', ' ')
                                    start_color2_name = cols[-2][0].replace('_', ' ')

                                    # Determine feasible target points for each object (removing obstructions)
                                    # Since y is the same for all generated coordinates, we can simply compare (x, z)
                                    all_coordinates_2d = [(c[0], c[2]) for c in coordinates]
                                    start_2d_1 = (start1[0], start1[2])
                                    start_2d_2 = (start2[0], start2[2])

                                    possible_destinations_1 = determine_possible_moves(start_2d_1, start_2d_2, all_coordinates_2d, size)
                                    possible_destinations_2 = determine_possible_moves(start_2d_2, start_2d_1, all_coordinates_2d, size)

                                    # If either object has no feasible path, skip this sample
                                    if len(possible_destinations_1) < 1 or len(possible_destinations_2) < 1:
                                        continue

                                    # Randomly select one destination point for each
                                    dest_1 = random.choice(possible_destinations_1)
                                    dest_2 = random.choice(possible_destinations_2)

                                    # Find the indices
                                    idx_1 = find_tuple_in_list(dest_1, all_coordinates_2d)
                                    idx_2 = find_tuple_in_list(dest_2, all_coordinates_2d)

                                    # Obtain target object info
                                    destination_object_1 = objs[idx_1].split("_")[1]
                                    # print(destination_object_1)
                                    destination_color_1_name = cols[idx_1][0].replace('_', ' ')

                                    destination_object_2 = objs[idx_2].split("_")[1]
                                    # print(destination_object_2)
                                    destination_color_2_name = cols[idx_2][0].replace('_', ' ')

                                    # Set output directory
                                    # output_path_scenario_cam = os.path.join(output_path_scenario, camera_id)
                                    # os.makedirs(output_path_scenario, exist_ok=True)

                                    # Set up the camera
                                    camera_id = camera_id.lower()
                                    camera = get_cameras(camera_id, camera_config)
                                    c.add_ons.append(camera)

                                    # Set up the ImageCapture AddOn
                                    capture = ImageCapture(avatar_ids=[camera_id],
                                                        path=output_path_scenario,
                                                        png=True)
                                    c.add_ons.append(capture)

                                    # Calculate movement paths for the two objects
                                    # Here we exemplify scaling the destination by speed1/speed2
                                    # First get direction vectors (2D)
                                    length1 = math.sqrt((dest_1[0] - start_2d_1[0]) ** 2 + (dest_1[1] - start_2d_1[1]) ** 2)
                                    length2 = math.sqrt((dest_2[0] - start_2d_2[0]) ** 2 + (dest_2[1] - start_2d_2[1]) ** 2)

                                    dir1 = ((dest_1[0] - start_2d_1[0]) / length1, (dest_1[1] - start_2d_1[1]) / length1)
                                    dir2 = ((dest_2[0] - start_2d_2[0]) / length2, (dest_2[1] - start_2d_2[1]) /length2)

                                    # Scale the endpoint by *speed1 / *speed2
                                    end_1 = (start_2d_1[0] + speed1 * dir1[0],
                                            start_2d_1[1] + speed1 * dir1[1])
                                    end_2 = (start_2d_2[0] + speed2 * dir2[0],
                                            start_2d_2[1] + speed2 * dir2[1])

                                    path_coordinates_1 = generate_line_coords(start_2d_1, end_1, num_points=8)
                                    path_coordinates_2 = generate_line_coords(start_2d_2, end_2, num_points=8)

                                    # Move the two objects simultaneously
                                    # In this example: in the same loop, move both objects, then send the commands
                                    max_len = max(len(path_coordinates_1), len(path_coordinates_2))

                                    y_common = start1[1]  # Suppose y is the same
                                    for i in range(max_len):
                                        commands_moving = []
                                        if i < len(path_coordinates_1):
                                            x_d1, z_d1 = path_coordinates_1[i]
                                            commands_moving.append({
                                                "$type": "teleport_object",
                                                "position": {"x": x_d1, "z": z_d1, "y": y_common},
                                                "id": movable_object_id_1,
                                                "physics": False,
                                                "absolute": True,
                                                "use_centroid": False
                                            })
                                        if i < len(path_coordinates_2):
                                            x_d2, z_d2 = path_coordinates_2[i]
                                            commands_moving.append({
                                                "$type": "teleport_object",
                                                "position": {"x": x_d2, "z": z_d2, "y": y_common},
                                                "id": movable_object_id_2,
                                                "physics": False,
                                                "absolute": True,
                                                "use_centroid": False
                                            })
                                        if commands_moving:
                                            c.communicate(commands_moving)

                                    # Organize record info
                                    image_info = {}
                                    image_info["scene"] = scene
                                    image_info["camera_view"] = camera_id
                                    image_info["image_path"] = f"{output_path_scenario}/"
                                    image_info["objects_info"] = objects_info

                                    # Detailed information of the two moving objects
                                    moving_info = [
                                        {
                                            "speed": speed1,
                                            "type": start_object1_simple,
                                            "material": material,
                                            "color": start_color1_name,
                                            "size": size
                                        },
                                        {
                                            "speed": speed2,
                                            "type": start_object2_simple,
                                            "material": material,
                                            "color": start_color2_name,
                                            "size": size
                                        }
                                    ]
                                    image_info["moving"] = moving_info

                                    # Detailed information of the two targets
                                    if idx_1 == idx_2:
                                        reference_info = [
                                            {
                                                "type": destination_object_1,
                                                "material": material,
                                                "color": destination_color_1_name,
                                                "size": size
                                            }
                                        ]
                                    else:
                                        reference_info = [
                                            {
                                                "type": destination_object_1,
                                                "material": material,
                                                "color": destination_color_1_name,
                                                "size": size
                                            },
                                            {
                                                "type": destination_object_2,
                                                "material": material,
                                                "color": destination_color_2_name,
                                                "size": size
                                            }
                                        ]
                                    image_info["reference"] = reference_info

                                    infos.append(copy.deepcopy(image_info))
                                    count += 1

                                    # Clear the scene
                                    c.add_ons.clear()
                                    c.communicate({"$type": "destroy_all_objects"})
                                    c.communicate(TDWUtils.create_empty_room(12, 12))

        # Write into JSON
        output_json_file = os.path.join(output_path, "speed.json")
        with open(output_json_file, 'w', encoding='utf-8') as f:
            json.dump(infos, f, ensure_ascii=False, indent=4)

        print(f"{len(infos)} scenarios generated.")

        # Terminate and close the server
        c.communicate({"$type": "terminate"})
        server_process.terminate()
        server_process.wait()

    except Exception as e:
        print("An error occurred:", e)
        c.communicate({"$type": "terminate"})
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    random.seed(39)
    parser = argparse.ArgumentParser(description="Generate a dataset with two objects moving at different speeds.")
    # Screen resolution
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512),
                        help="Width and Height of Screen. (W, H)")
    # Output path
    parser.add_argument("--output_path", type=str, required=True,
                        help="The path to save the outputs to.")
    # Render quality
    parser.add_argument("--render_quality", type=int, default=5,
                        help="The Render Quality of the output.")

    args = parser.parse_args()

    main(args)