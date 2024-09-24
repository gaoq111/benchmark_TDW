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
                    "scene": item["scene"],
                    "gt_answer": item["gt_answer"]
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
            sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/continuous_counting_tdw/images_smoothness/" + image_path)

        # Create the new data entries
        for key, value in sources.items():
            obj_type_1 = list(value["objects"].keys())[0]
            obj_type_2 = list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0]

            choices = [obj_type_1, obj_type_2, "They are the same"]
            random.shuffle(choices)

            obj_count = {shape: len(objs) for shape, objs in value["objects"].items()}
            num_objects = list(obj_count.values())
            
            # translate answer
            choices_character = ["A", "B", "C"]
            choices = [obj_type_1, obj_type_2, "They are the same"]

            combined = list(zip(choices_character, choices))
            random.shuffle(combined)

            choices_character, choices = zip(*combined)
            choices_character = list(choices_character)
            choices = list(choices)

            answer = choices_character.index(value["gt_answer"]) + 1

            background_map = {"tdw_room": 0, "monkey_physics_room": 1,"box_room_2018": 2}
            background = background_map.get(value["scene"], -1)

            new_data.append({
                "source": value["source"],
                "shape1": obj_type_1,
                "shape2": obj_type_2,
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
                    "scene": item["scene"],
                    "gt_answer": item["gt_answer"]
                }

                # Process object info
                for obj in item["objects_info"]:
                    obj_type = obj["type"]
                    obj_color = obj["color"]
                    obj_size = obj["size"]
                    obj_mtrl = obj["material"]

                    if obj_color not in sources[suffix]["objects"]:
                        sources[suffix]["objects"][obj_color] = []
                    
                    sources[suffix]["objects"][obj_color].append({
                        "type": obj_type,
                        "size": obj_size,
                        "color": obj_color,
                        "material": obj_mtrl
                    })

            # Append source image path
            sources[suffix]["source"].append("/data/shared/sim/benchmark/evaluation/datasets/continuous_counting_tdw/images_smoothness/" + image_path)
                # Create the new data entries
        for key, value in sources.items():
            obj_color_1 = list(value["objects"].keys())[0]
            obj_color_2 = list(value["objects"].keys())[1] if len(value["objects"].keys()) > 1 else list(value["objects"].keys())[0]

            choices_character = ["A", "B", "C"]
            choices = [obj_color_1, obj_color_2, "They are the same"]

            combined = list(zip(choices_character, choices))
            random.shuffle(combined)

            choices_character, choices = zip(*combined)
            choices_character = list(choices_character)
            choices = list(choices)

            answer = choices_character.index(value["gt_answer"]) + 1

            background_map = {"tdw_room": 0, "monkey_physics_room": 1,"box_room_2018": 2}
            background = background_map.get(value["scene"], -1)

            new_data.append({
                "source": value["source"],
                "color1": obj_color_1,
                "color2": obj_color_2,
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
    original_data = read_json('counting_smoothness/continuous_quantity_smoothness.json')
    processed_data_shape = process_data(original_data, "shape")
    processed_data_color = process_data(original_data, "color")
    save_new_format(processed_data_shape, 'index_shape.jsonl')
    save_new_format(processed_data_color, 'index_color.jsonl')
