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
# python3 generate_counting_relative.py --output_path ./output


def generate_color_shape_distribution(color_tuple, shape_tuple, combined_tuples):
    # same shape, two random colors
    color_shape_dic = {}
    colors_chosen = random.sample(color_tuple, 2)
    shape_chosen = random.sample(shape_tuple, 2)
    # shape_chosen = ["torus"] + random.sample([shape for shape in shape_tuple if shape != "torus"], 1)

    for color_shape_tuple in combined_tuples:
        if (color_shape_tuple[0] == colors_chosen[0] and color_shape_tuple[1] == shape_chosen[0]) \
            or (color_shape_tuple[0] == colors_chosen[1] and color_shape_tuple[1] == shape_chosen[1]):
            color_shape_dic[color_shape_tuple] = 1
        else:
            color_shape_dic[color_shape_tuple] = 0
    return color_shape_dic



def main(args):
    output_path = args.output_path
    os.makedirs(output_path, exist_ok=True) 

    c = Controller(launch_build=False, port=1071)

    # Add interior lighting
    interior_lighting = InteriorSceneLighting()
    c.add_ons.append(interior_lighting) 

    # Define camera views
    # camera_positions = {
    #     "top": {"x": 0, "z": 0, "y": 3.0},
    #     "left": {"x": -3.0, "z": 0, "y": 0.5},
    #     "right": {"x": 3.0, "z": 0, "y": 0.5},
    #     "front": {"x": 0, "z": -3.0, "y": 0.5},
    #     "back": {"x": 0, "z": 3.0, "y": 0.5},
    # }
    camera_positions = {
        "top": {"x": 0, "z": 0, "y": 3.0},
        "left": {"x": -3.0, "z": 0, "y": 0.5},
        "front": {"x": 0, "z": -3.0, "y": 0.5}
    }

    # Define scenes
    scenes = ["tdw_room", "monkey_physics_room", "box_room_2018"]

    # Define tables
    tables = {"marble_table": 0.45, "trapezoidal_table": 0.55, "small_table_green_marble": 1.33}

    # Define colors 
    # JCY: may need more colors
    object_colors = {
        "red": {"r": 1.0, "g": 0.2, "b": 0.2},  # Red
        "green": {"r": 0.2, "g": 1.0, "b": 0.2},  # Green
        "blue": {"r": 0.2, "g": 0.2, "b": 1.0}    # Blue
        # "yellow": {"r": 1.0, "g": 1.0, "b": 0.0}    # Yellow
    }
    color_tuples = list(itertools.combinations(object_colors.keys(), 2))

    # Define objects
    # special_lib = ['prim_cube', 'prim_cyl', 'prim_sphere']
    special_lib = ['torus', 'prim_cyl', 'prim_sphere']
    shape_tuples = [('torus', shape) for shape in special_lib if shape != 'torus']
    # shape_tuples = list(itertools.combinations(special_lib, 2))

    # Define materials
    object_materials = ["limestone_white", "glass_chopped_strands", "sand_covered_stone_ground"]

    # Initialize image info
    images_info = {}
    # images_info["shape_section"] = []    
    # images_info["color_section"] = []
    # images_info["material_section"] = []
    images_info["position_section"] = []    

    # Add CollisionManager to track object collisions
    collision_manager = CollisionManager(enter=True, exit=True, stay=True)
    c.add_ons.append(collision_manager)

    # Clear the output folder
    for filename in os.listdir(output_path):
        file_path = os.path.join(output_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)


    image_id = 0
    output = ""
    for scene in tqdm(scenes, desc="Processing scenes"):
        interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
        for shape_tuple in tqdm(shape_tuples, desc="Processing shapes", leave=False):
            for color_tuple in tqdm(color_tuples, desc="Processing colors", leave=False):
                for material in tqdm(object_materials, desc="Processing materials", leave=False):
                    for table, table_height in tqdm(tables.items(), desc="Processing tables", leave=False):
                        for question_type in ['yes', 'no']:

                            combined_tuples = list(itertools.product(color_tuple, shape_tuple))
                            
                            # while True:
                            #     color_shape_dic = generate_color_shape_distribution(combined_tuples)
                            #     if validate_color_shape_distribution(color_shape_dic, color_tuple, shape_tuple):
                            #         break

                            color_shape_dic = generate_color_shape_distribution(color_tuple, shape_tuple, combined_tuples)

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
                                # camera_positions["right"]["y"] = table_height + 0.5
                                camera_positions["front"]["y"] = table_height + 0.5
                                # camera_positions["back"]["y"] = table_height + 0.5

                            if scene == "monkey_physics_room":
                                camera_positions["top"]["y"] = 2.5
                                camera_positions["left"]["x"] = -2.5
                                # camera_positions["right"]["x"] = 2.5
                                camera_positions["front"]["z"] = -2.5
                                # camera_positions["back"]["z"] = 2.5



                            x1 = random.uniform(-0.1, 0.1)
                            x2 = x1 + 0.2 * random.choice([-1, 1])
                            
                            z1 = 0
                            z2 = z1 + 0.2 * random.choice([-1, 1])


                            image_info = {}
                            objects_info = []
                            positions = []
                            output += "\nOn a table:\n"

                            object_num = 0
                            object_full_name = ["object", "object"]
                            color_record = ""
                            for (color_name, object_name), obj_num in tqdm(color_shape_dic.items(), desc="Processing objects", leave=False):
                                if obj_num == 0:
                                    continue
                                
                                if object_name in ['prim_cube', 'prim_cyl', 'prim_sphere']:
                                    lib = "models_special.json"
                                    model_record = ModelLibrarian(lib).get_record(object_name)
                                else:
                                    lib = "models_flex.json"
                                    model_record = ModelLibrarian(lib).get_record(object_name)

                                # for _ in range(obj_num):
                                object_id = c.get_unique_id()

                                if object_num == 0:
                                    position = {
                                        "x": x1,
                                        "y": table_height+0.1,
                                        "z": z1
                                    }
                                else:
                                    position = {
                                        "x": x2,
                                        "y": table_height+0.1,
                                        "z": z2
                                    }


                                if positions == []:
                                    positions.append(position)
                                else:
                                    # avoid_adjacency(position, positions)
                                    positions.append(position)

                                color = object_colors[color_name]

                                if object_name == "prim_cyl" and table == "small_table_green_marble":
                                    position["y"] += 0.05

                                # Adjust the size of the object
                                # scale = random.uniform(0.1, 0.15)
                                # scale = round(scale, 2)

                                SIZE_SCALE = random.uniform(0.1, 0.15)
                                if question_type == "yes":
                                    if object_name == "prim_cyl" or object_name == "prim_sphere":
                                        scale = 1 * SIZE_SCALE
                                    elif object_name == "torus":
                                        scale = 2 * SIZE_SCALE
                                elif question_type == "no":
                                    if object_name == "prim_cyl" or object_name == "prim_sphere":
                                        scale = 2 * SIZE_SCALE
                                    elif object_name == "torus":
                                        scale = 1 * SIZE_SCALE
                                

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

                                object_info = {
                                    "type": object_name,
                                    "material": material,
                                    "color": color_name,
                                    "size": scale}

                                # Record object info
                                objects_info.append(object_info)

                                
                                if object_name == "prim_cube":
                                    object_full_name[object_num] = "cube"
                                elif object_name == "prim_cyl":
                                    object_full_name[object_num] = "cylinder"
                                elif object_name == "prim_sphere":
                                    object_full_name[object_num] = "sphere"
                                elif object_name == "torus":
                                    object_full_name[object_num] = "torus"
                                
                                if object_name != "torus":
                                    color_record = color_name

                                output += color_name + " " + object_full_name[object_num] + " " + str(obj_num) + "\n"

                                object_num += 1


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

                                # images_info["shape_section"].append(copy.deepcopy(image_info))
                                # images_info["color_section"].append(copy.deepcopy(image_info))
                                # images_info["material_section"].append(copy.deepcopy(image_info))
                                images_info["position_section"].append(copy.deepcopy(image_info))


                                name = [string for string in object_full_name if string != "torus"][0]
                                images_info["position_section"][-1]["question"] = f"Can the {color_record} {name} be placed into the bounded space from the top?"
                                if question_type == "yes":
                                    images_info["position_section"][-1]["gt_answer"] = "Yes."
                                elif question_type == "no":
                                    images_info["position_section"][-1]["gt_answer"] = "No."     

                                # Copy image
                                source_path = f"{image_folder}/{camera_position}/img_0000.png"
                                destination_path = f"{output_path}/{image_info['image_path']}"
                                shutil.copy(source_path, destination_path)


                                # Reset for the next loop
                                c.add_ons.clear() 
                                c.communicate({"$type": "destroy_all_objects"})
                                c.communicate(TDWUtils.create_empty_room(12, 12))

                            image_id += 1

                    #     break
                    # break
        #         break
        #     break
        # break

    # Save object info to JSON
    with open(os.path.join(output_path, "position.json"), 'w') as f:
        json.dump(images_info, f, indent=4)

    print(f"{len(images_info['position_section'])} images generated.")
    print(output)

    # Clean up
    c.communicate({"$type": "terminate"})

if __name__ == "__main__":
    random.seed(39)
    parser = argparse.ArgumentParser(description="Generate a dataset with different object configurations.")
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    parser.add_argument("--output_path", type=str, default="./position", help="The path to save the outputs to.")
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")

    args = parser.parse_args()
    main(args)
