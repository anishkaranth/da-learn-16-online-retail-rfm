"""Compact-but-readable JSON: containers that fit in `width` chars are written on one line."""
import json


def dumps(obj, width=110, indent=1, _level=0):
    flat = json.dumps(obj, ensure_ascii=True)
    if len(flat) + _level * indent <= width or not isinstance(obj, (dict, list)) or not obj:
        return flat
    pad, pad_in = " " * (_level * indent), " " * ((_level + 1) * indent)
    if isinstance(obj, dict):
        items = [f"{pad_in}{json.dumps(k)}: {dumps(v, width, indent, _level + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    items = [pad_in + dumps(v, width, indent, _level + 1) for v in obj]
    return "[\n" + ",\n".join(items) + "\n" + pad + "]"
