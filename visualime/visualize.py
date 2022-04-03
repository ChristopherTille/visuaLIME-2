import numpy as np
from typing import Union, Tuple, List, Optional


def select_segments(
    segment_weights: np.ndarray,
    segment_mask: np.ndarray,
    coverage: Optional[float] = None,
    num_of_segments: Optional[int] = None,
    min_coverage: float = 0.0,
    max_coverage: float = 1.0,
    min_num_of_segments: int = 0,
    max_num_of_segments: Optional[int] = None,
) -> np.ndarray:
    """Select the segments to color by selecting segments in the order of descending weight until
    the specified coverage or number of segments is reached.

    Parameters
    ----------
    segment_weights : np.ndarray
        The weights produced by `lime.weigh_segments()`: A one-dimensional array of length num_of_segments.

    segment_mask : np.ndarray
        The mask generated by `create_segments()`: An array of shape (image_width, image_height).

    coverage : float, optional
        The coverage of the selected segments relative to the area of the image.
        Either `coverage` or `num_of_segments` must be specified.

    num_of_segments : int, optional
        The number of segments to select.
        Either `num_of_segments` or `coverage` must be specified.

    min_coverage : float, default 0.0
        The minimum coverage of the selected segments.
        If the specified `num_of_segments` does not reach this coverage, additional
        segments will be selected until this minimum coverage is reached.

    max_coverage : float, default 1.0
        The maximum coverage of the selected segments.
        If the specified `num_of_segments` exceeds this coverage, segments will
        be removed from the selection until the coverage is below this maximum.

    min_num_of_segments : int, default 0
        The minimum number of segments to select.
        Even if the specified `coverage` is reached with fewer segments, at least
        this minimum number of segments are returned.

    max_num_of_segments : int, optional
        The maximum number of segments to select.
        Even if more segments would be required to reach the specified `coverage`,
        at most this maximum number of segments are returned.

    Returns
    -------
    A one-dimensional arrays that contains the selected segment numbers.

    Notes
    -----
    To select the segments with the lowest weights, pass the `segment_weights` array
    with negative sign:

    >>> select_segments(segment_weights=-segment_weights, ...)

    """
    max_num_of_segments = max_num_of_segments or int(np.max(segment_mask) + 1)

    if coverage is None and num_of_segments is None:
        raise ValueError("Either coverage or num_of_segments has to be specified")

    if coverage is not None and num_of_segments is not None:
        raise ValueError("Only either coverage or num_of_segments can be given")

    if min_coverage >= max_coverage:
        raise ValueError("min_coverage has to be strictly smaller than max_coverage")

    if min_num_of_segments >= max_num_of_segments:
        raise ValueError(
            "min_num_of_segments has to be strictly larger than max_num_of_segments"
        )

    _area = segment_mask.shape[0] * segment_mask.shape[1]

    ordered_segments = np.argsort(-segment_weights)

    if coverage is not None:
        coverage = min(coverage, max_coverage)
        coverage = max(coverage, min_coverage)

        for i in range(max_num_of_segments + 1):
            _selected_segments = ordered_segments[:i]
            if np.isin(segment_mask, _selected_segments).sum() / _area >= coverage:
                num_of_segments = i - 2
                break
        else:
            num_of_segments = max_num_of_segments

    if num_of_segments is not None:
        num_of_segments = min(num_of_segments, max_num_of_segments)
        num_of_segments = max(num_of_segments, min_num_of_segments)

        _selected_segments = ordered_segments[: num_of_segments + 1]

        if np.isin(segment_mask, _selected_segments).sum() / _area > max_coverage:
            selected_segments = select_segments(
                segment_weights=segment_weights,
                segment_mask=segment_mask,
                coverage=max_coverage,
            )
        elif np.isin(segment_mask, _selected_segments).sum() / _area < min_coverage:
            selected_segments = select_segments(
                segment_weights=segment_weights,
                segment_mask=segment_mask,
                coverage=min_coverage,
            )
        else:
            selected_segments = _selected_segments

    # TODO: Figure out why PyCharm believes that the return value could potentially be None
    return selected_segments


COLORS = {
    "green": [0, 255, 0],
    "blue": [38, 55, 173],
    "red": [173, 38, 38],
    "white": [255, 255, 255],
    "black": [0, 0, 0],
    "violet": [215, 102, 255],
}


def _get_color(color: str, opacity: float) -> np.ndarray:
    if isinstance(color, str):
        try:
            rgb_color = COLORS[color]
        except KeyError:
            raise ValueError(
                f"Unknown color '{color}'. Available colors: {list(COLORS.keys())}"
            )
    else:
        rgb_color = list(color)

    return np.array(rgb_color + [int(255 * opacity)])


def generate_overlay(
    segment_mask: np.ndarray,
    segments_to_color: Union[np.ndarray, List[int]],
    color: Union[str, Tuple[int]],
    opacity: float,
) -> np.ndarray:
    """Generate a semi-transparent overlay with selected segments colored.

    Parameters
    ----------
    segment_mask : np.ndarray
        The mask generated by `lime.create_segments()`: An array of shape (image_width, image_height).

    segments_to_color : np.ndarray
        An array that contains the integer segment numbers of the segments to color.
        Usually obtained through `select_segments()`.

    color : {str, 3-tuple of ints}
        The color for the segments.
        Can be a pre-defined color name or an RGB tuple.

    opacity : float
        The opacity of the overlay as a number between `0.0` and `1.0`.

    Returns
    -------
    An array of shape (image_width, image_height, 4) representing an RGBA image.

    """
    mask = np.isin(segment_mask, segments_to_color)
    channel_mask = np.dstack((mask, mask, mask, mask))
    return channel_mask * _get_color(color, opacity)


# TODO: Add a function to set the opacity according to segment weights


def scale_opacity(
    overlay: np.ndarray,
    segment_weights: np.ndarray,
    segment_mask: np.ndarray,
    segments_to_color: Union[np.ndarray, List[int]],
    relative_to: Union[str, float] = "max",
) -> np.ndarray:
    rescaled_weights = np.abs(segment_weights / np.linalg.norm(segment_weights))

    if relative_to == "max":
        reference = np.max(rescaled_weights)
    elif isinstance(relative_to, float):
        reference = max(0.0, min(relative_to, 1.0))
    else:
        raise ValueError(f"Invalid value '{relative_to}' for 'relative_to'.")

    # TODO: allow different scaling (e.g., quadratic, logarithmic)
    new_opacity = 255 * rescaled_weights/reference

    new_overlay = np.ndarray.copy(overlay)

    for segment_id in segments_to_color:
        mask = segment_mask == segment_id
        new_overlay[mask, 3] = new_opacity[segment_id]

    return new_overlay


# TODO: Add more functions to re-scale and/or normalize the segments weights, deal with outliers etc.

def smooth_weights(segment_weights: np.ndarray) -> np.ndarray:
    """

    Parameters
    ----------
    segment_weights :

    Returns
    -------

    """
    return 1 / (1 + np.exp(-segment_weights))
