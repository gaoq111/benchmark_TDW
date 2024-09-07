from typing import Literal, Tuple, List
from task_abstract import AbstractTask
from interface import AvailableObjectType, ObjectType, AvailableCameraParams
import hydra
import os
from omegaconf import DictConfig
import time
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.backend.paths import EXAMPLE_CONTROLLER_OUTPUT_PATH
from tdw.librarian import ModelLibrarian
from task_abstract import MoveObject
import cv2
import numpy as np

import traceback


def get_cameras(camera_id):
    camera_views = {"top": {"x": 0, "z": 0, "y": 5},
                    "left": {"x": -2.5, "z": 0, "y": 0.2},
                    "right": {"x": 2.5, "z": 0, "y": 0.2},
                    "front": {"x": 0, "z": -2.5, "y": 0.2},
                    "back": {"x": 0, "z": 2.5, "y": 0.2},}
    return ThirdPersonCamera(position=camera_views[camera_id],
                                avatar_id=camera_id,
                                look_at={"x": 0, "z": 0, "y": 0,})


class TemporalPositioning(AbstractTask):
    def __init__(self, output_path:str = None,
                 port:int = 1071,
                 display:str = ":4",
                 scene:str = "empty_scene",
                 screen_size:Tuple[int, int] = (1920, 1080),
                 physics:bool = False, # enable physics or not
                 render_quality:int = 10,
                 name:str = "temporal_positioning",
                 library:str = "models_core.json",
                 camera: List[str] = ["top"]):
        
        super().__init__(output_path=output_path, port=port, 
                         display=display, scene=scene, 
                         screen_size=screen_size, physics=physics, 
                         render_quality=render_quality, name=name, library=library, camera=camera)
        
        """
        cloth_1meter_square
        cloth_square
        fluid_receptacle1m_round
        fluid_receptacle1x1
        fluid_receptacle1x2
        new_ramp
        prim_capsule
        prim_cone
        prim_cube
        prim_cyl
prim_sphere
        ramp_scene_max
        ramp_with_platform
        """
        
        self.object_list: List[ObjectType] = [
            ObjectType(
                model_name="prim_sphere",
                library=self.library,
                position={"x": 0, "y": 0, "z": 0},
                rotation={"x": 0, "y": 0, "z": 0},
                scale_factor={"x": 0.1, "y": 0.1, "z": 0.1},
                texture_scale=1,
                object_id=None,
                material=None,
            ),
            ObjectType(
                model_name="prim_cone",
                library=self.library,
                position={"x": 1, "y": 0.5, "z": 0},
                rotation={"x": 0, "y": 0, "z": 0},
                scale_factor={"x": 0.1, "y": 0.1, "z": 0.1},
                texture_scale=1,
                object_id=None,
                material=None,
            ),
        ]
        
        self.object_track_dict = {
            
        }
        

    def run(self):
        try:
            for cam in self.camera:
                self.c.add_ons.append(get_cameras(cam))
            print("cameras added: ", self.camera)
            capture = ImageCapture(avatar_ids=self.camera, path=os.path.join(self.output_path, self.name), png=True)
            self.c.add_ons.append(capture)
            
            self.commands.append({"$type": "start_video_capture_linux", "output_path": os.path.join(self.output_path, self.name)})
            
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
                print(obj.model_name)
                object_id = self.c.get_unique_id()
                obj.object_id = object_id
                self.commands.extend(self.c.get_add_physics_object(model_name=obj.model_name,
                                                                library=obj.library,
                                                                position=obj.position,
                                                                rotation=obj.rotation,
                                                                scale_factor=obj.scale_factor if obj.scale_factor is not None else {"x": 1, "y": 1, "z": 1},
                                                                object_id=obj.object_id))
                self.commands.append({"$type": "set_color",
                                    "color": {"r": 1.0, "g": 0, "b": 0, "a": 1.0},
                                    "id": obj.object_id})
                
                if obj.material is not None:
                    print(obj.material)
                    self.commands.append(self.c.get_add_material(material_name=obj.material))
                    self.commands.extend(TDWUtils.set_visual_material(c=self.c, substructure=obj.model_record.substructure, material=obj.material, object_id=obj.object_id))
                
                # if obj.texture_scale is not None:
                #     for sub_object in obj.model_record.substructure:
                #         self.commands.append({"$type": "set_texture_scale",
                #                               "object_name": sub_object["name"],
                #                               "id": obj.object_id,
                #                               "scale": {"x": obj.texture_scale, "y": obj.texture_scale}})
                move_object_dict[obj.object_id] = MoveObject(obj)
                print("object added")
                

            self.c.communicate(self.commands)
            print("commands communicated")
            
            for obj in self.object_list[:1]:
                print(obj.model_name)
                for i in range(10):
                    move_object_dict[obj.object_id].execute_movement(self.c, "forward", magnitude=0.1)
            
            for obj in self.object_list[:1]:
                for i in range(10):
                    move_object_dict[obj.object_id].execute_movement(self.c, "down", magnitude=0.1)
            
            target_object = self.object_list[0]
            move_object_dict[target_object.object_id].execute_movement(self.c, "circle", magnitude=0.05)
            
        except Exception as e:
            traceback.print_exc()   
        finally:
            self.c.communicate({"$type": "terminate"})

@hydra.main(config_path="configs", config_name="temporal_positioning.yaml", version_base=None)
def main(cfg: DictConfig):
    task = TemporalPositioning(**cfg)
    task.run()

if __name__ == "__main__":
    main()