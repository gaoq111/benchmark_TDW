from utils import *
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.backend.paths import EXAMPLE_CONTROLLER_OUTPUT_PATH
from tdw.librarian import ModelLibrarian

import argparse
import os

# Initiate a tdw server:
# DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port 1071
# The server might exit when there are errors in executing the commands 
# "y" is the vertical axis in the setting

#Todo:
# 1. Better image write_out method, in tdw_physics, they write images to hfd5 files
# 2. Multiprocess tdw servers

#[Optional]: using python subprocess to initiate the server on-the-fly with a customized port

def get_cameras(camera_id):
    camera_views = {"top": {"x": 0, "z": 0, "y": 1.5},
                    "left": {"x": -2.5, "z": 0, "y": 0.2},
                    "right": {"x": 2.5, "z": 0, "y": 0.2},
                    "front": {"x": 0, "z": -2.5, "y": 0.2},
                    "back": {"x": 0, "z": 2.5, "y": 0.2},}
    return ThirdPersonCamera(position=camera_views[camera_id],
                                avatar_id=camera_id,
                                look_at={"x": 0, "z": 0, "y": 0,}) 

def get_action_coordinates(action):
    if action is None:
        return None
    else:
        traj, num = action.split("_")
        if traj == 'circle':
            radius = float(num)
            return generate_circle_coords(num_points=30, radius=radius), generate_circle_coords(num_points=30, radius=radius, direction='counterclockwise')
        if traj == 'square':
            side_length = float(num)
            return generate_square_coords(num_points=30, side_length=side_length), generate_square_coords(num_points=30, side_length=side_length, direction='counterclockwise')
        if traj == 'triangle':
            side_length = float(num)
            return generate_triangle_coords(num_points=30, side_length=side_length), generate_square_coords(num_points=30, side_length=side_length, direction='counterclockwise')            

def main(args):
    # Launch TDW Build
    try:
        c = Controller(launch_build=False)
    except Exception as e:
        print(e)
    
    output_path = args.output_path  #EXAMPLE_CONTROLLER_OUTPUT_PATH.joinpath("image_capture")
    task_name = args.name
    print(f"Images will be saved to: {os.path.join(output_path, task_name)}")

    # Camera specifying
    for camera_id in args.cameras:
        camera_id = camera_id.lower()
        camera = get_cameras(camera_id)
        c.add_ons.append(camera)
    capture = ImageCapture(avatar_ids=args.cameras, path=os.path.join(output_path, task_name), png=True)
    c.add_ons.append(capture)

    object_id1 = c.get_unique_id()
    object_id2 = c.get_unique_id()

    # General rendering configurations
    commands = [{"$type": "set_screen_size", "width": args.screen_size[0], "height": args.screen_size[1]}, 
                {"$type": "set_render_quality", "render_quality": args.render_quality},
                ]
    
    #Initialize background
    if args.scene is None:
        commands.append('empty_scene')
    else:
        commands.append(c.get_add_scene(args.scene))

    # Add the object and set location
    model_record1 = ModelLibrarian().get_record(args.object1)
    model_record2 = ModelLibrarian().get_record(args.object2)
    commands.extend(c.get_add_physics_object(model_name=args.object1,
                                                position={"x": 0.2,  "y": 0, "z": 0},
                                                # scale_factor={"x": 5, "y": 5, "z": 5},
                                                object_id=object_id1))
    commands.extend(c.get_add_physics_object(model_name=args.object2,
                                                position={"x": -0.2,  "y": 0, "z": 0},
                                                # scale_factor={"x": 5, "y": 5, "z": 5},
                                                object_id=object_id2))
    c.communicate(commands)

    # Change material of object if provided
    if args.material is not None:
        commands = [c.get_add_material(material_name=args.material)]
        # Set all of the object's visual materials.
        commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record1.substructure, material=args.material, object_id=object_id1))
        commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record2.substructure, material=args.material, object_id=object_id2))
    c.communicate(commands)

    # Get coordinates for motion trajectory
    coordinates1, coordinates2 = get_action_coordinates(args.action)
    if coordinates1 is not None and coordinates2 is not None:
        for (x_d1, y_d1), (x_d2, y_d2) in zip(coordinates1, coordinates2):
            commands = []
            commands.append({"$type": "teleport_object", 
                            "position": {"x": x_d1+0.2, "z": y_d1, "y": 0 }, 
                            "id": object_id1, "physics": True, "absolute": True, "use_centroid": False})
            commands.append({"$type": "teleport_object", 
                            "position": {"x": x_d2-0.2, "z": y_d2, "y": 0 }, 
                            "id": object_id2, "physics": True, "absolute": True, "use_centroid": False})
            c.communicate(commands)

    # Terminate the server after the job is done
    c.communicate({"$type": "terminate"})

# DISPLAY=:4 /data/shared/sim/benchmark/tdw/build/TDW.x86_64 -port 1071
# python tryout_kevin.py --output "/data/shared/sim/benchmark/tdw/image_capture/trajectory_demo" --cameras top --scene empty_scene --name circle --action circle_1
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Screen size
    parser.add_argument("--screen_size", type=int, nargs='+', default=(512, 512), help="Width and Height of Screen. (W, H)")
    # Cameras
    parser.add_argument("--cameras", type=str, nargs='+', default=['top'], choices=['top', 'left', 'right', 'front', 'back'], help="Set which cameras to enable.")
    # Output Path
    parser.add_argument("--output_path", type=str, required=True, help="The path to save the outputs to.")
    # Render Quality
    parser.add_argument("--render_quality", type=int, default=5, help="The Render Quality of the output.")
    # Scene
    parser.add_argument("--scene", type=str, default=None, help="The Scene to initialize.")
    # Object
    parser.add_argument("--object1", type=str, default="toy_monkey_medium")
    parser.add_argument("--object2", type=str, default="apple")
    # Action
    parser.add_argument("--action", type=str, default="circle_1", help="Format: [trajectory]_[radius]")
    # Enable Physics
    # parser.add_argument("--physics", type=bool, default=False, help="Enable Physics.")
    # Task Name
    parser.add_argument("--name", type=str, default="test", help="The name of the task.")
    # Material
    parser.add_argument("--material", type=str, default=None, help="The material of the object.")

    args = parser.parse_args()

    main(args)