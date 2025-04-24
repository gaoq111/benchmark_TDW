from tdw.librarian import ModelLibrarian, MaterialLibrarian, SceneLibrarian
from pprint import pprint

M = MaterialLibrarian()
MATERIAL_TYPES = M.get_material_types()
MATERIAL_NAMES = {mtype: [m.name for m in M.get_all_materials_of_type(mtype)] \
                  for mtype in MATERIAL_TYPES}

pprint(MATERIAL_NAMES)