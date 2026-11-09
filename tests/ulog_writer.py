"""Scrittore ULog minimale, usato solo per generare log di prova."""

from __future__ import annotations

import struct

import numpy as np

_CODES = {
    "int8_t": "b", "uint8_t": "B", "int16_t": "h", "uint16_t": "H", "int32_t": "i",
    "uint32_t": "I", "int64_t": "q", "uint64_t": "Q", "float": "f", "double": "d",
    "bool": "?", "char": "c",
}


class ULogWriter:
    def __init__(self, start_timestamp=0):
        self.start = start_timestamp
        self.formats = {}  # nome -> [(tipo, n, campo)]
        self.info = []
        self.params = {}
        self.defaults = {}
        self.topics = []  # (nome, multi_id, dict campi -> array)
        self.messages = []  # (timestamp, livello, testo)
        self.param_changes = []  # (timestamp, nome, valore)

    def add_format(self, name, fields):
        """fields: lista di stringhe 'float[3] xyz' (il primo deve essere 'uint64_t timestamp')."""
        parsed = []
        for f in fields:
            t, n = f.split(" ")
            size = 0
            if "[" in t:
                size = int(t[t.index("[") + 1 : t.index("]")])
                t = t[: t.index("[")]
            parsed.append((t, size, n))
        self.formats[name] = parsed

    def add_info(self, key, value):
        self.info.append((key, value))

    def add_topic(self, name, data, multi_id=0):
        self.topics.append((name, multi_id, data))

    def add_message(self, timestamp, level, text):
        self.messages.append((int(timestamp), level, text))

    def _expand(self, name, prefix=""):
        """Campi base (anche dei tipi annidati) come (nome piatto, tipo, dimensione)."""
        out = []
        for t, size, n in self.formats[name]:
            if t in _CODES:
                out.append((prefix + n, t, size))
            else:
                for i in range(max(1, size)):
                    sub = f"{prefix}{n}[{i}]." if size else f"{prefix}{n}."
                    out.extend(c for c in self._expand(t, sub) if not (c[0].startswith(sub) and c[0][len(sub):] == "timestamp" and False))
        return out

    def _fmt_struct(self, name):
        code = "<"
        cols = []
        for n, t, size in self._expand(name):
            if size:
                code += f"{size}{_CODES[t]}" if t != "char" else f"{size}s"
                cols.append((n, t, size))
            else:
                code += _CODES[t]
                cols.append((n, t, 0))
        return struct.Struct(code), cols

    def write(self, path):
        out = bytearray()
        out += b"ULog\x01\x12\x35" + bytes([1]) + struct.pack("<Q", self.start)

        def msg(mtype, payload):
            out.extend(struct.pack("<HB", len(payload), ord(mtype)))
            out.extend(payload)

        msg("B", bytes(8) + bytes(8) + struct.pack("<QQQ", 0, 0, 0))
        for key, value in self.info:
            if isinstance(value, str):
                v = value.encode()
                k = f"char[{len(v)}] {key}".encode()
            elif isinstance(value, float):
                v = struct.pack("<f", value)
                k = f"float {key}".encode()
            else:
                v = struct.pack("<I", value)
                k = f"uint32_t {key}".encode()
            msg("I", bytes([len(k)]) + k + v)
        for name, fields in self.formats.items():
            spec = name + ":" + "".join(f"{t}{'[%d]' % s if s else ''} {n};" for t, s, n in fields)
            msg("F", spec.encode())
        for name, value in self.params.items():
            if isinstance(value, float):
                k, v = f"float {name}".encode(), struct.pack("<f", value)
            else:
                k, v = f"int32_t {name}".encode(), struct.pack("<i", int(value))
            msg("P", bytes([len(k)]) + k + v)
        for name, value in self.defaults.items():
            if isinstance(value, float):
                k, v = f"float {name}".encode(), struct.pack("<f", value)
            else:
                k, v = f"int32_t {name}".encode(), struct.pack("<i", int(value))
            msg("Q", bytes([1, len(k)]) + k + v)

        # sottoscrizioni
        events = []
        for msg_id, (name, multi_id, data) in enumerate(self.topics):
            msg("A", struct.pack("<BH", multi_id, msg_id) + name.encode())
            st, cols = self._fmt_struct(name)
            n = len(data["timestamp"])
            columns = []
            for cname, t, size in cols:
                if size:
                    arr = np.asarray(data.get(cname, np.zeros((n, size))))
                    if arr.ndim == 1:
                        arr = arr[:, None]
                    columns.append((t, size, arr))
                else:
                    columns.append((t, 0, np.asarray(data.get(cname, np.zeros(n)))))
            for i in range(n):
                vals = []
                for t, size, arr in columns:
                    if size:
                        if t == "char":
                            vals.append(bytes(arr[i]))
                        else:
                            row = arr[i]
                            vals.extend(int(v) if t not in ("float", "double") else float(v) for v in row)
                    else:
                        v = arr[i]
                        if t in ("float", "double"):
                            vals.append(float(v))
                        elif t == "bool":
                            vals.append(bool(v))
                        else:
                            vals.append(int(v))
                payload = struct.pack("<H", msg_id) + st.pack(*vals)
                events.append((int(data["timestamp"][i]), 0, payload))
        for ts, level, text in self.messages:
            events.append((ts, 1, bytes([ord(str(level))]) + struct.pack("<Q", ts) + text.encode()))
        for ts, name, value in self.param_changes:
            k = (f"float {name}" if isinstance(value, float) else f"int32_t {name}").encode()
            v = struct.pack("<f", value) if isinstance(value, float) else struct.pack("<i", int(value))
            events.append((ts, 2, bytes([len(k)]) + k + v))
        events.sort(key=lambda e: (e[0], e[1]))
        for ts, kind, payload in events:
            msg({0: "D", 1: "L", 2: "P"}[kind], payload)
        with open(path, "wb") as fh:
            fh.write(out)
