"""
DJI Thermal SDK wrapper for extracting temperature data from R-JPEG images.
Handles SDK initialization, image processing, and temperature extraction.

DLL files are expected at backend/models/windows/ (shipped with the project).
"""

import ctypes as CT
from ctypes import c_int32, c_uint8
from pathlib import Path
import tempfile

import numpy as np

_sdk_initialized = False
_init_error = None

_BACKEND_DIR = Path(__file__).resolve().parent.parent
DLL_DIR = str(_BACKEND_DIR / "models" / "windows")
DLL_PATH = str(_BACKEND_DIR / "models" / "windows" / "libdirp.dll")


def dll_files_present() -> bool:
    return Path(DLL_PATH).is_file()


def init_sdk() -> tuple[bool, str]:
    global _sdk_initialized, _init_error
    if _sdk_initialized:
        return True, "SDK already initialized."

    if not dll_files_present():
        _init_error = "libdirp.dll not found"
        return False, f"DLL not found at `{DLL_PATH}`."

    try:
        from dji_thermal_sdk.dji_sdk import dji_init
        dji_init(dllpath=DLL_PATH)
        _sdk_initialized = True
        return True, "DJI Thermal SDK initialized successfully."
    except Exception as e:
        _init_error = str(e)
        return False, f"SDK initialization failed: {e}"


def is_initialized() -> bool:
    return _sdk_initialized


def extract_temperature_map(image_bytes: bytes, dtype: str = "float32") -> np.ndarray:
    """
    Extract per-pixel temperature values from R-JPEG binary data.
    dtype: 'float32' (Celsius as float) or 'int16' (Celsius * 10 as int).
    Returns a 2D numpy array of temperatures.
    """
    if not _sdk_initialized:
        raise RuntimeError("SDK not initialized. Call init_sdk() first.")

    from dji_thermal_sdk.dji_sdk import (
        dirp_create_from_rjpeg,
        dirp_get_rjpeg_resolution,
        dirp_measure_ex,
        dirp_destroy,
        dirp_resolution_t,
        DIRP_SUCCESS,
    )

    handle = CT.c_void_p()
    size = c_int32(len(image_bytes))
    rjpeg_data = CT.create_string_buffer(len(image_bytes))
    rjpeg_data.value = image_bytes

    ret = dirp_create_from_rjpeg(rjpeg_data, size, CT.byref(handle))
    if ret != DIRP_SUCCESS:
        raise ValueError(f"Failed to create R-JPEG handle (code {ret}).")

    try:
        resolution = dirp_resolution_t()
        ret = dirp_get_rjpeg_resolution(handle, CT.byref(resolution))
        if ret != DIRP_SUCCESS:
            raise ValueError(f"Failed to get resolution (code {ret}).")

        h, w = resolution.height, resolution.width

        if dtype == "float32":
            buf_size = h * w * CT.sizeof(CT.c_float)
            buf = CT.create_string_buffer(buf_size)
            ret = dirp_measure_ex(handle, CT.byref(buf), buf_size)
            if ret != DIRP_SUCCESS:
                raise ValueError(f"dirp_measure_ex failed (code {ret}).")
            temp_array = np.frombuffer(buf.raw, dtype=np.float32).reshape(h, w)
        else:
            buf_size = h * w * CT.sizeof(CT.c_int16)
            buf = CT.create_string_buffer(buf_size)
            ret = dirp_measure_ex(handle, CT.byref(buf), buf_size)
            if ret != DIRP_SUCCESS:
                raise ValueError(f"dirp_measure_ex failed (code {ret}).")
            raw = np.frombuffer(buf.raw, dtype=np.int16).reshape(h, w)
            temp_array = raw.astype(np.float32) / 10.0

        return temp_array
    finally:
        dirp_destroy(handle)


def render_thermal_image(image_bytes: bytes, palette: int = 0) -> np.ndarray:
    """
    Render a pseudo-color thermal image using the given palette index.
    Returns an HxWx3 uint8 RGB numpy array.

    Palette options:
        0=WhiteHot, 1=Fulgurite, 2=IronRed, 3=HotIron,
        4=Medical, 5=Arctic, 6=Rainbow1, 7=Rainbow2, 8=Tint, 9=BlackHot
    """
    if not _sdk_initialized:
        raise RuntimeError("SDK not initialized. Call init_sdk() first.")

    from dji_thermal_sdk.dji_sdk import (
        dirp_create_from_rjpeg,
        dirp_get_rjpeg_resolution,
        dirp_set_pseudo_color,
        dirp_process,
        dirp_destroy,
        dirp_resolution_t,
        DIRP_SUCCESS,
        c_int,
    )

    handle = CT.c_void_p()
    size = c_int32(len(image_bytes))
    rjpeg_data = CT.create_string_buffer(len(image_bytes))
    rjpeg_data.value = image_bytes

    ret = dirp_create_from_rjpeg(rjpeg_data, size, CT.byref(handle))
    if ret != DIRP_SUCCESS:
        raise ValueError(f"Failed to create R-JPEG handle (code {ret}).")

    try:
        resolution = dirp_resolution_t()
        ret = dirp_get_rjpeg_resolution(handle, CT.byref(resolution))
        if ret != DIRP_SUCCESS:
            raise ValueError(f"Failed to get resolution (code {ret}).")

        h, w = resolution.height, resolution.width

        dirp_set_pseudo_color(handle, c_int(palette))

        buf_size = h * w * 3 * CT.sizeof(c_uint8)
        buf = CT.create_string_buffer(buf_size)
        ret = dirp_process(handle, CT.byref(buf), buf_size)
        if ret != DIRP_SUCCESS:
            raise ValueError(f"dirp_process failed (code {ret}).")

        img = np.frombuffer(buf.raw, dtype=np.uint8).reshape(h, w, 3)
        return img
    finally:
        dirp_destroy(handle)


def get_temperature_stats(temp_map: np.ndarray) -> dict:
    """Compute summary statistics from a temperature map (2D float array)."""
    valid = temp_map[np.isfinite(temp_map)]
    if valid.size == 0:
        return {}
    return {
        "min_c": float(np.min(valid)),
        "max_c": float(np.max(valid)),
        "mean_c": float(np.mean(valid)),
        "median_c": float(np.median(valid)),
        "std_c": float(np.std(valid)),
        "height": temp_map.shape[0],
        "width": temp_map.shape[1],
        "pixels": int(valid.size),
    }


def convert_temp_map(temp_map: np.ndarray, unit: str) -> np.ndarray:
    """Convert a Celsius temperature map to the desired unit."""
    if unit == "Fahrenheit":
        return temp_map * 9 / 5 + 32
    if unit == "Kelvin":
        return temp_map + 273.15
    return temp_map


def get_roi_stats(temp_map: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> dict:
    """Return stats for a rectangular region of interest (pixel coordinates)."""
    roi = temp_map[y1:y2, x1:x2]
    return get_temperature_stats(roi)


def save_bytes_to_temp(image_bytes: bytes, suffix: str = ".jpg") -> str:
    """Save bytes to a temporary file and return its path (caller must delete)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(image_bytes)
    tmp.close()
    return tmp.name
