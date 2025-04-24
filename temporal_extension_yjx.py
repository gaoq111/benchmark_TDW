import itertools
import random
from typing import Literal, Tuple, List, Dict, Any
from tdw_object_utils import *
from task_abstract import AbstractTask
from interface import AVAILABLE_OBJECT, ObjectType, AVAILABLE_MOTION, AVAILABLE_CAMERA_POS, AVAILABLE_COLOR, AVAILABLE_SCENE, AVAILABLE_SCALE_FACTOR
import hydra
import os
from omegaconf import DictConfig
import time
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.librarian import ModelLibrarian
from task_abstract import MoveObject
import cv2
import shutil
import numpy as np
import json
import traceback
from tqdm import tqdm

def numpy_to_python(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [numpy_to_python(item) for item in obj]
    else:
        return obj


def filter_camera_view(motion, camera_view: List[str]):
    """
    We need to filter the camera view based on the motion of the object,
    for example, if the object is moving forward, we need to filter the camera view to exclude the front and back view, since the object's motion is in the same direction
    """
    
    if motion == "forward":
        return list(filter(lambda x: x != "front" and x != "back", camera_view))
    elif motion == "backward":
        return list(filter(lambda x: x != "front" and x != "back", camera_view))
    elif motion == "left":
        return list(filter(lambda x: x != "right" and x != "left", camera_view))
    elif motion == "right":
        return list(filter(lambda x: x != "left" and x != "right", camera_view))
    else:
        return camera_view


def format_dict_to_string(d:dict):
    res = ""
    for key, value in d.items():
        res += f"{key}={value},"
    return res

def get_object_id(object_type:ObjectType):
    TEMPLATE = "{model_name}_pos={position}_rot={rotation}_scale={scale_factor}_texture_scale={texture_scale}_material={material}_color={color}"
    res = TEMPLATE.format(model_name=object_type.model_name,
                          position=format_dict_to_string(object_type.position),
                          rotation=format_dict_to_string(object_type.rotation),
                          scale_factor=format_dict_to_string(object_type.scale_factor),
                          texture_scale=object_type.texture_scale,
                          material=object_type.material,
                          color=format_dict_to_string(object_type.color))
    return res

def get_object_shape_id(object_type:ObjectType):
    TEMPLATE = "{model_name}_color={color}"
    res = TEMPLATE.format(model_name=object_type.model_name,
                          texture_scale=object_type.texture_scale,
                          material=object_type.material,
                          color=format_dict_to_string(object_type.color))
    return res
def get_object(object: ObjectType):
    return {
        "model_name": object.model_name,
        "position": object.position,
        "rotation": object.rotation,
        "scale_factor": object.scale_factor,
        "motion": object.motion,
        "color": object.color_name,
        "material": object.material,
        "texture_scale": object.texture_scale
    }

def add_index_label(img, index):
    # Create a copy of the image to avoid modifying the original
    labeled_img = img.copy()
    
    # Parameters for the text
    font = cv2.FONT_HERSHEY_SIMPLEX
    org = (10, 30)  # Upper left corner
    font_scale = 1
    color = (0, 255, 0)  # Green color
    thickness = 2
    
    # Add a black background to make text more visible
    cv2.rectangle(labeled_img, (5, 5), (50, 40), (0, 0, 0), -1)
    
    # Add the text
    cv2.putText(labeled_img, str(index), org, font, font_scale, color, thickness, cv2.LINE_AA)
    
    return labeled_img

class TemporalExtension(AbstractTask):
    def __init__(self, output_path:str = None,
                 port:int = 1072,
                 display:str = ":4",
                 scene:str = "empty_scene",
                 screen_size:Tuple[int, int] = (1920, 1080),
                 physics:bool = False, # enable physics or not
                 render_quality:int = 10,
                 name:str = "temporal_extension",
                 library:str = "models_core.json",
                 camera: List[str] = AVAILABLE_CAMERA_POS.keys()):
        
        super().__init__(output_path=output_path, port=port, 
                         display=display, scene=scene, 
                         screen_size=screen_size, physics=physics, 
                         render_quality=render_quality, name=name, library=library, camera=camera)
        


        

    def run(self, 
            scene,
            main_obj_list: List[ObjectType] = None,
            fixed_obj_list: List[ObjectType] = None,
            seed: int = 12):
        
        # Add Scene
        self.scene = scene
        self.commands.append(self.c.get_add_scene(scene))


        self.object_list = main_obj_list + fixed_obj_list
        

        self.main_object_names = [obj.model_name for obj in main_obj_list]
        self.fixed_object_names = [obj.model_name for obj in fixed_obj_list]
        self.expr_id = f"scene{seed}"
        
        self.main_object_shaple_ids = [get_object_id(obj) for obj in main_obj_list]
        self.fixed_object_shape_ids = [get_object_id(obj) for obj in fixed_obj_list]
        
        try:
            move_object_dict = {}
            
            for obj in self.object_list:
                special_lib = []
                for record in ModelLibrarian("models_special.json").records:
                    special_lib.append(record.name)
                if obj.model_name in special_lib:
                    obj.library = "models_special.json"
                else:
                    obj.library = "models_core.json"
                
                obj.model_record = ModelLibrarian(obj.library).get_record(obj.model_name)
                object_id = self.c.get_unique_id()
                obj.object_id = object_id
                print(f"Object name: {obj.model_name}, with id = {obj.object_id}")
                
                # attention: here the gravity should be turned off                
                self.commands.extend(self.c.get_add_physics_object(model_name=obj.model_name,
                                                library=obj.library,
                                                gravity=False,
                                                position=obj.position,
                                                rotation=obj.rotation,
                                                scale_factor=obj.scale_factor if obj.scale_factor is not None else {"x": 1, "y": 1, "z": 1},
                                                object_id=obj.object_id))
                if obj.material is not None:
                    print(obj.material)
                    self.commands.append(self.c.get_add_material(material_name=obj.material))
                    self.commands.extend(TDWUtils.set_visual_material(c=self.c, substructure=obj.model_record.substructure, material=obj.material, object_id=obj.object_id))
                
                self.commands.append({"$type": "set_color",
                                    "color": obj.color,
                                    "id": obj.object_id})
                

                move_object_dict[obj.object_id] = MoveObject(obj)
                
                print(f"Object {obj.model_name} = {obj.object_id} added")
            
            main_obj = main_obj_list[0]
            other_objs = fixed_obj_list
            
            self.camera = filter_camera_view(motion = main_obj.motion, camera_view=self.camera)
            self.c.communicate(self.commands)
            print("commands for cameras completed")
            
            if os.path.exists(os.path.join(self.output_path, self.name, self.expr_id)):
                shutil.rmtree(os.path.join(self.output_path, self.name, self.expr_id))
            
            for cam in self.camera:
                self.c.add_ons.append(get_cameras(cam, scene))
            print("cameras added: ", self.camera)

            capture = ImageCapture(avatar_ids=self.camera, path=os.path.join(self.output_path, self.name, self.expr_id), png=True)
            self.c.add_ons.append(capture)
            
            MOVE_STEP = 6
            
            move_dict = {}
            
            #only works for two objects
            first_move_obj = self.object_list[0]
            second_move_obj = self.object_list[1]
            valid = False
            diff = random.randint(2, 5)

            while not valid:
                # Generate four sorted unique values from MOVE_STEP
                [start1, start2] = sorted(np.random.choice(MOVE_STEP, size=2, replace=True))
                if start2 < start1:
                    (t1, t2) = (start1, end1)
                    (start1, end1) = (start2, end2)
                    (start2, end2) = (t1, t2)
                
                # Check if the condition is met
                if abs(abs(end1 - start1) - abs(end2 - start2)) >= 2:
                    valid = True

            move_dict[first_move_obj.object_id] = range(start1, end1 + 1)
            move_dict[second_move_obj.object_id] = range(start2, end2 + 1)
            
            # record who starts moving first and who stops moving first

            print(f"Move Step: {MOVE_STEP}")
            for i in range(MOVE_STEP):
                commands = []
                for obj in self.object_list:
                    if obj.object_id in move_dict:
                        if i in move_dict[obj.object_id]:
                            magnitude = 0.15
                            move_commands = move_object_dict[obj.object_id].move_and_get_commands_only(movement = obj.motion, magnitude=magnitude)
                            commands.extend(move_commands)
                print(f"Step {i} completed")
                self.c.communicate(commands)
            # step1: randomly pick a range,which has length of 4, from (0, 10)

            query_image_index = list(range(MOVE_STEP))
            

            output_res_cam = {
                cam: {
                } for cam in self.camera
            }


            for cam in self.camera:
                output_path_dict = {
                    "query": [],
                }
                for i in query_image_index:
                    output_path_dict["query"].append(os.path.join(self.output_path, self.name, self.expr_id, cam, f"img_{i:04d}.png"))
                    
                output_res_cam[cam]["query"] = output_path_dict["query"] #
                
                
                output_res_cam[cam]["object_move_short"] = {
                    "move_time": start1,
                    "end_time": end1,
                    "model_name": first_move_obj.model_name,
                    "position": first_move_obj.position,
                    "rotation": first_move_obj.rotation,
                    "scale_factor": first_move_obj.scale_factor,
                    "motion": first_move_obj.motion,
                    "color": first_move_obj.color_name,
                    "material": first_move_obj.material,
                    "texture_scale": first_move_obj.texture_scale
                }
                output_res_cam[cam]["object_move_long"] = {
                    "move_time": start2,
                    "end_time": end2,
                    "model_name": second_move_obj.model_name,
                    "position": second_move_obj.position,
                    "rotation": second_move_obj.rotation,
                    "scale_factor": second_move_obj.scale_factor,
                    "motion": second_move_obj.motion,
                    "color": second_move_obj.color_name,
                    "material": second_move_obj.material,
                    "texture_scale": second_move_obj.texture_scale
                }
                output_res_cam[cam]["camera_direction"] = cam
                # output_res_cam[cam]["main_obj"] = {
                #     "model_name": main_obj.model_name,
                #     "position": main_obj.position,
                #     "rotation": main_obj.rotation,
                #     "scale_factor": main_obj.scale_factor,
                #     "motion": main_obj.motion,
                #     "color": main_obj.color_name,
                #     "material": main_obj.material,
                #     "texture_scale": main_obj.texture_scale
                # }
                # output_res_cam[cam]["other_objs"] = [
                #     {
                #         "model_name": obj.model_name,
                #         "position": obj.position,
                #         "rotation": obj.rotation,
                #         "scale_factor": obj.scale_factor,
                #         "motion": obj.motion,
                #         "color": obj.color_name,
                #         "material": obj.material,
                #         "texture_scale": obj.texture_scale
                #     } for obj in other_objs
                # ]
                output_res_cam[cam]["scene"] = self.scene

            # write the item in output_res_cam into jsonl
            with open(os.path.join(self.output_path, self.name, "index.jsonl"), "a") as f:
                for cam in self.camera:
                    json.dump(numpy_to_python(output_res_cam[cam]), f)
                    f.write("\n")
                    
            # we will concate the query imgs in the first line, and the candidates in the second line, and output a img
            # 3 query imgs first line
            # 4 candidates second line
            # make the answer img with boxed with red line

            for cam in self.camera:
                query_imgs = [cv2.imread(img) for img in output_res_cam[cam]["query"]]
                
                # Add index labels to images
                labeled_query_imgs = [add_index_label(img, i) for i, img in enumerate(query_imgs)]
                
                # Concatenate query images horizontally
                ROW_SIZE = 3
                rows = [
                    np.hstack(labeled_query_imgs[i*ROW_SIZE:(i+1)*ROW_SIZE]) for i in range(len(labeled_query_imgs) // ROW_SIZE)
                ]
                final_image = np.vstack(rows)
                
                # Save the final image
                cv2.imwrite(os.path.join(self.output_path, self.name, self.expr_id, cam, "sample.png"), final_image)
                
                # Create MP4 video
                output_video_path = os.path.join(self.output_path, self.name, self.expr_id, cam, "sample_video.avi")
                frame_size = (512, 512)  # Assuming each image is 224x224
                fps = 2  # You can adjust this value to change the speed of the video
    
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # Use MJPG codec
                out = cv2.VideoWriter(output_video_path, fourcc, fps, frame_size)
                for img in labeled_query_imgs:
                    out.write(img)
                
                
                out.release()
                
                print(f"Video saved to {output_video_path}")
        except Exception as e:
            traceback.print_exc()   
        finally:
            print("terminating the controller")
            self.c.communicate({"$type": "terminate"})

@hydra.main(config_path="configs", config_name="temporal_extension.yaml", version_base=None)
def main(cfg: DictConfig):

    
    target_size = 7
    
    ideal_size = len(AVAILABLE_CAMERA_POS) * len(AVAILABLE_MOTION) * len(AVAILABLE_OBJECT) * len(AVAILABLE_COLOR)**2
    
    print(f"Ideal size: {ideal_size}, target size: {target_size}")
    
    gen_id_set = set()
    
    x_range = [-0.1, 0.1]
    y_range = [0, 0]
    z_range = [-0.1, 0.1]
    
    rotation_range = [-90, 90]
    pbar = tqdm(total=target_size)
    seed = 0
    
    material_pairs = list(itertools.permutations(SELECTED_MATERIALS, 2))
    random.shuffle(material_pairs)

    texture_pairs = list(itertools.permutations(SELECTED_TEXTURES, 2))
    random.shuffle(texture_pairs)

    size_pairs = list(itertools.permutations(SELECTED_SIZES, 2))
    random.shuffle(size_pairs)

    object_pairs = list(itertools.permutations(SELECTED_OBJECTS, 2))
    random.shuffle(object_pairs)

    color_pairs = list(itertools.permutations(SELECTED_COLORS, 2))
    random.shuffle(color_pairs)

    scenes = SELECTED_SCENES
    random.shuffle(scenes)

    for scene in SELECTED_SCENES:
        random.shuffle(texture_pairs)
        for texture1, texture2 in texture_pairs[:2]:
            random.shuffle(size_pairs)
            for size1, size2 in size_pairs[:2]:
                random.shuffle(object_pairs)
                for object1, object2 in object_pairs[:6]: 
                    random.shuffle(color_pairs)
                    for color1, color2 in color_pairs[:6]:
                        task = None
                        task = TemporalExtension(**cfg)
                        np.random.seed(seed)
                        seed += 1
                        main_obj = ObjectType(
                            model_name=object1,
                            library="models_core.json",
                            position=get_position(scene, x_range, y_range, z_range),
                            rotation={"x": 0, "y": np.random.uniform(rotation_range[0], rotation_range[1]), "z": 0},
                            scale_factor=size1,
                            texture_scale=texture1,
                            object_id=None,
                            material="concrete_raw_damaged",
                            motion=np.random.choice(AVAILABLE_MOTION),
                            color=color1
                        )
                        fixed_obj = ObjectType(
                            model_name=object2,
                            library="models_core.json",
                            position=get_position_with_offset(scene, x_range, y_range, z_range, 0.2),
                            rotation={"x": 0, "y": np.random.uniform(rotation_range[0], rotation_range[1]), "z": 0},
                            scale_factor=size2,
                            texture_scale=texture2,
                            object_id=None,
                            material="concrete_raw_damaged",
                            motion=np.random.choice([motion for motion in AVAILABLE_MOTION if motion != main_obj.motion]),
                            color=color2
                        )
                        
                        main_obj_shape_id = get_object_shape_id(main_obj)
                        fixed_obj_shape_id = get_object_shape_id(fixed_obj)
                        
                        if main_obj_shape_id == fixed_obj_shape_id:
                            continue
                        
                        main_obj_id = get_object_id(main_obj)
                        fixed_obj_id = get_object_id(fixed_obj)
                        
                        case_id = main_obj_id + "_" + fixed_obj_id
                        
                        if case_id in gen_id_set:
                            continue
                        else:
                            gen_id_set.add(case_id)
                            
                            print(f"Generated {len(gen_id_set)} unique IDs")
                            task.run(scene, main_obj_list=[main_obj], fixed_obj_list=[fixed_obj], seed=seed)
                            pbar.update(1)
                        
                        del task

if __name__ == "__main__":
    main()