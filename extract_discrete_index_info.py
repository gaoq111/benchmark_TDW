import json
import random

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def process_data(data):
    new_data = []
    sources = {}
    
    for item in data["shape_section"]:  
        image_path = item["image_path"]
        suffix = image_path.split('_')[-1].split('.')[0]

        if suffix not in sources:
            sources[suffix] = {
                "source": [],
                "objects": {},
                "scene": item["scene"]
            }

            # Process object info
            for obj in item["objects_info"]:
                obj_type = obj["type"]
                obj_color = obj["color"]
                obj_size = obj["size"]
                obj_mtrl = obj["material"]

                if obj_type not in sources[suffix]["objects"]:
                    sources[suffix]["objects"][obj_type] = []
                
                sources[suffix]["objects"][obj_type].append({
                    "type": obj_type,
                    "size": obj_size,
                    "color": obj_color,
                    "material": obj_mtrl
                })

        # Append source image path
        sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/discrete_counting_tdw/images/" + image_path)



    # Create the new data entries
    for key, value in sources.items():
        obj_type_1 = list(value["objects"].keys())[0]
        obj_type_2 = list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0]

        choices = [obj_type_1, obj_type_2, "They are the same"]
        random.shuffle(choices)

        obj_count = {shape: len(objs) for shape, objs in value["objects"].items()}
        num_objects = list(obj_count.values())
        
        if len(set(num_objects)) > 1:
            if num_objects.index(max(num_objects)) == 1:
                answer = choices.index(obj_type_2) + 1
            else:
                answer = choices.index(obj_type_1) + 1
        else:
            answer = choices.index("They are the same") + 1

        background_map = {"tdw_room": 0, "monkey_physics_room": 1,"box_room_2018": 2}
        background = background_map.get(value["scene"], -1)

        new_data.append({
            "source": value["source"],
            "shape1": obj_type_1,
            "shape2": obj_type_2,
            "num_objects1": num_objects[0],
            "num_objects2": num_objects[1] if len(num_objects) > 1 else num_objects[0],
            "background": background,
            "round": 0,
            "objects": value["objects"],
            "choices": choices,
            "answer": answer
        })

    return new_data

def save_new_format(new_data, output_path):
    with open(output_path, 'w') as file:
        for entry in new_data:
            file.write(json.dumps(entry) + '\n')

original_data = read_json('output/discrete_counting_info.json')
processed_data = process_data(original_data)
save_new_format(processed_data, 'index.jsonl')
