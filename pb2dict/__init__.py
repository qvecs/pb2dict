import datetime
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

__all__ = ["to_dict", "to_message", "fields"]

EXTENSION_CONTAINER = "___X"
Timestamp_type_name = "Timestamp"

T = TypeVar("T", bound=Message)


class fields:
    """
    Collection of FieldDescriptor constants.
    """

    DOUBLE = FieldDescriptor.TYPE_DOUBLE
    FLOAT = FieldDescriptor.TYPE_FLOAT
    INT32 = FieldDescriptor.TYPE_INT32
    INT64 = FieldDescriptor.TYPE_INT64
    UINT32 = FieldDescriptor.TYPE_UINT32
    UINT64 = FieldDescriptor.TYPE_UINT64
    SINT32 = FieldDescriptor.TYPE_SINT32
    SINT64 = FieldDescriptor.TYPE_SINT64
    FIXED32 = FieldDescriptor.TYPE_FIXED32
    FIXED64 = FieldDescriptor.TYPE_FIXED64
    SFIXED32 = FieldDescriptor.TYPE_SFIXED32
    SFIXED64 = FieldDescriptor.TYPE_SFIXED64
    BOOL = FieldDescriptor.TYPE_BOOL
    STRING = FieldDescriptor.TYPE_STRING
    BYTES = FieldDescriptor.TYPE_BYTES
    ENUM = FieldDescriptor.TYPE_ENUM


DEFAULT_DECODE_MAP: Dict[int, Callable[[Any], Any]] = {
    fields.DOUBLE: float,
    fields.FLOAT: float,
    fields.INT32: int,
    fields.INT64: int,
    fields.UINT32: int,
    fields.UINT64: int,
    fields.SINT32: int,
    fields.SINT64: int,
    fields.FIXED32: int,
    fields.FIXED64: int,
    fields.SFIXED32: int,
    fields.SFIXED64: int,
    fields.BOOL: bool,
    fields.STRING: str,
    fields.BYTES: bytes,
    fields.ENUM: int,
}


def _is_map_field(fd: FieldDescriptor) -> bool:
    """
    Checks if a field descriptor corresponds to a map field.

    A map field is technically a repeated message where the message has a
    special 'map_entry' option set to True.
    """
    return (
        fd.type == FieldDescriptor.TYPE_MESSAGE
        and fd.message_type.has_options
        and fd.message_type.GetOptions().map_entry
    )


def _decode_call(
    fd: FieldDescriptor,
    custom_map: Dict[int, Callable[[Any], Any]],
    use_enum_labels: bool,
    lowercase_enum_labels: bool,
) -> Optional[Callable[[Any], Any]]:
    """
    Determines and returns a callable for decoding a single Protobuf field.

    1. If the field type is in custom_map, use that.
    2. If the field is a Timestamp, return a callable to convert it to datetime.
    3. If the field is a nested sub-message, return a callable that calls to_dict.
    4. If the field is an enum and use_enum_labels is True, return a callable
       that converts int enum values to labels (optionally lowercase).
    5. Otherwise, fall back to DEFAULT_DECODE_MAP if available.
    """
    if fd.type in custom_map:
        return custom_map[fd.type]

    if fd.message_type and fd.message_type.name == Timestamp_type_name:
        return lambda ts: ts.ToDatetime()

    if fd.type == FieldDescriptor.TYPE_MESSAGE:
        # Nested submessage -> call to_dict
        return lambda m: to_dict(
            m,
            custom_map,
            use_enum_labels=use_enum_labels,
            include_defaults=False,
            lowercase_enum_labels=lowercase_enum_labels,
        )

    if use_enum_labels and fd.type == FieldDescriptor.TYPE_ENUM:
        return lambda val: (
            fd.enum_type.values_by_number[int(val)].name.lower()
            if lowercase_enum_labels
            else fd.enum_type.values_by_number[int(val)].name
        )

    return DEFAULT_DECODE_MAP.get(fd.type)


def to_dict(
    pb: Message,
    fields: Optional[Dict[int, Callable[[Any], Any]]] = None,
    use_enum_labels: bool = False,
    include_defaults: bool = False,
    lowercase_enum_labels: bool = False,
) -> Dict[str, Any]:
    """
    Converts a Protobuf message into a Python dictionary representation.

    Args:
        pb: The Protobuf message instance to convert.
        fields: Optional dictionary mapping field types (like fields.INT32)
            to custom decode callables, overriding default behavior.
        use_enum_labels: If True, convert enum int values to their string names.
        include_defaults: If True, include default values for fields that are not set.
        lowercase_enum_labels: If True (and use_enum_labels is True), convert
            enum labels to lowercase.

    Returns:
        A dict with data from the message, possibly including defaults and
        converted enums/timestamps.
    """
    if fields is None:
        fields = {}

    result: Dict[str, Any] = {}
    extensions: Dict[str, Any] = {}
    decode_cache: Dict[FieldDescriptor, Callable[[Any], Any]] = {}

    for fd, raw_value in pb.ListFields():
        if _is_map_field(fd):
            # For map fields, figure out how to decode the value type.
            map_val_desc = fd.message_type.fields_by_name["value"]
            if map_val_desc not in decode_cache:
                decode_cache[map_val_desc] = _decode_call(map_val_desc, fields, use_enum_labels, lowercase_enum_labels)
            map_decode_fn = decode_cache[map_val_desc]
            result[fd.name] = {k: map_decode_fn(v) for k, v in raw_value.items()}
            continue

        if fd not in decode_cache:
            decode_cache[fd] = _decode_call(fd, fields, use_enum_labels, lowercase_enum_labels)
        decode_fn = decode_cache[fd]

        # Repeated fields => apply the decode function to each element
        if fd.label == FieldDescriptor.LABEL_REPEATED:
            decode_fn = lambda vals, fn=decode_fn: [fn(x) for x in vals]

        # Extensions get stored separately
        if fd.is_extension:
            extensions[str(fd.number)] = decode_fn(raw_value)
        else:
            result[fd.name] = decode_fn(raw_value)

    if include_defaults:
        for fdesc in pb.DESCRIPTOR.fields:
            # If field is missing, not in a oneof, and not a singular submessage
            if (
                fdesc.name not in result
                and not fdesc.containing_oneof
                and not (
                    fdesc.label != FieldDescriptor.LABEL_REPEATED and fdesc.cpp_type == FieldDescriptor.CPPTYPE_MESSAGE
                )
            ):
                if _is_map_field(fdesc):
                    result[fdesc.name] = {}
                elif fdesc.label == FieldDescriptor.LABEL_REPEATED:
                    result[fdesc.name] = []
                elif fdesc.type == FieldDescriptor.TYPE_ENUM and use_enum_labels:
                    if fdesc not in decode_cache:
                        decode_cache[fdesc] = _decode_call(fdesc, fields, use_enum_labels, lowercase_enum_labels)
                    result[fdesc.name] = decode_cache[fdesc](fdesc.default_value)
                else:
                    result[fdesc.name] = fdesc.default_value

    if extensions:
        result[EXTENSION_CONTAINER] = extensions

    return result


