import os
import json
import random
import argparse
from tqdm import tqdm
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.add_ons.collision_manager import CollisionManager
from tdw.librarian import ModelLibrarian
from tdw.librarian import MaterialLibrarian
import shutil
import itertools
from tdw.output_data import Raycast
import copy
from tdw.add_ons.interior_scene_lighting import InteriorSceneLighting

# Initiate a tdw server:
# sudo nohup Xorg :4 -config /etc/X11/xorg.conf

# Connect to the server
# DISPLAY=:4 ./TDW.x86_64 -port 1071

# Run this script
# python3 generate_counting_continuous_tone.py --output_path ./output

# TODO:
# 1. reconstrcut the code.
# 2. remove the default light in the scenes.
# 3. use other materials.
# 4. add questions and answers to the json file.
# 5. solve the lighting issue for first picture.


def get_floor_height(controller: Controller) -> float:
    raycast_command = {
        "$type": "send_raycast",
        "origin": {"x": 0, "y": 2.5, "z": 0},  
        "direction": {"x": 0, "y": -1, "z": 0},  
        "id": 0,
        "collision_types": ["environment"]  
    }
    
    response = controller.communicate([raycast_command])
    
    for res in response:
        r = Raycast(res)  
        if r.get_hit():
            hit_position = r.get_point()
            return hit_position[1]  
    
    # If no hit is detected, return a default floor height
    return 0

def avoid_adjacency(position, positions):
    while True:
        adjacent_flag = False
        for prev_position in positions:
            if abs(position["z"] - prev_position["z"]) < 0.2:
                position["z"] = random.uniform(-0.35, 0.35)
                adjacent_flag = True
                break
            if abs(position["x"] - prev_position["x"]) < 0.2:
                position["x"] = random.uniform(-0.8, 0.8)
                adjacent_flag = True
                break
        
        if adjacent_flag == False:
            break

