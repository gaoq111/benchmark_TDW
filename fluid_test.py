from tdw.controller import Controller
from tdw.add_ons.obi import Obi
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.obi_data.fluids.disk_emitter import DiskEmitter
from tdw.obi_data.fluids.cube_emitter import CubeEmitter
from tdw.obi_data.fluids.sphere_emitter import SphereEmitter
from tdw.tdw_utils import TDWUtils
from tdw.librarian import ModelLibrarian

"""
Pour water into a receptacle.
"""

c = Controller(port=1071, launch_build=False)
c.communicate([
    {"$type": "set_screen_size", "width": 512, "height": 512}, 
                {"$type": "set_render_quality", "render_quality": 10},
])
c.communicate(Controller.get_add_scene(scene_name="tdw_room"))
camera = ThirdPersonCamera(position={"x": -3.75, "y": 1.5, "z": -0.5},
                           look_at={"x": 0, "y": 0, "z": 0},
                           avatar_id="avatar")
capture = ImageCapture(path="./images/fluid", avatar_ids=["avatar"])
obi = Obi()
c.add_ons.extend([camera, obi, capture])
obi.create_fluid(fluid="honey",
                 shape=CubeEmitter(size={"x": 0.5, "y": 0.5, "z": 0.5}),
                 object_id=Controller.get_unique_id(),
                 position={"x": 0, "y": 2.35, "z": -1.5},
                 rotation={"x": 45, "y": 0, "z": 0},
                 speed=10)

#['fluid_receptacle1m_round', 'fluid_receptacle1x1', 'fluid_receptacle1x2']
object_id = c.get_unique_id()
model_name = "fluid_receptacle1m_round"
c.communicate(Controller.get_add_physics_object(model_name=model_name,
                                                object_id=object_id,
                                                library="models_special.json",
                                                kinematic=True,
                                                gravity=False,
                                                scale_factor={"x": 2, "y": 2, "z": 2}))

librarian = ModelLibrarian("models_special.json")
model_record = librarian.get_record(model_name)
material = "concrete_raw_damaged"
commands = []
commands.append(c.get_add_material(material_name=material))
commands.extend(TDWUtils.set_visual_material(c=c, substructure=model_record.substructure, material=material, object_id=object_id))
c.communicate(commands)    

for i in range(50):
    c.communicate([])
c.communicate({"$type": "terminate"})