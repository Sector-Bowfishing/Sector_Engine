"""Minimal stdlib JSON Schema (2020-12 subset) validator.

The repo's Python platform is stdlib-only, so Phase 1A schema checks must not add a
dependency. Supported keywords: type, enum, const, required, properties,
additionalProperties (bool), items, minItems, maxItems, uniqueItems, minLength, pattern,
minimum, maximum, exclusiveMinimum, $ref (local '#/...'), allOf, if/then. Unknown
keywords are ignored (annotations such as description/title/$id).
"""
import re

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "null": type(None),
}


def _is_type(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t]) and not (t != "boolean" and isinstance(v, bool))


def _resolve(root, ref):
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def iter_errors(instance, schema, root=None, path="$"):
    root = root if root is not None else schema
    if "$ref" in schema:
        yield from iter_errors(instance, _resolve(root, schema["$ref"]), root, path)
    if "type" in schema and not _is_type(instance, schema["type"]):
        yield f"{path}: expected {schema['type']}"
        return
    if "const" in schema and instance != schema["const"]:
        yield f"{path}: must equal {schema['const']!r}"
    if "enum" in schema and instance not in schema["enum"]:
        yield f"{path}: {instance!r} not in {schema['enum']}"
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            yield f"{path}: shorter than {schema['minLength']}"
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            yield f"{path}: {instance!r} does not match {schema['pattern']}"
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            yield f"{path}: below minimum {schema['minimum']}"
        if "maximum" in schema and instance > schema["maximum"]:
            yield f"{path}: above maximum {schema['maximum']}"
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            yield f"{path}: must be > {schema['exclusiveMinimum']}"
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            yield f"{path}: fewer than {schema['minItems']} items"
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            yield f"{path}: more than {schema['maxItems']} items"
        if schema.get("uniqueItems"):
            seen = [repr(x) for x in instance]
            if len(seen) != len(set(seen)):
                yield f"{path}: items not unique"
        if "items" in schema:
            for i, item in enumerate(instance):
                yield from iter_errors(item, schema["items"], root, f"{path}[{i}]")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                yield f"{path}: missing required '{key}'"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    yield f"{path}: unexpected property '{key}'"
        for key, sub in props.items():
            if key in instance:
                yield from iter_errors(instance[key], sub, root, f"{path}.{key}")
    for sub in schema.get("allOf", []):
        yield from iter_errors(instance, sub, root, path)
    if "if" in schema and not list(iter_errors(instance, schema["if"], root, path)):
        if "then" in schema:
            yield from iter_errors(instance, schema["then"], root, path)


def validate(instance, schema):
    """Return a list of error strings (empty list == valid)."""
    return list(iter_errors(instance, schema))
