import numpy as np
import math
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.third_person_camera import ThirdPersonCamera
from tdw.add_ons.image_capture import ImageCapture
from tdw.librarian import SceneLibrarian
import time
import os
import subprocess



def generate_circle_coords(num_points: int = 100, radius: float = 1, center: tuple = (0, 0), theta_start=0, direction="clockwise") -> list:
    """
    Generate the coordinates of a circle.

    :param num_points: The number of points in the circle.
    :param radius: The radius of the circle.
    :param center: A tuple (x_center, y_center) specifying the center of the circle.
    :param theta_start: The starting angle of the circle.
    :param direction: The direction of the circle. Options: "clockwise", "counterclockwise".
    :return: A list of tuples: [(x1, y1), (x2, y2), ...]
    """

    x_center, y_center = center

    # Angles in radians
    if(direction == "clockwise"):
        angles = np.linspace(theta_start, theta_start - 2 * np.pi, num_points)
    else:
        angles = np.linspace(theta_start, theta_start + 2 * np.pi, num_points)


    # Coordinates
    x = x_center + radius * np.cos(angles)
    y = y_center + radius * np.sin(angles)

    # Combine x and y into a list of tuples
    return list(zip(x, y))



def generate_square_coords(num_points: int = 100, side_length: float = 1, center: tuple = (0, 0), direction: str = "clockwise") -> list:
    """
    Generate the coordinates of a square around a specified center.

    :param num_points: The number of points on the square's perimeter.
    :param side_length: The length of the side of the square.
    :param center: A tuple (x_center, y_center) specifying the center of the square.
    :param direction: The direction of the square. Options: "clockwise", "counterclockwise".
    :return: A list of tuples: [(x1, y1), (x2, y2), ...]
    """
    x_center, y_center = center
    half_side = side_length / 2
    points = []
    
    points_per_side = num_points // 4
    remainder = num_points % 4

    if direction == 'clockwise':
        # (top)
        x = np.linspace(x_center - half_side, x_center + half_side, points_per_side + (1 if remainder > 0 else 0))
        y = np.full_like(x, y_center + half_side)
        points.extend(zip(x, y))
        
        # (right)
        x = np.full(points_per_side + (1 if remainder > 1 else 0), x_center + half_side)
        y = np.linspace(y_center + half_side, y_center - half_side, points_per_side + (1 if remainder > 1 else 0))
        points.extend(zip(x, y))
        
        # (bottom)
        x = np.linspace(x_center + half_side, x_center - half_side, points_per_side + (1 if remainder > 2 else 0))
        y = np.full_like(x, y_center - half_side)
        points.extend(zip(x, y))
        
        # (left)
        x = np.full(points_per_side, x_center - half_side)
        y = np.linspace(y_center - half_side, y_center + half_side, points_per_side)
        points.extend(zip(x, y))
    elif direction == 'counterclockwise':
        # (top)
        x = np.linspace(x_center - half_side, x_center + half_side, points_per_side + (1 if remainder > 0 else 0))
        y = np.full_like(x, y_center + half_side)
        points.extend(zip(x, y))
        
        # (left)
        x = np.full(points_per_side + (1 if remainder > 1 else 0), x_center - half_side)
        y = np.linspace(y_center + half_side, y_center - half_side, points_per_side + (1 if remainder > 1 else 0))
        points.extend(zip(x, y))
        
        # (bottom)
        x = np.linspace(x_center - half_side, x_center + half_side, points_per_side + (1 if remainder > 2 else 0))
        y = np.full_like(x, y_center - half_side)
        points.extend(zip(x, y))
        
        # (right)
        x = np.full(points_per_side, x_center + half_side)
        y = np.linspace(y_center - half_side, y_center + half_side, points_per_side)
        points.extend(zip(x, y))

    return points[:num_points]


def generate_triangle_coords(num_points: int = 100, side_length: float = 1, center: tuple = (0, 0), direction: str = "clockwise") -> list:
    """
    Generate the coordinates of an equilateral triangle around a specified center.

    :param num_points: The number of points on the triangle's perimeter.
    :param side_length: The length of the side of the triangle.
    :param center: A tuple (x_center, y_center) specifying the center of the triangle.
    :param direction: The direction of the triangle. Options: "clockwise", "counterclockwise".
    :return: A list of tuples: [(x1, y1), (x2, y2), ...]
    """
    
    x_center, y_center = center

    # Number of points per side
    points_per_side = num_points // 3
    remainder = num_points % 3

    # Height of the equilateral triangle
    h = np.sqrt(3) / 2 * side_length

    # Vertices of the equilateral triangle in counterclockwise order around the center
    counterclockwise_vertices = np.array([
        [x_center, y_center + 2 * h / 3],
        [x_center - side_length / 2, y_center - h / 3],
        [x_center + side_length / 2, y_center - h / 3]
    ])
    
    if direction == "clockwise":
        vertices = counterclockwise_vertices[::-1]
    elif direction == 'counterclockwise':
        vertices = counterclockwise_vertices

    # Generate points for each side
    side1 = np.linspace(vertices[0], vertices[1], points_per_side + (1 if remainder > 0 else 0), endpoint=False)
    side2 = np.linspace(vertices[1], vertices[2], points_per_side + (1 if remainder > 1 else 0), endpoint=False)
    side3 = np.linspace(vertices[2], vertices[0], points_per_side, endpoint=False)

    # Combine the points
    coords = np.vstack((side1, side2, side3))

    # Select the exact number of points requested
    coords = coords[:num_points]

    return list(map(tuple, coords))

