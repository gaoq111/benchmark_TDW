from typing import Tuple, List, Literal
from tdw.librarian import ModelLibrarian
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
import itertools
import random

from task_abstract import AbstractTask, ObjectType, DEFAULT_OUTPUT_PATH
from tdw_object_utils import SELECTED_COLORS, SELECTED_OBJECTS, SELECTED_MATERIALS, SELECTED_TEXTURES, SELECTED_SIZES


obj_id_map = {
    "sphere": "prim_sphere",
} 

class ObjectTask(AbstractTask):
    def __init__(self, output_path:str = DEFAULT_OUTPUT_PATH,
                 port:int = 1071,
                 display:str = ":4",
                 scene:str = "empty_scene",
                 screen_size:Tuple[int, int] = (1920, 1080),
                 physics:bool = False, # enable physics or not
                 render_quality:int = 10,
                 name:str = "default",
                 camera: List[str] = ["top", "left", "right", "front", "back"],
                 library:Literal["models_core.json", "models_special.json"] = "models_core.json"):
        super().__init__(output_path, port, display, scene, screen_size, physics, render_quality, name, camera, library)
        self.attr_generate_func = {
            "color": self.generate_attr_pair,
            "shape": self.generate_attr_pair,
            "material": self.generate_attr_pair,
            "texture": self.generate_attr_pair,
            "size": self.generate_attr_pair
        }
        
    def get_model_record(self, obj_type):
        try:
            return "models_special.json", self.special_librarian.get_record(obj_type)
        except:
            try:
                # Automatically use the core library
                return "models_core.json", self.core_librarian.get_record(obj_type)
            except:
                raise ValueError(f"Model {obj_type} not found in any library.")

    def generate_regular_object(self, obj_type, position={"x": 0, "y": 0.2, "z": 0}, scale=0.5, color="red",rotation={"x": 0, "y": 0, "z": 0}, 
                                material=None, texture_scale=1, motion="static"):
        object_id = self.c.get_unique_id()
        library, model_record = self.get_model_record(obj_type)
        
        object_info = ObjectType(model_name=obj_type, 
                 position=position, 
                 rotation=rotation, 
                 scale_factor=scale, 
                 object_id=object_id, 
                 library=library,
                 model_record=model_record,
                 material=material,
                 texture_scale=texture_scale,
                 color=color,
                 motion=motion)
        
        #print(f"Object name: {object_info.model_name}, with id = {object_info.object_id}")
        
        # attention: here the gravity should be turned off
        self.commands.extend(self.c.get_add_physics_object(model_name=object_info.model_name,
                                                        library=object_info.library,
                                                        gravity=True,
                                                        position=object_info.position,
                                                        rotation=object_info.rotation,
                                                        scale_factor=object_info.scale_factor,
                                                        object_id=object_info.object_id))
        
        
        
        if object_info.material is not None:
            self.commands.append(self.c.get_add_material(material_name=object_info.material))
            self.commands.extend(TDWUtils.set_visual_material(c=self.c, substructure=object_info.model_record.substructure, material=object_info.material, object_id=object_info.object_id))
        
        if object_info.texture_scale != 1:
            for sub_object in object_info.model_record.substructure:
                self.commands.append({"$type": "set_texture_scale",
                                      "object_name": sub_object["name"],
                                        "id": object_info.object_id,
                                        "scale": {"x": object_info.texture_scale, "y": object_info.texture_scale}})
        self.commands.append({"$type": "set_color",
                            "color": object_info.color,
                            "id": object_info.object_id})
                                    
        
        return object_info
    
    
    #Now clearly define the color, shape, material, texture, size pairs because these may be further customized depending on the task
    # def generate_color_pair(self, choices=SELECTED_COLORS):
    #     color_pairs = list(itertools.permutations(choices, self.num_objects))
    #     random.shuffle(color_pairs)
    #     return color_pairs
    
    # def generate_shape_pair(self, choices=SELECTED_OBJECTS, num=None):
    #     if num is None:
    #         num = self.num_objects
    #     shape_pairs = list(itertools.permutations(choices, num))
    #     random.shuffle(shape_pairs)
    #     return shape_pairs
    
    # def generate_material_pair(self, choices=SELECTED_MATERIALS):
    #     material_pairs = list(itertools.permutations(choices, self.num_objects))
    #     random.shuffle(material_pairs)
    #     return material_pairs
    
    # def generate_texture_pair(self, choices=SELECTED_TEXTURES):
    #     texture_pairs = list(itertools.permutations(choices, self.num_objects))
    #     random.shuffle(texture_pairs)
    #     return texture_pairs

    # def generate_size_pair(self, choices=SELECTED_SIZES):
    #     size_pairs = list(itertools.permutations(choices, self.num_objects))
    #     random.shuffle(size_pairs)
    #     return size_pairs
    
    def generate_attr_pair(self, choices, num=None):
        if num is None:
            num = self.num_objects
        attr_pairs = list(itertools.permutations(choices, num))
        random.shuffle(attr_pairs)
        return attr_pairs
    
    def adapt_center_position(self, positions, center_position):
        if(type(positions) == list):
            new_poses = []
            for pos in positions:
                new_pos = {key: pos[key] + center_position[key] for key in pos.keys()}
                new_poses.append(new_pos)
            return new_poses
        else:
            return {key: positions[key] + center_position[key] for key in positions.keys()}
    
    def scale_force(self, force, scale):
        return {"x": force["x"] * scale, "y": force["y"] * scale, "z": force["z"] * scale}