def main(args):
    output_path = args.output_path
    os.makedirs(output_path, exist_ok=True) 

    c = Controller(launch_build=False, port=1071)

    # Add interior lighting
    interior_lighting = InteriorSceneLighting()
    c.add_ons.append(interior_lighting)  

    # Define defalut camera views
    camera_positions = {
        "top": {"x": 0, "z": 0, "y": 3.0},
        "left": {"x": -2.0, "z": 0, "y": 1.0},
        "front": {"x": 0, "z": -2.0, "y": 1.0},
    }

    # Define scenes
    scenes = ["tdw_room", "monkey_physics_room", "box_room_2018"]

    tables = {"marble_table": 0.5, "trapezoidal_table": 0.6, "small_table_green_marble": 1.4}

    # Define object colors
    object_colors = {
        "red": {
            "dark_red": {"r": 0.4, "g": 0.0, "b": 0.0},  
            "medium_red": {"r": 0.8, "g": 0.1, "b": 0.1},  
            # "light_red": {"r": 1.0, "g": 0.6, "b": 0.6}   
        },
        "green": {
            "dark_green": {"r": 0.0, "g": 0.4, "b": 0.0},  
            "medium_green": {"r": 0.2, "g": 0.8, "b": 0.2},  
            # "light_green": {"r": 0.6, "g": 1.0, "b": 0.6}   
        },
        "yellow": {
            "dark_yellow": {"r": 0.6, "g": 0.6, "b": 0.0},  
            "medium_yellow": {"r": 0.9, "g": 0.9, "b": 0.1},  
            # "light_yellow": {"r": 1.0, "g": 1.0, "b": 0.6}
        },
        "blue": {
            "dark_blue": {"r": 0.0, "g": 0.0, "b": 0.4},  
            "medium_blue": {"r": 0.1, "g": 0.1, "b": 0.8},  
            # "light_blue": {"r": 0.6, "g": 0.6, "b": 1.0}   
        },
        "purple": {
            "dark_purple": {"r": 0.3, "g": 0.0, "b": 0.3},  
            "medium_purple": {"r": 0.5, "g": 0.1, "b": 0.5},  
            # "light_purple": {"r": 0.8, "g": 0.6, "b": 0.8}  
        },
        "cyan": {
            "dark_cyan": {"r": 0.0, "g": 0.4, "b": 0.4},  
            "medium_cyan": {"r": 0.1, "g": 0.8, "b": 0.8},  
            # "light_cyan": {"r": 0.6, "g": 1.0, "b": 1.0}   
        },
        "lime": {
            "dark_lime": {"r": 0.4, "g": 0.6, "b": 0.0},  
            "medium_lime": {"r": 0.6, "g": 0.9, "b": 0.1},  
            # "light_lime": {"r": 0.8, "g": 1.0, "b": 0.4}   
        }
    }

    # Define objects
    special_lib = ['prim_cube', 'prim_cyl', 'prim_sphere']
    shape_tuples = list(itertools.combinations(special_lib, 2))

    # object_materials = ["metal_brushed_copper", "limestone_white", "glass_chopped_strands"]
    object_materials = ["limestone_white", "glass_chopped_strands"]

    images_info = {}
    images_info["shape_section"] = []    

    image_id = 0

    # Add CollisionManager to track object collisions
    collision_manager = CollisionManager(enter=True, exit=True, stay=True)
    c.add_ons.append(collision_manager)

    for scene in tqdm(scenes, desc="Processing scenes"):
        interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
        for shape_tuple in tqdm(shape_tuples, desc="Processing shapes", leave=False):
            for color_genre in tqdm(object_colors, desc="Processing color genres", leave=False):
                color_tuples = list(itertools.permutations(object_colors[color_genre].items(), 2))
                for color_tuple in tqdm(color_tuples, desc="Processing colors", leave=False):
                    for material in tqdm(object_materials, desc="Processing materials", leave=False):
                        for table, table_height in tqdm(tables.items(), desc="Processing tables", leave=False):
                            for _ in range(1):
                                # General rendering configurations
                                commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]},
                                            {"$type": "set_render_quality", "render_quality": args.render_quality}]

                                # Initialize scene
                                commands.append(c.get_add_scene(scene))
                                c.communicate(commands)

                                # Add table
                                table_id = c.get_unique_id()
                                commands.extend(c.get_add_physics_object(model_name=table,
                                            library="models_core.json",
                                            object_id=table_id,
                                            scale_factor={"x": 1.5, "y": 1.5, "z": 1.5},
                                            position={"x": 0, "y": 0, "z": 0}))
                                try:
                                    c.communicate(commands)
                                except Exception as e:
                                    print(f"Error communicating with TDW: {e}")

                                # Setup camera
                                if table:
                                    camera_positions["left"]["y"] = table_height + 0.5
                                    camera_positions["front"]["y"] = table_height + 0.5

                                if scene == "monkey_physics_room":
                                    camera_positions["top"]["y"] = 2.5
                                    camera_positions["left"]["x"] = -2.5
                                    camera_positions["front"]["z"] = -2.5

                                image_info = {}
                                objects_info = []
                                positions = []

                                (color_name_1, color_1), (color_name_2, color_2) = color_tuple

                                obj_type = 0
   

                                for object_name in tqdm(shape_tuple, desc="Processing objects", leave=False):
                                    lib = "models_special.json"
                                    model_record = ModelLibrarian(lib).get_record(object_name)

                                    color = color_1 if obj_type == 0 else color_2
                                    color_name = color_name_1 if obj_type == 0 else color_name_2

                                    # for _ in range(obj_num):
                                    object_id = c.get_unique_id()

                                    position = {
                                        "x": random.uniform(-0.8, 0.8),
                                        "y": table_height,
                                        "z": random.uniform(-0.35, 0.35)
                                    }

                                    if positions == []:
                                        positions.append(position)
                                    else:
                                        avoid_adjacency(position, positions)
                                        positions.append(position)

                                    if object_name == "prim_cyl" and table == "small_table_green_marble":
                                        position["y"] += 0.05

                                    scale = random.uniform(0.2, 0.25)
                                    scale = round(scale, 2)

                                    # Place object with physics and check for collisions
                                    commands.extend(c.get_add_physics_object(model_name=object_name,
                                                                        library=lib,
                                                                        position=position,
                                                                        default_physics_values=False,
                                                                        scale_factor={"x": scale, "y": scale, "z": scale},
                                                                        object_id=object_id))
                                    
                                    # Set the object's material
                                    commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=material, object_id=object_id))
                                    commands.append({
                                        "$type": "set_color",
                                        "id": object_id,
                                        "color": color  
                                    })

                                    # Record object info
                                    object_info = {
                                            "type": object_name,
                                            "material": material,
                                            "color": color_name,
                                            "size": scale}

                                    # Record object info
                                    objects_info.append(object_info)

                                    obj_type += 1

                                for camera_position in tqdm(camera_positions, desc="Processing camera positions", leave=False):
                                    for add_on in c.add_ons:
                                        if isinstance(add_on, ThirdPersonCamera):
                                            c.add_ons.remove(add_on)

                                    camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=55)
                                    if scene == "monkey_physics_room" and camera_position == "top" and table == "small_table_green_marble":
                                        camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=80)
                                    elif scene == "monkey_physics_room":
                                        camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=60)
                                    elif scene == "box_room_2018" and camera_position == "top" and table == "small_table_green_marble":
                                        camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=75)
                                    
                                    c.add_ons.append(camera)

                                    # Add the ImageCapture add-on only after all objects have been placed
                                    image_folder = f"{output_path}/original"
                                    os.makedirs(image_folder, exist_ok=True)
                                    c.add_ons.append(ImageCapture(path=image_folder, avatar_ids=[camera.avatar_id], png=True))

                                    # Render the image
                                    c.communicate(commands)

                                    image_info["image_path"] = f"{scene}_{camera_position}_{image_id}.png"
                                    image_info["scene"] = scene
                                    image_info["camera_view"] = camera.avatar_id
                                    image_info["objects_info"] = objects_info
                                    image_info["table"] = table

                                    images_info["shape_section"].append(copy.deepcopy(image_info))

                                    object_shape_1 = objects_info[0]["type"].split("_")[1]
                                    object_shape_1 = "cylinder" if object_shape_1 == "cyl" else object_shape_1
                                    object_shape_2 = objects_info[1]["type"].split("_")[1]
                                    object_shape_2 = "cylinder" if object_shape_2 == "cyl" else object_shape_2

                                    images_info["shape_section"][-1]["question"] = f"Which object has a deeper color in the image, the {object_shape_1} or the {object_shape_2}? Answer with the letter of your choice: A. {object_shape_1} B. {object_shape_2} C. The same"
                                    images_info["shape_section"][-1]["gt_answer"] = "A" if color_name_1.split("_")[0] == "dark" else "B"

                                    if color_name_1.split("_")[0] == "dark" and color_name_1.split("_")[1] == "medium":
                                        images_info["shape_section"][-1]["gt_answer"] = "A"
                                    elif color_name_1.split("_")[0] == "medium" and color_name_1.split("_")[1] == "dark":
                                        images_info["shape_section"][-1]["gt_answer"] = "B"
                                    else:
                                        images_info["shape_section"][-1]["gt_answer"] = "C"

                                    # Copy image
                                    source_path = f"{image_folder}/{camera_position}/img_0000.png"
                                    destination_path = f"{output_path}/{image_info['image_path']}"
                                    shutil.copy(source_path, destination_path)

                                    # Reset for the next loop
                                    c.add_ons.clear() 
                                    c.communicate({"$type": "destroy_all_objects"})
                                    c.communicate(TDWUtils.create_empty_room(12, 12))

                                image_id += 1

    # Save object info to JSON
    with open(os.path.join(output_path, "continuous_quantity_tone.json"), 'w') as f:
        json.dump(images_info, f, indent=4)

    print(f"{len(images_info['shape_section'])} images generated.")

    # Clean up
    c.communicate({"$type": "terminate"})

if __name__ == "__main__":
    random.seed(42)
    parser = argparse.ArgumentParser(description="Generate a dataset with different object configurations.")
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    parser.add_argument("--output_path", type=str, default="./outputtone", help="The path to save the outputs to.")
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")

    args = parser.parse_args()
    main(args)
