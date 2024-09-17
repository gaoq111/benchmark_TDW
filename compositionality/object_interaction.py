import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Literal, Tuple, List, Dict, Any
from task_abstract import AbstractTask
from interface import AVAILABLE_OBJECT, ObjectType, AVAILABLE_MOTION, AVAILABLE_CAMERA_POS, AVAILABLE_COLOR, AVAILABLE_SCENE, AVAILABLE_SCALE_FACTOR
import hydra
from omegaconf import DictConfig
import time
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.add_ons.collision_manager import CollisionManager
from tdw.librarian import ModelLibrarian
from task_abstract import MoveObject
from task_object import ObjectTask, ObjectType
import cv2
import shutil
import numpy as np
import json
import traceback
from tqdm import tqdm
from collections import defaultdict
from tdw_object_utils import get_cameras, get_camera_views, numpy_to_python, get_object_id, get_object_shape_id, add_cameras, SELECTED_MATERIALS, SELECTED_SIZES, SELECTED_TEXTURES
import itertools
import random

MOVE_STEP = 10
PIC_NUM = 4 # the number of pictures serving as the query

def write_metadata(output_path, cameras,):
    
    # step1: randomly pick a range,which has length of 4, from (0, 10)
    random_start = 0 #np.random.randint(0, MOVE_STEP - PIC_NUM)
    query_image_index = []
    other_image_index = []
    for i in range(PIC_NUM):
        query_image_index.append(random_start + i)
    
    GEN_NUM = 2 # this means we will include two pics that not belong to those steps
    OTHER_NUM = PIC_NUM - GEN_NUM - 1 # this means we will include one pic that belongs to those steps
    
    for i in range(OTHER_NUM):
        while True:
            index = np.random.randint(0, MOVE_STEP)
            if(len(query_image_index) + 2 >= MOVE_STEP):
                break
            
            if index < np.min(query_image_index) - 1 or index > np.max(query_image_index) + 1:
                other_image_index.append(index)
                break
    query_image_index.sort()
    
    gen_commands = ["move_object", "set_color", "change_scale", "rotate_object"]

    # we need to know how many imgs have been generated
    before_gen = len(os.listdir(os.path.join(output_path, cameras[0])))
            
    print(f"Before gen: {before_gen}, the latters are generated for candidates")
    
    output_res_cam = defaultdict(dict)
            
    gen_img_index = [before_gen + i for i in range(GEN_NUM)]
            
    for cam in cameras:
        output_path_dict = {
            "query": [],
            "other": [],
            "gen": []
        }
        for i in query_image_index:
            output_path_dict["query"].append(os.path.join(output_path, cam, f"img_{i:04d}.png"))
        for i in other_image_index:
            output_path_dict["other"].append(os.path.join(self.output_path, self.name, self.expr_id, cam, f"img_{i:04d}.png"))
        for i in gen_img_index:
            output_path_dict["gen"].append(os.path.join(self.output_path, self.name, self.expr_id, cam, f"img_{i:04d}.png"))

        output_res_cam[cam]["query"] = output_path_dict["query"][1:] # this contains 3 imgs
        candidates = [output_path_dict["query"][0]] # 1, this is the ans
        candidates.extend(output_path_dict["gen"]) # 2
        candidates.extend(output_path_dict["other"]) # 1
        
        # shuffle candidates
        index = np.arange(len(candidates))
        np.random.shuffle(index)
        answer = [i for i, t in enumerate(index) if t == 0][0]
        candidates = [candidates[i] for i in index]
        output_res_cam[cam]["candidates"] = candidates
        output_res_cam[cam]["answer"] = answer
        output_res_cam[cam]["camera_direction"] = cam
        output_res_cam[cam]["main_obj"] = {
            "model_name": main_obj.model_name,
            "position": main_obj.position,
            "rotation": main_obj.rotation,
            "scale_factor": main_obj.scale_factor,
            "motion": main_obj.motion,
            "color": main_obj.color,
            "material": main_obj.material,
            "texture_scale": main_obj.texture_scale
        }
        output_res_cam[cam]["other_objs"] = [
            {
                "model_name": obj.model_name,
                "position": obj.position,
                "rotation": obj.rotation,
                "scale_factor": obj.scale_factor,
                "motion": obj.motion,
                "color": obj.color,
                "material": obj.material,
                "texture_scale": obj.texture_scale
            } for obj in other_objs
        ]
        output_res_cam[cam]["scene"] = self.scene

    # write the item in output_res_cam into jsonl
    with open(os.path.join(self.output_path, self.name, "output_res_cam.jsonl"), "a") as f:
        for cam in self.camera:
            json.dump(numpy_to_python(output_res_cam[cam]), f)
            f.write("\n")
            
