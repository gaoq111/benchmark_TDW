import os
import cv2
import sys

def create_video_from_images(scenario_number, fps=2):
    # Generate the directory path for the images
    base_path = f"./speed_new_benchmark/scenario_{scenario_number}/top"
    
    # Define the output path for the video
    output_video_path = f"./speed_new_benchmark/scenario_{scenario_number}/video_output.mp4"
    
    if not os.path.exists(base_path):
        print(f"Error: Path {base_path} does not exist!")
        return
    
    # Get all image files in the directory, sorted by filename
    image_files = sorted([f for f in os.listdir(base_path) if f.endswith((".png", ".jpg", ".jpeg"))])
    
    if not image_files:
        print(f"No images found in {base_path}.")
        return

    # Read the first image to get the frame size
    first_image_path = os.path.join(base_path, image_files[0])
    first_image = cv2.imread(first_image_path)
    height, width, layers = first_image.shape

    # Create a VideoWriter object to save the video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Use mp4v codec for .mp4 format
    video = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    
    # Write each image frame to the video
    for image_file in image_files:
        image_path = os.path.join(base_path, image_file)
        img = cv2.imread(image_path)
        if img is None:
            print(f"Warning: Unable to read image {image_path}. Skipping.")
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