from typing import Tuple, List, Literal
from tdw.librarian import ModelLibrarian
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils

# Assuming these are defined elsewhere in your project
from task_abstract import AbstractTask, ObjectType, DEFAULT_OUTPUT_PATH


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
        
        print(f"Object name: {object_info.model_name}, with id = {object_info.object_id}")
        
        # attention: here the gravity should be turned off
        self.commands.extend(self.c.get_add_physics_object(model_name=object_info.model_name,
                                                        library=object_info.library,
                                                        gravity=True,
                                                        position=object_info.position,
                                                        rotation=object_info.rotation,
                                                        scale_factor=object_info.scale_factor,
                                                        object_id=object_info.object_id))
        
        self.commands.append({"$type": "set_color",
                            "color": object_info.color,
                            "id": object_info.object_id})
        
        if object_info.material is not None:
            self.commands.append(self.c.get_add_material(material_name=object_info.material))
            self.commands.extend(TDWUtils.set_visual_material(c=self.c, substructure=object_info.model_record.substructure, material=object_info.material, object_id=object_info.object_id))
        
        if object_info.texture_scale != 1:
            for sub_object in object_info.model_record.substructure:
                self.commands.append({"$type": "set_texture_scale",
                                      "object_name": sub_object["name"],
                                        "id": object_info.object_id,
                                        "scale": {"x": object_info.texture_scale, "y": object_info.texture_scale}})
                                    
        
        return object_info