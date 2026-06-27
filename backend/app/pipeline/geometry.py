"""Scale rule geometry from editor reference size to frame size."""


def scale_geometry(geometry: dict, frame_w: int, frame_h: int) -> dict:
    if not geometry or frame_w <= 0 or frame_h <= 0:
        return geometry or {}

    ref = geometry.get("reference_size") or {"width": 640, "height": 360}
    rw = ref.get("width") or 640
    rh = ref.get("height") or 360
    if rw == frame_w and rh == frame_h:
        return geometry

    sx = frame_w / rw
    sy = frame_h / rh
    scaled = dict(geometry)

    line = geometry.get("line")
    if line:
        scaled["line"] = {
            "start": [int(line["start"][0] * sx), int(line["start"][1] * sy)],
            "end": [int(line["end"][0] * sx), int(line["end"][1] * sy)],
        }

    polygon = geometry.get("polygon")
    if polygon:
        scaled["polygon"] = [[int(p[0] * sx), int(p[1] * sy)] for p in polygon]

    return scaled
