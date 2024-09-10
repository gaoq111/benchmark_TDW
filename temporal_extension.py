from typing import Literal, Tuple, List, Dict, Any
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


def get_cameras(camera_id):
    if camera_id not in AVAILABLE_CAMERA_POS:
        raise ValueError(f"Camera id {camera_id} not found in AVAILABLE_CAMERA_POS")
    return ThirdPersonCamera(position=AVAILABLE_CAMERA_POS[camera_id],
                                avatar_id=camera_id,
                                look_at={"x": 0, "z": 0, "y": 0,})


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
            main_obj_list: List[ObjectType] = None,
            fixed_obj_list: List[ObjectType] = None,
            seed: int = 12):
        
        if main_obj_list is None or fixed_obj_list is None:
            self.object_list: List[ObjectType] = [
            ObjectType(
                model_name="prim_sphere",
                library=self.library,
                position={"x": 0, "y": 0.5, "z": 0},
                rotation={"x": 0, "y": 0, "z": 0},
                scale_factor=0.5,
                texture_scale=1,
                object_id=None,
                material=None,
                motion="forward",
                color="red"
            ),
            ObjectType(
                model_name="prim_cone",
                library=self.library,
                position={"x": 1, "y": 0.5, "z": 0},
                rotation={"x": 0, "y": 0, "z": 0},
                scale_factor=0.5,
                texture_scale=1,
                object_id=None,
                material=None,
                color="yellow",
                motion="forward"
                ),
            ]
            np.random.seed(seed)
            x_range = [-2, 2]
            y_range = [0.5, 2.5]
            z_range = [-2, 2]
            
            fixed_object_pos = {"x": np.random.uniform(x_range[0], x_range[1]),
                                "y": np.random.uniform(y_range[0], y_range[1]),
                                "z": np.random.uniform(z_range[0], z_range[1])}
            
            self.main_object = ["prim_sphere"]
            self.fixed_objects = ["prim_cone"]
            for obj in self.object_list:
                if obj.model_name in self.fixed_objects:
                    obj.position = fixed_object_pos
        else:
            self.object_list = main_obj_list + fixed_obj_list
        

        self.main_object_names = [obj.model_name for obj in main_obj_list]
        self.fixed_object_names = [obj.model_name for obj in fixed_obj_list]
        self.expr_id = f"test_seed={seed}_main_objects={str(self.main_object_names)}_fixed_object={str(self.fixed_object_names)}"
        
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
                cmds = [{"$type": "add_object", 
                        "id": obj.object_id, 
                        "name": obj.model_name, 
                        "position": obj.position, 
                        "rotation": obj.rotation, 
                        "scale_factor": obj.scale_factor["x"]}]
                cmds.append({"$type": "set_color",
                                    "color": obj.color,
                                    "id": obj.object_id})
                self.c.communicate(cmds)
                
                # if obj.material is not None:
                #     print(obj.material)
                #     self.commands.append(self.c.get_add_material(material_name=obj.material))
                #     self.commands.extend(TDWUtils.set_visual_material(c=self.c, substructure=obj.model_record.substructure, material=obj.material, object_id=obj.object_id))
                
                # if obj.texture_scale is not None:
                #     for sub_object in obj.model_record.substructure:
                #         self.commands.append({"$type": "set_texture_scale",
                #                               "object_name": sub_object["name"],
                #                               "id": obj.object_id,
                #                               "scale": {"x": obj.texture_scale, "y": obj.texture_scale}})
                
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
                self.c.add_ons.append(get_cameras(cam))
            print("cameras added: ", self.camera)

            capture = ImageCapture(avatar_ids=self.camera, path=os.path.join(self.output_path, self.name, self.expr_id), png=True)
            self.c.add_ons.append(capture)
            
            MOVE_STEP = 6
            
            move_dict = {}
            
            # the reason why we need to record four of this is because we might want to have > 2 objs
            moving_order = {
                "first_start": None,
                "first_end": None,
                "last_start": None,
                "last_end": None
            }
            
            min_start = MOVE_STEP
            max_start = 0
            max_end = 0
            min_end = MOVE_STEP
            
            for obj in self.object_list:
                move_dict[obj.object_id] = np.sort(np.random.choice(MOVE_STEP, size=np.random.randint(1, MOVE_STEP+1), replace=False))
                print(f"obj: {obj.model_name}, move_dict: {move_dict[obj.object_id]}")
                while (move_dict[obj.object_id])[0] == min_start or (move_dict[obj.object_id])[-1] == max_end:
                    print("Not valid, cannot discriminate which one is first or which one is last")
                    move_dict[obj.object_id] = np.sort(np.random.choice(MOVE_STEP, size=np.random.randint(1, MOVE_STEP+1), replace=False))
                if min_start > move_dict[obj.object_id][0]:
                    min_start = move_dict[obj.object_id][0]
                    moving_order["first_start"] = get_object_shape_id(obj)
                if max_end < move_dict[obj.object_id][-1]:
                    max_end = move_dict[obj.object_id][-1]
                    moving_order["last_end"] = get_object_shape_id(obj)
                if min_end > move_dict[obj.object_id][-1]:
                    min_end = move_dict[obj.object_id][-1]
                    moving_order["first_end"] = get_object_shape_id(obj)
                if max_start < move_dict[obj.object_id][0]:
                    max_start = move_dict[obj.object_id][0]
                    moving_order["last_start"] = get_object_shape_id(obj)
            
            # record who starts moving first and who stops moving first

            print(f"Move Step: {MOVE_STEP}")
            for i in range(MOVE_STEP):
                commands = []
                for obj in self.object_list:
                    if obj.object_id in move_dict:
                        if i in move_dict[obj.object_id]:
                            magnitude = 1.0 / len(move_dict[obj.object_id])
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
                
                
                output_res_cam[cam]["answer"] = {
                    "first_start": moving_order["first_start"],
                    "first_end": moving_order["first_end"],
                    "last_start": moving_order["last_start"],
                    "last_end": moving_order["last_end"]
                }
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
    
    x_range = [-0.3, 0.3]
    y_range = [0.5, 1.5]
    z_range = [-0.3, 0.3]
    
    rotation_range = [-90, 90]
    pbar = tqdm(total=target_size)
    seed = 0
    while len(gen_id_set) < target_size:
        task = None
        task = TemporalExtension(**cfg)
        np.random.seed(seed)
        seed += 1
        main_obj = ObjectType(
                model_name=np.random.choice(AVAILABLE_OBJECT),
                library="models_core.json",
                position={"x": np.random.uniform(x_range[0], x_range[1]), "y": 0.1, "z": np.random.uniform(z_range[0], z_range[1])},
                rotation={"x": 0, "y": np.random.uniform(rotation_range[0], rotation_range[1]), "z": 0},
                scale_factor=np.random.choice(AVAILABLE_SCALE_FACTOR),
                texture_scale=1,
                object_id=None,
                material=None,
                motion=np.random.choice(AVAILABLE_MOTION),
                color=np.random.choice(list(AVAILABLE_COLOR.keys())))
        fixed_obj = ObjectType(
                model_name=np.random.choice(AVAILABLE_OBJECT),
                library="models_core.json",
                position={"x": np.random.uniform(x_range[0], x_range[1]), "y": 0, "z": np.random.uniform(z_range[0], z_range[1])},
                rotation={"x": 0, "y": np.random.uniform(rotation_range[0], rotation_range[1]), "z": 0},
                scale_factor=np.random.choice(AVAILABLE_SCALE_FACTOR),
                texture_scale=1,
                object_id=None,
                material=None,
                motion=np.random.choice([motion for motion in AVAILABLE_MOTION if motion != main_obj.motion]),
                color=np.random.choice(list(AVAILABLE_COLOR.keys())))
        
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
            task.run(main_obj_list=[main_obj], fixed_obj_list=[fixed_obj], seed=seed)
            pbar.update(1)
        
        del task

if __name__ == "__main__":
    main()