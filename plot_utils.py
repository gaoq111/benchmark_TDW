from typing import List

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import HTML, display
from matplotlib import animation

import glob
import os
import sys
import shutil
import random
import cv2
import time

#in synchronous mode, sensor data must be added to a queue
import queue
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import math
import json
import random
from multiprocessing import Pool

def display_images(frames, instruction=""):
    num_frames = len(frames)
    col_size = 6
    if(len(frames) < col_size):
        fig_size = 120/len(frames)
    else:
        fig_size = 120/col_size
    fig, ax = plt.subplots(nrows=num_frames//col_size+(num_frames%col_size!=0), ncols=col_size, figsize=(fig_size,fig_size))
    plt.axis('off')
    ax = ax.ravel()
    for i,frame in enumerate(frames):
        ax[i].imshow(frame)
        ax[i].axis('off')
    ax_size = len(ax)
    for i in range(len(frames), ax_size):
        ax[i].set_visible(False)
    plt.suptitle(instruction)
    plt.show()

def carlaImage_postprocess(images):
    new_images = []
    for image in images:
        image = np.reshape(np.copy(image.raw_data),(image.height,image.width,4))[:, :, :3]
        new_images.append(Image.fromarray(image))
    return new_images

def generate_video(video_name, images, fps=10, color_change=True):
    images = images
    end_length = len(images) #int((len(images)//fps)*fps)
    for i,image in enumerate(images):
        images[i] = np.array(image)[:, :, :3]
    height, width, layers = images[0].shape

    video = cv2.VideoWriter(video_name, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width,height))

    for image in images[0:end_length]:
        if image.dtype != np.uint8 and image.dtype != np.uint16:
            if image.dtype == np.float32 or image.dtype == np.float64:
                # Normalize float image to 0-255 and convert to uint8
                image = cv2.convertScaleAbs(image, alpha=(255.0 / np.max(image)))
            else:
                # Convert other types to uint8
                image = image.astype(np.uint8)
        if(color_change):
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        video.write(image)

    video.release()
    cv2.destroyAllWindows()