def write_overview_image(output_path, cameras, ):
    pass
    # # we will concate the query imgs in the first line, and the candidates in the second line, and output a img
    # # 3 query imgs first line
    # # 4 candidates second line
    # # make the answer img with boxed with red line

    # for cam in self.camera:
    #     # Read and resize query images (3 images)
    #     query_imgs = [cv2.imread(img) for img in output_res_cam[cam]["query"]]
    #     query_imgs = [cv2.resize(img, (224, 224)) for img in query_imgs]
        
    #     # Read and resize candidate images (4 images)
    #     candidate_imgs = [cv2.imread(img) for img in output_res_cam[cam]["candidates"]]
    #     candidate_imgs = [cv2.resize(img, (224, 224)) for img in candidate_imgs]
        
    #     # Add red border to the answer image
    #     answer_index = output_res_cam[cam]["answer"]
    #     border_size = 5
    #     target_img = None
    #     for i in range(len(candidate_imgs)):
    #         if i == answer_index:
    #             target_img = candidate_imgs[i]
    #             candidate_imgs[i] = cv2.copyMakeBorder(candidate_imgs[i], border_size, border_size, border_size, border_size, cv2.BORDER_CONSTANT, value=[0, 0, 255])
    #         else:
    #             candidate_imgs[i] = cv2.copyMakeBorder(candidate_imgs[i], border_size, border_size, border_size, border_size, cv2.BORDER_CONSTANT, value=[0, 0, 0])

    #     # Ensure all images are the same size
    #     target_size = (224, 224)
    #     query_imgs = [target_img] + query_imgs
    #     query_imgs = [cv2.resize(img, target_size) for img in query_imgs]
    #     candidate_imgs = [cv2.resize(img, target_size) for img in candidate_imgs]
        
    #     # Concatenate query images horizontally
    #     query_row = np.hstack(query_imgs)
        
    #     # Add a blank image to match the width of candidate row
    #     # blank_img = np.zeros((224, 224, 3), dtype=np.uint8)
    #     # query_row = np.hstack([query_row, blank_img])
        
    #     # Concatenate candidate images horizontally
    #     candidate_row = np.hstack(candidate_imgs)
        
    #     # Concatenate both rows vertically
    #     final_image = np.vstack([query_row, candidate_row])
        
    #     # Save the final image
    #     cv2.imwrite(os.path.join(self.output_path, self.name, self.expr_id, cam, "sample.png"), final_image)
       
def create_choices():
    pass
    # for i in range(GEN_NUM):
    #     choice = np.random.choice(gen_commands)
    #     if choice == "move_object":
    #         print("move_object")
    #         MOVE_STEP = 2
    #         for obj in other_objs:
    #             motion = np.random.choice(AVAILABLE_MOTION)
    #             print(f"GENERATE: Object {obj.model_name} = {obj.object_id} is moving {motion}, {MOVE_STEP} steps")
    #             for i in range(MOVE_STEP):
    #                 move_object_dict[obj.object_id].execute_movement(self.c, motion, magnitude=0.3)
                    
    #     elif choice == "set_color":
    #         print("set_color")
    #         for obj in self.object_list:
    #             color = np.random.choice(list(AVAILABLE_COLOR.keys()))
    #             self.c.communicate({"$type": "set_color",
    #                                 "color": AVAILABLE_COLOR[color],
    #                                 "id": obj.object_id})
    #     elif choice == "change_scale":
    #         print("change_scale")
    #         for obj in self.object_list:
    #             scale = np.random.uniform(0.1, 2)
    #             scale_factor = {"x": scale, "y": scale, "z": scale}
    #             self.c.communicate({"$type": "scale_object",
    #                                 "scale_factor": scale_factor,
    #                                 "id": obj.object_id})
    #     elif choice == "rotate_object":
    #         print("rotate_object")
    #         for obj in self.object_list:
    #             rotation = {"x": 0, "y": np.random.uniform(0, 360), "z": 0}
    #             self.c.communicate({"$type": "rotate_object_to",
    #                                 "rotation": rotation,
    #                                 "id": obj.object_id})
                
    #     elif choice == "change_scene":
    #         print("change_scene")
    #         self.c.communicate(self.c.get_add_scene(np.random.choice(AVAILABLE_SCENE)))


            


