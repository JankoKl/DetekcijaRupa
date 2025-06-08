import torch
import cv2
import numpy as np
import matplotlib.pyplot as plt

# Load MiDaS model
midas = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
midas.to("cuda" if torch.cuda.is_available() else "cpu").eval()

# Load transforms for MiDaS_small
midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
transform = midas_transforms.small_transform
