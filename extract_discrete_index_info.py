import json
import random

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def process_data(data, qstn_type):
    new_data = []
    sources = {}

    if qstn_type == "shape":   
        for item in data["shape_section"]:  
            image_path = item["image_path"]
            suffix = image_path.split('_')[-1].split('.')[0]

            if suffix not in sources:
                sources[suffix] = {
                    "source": [],
                    "color": item["color"],
                    "objects": {},
                    "scene": item["scene"],
                    "sizes": [],
                    "obj_names": [],
                    "poses_final": []
                }

                # Process object info
                for obj in item["objects_info"]:
                    obj_type = obj["type"]
                    obj_color = obj["color"]
                    obj_size = obj["size"]
                    obj_mtrl = obj["material"]
                    obj_pos = obj["position"]

                    if obj_type not in sources[suffix]["objects"]:
                        sources[suffix]["objects"][obj_type] = []
                    
                    sources[suffix]["objects"][obj_type].append({
                        "type": obj_type,
                        "size": obj_size,
                        "color": obj_color,
                        "material": obj_mtrl
                    })

                    sources[suffix]["sizes"].append(obj_size)
                    sources[suffix]["obj_names"].append(obj_type)
                    sources[suffix]["poses_final"].append(obj_pos)

            # Append source image path
            sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/discrete_counting_tdw/images/" + image_path)

        # Create the new data entries
        for key, value in sources.items():
            obj_type_1 = list(value["objects"].keys())[0]
            obj_type_2 = list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0]

            obj_count = {shape: len(objs) for shape, objs in value["objects"].items()}
            num_objects = sum(list(obj_count.values()))

            remaining_numbers = list(set(range(1, 9)) - {num_objects})
            random_three = random.sample(remaining_numbers, 3)
            choices = [num_objects] + random_three
            random.shuffle(choices)

            answer = choices.index(num_objects) + 1

            background_map = {"tdw_room": 0, "monkey_physics_room": 1,"box_room_2018": 2}
            background = background_map.get(value["scene"], -1)

            new_data.append({
                "source": value["source"],
                "color": value["color"],
                "num_objects": num_objects,
                "background": background,
                "round": 0,
                "sizes": value["sizes"],
                "obj_names": value["obj_names"],
                "poses_final": value["poses_final"],
                "choices": choices,
                "answer": answer
            })
    else:
        raise Exception("Unexpected question type.")

    return new_data

def save_new_format(new_data, output_path):
    with open(output_path, 'w') as file:
        for entry in new_data:
            file.write(json.dumps(entry) + '\n')

if __name__ == "__main__":
    original_data = read_json('counting_discrete/discrete_counting_info.json')
    processed_data_shape = process_data(original_data, "shape")
    save_new_format(processed_data_shape, 'index.jsonl')    
