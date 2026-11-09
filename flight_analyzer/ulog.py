"""Lettore del formato ULog di PX4, scritto da zero sulla specifica pubblica.

Non dipende da pyulog: legge l'intero file in memoria, ricostruisce i formati
(anche annidati), raccoglie i messaggi dati per sottoscrizione e li converte in
array numpy strutturati. Gli array dei messaggi vengono appiattiti come fa
pyulog (``xyz[0]``, ``xyz[1]``, ``q[3]`` ...).

Gestisce: info e info multiple, parametri iniziali/modificati/di default,
messaggi di log (anche con tag), dropout, dati accodati (appended offsets),
sincronizzazione dopo corruzione e file troncati.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .i18n import N_, _

HEADER_MAGIC = b"ULog\x01\x12\x35"
SYNC_BYTES = b"\x2F\x73\x13\x20\x25\x0C\xBB\x12"

# tipo ULog -> (codice struct, dimensione, tipo numpy)
TYPES = {
    "int8_t": ("b", 1, np.int8),
    "uint8_t": ("B", 1, np.uint8),
    "int16_t": ("h", 2, np.int16),
    "uint16_t": ("H", 2, np.uint16),
    "int32_t": ("i", 4, np.int32),
    "uint32_t": ("I", 4, np.uint32),
    "int64_t": ("q", 8, np.int64),
    "uint64_t": ("Q", 8, np.uint64),
    "float": ("f", 4, np.float32),
    "double": ("d", 8, np.float64),
    "bool": ("?", 1, np.uint8),
    "char": ("c", 1, np.uint8),
}

# nomi in italiano: l'interfaccia li traduce con i18n._() quando li mostra
LOG_LEVELS = {
    ord("0"): N_("EMERGENZA"),
    ord("1"): N_("ALLARME"),
    ord("2"): N_("CRITICO"),
    ord("3"): N_("ERRORE"),
    ord("4"): N_("AVVISO"),
    ord("5"): N_("NOTA"),
    ord("6"): N_("INFO"),
    ord("7"): N_("DEBUG"),
}

_HDR = struct.Struct("<HB")
_U16 = struct.Struct("<H")
_U64 = struct.Struct("<Q")

MSG_FORMAT = ord("F")
MSG_DATA = ord("D")
MSG_INFO = ord("I")
MSG_INFO_MULTI = ord("M")
MSG_PARAM = ord("P")
MSG_PARAM_DEFAULT = ord("Q")
MSG_ADD_LOGGED = ord("A")
MSG_REMOVE_LOGGED = ord("R")
MSG_SYNC = ord("S")
MSG_DROPOUT = ord("O")
MSG_LOGGING = ord("L")
MSG_LOGGING_TAGGED = ord("C")
MSG_FLAG_BITS = ord("B")
_KNOWN = {
    MSG_FORMAT, MSG_DATA, MSG_INFO, MSG_INFO_MULTI, MSG_PARAM, MSG_PARAM_DEFAULT,
    MSG_ADD_LOGGED, MSG_REMOVE_LOGGED, MSG_SYNC, MSG_DROPOUT, MSG_LOGGING,
    MSG_LOGGING_TAGGED, MSG_FLAG_BITS,
}


class ULogError(Exception):
    """File non leggibile come ULog."""


@dataclass
class Dataset:
    """Dati di un topic (una istanza)."""

    name: str
    multi_id: int
    msg_id: int
    data: dict
    field_types: dict

    def __len__(self):
        ts = self.data.get("timestamp")
        return 0 if ts is None else len(ts)


@dataclass
class LoggedMessage:
    timestamp: int
    level: int
    text: str
    tag: int | None = None

    @property
    def level_name(self) -> str:
        return LOG_LEVELS.get(self.level, "?")


@dataclass
class Dropout:
    timestamp: int
    duration_ms: int


@dataclass
class _Subscription:
    name: str
    multi_id: int
    msg_id: int
    fields: list
    dtype: np.dtype
    min_size: int
    max_size: int
    ts_offset: int
    chunks: list = field(default_factory=list)


def _cstr(raw) -> str:
    raw = bytes(raw)
    cut = raw.find(b"\x00")
    if cut >= 0:
        raw = raw[:cut]
    return raw.decode("utf-8", errors="replace")


def _parse_field(spec: str):
    type_str, name = spec.strip().split(" ", 1)
    name = name.strip()
    size = 0
    if "[" in type_str:
        a, b = type_str.index("["), type_str.index("]")
        size = int(type_str[a + 1 : b])
        if size < 0 or size > 0xFFFF:
            raise ValueError(_("dimensione array non valida"))
        type_str = type_str[:a]
    return type_str, size, name


def _parse_typed_value(type_key: str, raw):
    """Decodifica ``"<tipo> <nome>"`` + valore. Restituisce (nome, tipo, valore)."""
    type_str, _x, key = type_key.partition(" ")
    if type_str.startswith("char["):
        value = _cstr(raw)
    elif type_str in TYPES:
        code, size, _x = TYPES[type_str]
        value = struct.unpack("<" + code, bytes(raw[:size]))[0]
        if type_str == "bool":
            value = bool(value)
    else:
        value = bytes(raw)
    return key, type_str, value


class ULog:
    """Contenuto di un file .ulg.

    Attributi principali: ``datasets`` (lista di :class:`Dataset`), ``info``,
    ``initial_parameters``, ``changed_parameters`` [(timestamp, nome, valore)],
    ``default_parameters`` {bit: {nome: valore}}, ``messages``, ``dropouts``,
    ``start_timestamp``, ``last_timestamp``, ``corrupt``.
    """

    def __init__(self, source):
        if isinstance(source, (bytes, bytearray)):
            buf = bytes(source)
            self.path = None
        else:
            self.path = Path(source)
            buf = self.path.read_bytes()
        self._buf = buf
        self.file_version = 0
        self.start_timestamp = 0
        self.last_timestamp = 0
        self.info: dict = {}
        self.info_types: dict = {}
        self.info_multiple: dict = {}
        self.formats: dict = {}
        self.initial_parameters: dict = {}
        self.changed_parameters: list = []
        self.default_parameters: dict = {}
        self.messages: list = []
        self.dropouts: list = []
        self.datasets: list = []
        self.corrupt = False
        self.compat_flags = [0] * 8
        self.incompat_flags = [0] * 8
        self.appended_offsets: list = []
        self._subs: dict = {}
        self._missing_ids: set = set()
        self._parse()
        del self._buf

    # ------------------------------------------------------------------ parsing
    def _parse(self):
        buf = self._buf
        if len(buf) < 16 or buf[:7] != HEADER_MAGIC:
            raise ULogError(_("Il file non è un log ULog valido (intestazione non riconosciuta)."))
        self.file_version = buf[7]
        self.start_timestamp = _U64.unpack_from(buf, 8)[0]
        self.last_timestamp = self.start_timestamp
        pos = self._read_definitions(16)
        if self.incompat_flags[0] & 1 and self.appended_offsets:
            for offset in self.appended_offsets:
                pos = self._read_data(pos, until=offset)
                if offset >= len(buf):
                    self.corrupt = True
                    break
                pos = offset
        self._read_data(pos, until=len(buf))
        self._finalize()

    def _read_definitions(self, pos: int) -> int:
        buf = self._buf
        n = len(buf)
        while pos + 3 <= n:
            size, mtype = _HDR.unpack_from(buf, pos)
            start = pos + 3
            end = start + size
            if end > n:
                self.corrupt = True
                return n
            payload = memoryview(buf)[start:end]
            try:
                if mtype == MSG_FLAG_BITS:
                    self.compat_flags = list(payload[0:8])
                    self.incompat_flags = list(payload[8:16])
                    offs = list(struct.unpack_from("<QQQ", payload, 16)) if size >= 40 else []
                    while offs and offs[-1] == 0:
                        offs.pop()
                    self.appended_offsets = offs
                    if self.incompat_flags[0] & ~1 or any(self.incompat_flags[1:]):
                        raise ULogError(_("Il log usa flag incompatibili sconosciuti: impossibile leggerlo."))
                elif mtype == MSG_FORMAT:
                    text = _cstr(payload)
                    name, _x, rest = text.partition(":")
                    self.formats[name] = [_parse_field(f) for f in rest.split(";") if f.strip()]
                elif mtype == MSG_INFO:
                    self._handle_info(payload)
                elif mtype == MSG_INFO_MULTI:
                    self._handle_info_multi(payload)
                elif mtype == MSG_PARAM:
                    key, _x, value = _parse_typed_value(_cstr(payload[1 : 1 + payload[0]]), payload[1 + payload[0] :])
                    self.initial_parameters[key] = value
                elif mtype == MSG_PARAM_DEFAULT:
                    self._handle_param_default(payload)
                elif mtype in (MSG_ADD_LOGGED, MSG_LOGGING, MSG_LOGGING_TAGGED, MSG_DATA):
                    return pos
                elif mtype not in _KNOWN and (mtype == 0 or size == 0 or size > 10000):
                    self.corrupt = True
                    pos += 1
                    continue
            except ULogError:
                raise
            except (ValueError, IndexError, KeyError, struct.error, UnicodeDecodeError):
                self.corrupt = True
            pos = end
        return pos

    def _handle_info(self, payload):
        klen = payload[0]
        key, typ, value = _parse_typed_value(_cstr(payload[1 : 1 + klen]), payload[1 + klen :])
        self.info[key] = value
        self.info_types[key] = typ

    def _handle_info_multi(self, payload):
        continued = payload[0]
        klen = payload[1]
        key, _x, value = _parse_typed_value(_cstr(payload[2 : 2 + klen]), payload[2 + klen :])
        entries = self.info_multiple.setdefault(key, [])
        if continued and entries:
            entries[-1].append(value)
        else:
            entries.append([value])

    def _handle_param_default(self, payload):
        bits = payload[0]
        klen = payload[1]
        key, _x, value = _parse_typed_value(_cstr(payload[2 : 2 + klen]), payload[2 + klen :])
        bit = 0
        while bits:
            if bits & 1:
                self.default_parameters.setdefault(bit, {})[key] = value
            bits >>= 1
            bit += 1

    def _flatten(self, prefix: str, type_name: str, out: list, depth: int = 0):
        if depth > 16:
            raise ValueError(_("annidamento dei formati troppo profondo"))
        for type_str, size, fname in self.formats[type_name]:
            if type_str in TYPES:
                if size > 0:
                    for i in range(size):
                        out.append((f"{prefix}{fname}[{i}]", type_str))
                else:
                    out.append((prefix + fname, type_str))
            else:
                if size > 0:
                    for i in range(size):
                        self._flatten(f"{prefix}{fname}[{i}].", type_str, out, depth + 1)
                else:
                    self._flatten(f"{prefix}{fname}.", type_str, out, depth + 1)

    def _add_subscription(self, payload):
        multi_id = payload[0]
        msg_id = _U16.unpack_from(payload, 1)[0]
        name = _cstr(payload[3:])
        fields: list = []
        self._flatten("", name, fields)
        max_size = sum(TYPES[t][1] for _, t in fields)
        while fields and fields[-1][0].startswith("_padding"):
            fields.pop()
        min_size = sum(TYPES[t][1] for _, t in fields)
        ts_offset = -1
        offset = 0
        for fname, t in fields:
            if fname == "timestamp":
                ts_offset = offset
                break
            offset += TYPES[t][1]
        dtype = np.dtype([(fname, np.dtype(TYPES[t][2]).newbyteorder("<")) for fname, t in fields])
        self._subs[msg_id] = _Subscription(name, multi_id, msg_id, fields, dtype, min_size, max_size, ts_offset)

    def _read_data(self, pos: int, until: int) -> int:
        buf = self._buf
        n = min(len(buf), until)
        subs = self._subs
        hdr = _HDR.unpack_from
        u16 = _U16.unpack_from
        u64 = _U64.unpack_from
        last_ts = self.last_timestamp
        while pos + 3 <= n:
            size, mtype = hdr(buf, pos)
            start = pos + 3
            end = start + size
            if end > n:
                if end > len(buf):
                    self.corrupt = True  # file troncato
                break
            if mtype == MSG_DATA:
                if size >= 2:
                    msg_id = u16(buf, start)[0]
                    sub = subs.get(msg_id)
                    dsize = size - 2
                    if sub is not None and sub.min_size <= dsize <= sub.max_size:
                        sub.chunks.append(buf[start + 2 : start + 2 + sub.min_size])
                        if sub.ts_offset >= 0:
                            ts = u64(buf, start + 2 + sub.ts_offset)[0]
                            if ts > last_ts:
                                last_ts = ts
                    else:
                        if sub is None:
                            self._missing_ids.add(msg_id)
                        self.corrupt = True
                pos = end
                continue
            try:
                payload = memoryview(buf)[start:end]
                if mtype == MSG_ADD_LOGGED:
                    self._add_subscription(payload)
                elif mtype == MSG_REMOVE_LOGGED:
                    pass
                elif mtype == MSG_LOGGING:
                    level = payload[0]
                    ts = u64(payload, 1)[0]
                    self.messages.append(LoggedMessage(ts, level, _cstr(payload[9:])))
                elif mtype == MSG_LOGGING_TAGGED:
                    level = payload[0]
                    tag = u16(payload, 1)[0]
                    ts = u64(payload, 3)[0]
                    self.messages.append(LoggedMessage(ts, level, _cstr(payload[11:]), tag))
                elif mtype == MSG_PARAM:
                    key, _x, value = _parse_typed_value(_cstr(payload[1 : 1 + payload[0]]), payload[1 + payload[0] :])
                    self.changed_parameters.append((last_ts, key, value))
                elif mtype == MSG_PARAM_DEFAULT:
                    self._handle_param_default(payload)
                elif mtype == MSG_INFO:
                    self._handle_info(payload)
                elif mtype == MSG_INFO_MULTI:
                    self._handle_info_multi(payload)
                elif mtype == MSG_DROPOUT:
                    self.dropouts.append(Dropout(last_ts, u16(payload, 0)[0]))
                elif mtype == MSG_FORMAT:
                    text = _cstr(payload)
                    name, _x, rest = text.partition(":")
                    self.formats[name] = [_parse_field(f) for f in rest.split(";") if f.strip()]
                elif mtype in (MSG_SYNC, MSG_FLAG_BITS):
                    pass
                else:
                    if mtype == 0 or size == 0 or size > 10000:
                        # pacchetto corrotto: cerca la prossima sequenza di sync
                        self.corrupt = True
                        nxt = buf.find(SYNC_BYTES, pos + 1, n)
                        if nxt < 0:
                            break
                        pos = nxt + len(SYNC_BYTES)
                        continue
            except (ValueError, IndexError, KeyError, struct.error):
                self.corrupt = True
            pos = end
        self.last_timestamp = last_ts
        return pos

    def _finalize(self):
        for sub in self._subs.values():
            if not sub.chunks:
                continue
            raw = b"".join(sub.chunks)
            arr = np.frombuffer(raw, dtype=sub.dtype)
            data = {name: arr[name] for name in sub.dtype.names}
            types = {fname: t for fname, t in sub.fields}
            self.datasets.append(Dataset(sub.name, sub.multi_id, sub.msg_id, data, types))
        self.datasets.sort(key=lambda d: (d.name, d.multi_id))
        self._subs = {}
        self.messages.sort(key=lambda m: m.timestamp)

    # ------------------------------------------------------------------ helpers
    def get(self, name: str, multi_id: int = 0):
        for d in self.datasets:
            if d.name == name and d.multi_id == multi_id:
                return d
        return None

    def version_string(self) -> str | None:
        """Versione software, es. ``v1.17.0`` (None per build di sviluppo)."""
        val = self.info.get("ver_sw_release")
        if isinstance(val, int):
            major, minor, patch, typ = (val >> 24) & 0xFF, (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF
            if typ >= 64:
                suffix = "" if typ == 255 else (" (RC)" if typ >= 192 else (" (beta)" if typ >= 128 else " (alpha)"))
                return f"v{major}.{minor}.{patch}{suffix}"
        return None
