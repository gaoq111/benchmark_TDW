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
# DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port 1071

# Connect to the server
# DISPLAY=:4 ./TDW.x86_64 -port 1071

# Run this script
# python3 generate_counting_discrete.py --output_path ./output

# TODO:
# 1. reconstrcut the code.
# 2. remove defalut light in the scenes.
# 3. determine how to describe the color (yellow or brown)
# 4. use 3 camera views instead of 5.
# 5. make sure the number of questions is between 600 and 2000.
# 6. for each question, use one color and two shapes.


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

def main(args):
    output_path = args.output_path
    os.makedirs(output_path, exist_ok=True) 

    c = Controller(launch_build=False, port=1071)

    # Add interior lighting
    interior_lighting = InteriorSceneLighting()
    c.add_ons.append(interior_lighting) 

    # Define camera views
    camera_positions = {
        "top": {"x": 0, "z": 0, "y": 3.0},
        "left": {"x": -3.0, "z": 0, "y": 0.5},
        "right": {"x": 3.0, "z": 0, "y": 0.5},
        "front": {"x": 0, "z": -3.0, "y": 0.5},
        "back": {"x": 0, "z": 3.0, "y": 0.5},
    }

    # Define scenes
    scenes = ["tdw_room", "monkey_physics_room", "box_room_2018"]

    # Define tables
    tables = {"marble_table": 0.45, "trapezoidal_table": 0.55, "small_table_green_marble": 1.33}

    # Define colors
    object_colors = {
        "red": {"r": 1.0, "g": 0.2, "b": 0.2},  # Red
        "green": {"r": 0.2, "g": 1.0, "b": 0.2},  # Green
        "yellow": {"r": 1.0, "g": 1.0, "b": 0.0}   # Yellow
    }
    color_tuples = list(itertools.combinations(object_colors.items(), 2))

    # Define objects
    special_lib = ['prim_cone', 'prim_cube', 'prim_cyl', 'prim_sphere']

    # Define materials
    object_materials = ["limestone_white", "metal_brushed_copper", "wood_american_cherry"]
    material_tuples = list(itertools.permutations(object_materials, 2))

    # Initialize image info
    images_info = {}
    images_info["shape_section"] = []    
    images_info["color_section"] = []
    images_info["material_section"] = []

    # Add CollisionManager to track object collisions
    collision_manager = CollisionManager(enter=True, exit=True, stay=True)
    c.add_ons.append(collision_manager)

    image_id = 0

    for scene in tqdm(scenes, desc="Processing scenes"):
        interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
        for camera_position in tqdm(camera_positions, desc="Processing camera positions", leave=False):
            for color_tuple in tqdm(color_tuples, desc="Processing colors", leave=False):
                for material_tuple in tqdm(material_tuples, desc="Processing materials", leave=False):
                    for table, table_height in tqdm(tables.items(), desc="Processing tables", leave=False):
                        for _ in range(1):
                            selected_obj_names = random.sample(special_lib, 2)

                            # General rendering configurations
                            commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]},
                                        {"$type": "set_render_quality", "render_quality": args.render_quality}]

                            # Initialize scene
                            commands.append(c.get_add_scene(scene))
                            c.communicate(commands)

                            # Get floor height
                            floor_height = get_floor_height(c)

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
                                camera_positions["right"]["y"] = table_height + 0.5
                                camera_positions["front"]["y"] = table_height + 0.5
                                camera_positions["back"]["y"] = table_height + 0.5

                            if scene == "monkey_physics_room":
                                camera_positions["top"]["y"] = 2.5
                                camera_positions["left"]["x"] = -2.5
                                camera_positions["right"]["x"] = 2.5
                                camera_positions["front"]["z"] = -2.5
                                camera_positions["back"]["z"] = 2.5

                            camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=55)

                            if scene == "monkey_physics_room" and camera_position == "top" and table == "small_table_green_marble":
                                camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=80)
                            elif scene == "monkey_physics_room":
                                camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": table_height, "z": 0}, field_of_view=60)

                            c.add_ons.append(camera)

                            # Get colors
                            (color_name_1, color_1), (color_name_2, color_2) = color_tuple

                            # Add the ImageCapture add-on only after all objects have been placed
                            image_folder = f"{output_path}/{scene}/{material_tuple[0]}_{material_tuple[1]}_{camera_position}_{color_1['r']}_{color_1['g']}_{color_1['b']}_{color_2['r']}_{color_2['g']}_{color_2['b']}/{image_id}"
                            os.makedirs(image_folder, exist_ok=True)
                            c.add_ons.append(ImageCapture(path=image_folder, avatar_ids=[camera.avatar_id], png=True))

                            # Generate num of objects
                            obj_num_1 = random.randint(1, 4)
                            obj_num_2 = obj_num_1
                            while obj_num_2 == obj_num_1:
                                obj_num_2 = random.randint(1, 4)

                            obj_type = 0

                            image_info = {}
                            objects_info = []
                            
                            for object_name in tqdm(selected_obj_names, desc="Processing objects", leave=False):
                                lib = "models_special.json"
                                model_record = ModelLibrarian(lib).get_record(object_name)

                                obj_num = obj_num_1 if obj_type == 0 else obj_num_2
                                material = material_tuple[0] if obj_type == 0 else material_tuple[1]
                                color = color_1 if obj_type == 0 else color_2
                                color_name = color_name_1 if obj_type == 0 else color_name_2

                                for _ in range(obj_num):
                                    object_id = c.get_unique_id()

                                    position = {
                                        "x": random.uniform(-0.8, 0.8),
                                        "y": table_height,
                                        "z": random.uniform(-0.4, 0.4)
                                    }

                                    if object_name == "prim_cyl" and table == "small_table_green_marble":
                                        position["y"] += 0.05

                                    # Place object with physics and check for collisions
                                    commands.extend(c.get_add_physics_object(model_name=object_name,
                                                                        library=lib,
                                                                        position=position,
                                                                        default_physics_values=False,
                                                                        scale_factor={"x": 0.15, "y": 0.15, "z": 0.15},
                                                                        object_id=object_id))
                                    
                                    # Set the object's material
                                    commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=material, object_id=object_id))
                                    commands.append({
                                        "$type": "set_color",
                                        "id": object_id,
                                        "color": color  
                                    })

                                # Record object info
                                objects_info.append({
                                    "name": object_name,
                                    "obj_num": obj_num,
                                    "material": material,
                                    "color": color_name
                                })

                                obj_type += 1

                            # Render the image
                            c.communicate(commands)

                            image_info["image_path"] = f"{scene}_{camera_position}_{image_id}.png"
                            image_info["scene"] = scene
                            image_info["camera_view"] = camera.avatar_id
                            image_info["objects_info"] = objects_info

                            images_info["shape_section"].append(copy.deepcopy(image_info))
                            images_info["color_section"].append(copy.deepcopy(image_info))
                            images_info["material_section"].append(copy.deepcopy(image_info))

                            object_shape_1 = objects_info[0]["name"].split("_")[1]
                            object_shape_1 = "cylinder" if object_shape_1 == "cyl" else object_shape_1
                            object_shape_2 = objects_info[1]["name"].split("_")[1]
                            object_shape_2 = "cylinder" if object_shape_2 == "cyl" else object_shape_2
                            images_info["shape_section"][-1]["question"] = f"Which are more numerous in the image, {object_shape_1}s or {object_shape_2}s? Answer with the letter of your choice: A. {object_shape_1}s B. {object_shape_2}s"
                            images_info["shape_section"][-1]["gt_answer"] = "A" if objects_info[0]["obj_num"] > objects_info[1]["obj_num"] else "B"

                            object_color_1 = objects_info[0]["color"]
                            object_color_2 = objects_info[1]["color"]                    
                            images_info["color_section"][-1]["question"] = f"Which color has more objects in the image, {object_color_1} or {object_color_2}? Answer with the letter of your choice: A. {object_color_1} B. {object_color_2}"
                            images_info["color_section"][-1]["gt_answer"] = "A" if objects_info[0]["obj_num"] > objects_info[1]["obj_num"] else "B"         

                            object_material_1 = objects_info[0]["material"].split("_")[0]
                            object_material_2 = objects_info[1]["material"].split("_")[0]
                            images_info["material_section"][-1]["question"] = f"Which material has more objects in the image, {object_material_1} or {object_material_2}? Answer with the letter of your choice: A. {object_material_1} B. {object_material_2}"
                            images_info["material_section"][-1]["gt_answer"] = "A" if objects_info[0]["obj_num"] > objects_info[1]["obj_num"] else "B"           

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
    with open(os.path.join(output_path, "discrete_counting_info.json"), 'w') as f:
        json.dump(images_info, f, indent=4)

    print(f"{len(images_info['shape_section'])} images generated.")

    # Clean up
    c.communicate({"$type": "terminate"})

if __name__ == "__main__":
    random.seed(39)
    parser = argparse.ArgumentParser(description="Generate a dataset with different object configurations.")
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    parser.add_argument("--output_path", type=str, default="./output", help="The path to save the outputs to.")
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")

    args = parser.parse_args()
    main(args)