class ObjectInteractionTask(ObjectTask):
    def __init__(self, output_path:str = None,
                 port:int = 1071,
                 display:str = ":4",
                 scene:str = "empty_scene",
                 screen_size:Tuple[int, int] = (1920, 1080),
                 physics:bool = False, # enable physics or not
                 render_quality:int = 10,
                 name:str = "object_interaction",
                 library:str = "models_core.json",
                 camera: List[str] = AVAILABLE_CAMERA_POS.keys()):
        
        super().__init__(output_path=output_path, port=port, 
                         display=display, scene=scene, 
                         screen_size=screen_size, physics=physics, 
                         render_quality=render_quality, name=name, library=library, camera=camera)
        self.num_objects = 3
        
    def generate_color_pair(self):
        color_pairs = []
        for color in AVAILABLE_COLOR.keys():
            #this is iterating the color used for the fixed object
            other_colors = [c for c in AVAILABLE_COLOR.keys() if c != color]
            other_color_pairs = random.choice(list(itertools.permutations(other_colors, self.num_objects - 1)))
            
            color_pair = list(other_color_pairs) + [color]
            print(color_pair)
            color_pairs.append(color_pair)
            
        return color_pairs
    
    def generate_shape_pair(self):
        shape_pairs = list(itertools.permutations(AVAILABLE_OBJECT, self.num_objects))
        shape_pairs.shuffle()
        return shape_pairs
    
    def generate_material_pair(self):
        material_pairs = list(itertools.permutations(selected_materials, self.num_objects))
        material_pairs.shuffle()
        return material_pairs
    
    def generate_texture_pair(self):
        texture_pairs = list(itertools.permutations(selected_textures, self.num_objects))
        texture_pairs.shuffle()
        return texture_pairs

    def generate_size_pair(self):
        size_pairs = list(itertools.permutations(selected_sizes, self.num_objects-1))
        #Replicate the size for the first two moving objects
        size_pairs = [[s[0]] + list(s) for s in size_pairs]
        size_pairs.shuffle()
        return size_pairs

    def trial(self, background, colors, shapes, materials, textures, sizes, trial_id=0, flush=True):
        
        total_size = len(colors) * len(shapes) * len(materials) * len(textures) * len(sizes)
        pbar = tqdm(total=total_size)
        positions = [{"x": -1, "y": 0.2, "z": 1}, {"x": -1, "y": 0.2, "z": -1}, {"x": 0, "y": 0.2, "z": 0}]
        
        scene_id = 0
        for color_pair in colors:
            for shape_pair in shapes:
                for material_pair in materials:
                    for texture_pair in textures:
                        for size_pair in sizes:
                            
                            np.random.seed(trial_id*10000 + scene_id)
                            random.seed(trial_id*10000 + scene_id)
                            
                            output_pth = os.path.join(self.output_path, self.name, background, f"scene_{scene_id:04d}")
                            if os.path.exists(output_pth) and flush:
                                shutil.rmtree(output_pth)
                            
                            
                                
                            self.camera = get_camera_views(motion = "forward", camera_view=self.camera)
                            add_cameras(self.c, self.camera, output_pth)
                                
                            ### Collison Manager
                            collision_manager = CollisionManager(enter=True, stay=False, exit=False, objects=True, environment=True)
                            self.c.add_ons.append(collision_manager)
                            
                            objects = []
                            
                            for i, (color, shape, size, material, texture_scale) in enumerate(zip(color_pair, shape_pair, size_pair, material_pair, texture_pair)):
                        
    
                                object_info = self.generate_regular_object(shape, position=positions[i], scale=size, color=color, rotation={"x": 0, "y": 0, "z": 0}, 
                                                                        material=material, texture_scale=texture_scale)
                                objects.append(object_info)


                            self.step()
                            
          
                            vecs = [{"x": 3, "y": 0, "z": -3}, {"x": 6, "y": 0, "z": 6}]
                            for i, vec in enumerate(vecs):
                                self.commands.append({"$type": "apply_force_to_object",
                                                    "id": objects[i].object_id,
                                                    "force": vec})
                                   
                            for i in range(MOVE_STEP):
                                if(len(collision_manager.obj_collisions) != 0):
                                    print(f'the {i}th step has collision')
                                resp = self.c.communicate([])
                                
                                

                            scene_id += 1
                            pbar.update(1)
                            self.reset_scene([obj_info.object_id for obj_info in objects])
                            
                            
                            
        self.c.communicate({"$type": "terminate"})

    def run(self, flush: bool = True):
        
        for background in tqdm(AVAILABLE_SCENE):
            color_pairs = self.generate_color_pair()[:1]
            shape_pairs = self.generate_shape_pair()[:1]
            material_pairs = self.generate_material_pair()[:1]
            texture_pairs = self.generate_texture_pair()[:1]
            size_pairs = self.generate_size_pair()[:1]
            
            self.trial(background, color_pairs, shape_pairs, material_pairs, texture_pairs, size_pairs, flush=flush)
        

@hydra.main(config_path="../configs", config_name="compositionality.yaml", version_base=None)
def main(cfg: DictConfig):
        
    #rotation_range = [-90, 90]
    
    task = ObjectInteractionTask(**cfg)
    task.run(flush=True)
    

if __name__ == "__main__":
    main()