def generate_video_from_ticks(image_dir, tick_start, tick_end, fps=10, color_change=True, car_id=0, render_mode=""):

    images = get_images_from_ticks(image_dir, tick_start, tick_end, car_id=car_id, render_mode=render_mode)

    end_length = int((len(images)//fps)*fps)

    for i,image in enumerate(images):
        images[i] = np.array(image)[:, :, :3]
    height, width, layers = images[0].shape

    video_name = f"{image_dir}/{tick_start}_{tick_end}_{render_mode}.mp4"

    video = cv2.VideoWriter(video_name, cv2.VideoWriter_fourcc(*'MP4V'), fps, (width,height))

    for image in images:
        if(color_change):
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        video.write(image)

    video.release()
    cv2.destroyAllWindows()

    return video_name

def get_images_from_ticks(image_dir, tick_start, tick_end, car_id=0, render_mode=""):
    images = []
    for i in range(tick_start, tick_end+1):
        if(render_mode == "topdown"):
            image_path = f"{image_dir}/images/{str(i).zfill(6)}_{render_mode}_{car_id}.png"
        else:
            image_path = f"{image_dir}/images/{str(i).zfill(6)}_{car_id}.png"
        if(os.path.exists(image_path)):
            image = Image.open(image_path)
            images.append(image)

    return images

def write_images_to_video(paths, video_name, fps=10, color_change=True):
    images = []
    for path in paths:
        if(os.path.exists(path)):
            images.append(Image.open(path))
    print(f"{len(images)} have been compiled to video")
    generate_video(video_name, images, fps, color_change)

def generate_video_from_sample(sample, name=f"demos/checks/demo_show.mp4", fps=5, compiled=False):
    if(type(sample) is list):
        raw_paths = [item['target'] for item in sample ]
    else:
        if(len(sample['target']) == 0):
            return
        if(type(sample['target'][0]) is not list):
            raw_paths = [sample['target']]
        else:
            raw_paths = sample['target']
    if(compiled):
        all_paths = []
        for raw_path in raw_paths:
            all_paths += raw_path
        raw_paths = [all_paths]

    video_names = []
    for i, raw_path in enumerate(raw_paths):
        paths = [f"output/{pth.replace('_images', '/images')}" for pth in raw_path]
        video_name = name.replace(".mp4", f"_{i}.mp4")
        write_images_to_video(paths, video_name, fps=fps)
        video_names.append(video_name)
    
    return video_names

def display_images_inVideo(images: List[np.ndarray], dpi=100.0, format="html5_video", **kwargs):
    """Display images as an animation in jupyter notebook.

    Args:
        images: images with equal shape.
        dpi: resolution (dots per inch).
        format (str): one of ["html5_video", "jshtml"]

    References:
        https://gist.github.com/foolishflyfox/e30fd8bfbb6a9cee9b1a1fa6144b209c
        http://louistiao.me/posts/notebooks/embedding-matplotlib-animations-in-jupyter-as-interactive-javascript-widgets/
        https://stackoverflow.com/questions/35532498/animation-in-ipython-notebook/46878531#46878531
    """
    h, w = images[0].shape[:2]
    fig = plt.figure(figsize=(h / dpi, w / dpi), dpi=dpi)
    fig_im = plt.figimage(images[0])

    def animate(image):
        fig_im.set_array(image)
        return (fig_im,)

    anim = animation.FuncAnimation(fig, animate, frames=images, **kwargs)
    if format == "html5_video":
        # NOTE(jigu): can not show in VSCode
        display(HTML(anim.to_html5_video()))
    elif format == "jshtml":
        display(HTML(anim.to_jshtml()))
    else:
        raise NotImplementedError(format)

    plt.close(fig)

def save_image(info):
    image, path = info
    if(type(image) is not Image.Image):
        image = Image.fromarray((image* 255).astype(np.uint8))
    image.save(path)

def image_save_generator(images, image_dir):
    for i,image in enumerate(images):
        yield image, os.path.join(image_dir, f"image_{i}.png")

def save_images_pararell(images, image_dir):
    os.makedirs(image_dir, exist_ok=True)
    # Number of processes
    num_processes = 16

    # Create a pool of processes
    with Pool(processes=num_processes) as pool:
        # Map the save_image function to the images
        for _ in pool.imap_unordered(save_image, image_save_generator(images, image_dir)):
            pass

def select_even_frames(img_dir, output_folder, num_samples=6):

    # Create the output folder if it does not exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    if not os.path.exists(img_dir):
        print(f"Error: Image source directory does not exist")
        return

    image_paths = glob.glob(f"{img_dir}/*")
    image_paths.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))
    # Get the total number of frames
    total_frames = len(image_paths)
    
    # selecting the indices evenly
    frame_indices = np.linspace(0, total_frames - 1, num_samples, dtype=int)
    
    saved_count = 0
    saved_names = []

    for frame_index in frame_indices:
        # Set the video capture to the specific frame
        frame = Image.open(image_paths[frame_index])

        frame_filename = os.path.join(output_folder, f"frame_{frame_index}.png")
        if(not os.path.exists(frame_filename)):
            frame.save(frame_filename, 'PNG')
        saved_names.append(frame_filename)
        saved_count += 1

    #print(f"Selected {saved_count} frames from {img_dir} to {output_folder}")

    return saved_names

def extract_even_frames_from_video(video_path, output_folder, num_samples=6):
    # Create the output folder if it does not exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Open the video file
    video_capture = cv2.VideoCapture(video_path)
    if not video_capture.isOpened():
        print(f"Error: Unable to open video file {video_path}")
        return

    # Get the total number of frames
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Calculate the interval between frames to sample
    interval = total_frames // num_samples
    
    frame_indices = np.linspace(0, total_frames - 1, num_samples, dtype=int)
    
    saved_count = 0
    saved_names = []

    for frame_index in frame_indices:
        # Set the video capture to the specific frame
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        success, frame = video_capture.read()

        if success:
            frame_filename = os.path.join(output_folder, f"frame_{frame_index}.png")
            if(not os.path.exists(frame_filename)):
                Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(frame_filename, 'PNG')
            saved_names.append(frame_filename)
            saved_count += 1

    video_capture.release()
    #print(f"Extracted {saved_count} frames from {video_path} to {output_folder}")

    return saved_names
