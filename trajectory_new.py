import argparse
import os
import time
import yaml
import subprocess
import random
import json
import copy
import random
from math import sqrt

from tqdm import tqdm

from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.librarian import ModelLibrarian
from tdw.output_data import OutputData, FieldOfView

from utils import generate_square_coords, generate_circle_coords, generate_triangle_coords, generate_line_coords_with_length
from consts import COLORS

# Initiate a tdw server:
# The server might exit when there are errors in executing the commands 
# "y" is the vertical axis in the setting

# TODO:
# 1. Better image write_out method, in tdw_physics, they write images to hfd5 files
# 2. Multiprocess tdw servers

#[Optional]: using python subprocess to initiate the server on-the-fly with a customized port

def start_tdw_server(display=":4", port=1072):
    """
    Start a TDW server.
    """
    command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
    process = subprocess.Popen(command, shell=True)
    time.sleep(5)  # Wait for the server to start
    return process

def get_cameras(camera_id, camera_config):
    """
    Return a ThirdPersonCamera with the specified ID.
    """
    return ThirdPersonCamera(
        position=camera_config[camera_id],
        avatar_id=camera_id,
        look_at=camera_config['look_at'],
        field_of_view=80,
    )

def get_position(pos_name, object_config):
    """
    Retrieve the specified position from the 'object' section of scene_settings.yaml.
    """
    return object_config[pos_name]

def generate_objects(object_list, n=1):
    """
    Randomly select n object names from object_list and return them.
    """
    return random.choices(object_list, k=n)

def generate_colors(colors_dict, n=1):
    """
    Randomly select n colors from a color dictionary.
    Return a list of tuples [(color_name, (r, g, b)), ...].
    """
    processed_colors = []
    selected_colors = random.sample(list(colors_dict.items()), n)
    for color in selected_colors:
        color_name, color_value = color
        color_new_value = tuple(value / 255 for value in color_value)
        processed_colors.append((color_name, color_new_value))
    return processed_colors

def get_action_coordinates(action, radius, center, direction='right'):
    """
    Generate a list of (x, z) coordinates according to the specified trajectory type.
    """
    if action is None:
        return None
    if action == 'circle':
        radius = float(radius)
        return generate_circle_coords(num_points=8, radius=radius, center=center)
    if action == 'square':
        side_length = float(radius)
        return generate_square_coords(num_points=8, side_length=side_length, center=center)
    if action == 'triangle':
        side_length = float(radius)
        return generate_triangle_coords(num_points=8, side_length=side_length, center=center)
    if action == 'line':
        length = float(radius)
        return generate_line_coords_with_length(start_point=center, length=length, direction=direction, num_points=8)

    return None

def check_trajectories_intersect(coords1, coords2, min_dist=0.2):
    """
    Check if two trajectories intersect or are too close.
    If any pair of points (x1, z1) in coords1 and (x2, z2) in coords2 is within min_dist, 
    we consider the trajectories to intersect (or be too close).
    """
    for (x1, z1) in coords1:
        for (x2, z2) in coords2:
            dist = sqrt((x1 - x2) ** 2 + (z1 - z2) ** 2)
            if dist < min_dist:
                return True
    return False

