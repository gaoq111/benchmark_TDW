import os
import cv2
import sys

def find_scenario_directory(scenario_number):
    # Scan the directories in the "output" folder to find one that matches the scenario number
    base_path = "./trajectory_new_benchmark"
    directories = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and f"scenario_{scenario_number}_" in d]

    if not directories:
        print(f"Error: No directory found for scenario number {scenario_number}.")
        return None
    
    # Return the first matching directory (assuming unique naming)
    return os.path.join(base_path, directories[0])

def create_video_from_images(scenario_number, fps=2):
    # Find the directory containing the scenario's images
    base_path = find_scenario_directory(scenario_number)
    
    if not base_path:
        return

    # Define the output path for the video
    output_video_path = f"{base_path}/video_output.mp4"

    image_input_path = f"{base_path}/top"

    # Get all image files in the directory, sorted by filename
    image_files = sorted([f for f in os.listdir(image_input_path) if f.endswith((".png", ".jpg", ".jpeg"))])
    
    if not image_files:
        print(f"No images found in {image_input_path}.")
        return

    # Read the first image to get the frame size
    first_image_path = os.path.join(image_input_path, image_files[0])
    first_image = cv2.imread(first_image_path)
    if first_image is None:
        print(f"Error: Unable to read the first image at {first_image_path}.")
        return

    height, width, layers = first_image.shape

    # Create a VideoWriter object to save the video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Use mp4v codec for .mp4 format
    video = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    
    # Write each image frame to the video
    for image_file in image_files:
        image_path = os.path.join(image_input_path, image_file)
        img = cv2.imread(image_path)
        if img is None:
            print(f"Warning: Unable to read image {image_input_path}. Skipping.")
            continue
        video.write(img)

    # Release the video object after writing all frames
    video.release()
    print(f"Video saved at {output_video_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_video.py <scenario_number>")
        sys.exit(1)
    
    scenario_number = sys.argv[1]
    if not scenario_number.isdigit():
        print("Error: scenario_number must be a digit.")
        sys.exit(1)

    create_video_from_images(scenario_number)