def to_message(
    pb: Union[Type[T], T],
    data: Dict[str, Any],
    fields: Optional[Dict[int, Callable[[Any], Any]]] = None,
    strict: bool = True,
    ignore_none: bool = False,
) -> T:
    if fields is None:
        fields = {}

    if isinstance(pb, type):
        pb = pb()

    field_info = []
    for k, v in data.items():
        if k == EXTENSION_CONTAINER:
            continue
        if k not in pb.DESCRIPTOR.fields_by_name:
            if strict:
                raise KeyError(f"{pb.__class__.__name__} has no field '{k}'")
            continue
        desc = pb.DESCRIPTOR.fields_by_name[k]
        field_info.append((desc, v, getattr(pb, k, None)))

    # Handle extensions
    for ext_num_str, ext_val in data.get(EXTENSION_CONTAINER, {}).items():
        try:
            ext_num = int(ext_num_str)
        except ValueError:
            raise ValueError("Extension keys must be integers.")
        if ext_num not in pb._extensions_by_number:
            if strict:
                raise KeyError(f"{pb} has no extension with number {ext_num}")
            continue
        ext_field = pb._extensions_by_number[ext_num]
        field_info.append((ext_field, ext_val, pb.Extensions[ext_field]))

    for fd, input_val, current_val in field_info:
        if ignore_none and input_val is None:
            continue

        if fd.label == FieldDescriptor.LABEL_REPEATED:
            if _is_map_field(fd):
                key_fd = fd.message_type.fields_by_name["key"]
                val_fd = fd.message_type.fields_by_name["value"]
                for mk, mv in input_val.items():
                    if ignore_none and mv is None:
                        continue
                    if val_fd.cpp_type == FieldDescriptor.CPPTYPE_MESSAGE:
                        to_message(getattr(pb, fd.name)[mk], mv, fields, strict, ignore_none)
                    else:
                        if key_fd.type in fields:
                            mk = fields[key_fd.type](mk)
                        if val_fd.type in fields:
                            mv = fields[val_fd.type](mv)
                        getattr(pb, fd.name)[mk] = mv
            else:
                for item in input_val:
                    if ignore_none and item is None:
                        continue
                    if fd.type == FieldDescriptor.TYPE_MESSAGE:
                        sub_msg = current_val.add()
                        to_message(sub_msg, item, fields, strict, ignore_none)
                    elif fd.type == FieldDescriptor.TYPE_ENUM and isinstance(item, str):
                        try:
                            enum_num = fd.enum_type.values_by_name[item].number
                        except KeyError:
                            if item.upper() in fd.enum_type.values_by_name:
                                enum_num = fd.enum_type.values_by_name[item.upper()].number
                            else:
                                if strict:
                                    raise KeyError(f"Invalid enum label '{item}' for {fd.name}")
                                # Non-strict fallback
                                enum_num = 0
                        current_val.append(enum_num)
                    elif isinstance(item, datetime.datetime):
                        ts = Timestamp()
                        ts.FromDatetime(item)
                        current_val.add().CopyFrom(ts)
                    else:
                        if fd.type in fields:
                            item = fields[fd.type](item)
                        current_val.append(item)
            continue

        # Single field
        if isinstance(input_val, datetime.datetime):
            ts = Timestamp()
            ts.FromDatetime(input_val)
            getattr(pb, fd.name).CopyFrom(ts)
            continue

        if fd.type == FieldDescriptor.TYPE_MESSAGE:
            to_message(current_val, input_val, fields, strict, ignore_none)
            continue

        if fd.type in fields:
            input_val = fields[fd.type](input_val)

        if fd.is_extension:
            pb.Extensions[fd] = input_val
            continue

        # Convert enum labels -> numbers
        if fd.type == FieldDescriptor.TYPE_ENUM and isinstance(input_val, str):
            try:
                input_val = fd.enum_type.values_by_name[input_val].number
            except KeyError:
                # Fallback to uppercase
                up = input_val.upper()
                if up in fd.enum_type.values_by_name:
                    input_val = fd.enum_type.values_by_name[up].number
                else:
                    if strict:
                        raise KeyError(f"Invalid enum label '{input_val}' for {fd.name}")
                    # Non-strict fallback
                    input_val = 0

        setattr(pb, fd.name, input_val)

    return pb
