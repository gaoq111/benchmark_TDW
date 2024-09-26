import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hydra.core.hydra_config import HydraConfig
from typing import Literal, Tuple, List, Dict, Any
from task_abstract import AbstractTask
from interface import AVAILABLE_OBJECT, ObjectType, AVAILABLE_MOTION, AVAILABLE_CAMERA_POS, AVAILABLE_COLOR, AVAILABLE_SCENE, AVAILABLE_SCALE_FACTOR
from tdw.add_ons.interior_scene_lighting import InteriorSceneLighting
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
from tdw_object_utils import get_cameras, get_camera_views, numpy_to_python, get_object_id, get_object_shape_id, add_cameras, \
    SELECTED_MATERIALS, SELECTED_SIZES, SELECTED_TEXTURES, SELECTED_SCENES
import itertools
import random
import yaml

MOVE_STEP = 10
PIC_NUM = 4 # the number of pictures serving as the query  


class VisualAttributeTask(ObjectTask):
    def __init__(self, output_path:str = None,
                 port:int = 1071,
                 display:str = ":4",
                 scene:str = "empty_scene",
                 screen_size:Tuple[int, int] = (1920, 1080),
                 physics:bool = False, # enable physics or not
                 render_quality:int = 10,
                 name:str = "object_interaction",
                 library:str = "models_core.json",
                 camera: List[str] = AVAILABLE_CAMERA_POS.keys(),
                 **kwargs):
        
        super().__init__(output_path=output_path, port=port, 
                         display=display, scene=scene, 
                         screen_size=screen_size, physics=physics, 
                         render_quality=render_quality, name=name, library=library, camera=camera)
        self.num_objects = 1
        
    def set_scene_get_camera_config(self, background):
        self.scene = background
        self.c.communicate(self.c.get_add_scene(self.scene))
        with open('/data/shared/sim/benchmark/benchmark_TDW/scene_settings.yaml', 'r') as file:
            config = yaml.safe_load(file)[self.scene]['camera']
            return config

    def trial(self, background, colors, shapes, materials, textures, sizes, trial_id=0, fileWriter=None, flush=True):
        
        ### Set the scene
        #print("start setting scene")
        camera_config = self.set_scene_get_camera_config(background)
        scene_center = camera_config["look_at"]
        #print("finish setting scene")
        
        total_size = len(colors) * len(shapes) * len(materials) * len(textures) * len(sizes)
        pbar = tqdm(total=total_size)
        
        #### Object position
        object_position = scene_center.copy()
        object_position["x"] += 0.5
        positions = [object_position]
        
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
                            
                            ### Lightning
                            # interior_lighting = InteriorSceneLighting()
                            # self.c.add_ons.append(interior_lighting) 
                            # interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
                                
                            self.camera = ["front", "right", "top"] 
                            add_cameras(self.c, self.camera, output_pth, self.scene)
                                
                            ### Collison Manager
                            collision_manager = CollisionManager(enter=True, stay=False, exit=False, objects=True, environment=True)
                            self.c.add_ons.append(collision_manager)
                            
                            #print("Cameras added!")
                            
                            objects = []
                            
                            for i, (color, shape, size, material, texture_scale) in enumerate(zip(color_pair, shape_pair, size_pair, material_pair, texture_pair)):
                        

                                object_info = self.generate_regular_object(shape, position=positions[i], scale=size, color=color, rotation={"x": 0, "y": np.random.uniform(-90, 90), "z": 0}, 
                                                                        material=material, texture_scale=texture_scale)
                                objects.append(object_info)


                            self.step()
                            
                            #print("Objects generated!")
                            
          
                            # vecs = [{"x": 3, "y": 0, "z": -3}, {"x": 6, "y": 0, "z": 6}]
                            # for i, vec in enumerate(vecs):
                            #     self.commands.append({"$type": "apply_force_to_object",
                            #                         "id": objects[i].object_id,
                            #                         "force": vec})
                                   
                            for i in range(1):
                                resp = self.c.communicate([])
                                
                                
                            if(fileWriter is not None):
                                output_dict = {"source_dir": output_pth, "scene_id": scene_id, "background": self.scene, **objects[0].get_attributes()}
                                json.dump(output_dict, fileWriter)
                                fileWriter.write("\n")
                    

                            scene_id += 1
                            pbar.update(1)
                            self.reset_scene([obj_info.object_id for obj_info in objects])
                            
                            
                            

    def run(self, question_type="color", flush: bool = True):
        
        count = 0
        color_pairs = self.generate_color_pair()
        shape_pairs = self.generate_shape_pair()
        material_pairs = self.generate_material_pair()
        texture_pairs = self.generate_texture_pair()
        size_pairs = self.generate_size_pair()
        
        if(question_type == "color"):
            ### Fix the material if we are testing color
            material_pairs = [["concrete_raw_damaged" for i in range(self.num_objects)]]
        else:
            color_pairs = [[key for i in range(self.num_objects)] for key in ['red', 'blue','black','green','white']]
            
        if(not os.path.exists(self.output_path)):
            os.makedirs(self.output_path, exist_ok=True)
        
        with open(os.path.join(self.output_path, "index.jsonl"), "w") as f:
            
            
            for background in tqdm(SELECTED_SCENES):
                
                
                self.trial(background, color_pairs, shape_pairs, material_pairs, texture_pairs, size_pairs, fileWriter=f, flush=flush)
                count += len(color_pairs) * len(shape_pairs) * len(material_pairs) * len(texture_pairs) * len(size_pairs)
                #print(texture_pairs)
        
        print(f"Total number of trials: {count}") 
           
            
        self.c.communicate({"$type": "terminate"})
        

@hydra.main(config_path="../configs", config_name="visual_attributes.yaml", version_base=None)
def main(cfg: DictConfig):
    
    #HydraConfig.get() .output_subdir = None
    #rotation_range = [-90, 90]
    task = VisualAttributeTask(**cfg)
    task.run(question_type=cfg["question_type"], flush=True)
    

if __name__ == "__main__":
    main()