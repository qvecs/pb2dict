# Protobuf to Dictionary _(pb2dict)_

<p align="center">

  <a href="https://github.com/qvecs/pb2dict/actions?query=workflow%3ABuild">
    <img src="https://github.com/qvecs/pb2dict/workflows/Build/badge.svg">
  </a>

  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg">
  </a>
</p>

Utility to convert Protobuf messages to dictionary with optional custom conversions.

## Install

```
pip install pb2dict
```

## Usage

### Basic Usage

```python
from message_pb2 import Message
from pb2dict import to_dict, to_message

msg = Message(msg=b"hello")

msg_dict = to_dict(msg)
# {'msg': b'hello'}

msg_original = to_message(Message, msg_dict)
# Message(msg=b'hello')
```

### Custom Conversions

Use `fields` to specify overrides for particular field types.

```python
import base64
from message_pb2 import Message

from pb2dict import to_dict, to_message, fields

msg = Message(msg=b"hello")

msg_dict = to_dict(
    pb=msg,
    fields={fields.BYTES: lambda raw: base64.b64encode(raw).decode("utf-8")},
)
# {'msg': 'aGVsbG8='}

original_msg = to_message(
    pb=Message,
    data=msg_dict,
    fields={fields.BYTES: lambda txt: base64.b64decode(txt)},
)
# Message(msg=b'hello')
```

### `fields` Type

```python
class fields:
    DOUBLE
    FLOAT
    INT32
    INT64
    UINT32
    UINT64
    SINT32
    SINT64
    FIXED32
    FIXED64
    SFIXED32
    SFIXED64
    BOOL
    STRING
    BYTES
    ENUM
```