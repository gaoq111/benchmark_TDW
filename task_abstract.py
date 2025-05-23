import abc
import subprocess
import os
import time
from typing import List, Dict, Any, Literal, Tuple
from tdw.controller import Controller
from typing import List, Dict, Union
import math
from tqdm import tqdm
from interface import ObjectType
from tdw.librarian import ModelLibrarian

base_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_PATH = os.path.join(base_dir, "image_capture")

class AbstractTask(abc.ABC):
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
        
        self.name = name
        if output_path is None or output_path == "default":
            self.output_path = DEFAULT_OUTPUT_PATH
        else:
            self.output_path = output_path
        self.port = port
        self.display = display
        self.scene = scene
        self.physics = physics
        self.render_quality = render_quality
        self.screen_size = screen_size
        self.commands = []
        self.camera = camera
        self.special_librarian = ModelLibrarian("models_special.json")
        self.core_librarian = ModelLibrarian("models_core.json")
        self.image_ticks = 0
        
        self.init_scene()
        
    def init_scene(self, background=None, display=None, port=None):
        if background is not None:
            self.scene = background
        else:
            self.scene = "empty_scene"
        
        if display is not None:
            self.display = display
        if port is not None:
            self.port = port
        
        print(f"Launching TDW server on port {self.port}, display {self.display}")
        self.start_tdw_server(display=self.display, port=self.port)
    
        try:
            self.c = Controller(port=self.port, launch_build=False)
        except Exception as e:
            print(f"Error: {e}")
            raise e

        time.sleep(5)
        self.commands = [{"$type": "set_screen_size", "width": self.screen_size[0], "height": self.screen_size[1]}, 
                {"$type": "set_render_quality", "render_quality": self.render_quality},
                #{"$type": "set_field_of_view", "field_of_view": 55},
                ]
        
        
        
        self.commands.append(self.c.get_add_scene(self.scene))
            
        self.step()

    @abc.abstractmethod
    def run(self):
        pass
    
    def step(self, reset=True):
        resp = self.c.communicate(self.commands)
        if reset:
            self.commands = []
        self.image_ticks += 1
        return resp

    
    def start_tdw_server(self, display=":4", port=1071):
        # DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port=1071
        command = f"DISPLAY={display} /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port={port}"
        process = subprocess.Popen(command, shell=True)
        time.sleep(5)  # Wait for the server to start
        return process
    
    def reset_scene(self, object_ids):
        self.commands = []
        
        ### Remove all objects later
        # for object_id in object_ids:
        #     self.commands.append({"$type": "destroy_object", "id": object_id})
        for add_on in self.c.add_ons:
            if hasattr(add_on, 'reset'):
                add_on.reset()
            else:
                add_on.initialized = False
                
        
        #remove the add_ons
        self.c.add_ons.clear()
        self.commands.append({"$type": "destroy_all_objects"})
        self.step()
        self.image_ticks = 0
    

class MoveObject:
    def __init__(self, object_type: ObjectType):
        self.object_type = object_type

    def generate_commands(self, movement: str, magnitude: float = 1.0) -> List[Dict]:
        commands = []
        object_id = self.object_type.object_id

        if movement in ["up", "down", "left", "right", "forward", "backward"]:
            direction = {
                "up": {"x": 0, "y": 1, "z": 0},
                "down": {"x": 0, "y": -1, "z": 0},
                "left": {"x": -1, "y": 0, "z": 0},
                "right": {"x": 1, "y": 0, "z": 0},
                "forward": {"x": 0, "y": 0, "z": 1},
                "backward": {"x": 0, "y": 0, "z": -1}
            }[movement]

            commands.append({
                "$type": "teleport_object_by",
                "id": object_id,
                "position": {k: v * magnitude for k, v in direction.items()}
            })

        elif movement == "rotate":
            commands.append({
                "$type": "rotate_object_by",
                "id": object_id,
                "angle": magnitude,
                "axis": "yaw",
                "is_world": True
            })

        elif movement == "circle":
            steps = 36  # Number of steps to complete a circle
            radius = magnitude
            print(f"{self.object_type.model_name} is moving in a circle with radius {radius}")
            for i in tqdm(range(steps), desc=f"Moving {self.object_type.model_name} in a circle"):
                angle = 2 * math.pi * i / steps
                x = radius * math.cos(angle)
                z = radius * math.sin(angle)
                commands.append({
                    "$type": "teleport_object_by",
                    "id": object_id,
                    "position": {"x": x, "y": self.object_type.position["y"], "z": z}
                })

        else:
            raise ValueError(f"Unknown movement: {movement}")

        return commands

    def execute_movement(self, controller: Controller, movement: str, magnitude: float = 1.0, duration: float = 1.0):
        commands = self.generate_commands(movement, magnitude)
        for cmd in commands:
            controller.communicate(cmd)
            
    def move_and_get_commands_only(self, movement: str, magnitude: float = 1.0, duration: float = 1.0):
        commands = self.generate_commands(movement, magnitude)
        return commands

if __name__ == "__main__":
    task = AbstractTask()
    task.run()