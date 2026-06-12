from __future__ import annotations

from typing import Any

from .types import PngPixels


def find_leading_symbol_gap(
    pixels: PngPixels,
    bbox: list[int],
    bg_rgb: tuple[int, int, int] | list[int],
) -> dict[str, Any] | None:
    if len(bbox) != 4:
        return None
    if len(bg_rgb) != 3:
        return None

    x, y, width, height = [round(value) for value in bbox]
    if width <= 0 or height <= 0:
        return None

    max_search_width = round(min(width * 0.28, height * 1.4))
    if max_search_width < 12 or width <= max_search_width:
        return None

    x1 = clamp_int(x, 0, pixels.width)
    y1 = clamp_int(y + 1, 0, pixels.height)
    x2 = clamp_int(x + max_search_width, 0, pixels.width)
    y2 = clamp_int(y + height - 1, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        return None

    bg = tuple(clamp_int(round(channel), 0, 255) for channel in bg_rgb)
    bg_r, bg_g, bg_b = bg
    column_height = y2 - y1
    ink_densities: list[float] = []
    for column in range(x1, x2):
        ink_count = 0
        for row_index in range(y1, y2):
            row = pixels.rows[row_index]
            offset = column * 3
            red = row[offset]
            green = row[offset + 1]
            blue = row[offset + 2]
            if abs(red - bg_r) + abs(green - bg_g) + abs(blue - bg_b) > 64:
                ink_count += 1
        ink_densities.append(ink_count / column_height)

    def count_ink_columns(start_x: int, end_x: int, min_density: float) -> int:
        probe_x1 = clamp_int(start_x, 0, pixels.width)
        probe_x2 = clamp_int(end_x, 0, pixels.width)
        if probe_x2 <= probe_x1:
            return 0
        count = 0
        for column in range(probe_x1, probe_x2):
            ink_count = 0
            for row_index in range(y1, y2):
                row = pixels.rows[row_index]
                offset = column * 3
                red = row[offset]
                green = row[offset + 1]
                blue = row[offset + 2]
                if abs(red - bg_r) + abs(green - bg_g) + abs(blue - bg_b) > 64:
                    ink_count += 1
            if ink_count / column_height >= min_density:
                count += 1
        return count

    low_ink_threshold = 0.10
    min_gap_width = max(2, round(height * 0.08))
    min_ink_density = 0.12
    min_ink_columns = 2
    candidate_count = len(ink_densities)
    best: dict[str, Any] | None = None

    run_start: int | None = None
    for index, density in enumerate([*ink_densities, 1.0]):
        if index < candidate_count and density <= low_ink_threshold:
            if run_start is None:
                run_start = index
            continue

        if run_start is not None:
            run_end = index
            gap_width = run_end - run_start
            if gap_width >= min_gap_width:
                left_columns = ink_densities[:run_start]
                left_ink_columns = sum(1 for item in left_columns if item >= min_ink_density)
                gap_end_x = x1 + run_end
                right_probe_end = min(x + width, gap_end_x + max_search_width)
                right_ink_columns = count_ink_columns(gap_end_x, right_probe_end, min_ink_density)
                if left_ink_columns >= min_ink_columns and right_ink_columns >= min_ink_columns:
                    gap_density = sum(ink_densities[run_start:run_end]) / gap_width
                    score = gap_width - gap_density
                    if best is None or score > best["score"]:
                        best = {
                            "start": run_start,
                            "width": gap_width,
                            "density": gap_density,
                            "leftInkColumnCount": left_ink_columns,
                            "rightInkColumnCount": right_ink_columns,
                            "score": score,
                        }
            run_start = None

    if best is None:
        return None

    gap_x = x1 + int(best["start"])
    gap_width = int(best["width"])
    cleaned_x = gap_x + gap_width
    cleaned_width = x + width - cleaned_x
    protected_width = gap_x - x
    if protected_width <= 0 or cleaned_width <= 0:
        return None

    return {
        "protectedSymbolBBox": [x, y, protected_width, height],
        "gapBBox": [gap_x, y, gap_width, height],
        "cleanedBBox": [cleaned_x, y, cleaned_width, height],
        "metrics": {
            "maxSearchWidth": max_search_width,
            "minGapWidth": min_gap_width,
            "gapInkDensity": round(float(best["density"]), 4),
            "leftInkColumnCount": int(best["leftInkColumnCount"]),
            "rightInkColumnCount": int(best["rightInkColumnCount"]),
        },
    }


def rect_edge_points(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    sides: set[str],
    thickness: int,
) -> list[tuple[int, int]]:
    edge_thickness = max(1, min(thickness, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2)))
    points: list[tuple[int, int]] = []
    normalized_sides = {side.lower() for side in sides}
    for row_index in range(y1, y2):
        for column in range(x1, x2):
            near_top = row_index < y1 + edge_thickness
            near_bottom = row_index >= y2 - edge_thickness
            near_left = column < x1 + edge_thickness
            near_right = column >= x2 - edge_thickness
            on_top = near_top and ("left" in normalized_sides or not near_left) and ("right" in normalized_sides or not near_right)
            on_bottom = near_bottom and ("left" in normalized_sides or not near_left) and ("right" in normalized_sides or not near_right)
            on_left = near_left and ("top" in normalized_sides or not near_top) and ("bottom" in normalized_sides or not near_bottom)
            on_right = near_right and ("top" in normalized_sides or not near_top) and ("bottom" in normalized_sides or not near_bottom)
            if (
                ("top" in normalized_sides and on_top)
                or ("bottom" in normalized_sides and on_bottom)
                or ("left" in normalized_sides and on_left)
                or ("right" in normalized_sides and on_right)
            ):
                points.append((row_index, column))
    return points


def perimeter_points(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    border = min(2, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
    for row_index in range(y1, y2):
        for column in range(x1, x2):
            if row_index < y1 + border or row_index >= y2 - border or column < x1 + border or column >= x2 - border:
                points.append((row_index, column))
    return points


def points_bbox(points: list[tuple[int, int]]) -> list[int]:
    min_y = min(row_index for row_index, _column in points)
    max_y = max(row_index for row_index, _column in points)
    min_x = min(column for _row_index, column in points)
    max_x = max(column for _row_index, column in points)
    return [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]


def rgb_to_hex(rgb: list[int]) -> str:
    return "#" + "".join(f"{clamp_int(value, 0, 255):02X}" for value in rgb)


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
