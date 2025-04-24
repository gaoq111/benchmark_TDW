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
from tdw_object_utils import coordinate_addition, coordinate_difference, get_cameras, get_camera_views, numpy_to_python, get_object_id, get_object_shape_id, add_cameras, \
    SELECTED_MATERIALS, SELECTED_SIZES, SELECTED_TEXTURES
SELECTED_SCENES = ["box_room_2018", "monkey_physics_room", "suburb_scene_2018"]
import itertools
import random
import yaml

MOVE_STEP = 10
PIC_NUM = 4 # the number of pictures serving as the query  
TABLES = {"marble_table": 0.45, "trapezoidal_table": 0.55, "small_table_green_marble": 1.33, "willisau_varion_w3_table": 0.74}
SHAPE_OFFSET = {
    "sphere": 0.05,
    "cube": 0.05,
    "cylinder": 0.05,
    "cone": 0.0,
}
SHAPE_MAP = {
    "prim_sphere": "sphere",
    "prim_cube": "cube",
    "prim_cyl": "cylinder",
    "prim_cone": "cone"
}
RELATIVE_OFFSETS = {
    "front":  {"x": 0.0,  "y": 0.0,  "z": -0.3},
    "behind": {"x": 0.0,  "y": 0.0,  "z": 0.3},
    "left":   {"x": -0.3, "y": 0.0,  "z": 0.0},
    "right":  {"x": 0.3,  "y": 0.0,  "z": 0.0},
    "top":    {"x": 0.0,  "y": 0.3,  "z": 0.0},
}

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
        self.num_objects = 2
        
    def set_scene_get_camera_config(self, background):
        self.scene = background
        self.c.communicate(self.c.get_add_scene(self.scene))
        with open('/data/shared/sim/benchmark/benchmark_TDW/scene_settings.yaml', 'r') as file:
            config = yaml.safe_load(file)[self.scene]['camera']
            return config

    def flush_output_folder(self, path: str):
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)

    def add_table(self, table_name="willisau_varion_w3_table", table_pos={"x": 0, "y": 0, "z": 0}):
        
        table_id = self.c.get_unique_id()
        scale = 1.5

        # Set table
        self.commands.extend(self.c.get_add_physics_object(model_name=table_name,
                                                library="models_core.json",
                                                position=table_pos,
                                                kinematic = True,
                                                scale_factor={"x": scale, "y": scale, "z": scale},
                                                object_id=table_id))
        
        table_top_center = table_pos.copy()
        table_top_center["y"] += TABLES[table_name]*scale
        
        return table_id, table_top_center
    
    def trial(self, background, colors, shapes, materials, textures, sizes, trial_id=0, fileWriter=None, flush=True):
        
        ### Set the scene
        #print("start setting scene")
        camera_config = self.set_scene_get_camera_config(background)
        scene_center = camera_config["look_at"]
        #print("finish setting scene")
        
        self.commands.extend(self.c.get_add_physics_object(model_name="willisau_varion_w3_table",
                                                library="models_core.json",
                                                position={"x": 0, "y": 0, "z": 0},
                                                kinematic = True,
                                                scale_factor={"x": 1.5, "y": 1.5, "z": 1.5},
                                                object_id=self.c.get_unique_id()))
        
        total_size = len(colors) * len(shapes) * len(materials) * len(textures) * len(sizes)
        # print("color length: ", len(colors))
        # print("Color: ", colors)
        # print("shape length: ", len(shapes))
        # print("shape: ", shapes)
        # print("material length: ", len(materials))
        # print("material: ", materials)
        # print("texture length: ", len(textures))
        # print("texture: ", textures)
        # print("size length: ", len(sizes))
        # print("size: ", sizes)
        pbar = tqdm(total=total_size)
        
        #### Object position
        object_position = scene_center.copy()
        object_position["x"] += 0.5
        object_position2 = scene_center.copy()
        object_position2["x"] -= 0.5
        positions = [object_position, object_position2]
        
        scene_id = 0
        for color_pair in colors:
            for shape_pair in shapes:
                for material_pair in materials:
                    for texture_pair in textures:
                        for size_pair in sizes:
                            
                            np.random.seed(trial_id*10000 + scene_id)
                            random.seed(trial_id*10000 + scene_id)
                            
                            output_pth = os.path.join(self.output_path, self.name, background, f"scene_{scene_id:04d}")
                            if flush:
                                self.flush_output_folder(output_pth)
                            
                            ### Lightning
                            # interior_lighting = InteriorSceneLighting()
                            # self.c.add_ons.append(interior_lighting) 
                            # interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
                            
                            #add table
                            table_id, table_top_center = self.add_table(table_name="willisau_varion_w3_table", table_pos=scene_center)      

                            #  Camera capture
                            self.camera = ["front", "right", "top"]
                            offset_center = scene_center.copy()
                            center_diff = coordinate_difference(table_top_center, offset_center)
                            offsets = {}
                            for camera in self.camera:
                                total_diff = center_diff.copy()
                                ### Elevate the front and top cameras a bit
                                if(camera == "front"):
                                    total_diff["y"] += 0.3
                                elif(camera == "top"):
                                    total_diff["y"] += 0.15
                                offsets[camera] = total_diff
                            add_cameras(self.c, self.camera, output_pth, self.scene, offset=offsets)
                                
                            ### Collison Manager
                            collision_manager = CollisionManager(enter=True, stay=False, exit=False, objects=True, environment=True)
                            self.c.add_ons.append(collision_manager)
                            
                            #print("Cameras added!")
                            
                            objects = []
                            objects_info = []
                            
                            for i, (color, shape, size, material, texture_scale) in enumerate(zip(color_pair, shape_pair, size_pair, material_pair, texture_pair)):

                                # Iterate over the quadrants

                                object_info = self.generate_regular_object(shape, position=coordinate_addition([table_top_center.copy(), positions[i]]), scale=size, color=color, rotation={"x": 0, "y": np.random.uniform(-90, 90), "z": 0}, 
                                                                        material=material, texture_scale=texture_scale)
                                objects.append(object_info)
                                objects_info.append(object_info.get_attributes())


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
                                output_dict = {"source_dir": output_pth, "scene_id": scene_id, "background": self.scene, "objects": objects_info}
                                json.dump(output_dict, fileWriter)
                                fileWriter.write("\n")
                    

                            scene_id += 1
                            pbar.update(1)
                            self.reset_scene([obj_info.object_id for obj_info in objects])
                            
                            
                            

    def run(self, question_type="color", flush: bool = True):
        
        count = 0
        color_pairs = self.generate_color_pair({
            "red": {
                "r": 1, "g": 0, "b": 0, "a": 1
            },
            "green": {
                "r": 0, "g": 1, "b": 0, "a": 1
            },
            "blue": {
                "r": 0, "g": 0, "b": 1, "a": 1
            },
            "yellow": {
                "r": 1, "g": 1, "b": 0, "a": 1
            },
            "purple": {
                "r": 1, "g": 0, "b": 1, "a": 1
            },
            "orange": {
                "r": 1, "g": 0.5, "b": 0, "a": 1
            },
            "gray": {
                "r": 0.5, "g": 0.5, "b": 0.5, "a": 1
            },
            "white": {
                "r": 1, "g": 1, "b": 1, "a": 1
            },
            # "transparent": {
            #     "r": 1, "g": 1, "b": 1, "a": 0.5
            # },
        })
        shape_pairs = self.generate_shape_pair()
        material_pairs = self.generate_material_pair(["concrete_raw_damaged", "glass_clear", "rock_surface_rough"])
        texture_pairs = self.generate_texture_pair()
        size_pairs = self.generate_size_pair([0.2, 0.3, 0.4])
        
        if(question_type == "color"):
            ### Fix the material if we are testing color
            material_pairs = [["concrete_raw_damaged" for i in range(self.num_objects)]]
        else:
            #color_pairs = [[key for i in range(self.num_objects)] for key in ['red', 'blue','black','green','white']]
            pass
        
        #cut the number of scenes:
        color_pairs = color_pairs[:4]
        shape_pairs = shape_pairs[:4]
        material_pairs = material_pairs[:3]
        ### Add pairs of same material
        material_pairs.extend([[item, item] for item in ["concrete_raw_damaged", "glass_clear", "rock_surface_rough"]])
        texture_pairs = [[0.5, 0.5]]
            
        if(not os.path.exists(self.output_path)):
            os.makedirs(self.output_path, exist_ok=True)
        
        with open(os.path.join(self.output_path, f"{self.name}_index.jsonl"), "w") as f:
            
            
            for background in tqdm(SELECTED_SCENES):
                
                
                self.trial(background, color_pairs, shape_pairs, material_pairs, texture_pairs, size_pairs, fileWriter=f, flush=flush)
                count += len(color_pairs) * len(shape_pairs) * len(material_pairs) * len(texture_pairs) * len(size_pairs)
                #print(texture_pairs)
        
        print(f"Total number of trials: {count}") 
           
            
        self.c.communicate({"$type": "terminate"})
        

@hydra.main(config_path="../configs", config_name="visual_attributes_comparison_material.yaml", version_base=None)
def main(cfg: DictConfig):
    
    #HydraConfig.get() .output_subdir = None
    #rotation_range = [-90, 90]
    task = VisualAttributeTask(**cfg)
    task.run(question_type=cfg["question_type"], flush=True)
    

if __name__ == "__main__":
    main()