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
# python3 generate_counting_continuous_smoothness.py --output_path ./output

# TODO:
# 1. reconstrcut the code.
# 2. remove the default light in the scenes.


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


    object_colors = {
        "red": {"r": 1.0, "g": 0.2, "b": 0.2},  # Red
        "green": {"r": 0.2, "g": 1.0, "b": 0.2},  # Green
        "yellow": {"r": 1.0, "g": 1.0, "b": 0.0}   # Yellow
    }

    
    color_tuples = list(itertools.combinations(object_colors.items(), 2))

    special_lib = ['prim_cone', 'prim_cube', 'prim_cyl', 'prim_sphere']

    object_materials = ["metal_brushed_copper", "limestone_white", "sand_covered_stone_ground"]
    material_tuples = list(itertools.permutations(object_materials, 2))

    images_info = {}

    images_info["shape_section"] = []    
    images_info["color_section"] = []

    image_id = 0

    # Add CollisionManager to track object collisions
    collision_manager = CollisionManager(enter=True, exit=True, stay=True)
    c.add_ons.append(collision_manager)

    for scene in tqdm(scenes, desc="Processing scenes"):
        interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
        for camera_position in tqdm(camera_positions, desc="Processing camera positions", leave=False):
            for color_tuple in tqdm(color_tuples, desc="Processing colors", leave=False):
                for material_tuple in tqdm(material_tuples, desc="Processing materials", leave=False):
                    for _ in range(2):
                        selected_obj_names = random.sample(special_lib, 2)

                        # General rendering configurations
                        commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]},
                                    {"$type": "set_render_quality", "render_quality": args.render_quality}]

                        # Initialize scene
                        commands.append(c.get_add_scene(scene))
                        c.communicate(commands)

                        # Get floor height
                        floor_height = get_floor_height(c)

                        # Setup camera
                        if scene == "monkey_physics_room":
                                camera_positions = {
                                    "top": {"x": 0, "z": -0.2, "y": 2.5},
                                    "left": {"x": -2.6, "z": 0, "y": 0.5},
                                    "right": {"x": 2.6, "z": 0, "y": 0.5},
                                    "front": {"x": 0, "z": -2.6, "y": 0.5},
                                    "back": {"x": 0, "z": 2.6, "y": 0.5},
                                }

                        camera = ThirdPersonCamera(position=camera_positions[camera_position], avatar_id=camera_position, look_at={"x": 0, "y": 0, "z": 0})
                        c.add_ons.append(camera)

                        (color_name_1, color_1), (color_name_2, color_2) = color_tuple

                        # Add the ImageCapture add-on only after all objects have been placed
                        image_folder = f"{output_path}/{scene}/{material_tuple[0]}_{material_tuple[1]}_{camera_position}_{color_1['r']}_{color_1['g']}_{color_1['b']}_{color_2['r']}_{color_2['g']}_{color_2['b']}/{image_id}"
                        os.makedirs(image_folder, exist_ok=True)
                        c.add_ons.append(ImageCapture(path=image_folder, avatar_ids=[camera.avatar_id], png=True))

                        obj_type = 0

                        image_info = {}
                        objects_info = []

                        positions = []

                        for object_name in tqdm(selected_obj_names, desc="Processing objects", leave=False):
                            lib = "models_special.json"
                            model_record = ModelLibrarian(lib).get_record(object_name)

                            # obj_num = obj_num_1 if obj_type == 0 else obj_num_2
                            material = material_tuple[0] if obj_type == 0 else material_tuple[1]
                            color = color_1 if obj_type == 0 else color_2
                            color_name = color_name_1 if obj_type == 0 else color_name_2

                            # for _ in range(obj_num):
                            object_id = c.get_unique_id()

                            position = {
                                "x": random.uniform(-0.8, 0.8),
                                "y": floor_height +0.03,
                                "z": random.uniform(-0.8, 0.8)
                            }

                            if scene == "tdw_room":
                                position["y"] += 0.01
                            

                            if positions == []:
                                positions.append(position)
                            else:
                                if camera_position == "left" or camera_position == "right" or camera_position == "top":
                                    while abs(position["z"] - positions[0]["z"]) < 0.3:
                                        position["z"] = random.uniform(-0.8, 0.8)
                                elif camera_position == "front" or camera_position == "back":
                                    while abs(position["x"] - positions[0]["x"]) < 0.3:
                                        position["x"] = random.uniform(-0.8, 0.8)

                                positions.append(position)

                            # Place object with physics and check for collisions
                            commands.extend(c.get_add_physics_object(model_name=object_name,
                                                                library=lib,
                                                                position=position,
                                                                default_physics_values=False,
                                                                scale_factor={"x": 0.4, "y": 0.4, "z": 0.4},
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
                                # "obj_num": obj_num,
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
                        # images_info["material_section"].append(copy.deepcopy(image_info))

                        object_shape_1 = objects_info[0]["name"].split("_")[1]
                        object_shape_1 = "cylinder" if object_shape_1 == "cyl" else object_shape_1
                        object_shape_2 = objects_info[1]["name"].split("_")[1]
                        object_shape_2 = "cylinder" if object_shape_2 == "cyl" else object_shape_2
                        images_info["shape_section"][-1]["question"] = f"Which object has a smoother surface in the image, the {object_shape_1} or the {object_shape_2}? Answer with the letter of your choice: A. {object_shape_1} B. {object_shape_2}"
                        images_info["shape_section"][-1]["gt_answer"] = "A" if object_materials.index(objects_info[0]["material"]) < object_materials.index(objects_info[1]["material"]) else "B"

                        object_color_1 = objects_info[0]["color"]
                        object_color_2 = objects_info[1]["color"]                    
                        images_info["color_section"][-1]["question"] = f"Which object has a smoother surface in the image, the {object_color_1} one or the {object_color_2} one? Answer with the letter of your choice: A. {object_color_1} B. {object_color_2}"
                        images_info["color_section"][-1]["gt_answer"] = "A" if object_materials.index(objects_info[0]["material"]) < object_materials.index(objects_info[1]["material"]) else "B"        

                        # object_material_1 = objects_info[0]["material"].split("_")[0]
                        # object_material_2 = objects_info[1]["material"].split("_")[0]
                        # images_info["material_section"][-1]["question"] = f"Which material has more objects in the image, {object_material_1} or {object_material_2}? Answer with the letter of your choice: A. {object_material_1} B. {object_material_2}"
                        # images_info["material_section"][-1]["gt_answer"] = "A" if object_materials.index(objects_info[0]["material"]) < object_materials.index(objects_info[1]["material"]) else "B"          

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
    with open(os.path.join(output_path, "continuous_quantity_smoothness.json"), 'w') as f:
        json.dump(images_info, f, indent=4)

    print(f"{len(images_info['shape_section'])} images generated.")

    # Clean up
    c.communicate({"$type": "terminate"})

if __name__ == "__main__":
    random.seed(42)
    parser = argparse.ArgumentParser(description="Generate a dataset with different object configurations.")
    parser.add_argument("--screen_size", type=int, nargs='+', default=(1024, 1024), help="Width and Height of Screen. (W, H)")
    parser.add_argument("--output_path", type=str, default="./output", help="The path to save the outputs to.")
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")

    args = parser.parse_args()
    main(args)
