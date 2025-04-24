from utils import *
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.backend.paths import EXAMPLE_CONTROLLER_OUTPUT_PATH
from tdw.librarian import ModelLibrarian

import argparse
import os
import subprocess
import psutil
import time
import numpy as np

import socket

librarian = ModelLibrarian("models_special.json")
print(librarian)
special_lib = []
for record in librarian.records:
    special_lib.append(record.name)
print(special_lib)
f = open("special_lib.txt", "w")
for name in special_lib:
    f.write(name + "\n")
f.close()


f = open("core_lib.txt", "w")
for record in ModelLibrarian("models_core.json").records:
    f.write(record.name + "\n")
f.close()