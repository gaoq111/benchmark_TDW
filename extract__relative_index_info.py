import json

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def process_data(data):
    new_data = []
    sources = {}
    
    for item in data["color_section"]:  
        image_path = item["image_path"]
        suffix = image_path.split('_')[-1].split('.')[0]  

        if suffix not in sources:
            sources[suffix] = {
                "source": [],
                "objects": {},
                "scene": item["scene"]
            }

        # Append source image path
        sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/relative_counting/tdw/images/" + image_path)

        # Process object info
        for obj in item["objects_info"]:
            obj_type = obj["type"]
            obj_color = obj["color"]
            obj_size = obj["size"]

            if obj_color not in sources[suffix]["objects"]:
                sources[suffix]["objects"][obj_color] = []
            
            sources[suffix]["objects"][obj_color].append({
                "type": obj_type,
                "size": obj_size
            })

    # Create the new data entries
    for key, value in sources.items():
        obj_count = {color: len(objs) for color, objs in value["objects"].items()}
        num_objects = list(obj_count.values())
        answer = num_objects.index(max(num_objects)) + 1 if len(set(num_objects)) > 1 else 3

        background_map = {"tdw_room": 0, "monkey_physics_room": 1}
        background = background_map.get(value["scene"], 3)

        new_data.append({
            "source": value["source"],
            "color1": list(value["objects"].keys())[0],
            "color2": list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0],
            "num_objects1": num_objects[0],
            "num_objects2": num_objects[1] if len(num_objects) > 1 else num_objects[0],
            "background": background,
            "round": 0,  
            "objects": value["objects"],
            "choices": [list(value["objects"].keys())[0], list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0], "They are the same"],
            "answer": answer
        })

    return new_data

def save_new_format(new_data, output_path):
    with open(output_path, 'w') as file:
        for entry in new_data:
            file.write(json.dumps(entry) + '\n')

original_data = read_json('output/relative_counting_info.json')
processed_data = process_data(original_data)
save_new_format(processed_data, 'index.jsonl')
