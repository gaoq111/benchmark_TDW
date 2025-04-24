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
from tdw.add_ons.object_manager import ObjectManager
from tdw.librarian import ModelLibrarian
from tdw.output_data import OutputData, AvatarKinematic

from task_abstract import MoveObject
from task_object import ObjectTask, ObjectType
import cv2
import shutil
import numpy as np
import json
import math
import traceback
from tqdm import tqdm
from collections import defaultdict
from tdw_object_utils import get_cameras, get_camera_views, numpy_to_python, get_object_id, get_object_shape_id, add_cameras, array_to_transform,\
    SELECTED_MATERIALS, SELECTED_SIZES, SELECTED_TEXTURES, SELECTED_SCENES, SELECTED_COLORS, SELECTED_OBJECTS
import itertools
import random
import yaml

MOVE_STEP = 12
PIC_NUM = 4 # the number of pictures serving as the query
        

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
                 camera: List[str] = AVAILABLE_CAMERA_POS.keys(),
                 **kwargs):
        
        super().__init__(output_path=output_path, port=port, 
                         display=display, scene=scene, 
                         screen_size=screen_size, physics=physics, 
                         render_quality=render_quality, name=name, library=library, camera=camera)
        self.num_objects = 3
        self.attr_generate_func = {
            "color": self.generate_color_pair,
            "shape": self.generate_attr_pair,
            "material": self.generate_attr_pair,
            "texture": self.generate_attr_pair,
            "size": self.generate_size_pair
        }
        
    def set_scene_get_camera_config(self, background):
        self.scene = background
        self.c.communicate(self.c.get_add_scene(self.scene))
        with open('/data/shared/sim/benchmark/benchmark_TDW/scene_settings.yaml', 'r') as file:
            config = yaml.safe_load(file)[self.scene]['camera']
            return config
        
    def add_managers(self, output_pth):
        
        ### Lightning
        # interior_lighting = InteriorSceneLighting()
        # self.c.add_ons.append(interior_lighting) 
        # interior_lighting.reset(hdri_skybox="old_apartments_walkway_4k", aperture=8, focus_distance=2.5, ambient_occlusion_intensity=0.125, ambient_occlusion_thickness_modifier=3.5, shadow_strength=1)
            
        ### Cameras
        self.camera = ["top_front"] 
        add_cameras(self.c, self.camera, output_pth, self.scene)
        self.image_ticks = 0
        #print("Cameras added!")
        
            
        ### Collison Manager
        self.collision_manager = CollisionManager(enter=True, stay=False, exit=False, objects=True, environment=True)
        self.c.add_ons.append(self.collision_manager)
        self.collison_frames = []
        
        
        #Object manager.
        self.object_manager = ObjectManager(transforms=False, rigidbodies=True)
        self.c.add_ons.append(self.object_manager)
    
    def generate_color_pair(self, choices=SELECTED_COLORS):
        color_pairs = []
        for color in choices.keys():
            #this is iterating the color used for the fixed object
            other_colors = [c for c in SELECTED_COLORS.keys() if c != color]
            other_color_pairs = random.choice(list(itertools.permutations(other_colors, self.num_objects - 1)))
            
            color_pair = list(other_color_pairs) + [color]
            color_pairs.append(color_pair)
            
        return color_pairs
    
    def generate_size_pair(self, choices=SELECTED_SIZES):
        size_pairs = list(itertools.product(choices, repeat=self.num_objects-1))
        #Replicate the size for the first two moving objects
        size_pairs = [[s[0]] + list(s) for s in size_pairs]
        random.shuffle(size_pairs)
        return size_pairs
    
    def transport_object(self, object_id, direction, magnitude):
        movement = {k: v * magnitude for k, v in direction.items()}
        
        self.commands.append({
            "$type": "teleport_object_by",
            "id": object_id,
            "position": movement
        })
    
    def get_velocity(self, obj_move_info):
        
        vel = array_to_transform(obj_move_info.velocity)
        return vel
    
    def render_non_physics_move(self, obj_ids, obj_manager, move_steps=5):
        self.commands.append({"$type": "simulate_physics",
                            "value": False})
        
        
        for i in range(move_steps):
            for obj_id in obj_ids:   
                vel = self.get_velocity(obj_manager.rigidbodies[obj_id])
                self.transport_object(obj_id, vel, 0.05)
                
            self.step()
            
        self.commands.append({"$type": "simulate_physics",
                            "value": True})
        self.step()
        
    def apply_force_scale(self, forces, force_scale):
        forces = [{"x": f["x"]*force_scale, "y": f["y"]*force_scale, "z": f["z"]*force_scale} for f in forces]
        return forces
        
    def apply_force(self, objects, force_scale=1):
        vecs = [{"x": 40, "y": 0, "z": -40}, {"x": 40, "y": 0, "z": 40}]
        vecs = self.apply_force_scale(vecs, force_scale)
        for i, vec in enumerate(vecs):
            obj_size = objects[i].get_size()
            force = self.scale_force(vec, math.pow(obj_size, 3))
            self.commands.append({"$type": "apply_force_to_object",
                                "id": objects[i].object_id,
                                "force": force})
    
    def add_pulse_render(self, objects, move_steps=3, z = 0):
        # pulse = {"x": 0, "y": 0.01, "z": 0}
        # obj_size = objects[-1].get_size()
        # force = self.scale_force(pulse, math.pow(obj_size, 3))
        self.commands.append({"$type": "set_velocity",
                            "id": objects[-1].object_id,
                            "velocity": {"x": 5, "y":0, "z": 0}})
        self.step()

        self.commands.append({"$type": "set_velocity",
                            "id": objects[-1].object_id,
                            "velocity": {"x": 15, "y":0, "z": z}})
        for i in range(move_steps):
            self.step()

        # self.commands.append({"$type": "apply_force_to_object",
        #                     "id": objects[-1].object_id,
        #                     "force": {"x": 0, "y":0.0001, "z": 0.00010}})
        
        # self.step()
        

    def trial(self, background, colors, shapes, materials, textures, sizes, force_scales, physic_types,
              trial_id=0, index_name="index.jsonl", flush=True):
        
        ### Set the scene
        #print("start setting scene")
        camera_config = self.set_scene_get_camera_config(background)
        scene_center = camera_config["look_at"]
        #print("finish setting scene")
        
        total_size = len(colors) * len(shapes) * len(materials) * len(textures) * len(sizes) * len(force_scales) * len(physic_types)
        pbar = tqdm(total=total_size)
        
        #### Object position
        positions = [{"x": -1, "y": 0.05, "z": 1}, {"x": -1, "y": 0.05, "z": -1}, {"x": 0, "y": 0.05, "z": 0}]
        positions = self.adapt_center_position(positions, scene_center)
        
        scene_id = 0
        scene_setting_id = 0
        for color_pair in colors:
            for shape_pair in shapes:
                for material_pair in materials:
                    for texture_pair in textures:
                        for size_pair in sizes:
                            for force_scale in force_scales:
                                scene_setting_id += 1
                                for physic_type in physic_types: #
                                    
                                    np.random.seed(trial_id*10000 + scene_id)
                                    random.seed(trial_id*10000 + scene_id)
                                    
                                    output_dir = os.path.join(self.output_path, self.name)
                                    output_pth = os.path.join(output_dir, "images", f"{background}-scene_{scene_id:04d}-{force_scale}-{physic_type}")
                                    if os.path.exists(output_pth) and flush:
                                        shutil.rmtree(output_pth)
                                    
                                    self.add_managers(output_pth)
                                    
                                    objects = []
                                    
                                    for i, (color, shape, size, material, texture_scale) in enumerate(zip(color_pair, shape_pair, size_pair, material_pair, texture_pair)):
                                        
                                        positions_cyl = [{"x": -1, "y": 0.05+size/2, "z": 1}, {"x": -1, "y": 0.05+size/2, "z": -1}, {"x": 0, "y": 0.05+size/2, "z": 0}]
                                        positions_cyl = self.adapt_center_position(positions_cyl, scene_center)
                                        object_info = self.generate_regular_object(shape, position=positions_cyl[i] if shape == 'prim_cyl' else positions[i], scale=size, color=color, rotation={"x": 0, "y": np.random.uniform(-90, 90), "z": 0}, 
                                                                                material=material, texture_scale=texture_scale, mass=16*size**3, bounciness=1)
                                        objects.append(object_info)
                                    object_ids = [obj.object_id for obj in objects]


                                    
                                    #print("Objects generated!")
                                    self.step()
                                    
                                    #Currently hardcoded the forces
                                    self.apply_force(objects, force_scale)
                                        
                                        
                                        
                                    for i in range(MOVE_STEP):
                                        
                                        resp = self.step()
                                        if(len(self.collision_manager.obj_collisions) > 0): 
                                            self.collison_frames.append(self.image_ticks-1)
                                            
                                            # if(physic_type == "non_physics"):
                                            #     self.render_non_physics_move(object_ids[:-1], self.object_manager, move_steps=3)
                                            #     break
                                            if(physic_type == "countefactual_pulse_1"):
                                                self.add_pulse_render(objects, move_steps=3, z=15)
                                                break
                                            elif(physic_type == "countefactual_pulse_2"):
                                                self.add_pulse_render(objects, move_steps=3, z=-15)
                                                break
                                        
                                    with open(os.path.join(output_dir, index_name), "a") as f:
                                        output_dict = {"source_dir": output_pth, "scene_id": scene_id, "setting_id": f"{background}-{scene_setting_id}", "background": self.scene, 
                                                       "force_scale": force_scale, "physic_type": physic_type, "collison_frames": self.collison_frames,
                                                    "objects": [obj.get_attributes() for obj in objects], 
                                                    }
                                        json.dump(output_dict, f)
                                        f.write("\n")
                            

                                    scene_id += 1
                                    pbar.update(1)
                                    self.reset_scene([obj_info.object_id for obj_info in objects])
                            
                            
                            

    def simple_run(self, flush: bool = True):
        ### A setting for two objects(sphere) colliding with a third random object
        
        
        count = 0
        color_pairs = self.attr_generate_func["color"](choices=SELECTED_COLORS)[:25]
        # This cone does not move
        SELECTED_OBJECTS.remove("prim_cone")
        shape_pairs = self.attr_generate_func["shape"](choices=SELECTED_OBJECTS, num=1)
        # shape_pairs = self.attr_generate_func["shape"](choices=["prim_cyl", "prim_cube"], num=1)
        shape_pairs = [["prim_sphere", "prim_sphere"]+list(pair) for pair in shape_pairs]
        
        material_pairs = self.attr_generate_func["material"](choices=SELECTED_MATERIALS)
        material_pairs = [["concrete_raw_damaged" for _ in range(self.num_objects)], ["glass_clear" for _ in range(self.num_objects)]] #"glass_clear"
        texture_choices = [0.1, 1.0]
        texture_pairs = [[texture for _ in range(self.num_objects)] for texture in texture_choices]
        size_pairs = self.attr_generate_func["size"](choices=[0.25,0.3])
        #size_pairs = self.attr_generate_func["size"](choices=[0.5,0.5])
        force_scales = [0.5, 0.7, 0.9]
        physic_types = ["countefactual_pulse_1","countefactual_pulse_2", "normal"]  # , "non_physics", "countefactual_pulse", "normal"]
        
        # color_pairs = color_pairs[:1]
        # shape_pairs = shape_pairs[:1]
        # material_pairs = material_pairs[:1]
        # texture_pairs = texture_pairs[:1]
        # size_pairs = size_pairs[:1]
        
        output_dir = os.path.join(self.output_path, self.name)
        
        if(not os.path.exists(output_dir)):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, f"{self.name}_index.jsonl"), "w") as f:
            pass

        backgrounds = SELECTED_SCENES
        backgrounds.remove("ruin")
        
        for background in tqdm(SELECTED_SCENES):
            
            print(color_pairs)
            print(shape_pairs)
            print(material_pairs)
            print(texture_pairs)
            print(size_pairs)
            print(force_scales)
            
            self.trial(background, color_pairs, shape_pairs, material_pairs, texture_pairs, size_pairs, 
                        force_scales, physic_types,
                        index_name=f"{self.name}_index.jsonl", flush=flush)
            count += len(color_pairs) * len(shape_pairs) * len(material_pairs) * len(texture_pairs) * len(size_pairs) \
                    * len(force_scales)
            
            break
        
        print(f"Total number of trials: {count}") 
           
            
        self.c.communicate({"$type": "terminate"})
    
    def run(self, task_name:str = "two_spheres", flush: bool = True):
        if(task_name == "two_spheres"):
            self.simple_run(flush=flush)
        

@hydra.main(config_path="../configs", config_name="compositionality.yaml", version_base=None)
def main(cfg: DictConfig):
    
    #HydraConfig.get() .output_subdir = None
    #rotation_range = [-90, 90]
    task = ObjectInteractionTask(**cfg)
    task.run(task_name="two_spheres", flush=True)
    

if __name__ == "__main__":
    main()