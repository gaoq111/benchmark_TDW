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
                    "objects": {},
                    "scene": item["scene"]
                }

                # Process object info
                for obj in item["objects_info"]:
                    obj_type = obj["type"]
                    obj_type = obj_type.split("_")[1]
                    obj_type = "cylinder" if obj_type == "cyl" else obj_type

                    obj_color = obj["color"]
                    obj_size = obj["size"]

                    if obj_type not in sources[suffix]["objects"]:
                        sources[suffix]["objects"][obj_type] = []
                    
                    sources[suffix]["objects"][obj_type].append({
                        "type": obj_type,
                        "size": obj_size
                    })

            # Append source image path
            sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/relative_counting_tdw/images/" + image_path)



        # Create the new data entries
        for key, value in sources.items():
            shape_1 = list(value["objects"].keys())[0]
            shape_2 = list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0]

            choices = [shape_1, shape_2, "They are the same"]
            random.shuffle(choices)

            obj_count = {shape: len(objs) for shape, objs in value["objects"].items()}
            num_objects = list(obj_count.values())
            
            if len(set(num_objects)) > 1:
                if num_objects.index(max(num_objects)) == 1:
                    answer = choices.index(shape_2) + 1
                else:
                    answer = choices.index(shape_1) + 1
            else:
                answer = choices.index("They are the same") + 1

            background_map = {"tdw_room": 0, "monkey_physics_room": 1, "box_room_2018": 2}
            background = background_map.get(value["scene"], -1)

            new_data.append({
                "source": value["source"],
                "shape1": shape_1,
                "shape2": shape_2,
                "num_objects1": num_objects[0],
                "num_objects2": num_objects[1] if len(num_objects) > 1 else num_objects[0],
                "background": background,
                "round": 0,  
                "objects": value["objects"],
                "choices": choices,
                "answer": answer
            })
    elif qstn_type == "color":  
        for item in data["color_section"]:  
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
                    obj_type = obj_type.split("_")[1]
                    obj_type = "cylinder" if obj_type == "cyl" else obj_type
                    
                    obj_color = obj["color"]
                    obj_size = obj["size"]

                    if obj_color not in sources[suffix]["objects"]:
                        sources[suffix]["objects"][obj_color] = []
                    
                    sources[suffix]["objects"][obj_color].append({
                        "type": obj_type,
                        "size": obj_size
                    })

            # Append source image path
            sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/relative_counting_tdw/images/" + image_path)



        # Create the new data entries
        for key, value in sources.items():
            color_1 = list(value["objects"].keys())[0]
            color_2 = list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0]

            choices = [color_1, color_2, "They are the same"]
            random.shuffle(choices)

            obj_count = {color: len(objs) for color, objs in value["objects"].items()}
            num_objects = list(obj_count.values())
            
            if len(set(num_objects)) > 1:
                if num_objects.index(max(num_objects)) == 1:
                    answer = choices.index(color_2) + 1
                else:
                    answer = choices.index(color_1) + 1
            else:
                answer = choices.index("They are the same") + 1

            background_map = {"tdw_room": 0, "monkey_physics_room": 1, "box_room_2018": 2}
            background = background_map.get(value["scene"], -1)

            new_data.append({
                "source": value["source"],
                "color1": color_1,
                "color2": color_2,
                "num_objects1": num_objects[0],
                "num_objects2": num_objects[1] if len(num_objects) > 1 else num_objects[0],
                "background": background,
                "round": 0,  
                "objects": value["objects"],
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
    original_data = read_json('counting_relative/relative_counting_info.json')
    processed_data_shape = process_data(original_data, "shape")
    processed_data_color = process_data(original_data, "color")
    save_new_format(processed_data_shape, 'index_shape.jsonl')
    save_new_format(processed_data_color, 'index_color.jsonl')