def main(args):
    """
    Create two objects in the same scene, each moving along different trajectories that do not intersect.
    Trajectory types must also be different.
    """
    # Start the TDW server
    server_process = start_tdw_server(display=":4", port=1075)

    try:
        # Initialize the controller without automatically launching a build
        c = Controller(port=1075, launch_build=False)

        output_path = args.output_path
        os.makedirs(output_path, exist_ok=True)

        # Load camera and object configurations from the YAML file
        with open('scene_settings.yaml', 'r') as file:
            congfig = yaml.safe_load(file)

        # Define scenes to be processed
        scenes = ["monkey_physics_room", "box_room_2018",
                  "archviz_house", "ruin", "suburb_scene_2018"]

        # Define available materials
        object_materials = ["limestone_white", "glass_chopped_strands", "sand_covered_stone_ground"]

        # Define available objects
        object_list = ['prim_cube', 'prim_sphere']

        # Define possible trajectories
        trajectories = ['circle', 'triangle', 'square', 'left_line', 'right_line', 'up_line', 'down_line']

        # Define possible radii for trajectories
        radius_candidates = [0.3, 0.6, 1, 1.2]

        # Select the model library
        lib = "models_special.json"

        # Define camera IDs
        cameras = ['top']

        # Define object size
        size = 0.25

        # Number of data samples per scene
        num_data = 1

        # List for storing metadata of all scenes/objects
        images_info = []
        count = 0

        # Iterate over all scenes
        for scene in tqdm(scenes, desc="Processing scenes"):
            for camera_id in tqdm(cameras, leave=False, desc="Processing camera"):
                for material in tqdm(object_materials, leave=False, desc="Processing material"):
                    for traj1 in tqdm(trajectories, leave=False, desc="Processing traj1"):
                        for traj_radius_1 in tqdm(radius_candidates, leave=False, desc="Processing traj_radius_1"):
                            # remaining_trajectories = [t for t in trajectories if t.find('line') == -1]
                            # for _ in tqdm(range(num_data), leave=False):
                            for traj2_candidate in tqdm(trajectories, leave=False, desc="Processing traj2_candidate"):
                                for traj_radius_2_candidate in tqdm(radius_candidates, leave=False, desc="Processing traj_radius_2_candidate"):
                                
                                    # # 1) Randomly select a trajectory for the first object
                                    # traj1 = random.choice(trajectories)
                                    # traj_radius_1 = random.choice(radius_candidates)

                                    # Read position data from the config file
                                    camera_config = congfig[scene]['camera']
                                    object_config = congfig[scene]['object']

                                    # Base commands for initializing the scene
                                    commands = [
                                        {"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]},
                                        {"$type": "set_render_quality", "render_quality": args.render_quality}
                                    ]
                                    commands.append(c.get_add_scene(scene))
                                    c.communicate(commands)

                                    # Scene center
                                    object_center = get_position('center', object_config)
                                    object_center = [object_center[0], object_center[2]]
                                    center1 = [object_center[0] - 0.2, object_center[1] + 0.2] # TODO: add bias to the line trajectory

                                    # Initial position for object1
                                    initial_pos_1 = get_position('left', object_config)
                                    x1, y1, z1 = initial_pos_1

                                    # Generate object1 and its trajectory (coords1)
                                    obj1_id = c.get_unique_id()
                                    obj1_name = random.choice(object_list)  # object type
                                    color1_name, color1_value = generate_colors(COLORS, n=1)[0]
                                    model_record_1 = ModelLibrarian(lib).get_record(obj1_name)
                                    if traj1.find('line') != -1: #TODO：add bias to the line trajectory
                                        direction1 = traj1.split('_')[0]
                                        traj1_temp = traj1.split('_')[1]
                                        coords1 = get_action_coordinates(traj1_temp, traj_radius_1, center1, direction1)
                                    else:
                                        coords1 = get_action_coordinates(traj1, traj_radius_1, center1)
                                    if coords1 is None:
                                        print(f"Trajectory generation error for object1. Skipping.")
                                        continue

                                    # Add object1
                                    commands_obj1 = c.get_add_physics_object(
                                        model_name=obj1_name,
                                        library=lib,
                                        position={"x": x1, "y": y1, "z": z1},
                                        scale_factor={"x": size, "y": size, "z": size},
                                        gravity=False,
                                        default_physics_values=False,
                                        object_id=obj1_id
                                    )
                                    commands_obj1.extend(TDWUtils.set_visual_material(
                                        c=c,
                                        substructure=model_record_1.substructure,
                                        material=material,
                                        object_id=obj1_id
                                    ))
                                    r1, g1, b1 = color1_value
                                    commands_obj1.append({
                                        "$type": "set_color",
                                        "color": {"r": r1, "g": g1, "b": b1, "a": 1.0},
                                        "id": obj1_id
                                    })
                                    c.communicate(commands_obj1)

                                    obj1_type = obj1_name.split("_")[1]  # e.g. prim_cube -> cube

                                    # 2) Randomly pick a different trajectory for the second object
                                    # remaining_trajectories = [t for t in trajectories if t != traj1]

                                    # max_attempts = 20
                                    # attempt = 0
                                    coords2 = None
                                    traj2 = None
                                    traj_radius_2 = None

                                    # Initial position for object2
                                    initial_pos_2 = get_position('right', object_config)
                                    x2, y2, z2 = initial_pos_2

                                    obj2_id = c.get_unique_id()
                                    obj2_name = random.choice(object_list)
                                    color2_name, color2_value = generate_colors(COLORS, n=1)[0]
                                    model_record_2 = ModelLibrarian(lib).get_record(obj2_name)

                                    # Try multiple times to find a non-intersecting path
                                    # while attempt < max_attempts:
                                    # attempt += 1
                                    # traj2_candidate = random.choice(remaining_trajectories)
                                    # traj_radius_candidate = random.choice(radius_candidates)

                                    center2 = [object_center[0] + 0.2, object_center[1] - 0.2]
                                    if traj2_candidate.find('line') != -1:
                                        # print(f"Current traj2_candidate: {traj2_candidate}")
                                        direction2 = traj2_candidate.split('_')[0]
                                        traj2_candidate_temp = traj2_candidate.split('_')[1]
                                        coords2_candidate = get_action_coordinates(traj2_candidate_temp,
                                                                            traj_radius_2_candidate,
                                                                            center2,
                                                                            direction2)
                                    else:
                                        coords2_candidate = get_action_coordinates(traj2_candidate,
                                                                                traj_radius_2_candidate,
                                                                                center2)
                                    if coords2_candidate is None:
                                        print(f"Cannot find a trajectory candidate for object2.")
                                        c.communicate({"$type": "destroy_all_objects"})
                                        c.communicate(TDWUtils.create_empty_room(12, 12))
                                        continue

                                    # Check if coords2_candidate intersects coords1
                                    if not check_trajectories_intersect(coords1, coords2_candidate, min_dist=0.3):
                                        coords2 = coords2_candidate
                                        traj2 = traj2_candidate
                                        traj_radius_2 = traj_radius_2_candidate
                                        # break

                                    if coords2 is None:
                                        # Failed to find a suitable trajectory after max_attempts
                                        # print(f"Cannot find a non-intersecting trajectory for object2.")
                                        # if traj1 == traj2 and traj1.find('line') != -1:
                                        with open("intersection.txt", 'a') as f:
                                            f.write(f"Intersection: {traj1} - {traj2_candidate}, {traj_radius_1} - {traj_radius_2_candidate}\n")
                                            f.write(f"Coords1: {coords1}\n")
                                            f.write(f"Coords2: {coords2_candidate}\n")
                                        c.communicate({"$type": "destroy_all_objects"})
                                        c.communicate(TDWUtils.create_empty_room(12, 12))
                                        continue
                                    
                                    if traj1 != traj2:
                                        # 2/3 chance to skip the scenario
                                        if random.random() < 0.67:
                                            c.communicate({"$type": "destroy_all_objects"})
                                            c.communicate(TDWUtils.create_empty_room(12, 12))
                                            continue

                                    # Add object2
                                    commands_obj2 = c.get_add_physics_object(
                                        model_name=obj2_name,
                                        library=lib,
                                        position={"x": x2, "y": y2, "z": z2},
                                        scale_factor={"x": size, "y": size, "z": size},
                                        gravity=False,
                                        default_physics_values=False,
                                        object_id=obj2_id
                                    )
                                    commands_obj2.extend(TDWUtils.set_visual_material(
                                        c=c,
                                        substructure=model_record_2.substructure,
                                        material=material,
                                        object_id=obj2_id
                                    ))
                                    r2, g2, b2 = color2_value
                                    commands_obj2.append({
                                        "$type": "set_color",
                                        "color": {"r": r2, "g": g2, "b": b2, "a": 1.0},
                                        "id": obj2_id
                                    })
                                    c.communicate(commands_obj2)

                                    obj2_type = obj2_name.split("_")[1]  # e.g. prim_sphere -> sphere

                                    # ============ Specify camera & capture images ============
                                    camera_id_lower = camera_id.lower()
                                    camera = get_cameras(camera_id_lower, camera_config)
                                    c.add_ons.append(camera)

                                    task_name = f"scenario_{count}_{material}_{traj1}_{traj2}_R1={traj_radius_1}_R2={traj_radius_2}"
                                    scenario_output_path = os.path.join(output_path, task_name)

                                    capture = ImageCapture(avatar_ids=[camera_id_lower], path=scenario_output_path, png=True)
                                    c.add_ons.append(capture)

                                    # ============ Move both objects together =============
                                    for (px1, pz1), (px2, pz2) in zip(coords1, coords2):
                                        commands_move = []
                                        commands_move.append({
                                            "$type": "teleport_object",
                                            "position": {"x": px1, "y": y1, "z": pz1},
                                            "id": obj1_id,
                                            "physics": False,
                                            "absolute": True,
                                            "use_centroid": False
                                        })
                                        commands_move.append({
                                            "$type": "teleport_object",
                                            "position": {"x": px2, "y": y2, "z": pz2},
                                            "id": obj2_id,
                                            "physics": False,
                                            "absolute": True,
                                            "use_centroid": False
                                        })
                                        c.communicate(commands_move)

                                    # ============ Record metadata ============
                                    objects_meta = [
                                        {
                                            "id": obj1_id,
                                            "type": obj1_type,
                                            "material": material,
                                            "color": color1_name,
                                            "size": size,
                                            "trajectory": traj1,
                                            "radius": traj_radius_1
                                        },
                                        {
                                            "id": obj2_id,
                                            "type": obj2_type,
                                            "material": material,
                                            "color": color2_name,
                                            "size": size,
                                            "trajectory": traj2,
                                            "radius": traj_radius_2
                                        }
                                    ]
                                    image_info = {
                                        "scene": scene,
                                        "camera_view": camera_id_lower,
                                        "image_path": f"{scenario_output_path}/{camera_id_lower}",
                                        "objects": objects_meta
                                    }
                                    images_info.append(copy.deepcopy(image_info))

                                    json_file_path = os.path.join(output_path, "trajectory.json")
                                    with open(json_file_path, 'w') as f:
                                        json.dump(images_info, f, indent=4)

                                    count += 1

                                    # ============ Clean up for the next loop ============
                                    c.add_ons.clear()
                                    c.communicate({"$type": "destroy_all_objects"})
                                    c.communicate(TDWUtils.create_empty_room(12, 12))

        # # Save all info into a JSON file
        # with open(os.path.join(output_path, "trajectory.json"), 'w') as f:
        #     json.dump(images_info, f, indent=4)

        print(f"{len(images_info)} scenarios generated.")

        # Terminate the simulation
        c.communicate({"$type": "terminate"})

    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    random.seed(39)
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512),
                        help="Width and Height of Screen. (W, H)")
    parser.add_argument("--output_path", type=str, required=True,
                        help="The path to save the outputs to.")
    parser.add_argument("--render_quality", type=int, default=5,
                        help="The Render Quality of the output.")

    args = parser.parse_args()
    main(args)
