from pathlib import Path

import cv2
from skimage.metrics import structural_similarity as ssim
import numpy as np

from models import Metrics


def compute_metrics(run_file: Path, ref_file: Path) -> Metrics | None:
    ref_exists = ref_file.is_file() and ref_file.exists()
    run_exists = run_file.is_file() and run_file.exists()
    if not ref_exists or not run_exists:
        print(f"Missing files: {run_file}, {ref_file}")
        return None

    run_image = cv2.imread(str(run_file), cv2.IMREAD_GRAYSCALE)
    ref_image = cv2.imread(str(ref_file), cv2.IMREAD_GRAYSCALE)
    if run_image is None or ref_image is None:
        print(f"Failed to read images: {run_file}, {ref_file}")
        return None
    if run_image.shape != ref_image.shape:
        print(f"Image sizes do not match: {run_image.shape}, {ref_image.shape}")
        return None
    diff_image = cv2.absdiff(run_image, ref_image)

    total_pixels = run_image.size
    diff_pixels = np.count_nonzero(diff_image)
    mse = np.mean((run_image.astype(np.float64) - ref_image.astype(np.float64)) ** 2)
    ssim_value = ssim(run_image, ref_image)

    return Metrics(total_pixels, diff_pixels, mse, ssim_value)
