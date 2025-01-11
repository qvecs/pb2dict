import datetime

import pytest
from google.protobuf.timestamp_pb2 import Timestamp
from proto.message_pb2 import Message, MyEnum, NestedMessage

from pb2dict import fields, to_dict, to_message


def test_my_message_roundtrip():
    now = datetime.datetime.now(datetime.timezone.utc)
    msg = Message()
    msg.double_val = 3.14
    msg.float_val = 2.72
    msg.int32_val = 42
    msg.int64_val = 4242
    msg.uint32_val = 123
    msg.uint64_val = 1234567
    msg.sint32_val = -42
    msg.sint64_val = -4242
    msg.fixed32_val = 999
    msg.fixed64_val = 9999
    msg.sfixed32_val = -999
    msg.sfixed64_val = -9999
    msg.bool_val = True
    msg.string_val = "Hello"
    msg.bytes_val = b"binary data"
    msg.enum_val = MyEnum.BAR
    msg.timestamp_val.FromDatetime(now)
    msg.repeated_int32_val.extend([1, 2, 3, 100])
    nested1 = msg.repeated_msg_val.add()
    nested1.str_val = "nested1"
    nested1.ts_val.FromDatetime(now)
    nested2 = msg.repeated_msg_val.add()
    nested2.str_val = "nested2"
    nested2.ts_val.FromDatetime(now + datetime.timedelta(days=1))
    msg.str_to_msg_map["key1"].str_val = "map_value1"
    msg.str_to_msg_map["key1"].ts_val.FromDatetime(now)
    msg.str_to_msg_map["key2"].str_val = "map_value2"
    msg.str_to_msg_map["key2"].ts_val.FromDatetime(now + datetime.timedelta(days=2))

    msg_dict = to_dict(msg, use_enum_labels=False)
    msg_roundtrip = to_message(Message, msg_dict)

    assert msg_roundtrip.double_val == 3.14
    assert abs(msg_roundtrip.float_val - 2.72) < 1e-5
    assert msg_roundtrip.int32_val == 42
    assert msg_roundtrip.int64_val == 4242
    assert msg_roundtrip.uint32_val == 123
    assert msg_roundtrip.uint64_val == 1234567
    assert msg_roundtrip.sint32_val == -42
    assert msg_roundtrip.sint64_val == -4242
    assert msg_roundtrip.fixed32_val == 999
    assert msg_roundtrip.fixed64_val == 9999
    assert msg_roundtrip.sfixed32_val == -999
    assert msg_roundtrip.sfixed64_val == -9999
    assert msg_roundtrip.bool_val is True
    assert msg_roundtrip.string_val == "Hello"
    assert msg_roundtrip.bytes_val == b"binary data"
    assert msg_roundtrip.enum_val == MyEnum.BAR

    original_ts = msg.timestamp_val.ToDatetime()
    roundtrip_ts = msg_roundtrip.timestamp_val.ToDatetime()
    assert abs((original_ts - roundtrip_ts).total_seconds()) < 1e-3
    assert list(msg_roundtrip.repeated_int32_val) == [1, 2, 3, 100]
    assert len(msg_roundtrip.repeated_msg_val) == 2
    assert msg_roundtrip.repeated_msg_val[0].str_val == "nested1"
    assert msg_roundtrip.repeated_msg_val[1].str_val == "nested2"
    assert "key1" in msg_roundtrip.str_to_msg_map
    assert "key2" in msg_roundtrip.str_to_msg_map
    assert msg_roundtrip.str_to_msg_map["key1"].str_val == "map_value1"
    assert msg_roundtrip.str_to_msg_map["key2"].str_val == "map_value2"
    orig_key1_ts = msg.str_to_msg_map["key1"].ts_val.ToDatetime()
    rt_key1_ts = msg_roundtrip.str_to_msg_map["key1"].ts_val.ToDatetime()
    assert abs((orig_key1_ts - rt_key1_ts).total_seconds()) < 1e-3


def test_strict_mode_unknown_field():
    data = {"nonexistent_field": 123}
    with pytest.raises(KeyError):
        to_message(Message, data, strict=True)


def test_non_strict_mode_unknown_field():
    data = {"nonexistent_field": 123}
    result = to_message(Message, data, strict=False)
    assert isinstance(result, Message)


def test_ignore_none():
    data = {"int32_val": None, "float_val": 1.234}
    result = to_message(Message, data, ignore_none=True)
    # None should not overwrite int32_val, float_val should be set
    assert result.int32_val == 0  # default since not set
    assert abs(result.float_val - 1.234) < 1e-5


def test_include_defaults():
    msg = Message()
    msg_dict = to_dict(msg, include_defaults=True)
    assert msg_dict["int32_val"] == 0
    assert msg_dict["string_val"] == ""
    assert msg_dict["repeated_int32_val"] == []
    assert msg_dict["str_to_msg_map"] == {}


def test_use_enum_labels():
    msg = Message()
    msg.enum_val = MyEnum.BAZ
    dict_with_labels = to_dict(msg, use_enum_labels=True)
    assert dict_with_labels["enum_val"] == "BAZ"

    roundtrip = to_message(Message, dict_with_labels)
    assert roundtrip.enum_val == MyEnum.BAZ


def test_lowercase_enum_labels():
    msg = Message()
    msg.enum_val = MyEnum.FOO
    dict_with_labels = to_dict(msg, use_enum_labels=True, lowercase_enum_labels=True)
    assert dict_with_labels["enum_val"] == "foo"

    roundtrip = to_message(Message, dict_with_labels)
    assert roundtrip.enum_val == MyEnum.FOO


def test_custom_decode_map():
    def decode_str(s):
        return f"prefix_{s}"

    msg = Message()
    msg.string_val = "test"
    custom_map = {fields.STRING: decode_str}
    dict_custom = to_dict(msg, custom_map)
    assert dict_custom["string_val"] == "prefix_test"
