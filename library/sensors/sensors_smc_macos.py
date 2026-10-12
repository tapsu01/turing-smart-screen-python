# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# CPU temperature and fan speed on macOS, read from the System Management Controller (AppleSMC) through IOKit.
# psutil has no temperature/fan support on macOS. Reading SMC keys does not need root privileges.
#
# SMC key names depend on the chip, so CPU temperature keys are discovered once by enumerating all keys:
# - Apple Silicon: 'Tp..' (performance cores) and 'Te..' (efficiency cores), 'flt ' type
# - Intel Macs: 'TC0P' / 'TC0D'... ('sp78' type)
# Fan 0: 'F0Ac' actual RPM, 'F0Mx' maximum RPM

import ctypes
import ctypes.util
import math
import struct
import threading
from typing import List, Optional

KERNEL_INDEX_SMC = 2
SMC_CMD_READ_BYTES = 5
SMC_CMD_READ_INDEX = 8
SMC_CMD_READ_KEYINFO = 9

# Ignore keys whose value is obviously not a CPU temperature (disconnected / idle sensors)
MIN_VALID_TEMP = 5.0
MAX_VALID_TEMP = 125.0


class _Vers(ctypes.Structure):
    _fields_ = [("major", ctypes.c_uint8), ("minor", ctypes.c_uint8), ("build", ctypes.c_uint8),
                ("reserved", ctypes.c_uint8), ("release", ctypes.c_uint16)]


class _PLimitData(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint16), ("length", ctypes.c_uint16), ("cpuPLimit", ctypes.c_uint32),
                ("gpuPLimit", ctypes.c_uint32), ("memPLimit", ctypes.c_uint32)]


class _KeyInfo(ctypes.Structure):
    _fields_ = [("dataSize", ctypes.c_uint32), ("dataType", ctypes.c_uint32), ("dataAttributes", ctypes.c_uint8)]


class _SMCKeyData(ctypes.Structure):
    _fields_ = [("key", ctypes.c_uint32), ("vers", _Vers), ("pLimitData", _PLimitData), ("keyInfo", _KeyInfo),
                ("result", ctypes.c_uint8), ("status", ctypes.c_uint8), ("data8", ctypes.c_uint8),
                ("data32", ctypes.c_uint32), ("bytes", ctypes.c_uint8 * 32)]


def _key_to_int(key: str) -> int:
    return struct.unpack(">I", key.encode("latin1"))[0]


def _int_to_key(value: int) -> str:
    return struct.pack(">I", value).decode("latin1")


def _decode(data_type: str, raw: bytes) -> float:
    if data_type == "flt " and len(raw) == 4:
        return struct.unpack("<f", raw)[0]
    if data_type == "sp78" and len(raw) == 2:
        return struct.unpack(">h", raw)[0] / 256.0
    if data_type == "fpe2" and len(raw) == 2:
        return struct.unpack(">H", raw)[0] / 4.0
    if data_type in ("ui8 ", "ui16", "ui32"):
        return float(int.from_bytes(raw, "big"))
    return math.nan


class _SMC:
    def __init__(self):
        self.lock = threading.Lock()
        self.iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
        libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("c"))

        self.iokit.IOServiceMatching.restype = ctypes.c_void_p
        self.iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
        self.iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
        self.iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        self.iokit.IOServiceOpen.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                             ctypes.POINTER(ctypes.c_uint32)]
        self.iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]
        self.iokit.IOConnectCallStructMethod.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                                         ctypes.c_size_t, ctypes.c_void_p,
                                                         ctypes.POINTER(ctypes.c_size_t)]

        service = self.iokit.IOServiceGetMatchingService(0, self.iokit.IOServiceMatching(b"AppleSMC"))
        if not service:
            raise OSError("AppleSMC service not found")
        self.connection = ctypes.c_uint32()
        result = self.iokit.IOServiceOpen(service, ctypes.c_uint32.in_dll(libc, "mach_task_self_").value, 0,
                                          ctypes.byref(self.connection))
        self.iokit.IOObjectRelease(service)
        if result != 0:
            raise OSError(f"Cannot open AppleSMC (error {result})")

        self.key_info_cache = {}
        self.cpu_temp_keys = self._find_cpu_temp_keys()

    def _call(self, data_in: _SMCKeyData) -> Optional[_SMCKeyData]:
        data_out = _SMCKeyData()
        size = ctypes.c_size_t(ctypes.sizeof(data_out))
        result = self.iokit.IOConnectCallStructMethod(self.connection.value, KERNEL_INDEX_SMC,
                                                      ctypes.byref(data_in), ctypes.sizeof(data_in),
                                                      ctypes.byref(data_out), ctypes.byref(size))
        if result != 0 or data_out.result != 0:
            return None
        return data_out

    def _key_info(self, key: str):
        if key not in self.key_info_cache:
            out = self._call(_SMCKeyData(key=_key_to_int(key), data8=SMC_CMD_READ_KEYINFO))
            self.key_info_cache[key] = None if out is None else (out.keyInfo.dataSize,
                                                                 _int_to_key(out.keyInfo.dataType))
        return self.key_info_cache[key]

    def read(self, key: str) -> float:
        with self.lock:
            info = self._key_info(key)
            if info is None:
                return math.nan
            data_size, data_type = info
            data_in = _SMCKeyData(key=_key_to_int(key), data8=SMC_CMD_READ_BYTES)
            data_in.keyInfo.dataSize = data_size
            out = self._call(data_in)
            if out is None:
                return math.nan
            return _decode(data_type, bytes(out.bytes[:data_size]))

    def _find_cpu_temp_keys(self) -> List[str]:
        key_count = int(self.read("#KEY"))
        apple_silicon_keys = []
        intel_keys = []
        for index in range(key_count if key_count > 0 else 0):
            with self.lock:
                out = self._call(_SMCKeyData(data8=SMC_CMD_READ_INDEX, data32=index))
            if out is None:
                continue
            key = _int_to_key(out.key)
            if key.startswith(("Tp", "Te")):
                apple_silicon_keys.append(key)
            elif key in ("TC0P", "TC0D", "TC0E", "TC0F", "TC0H"):
                intel_keys.append(key)
        keys = apple_silicon_keys or intel_keys
        return [key for key in keys if MIN_VALID_TEMP < self.read(key) < MAX_VALID_TEMP]


_smc = None
_smc_unavailable = False


def _get_smc() -> Optional[_SMC]:
    global _smc, _smc_unavailable
    if _smc is None and not _smc_unavailable:
        try:
            _smc = _SMC()
        except Exception:
            _smc_unavailable = True
    return _smc


def cpu_temperature() -> float:
    """Average temperature of all CPU core sensors, in °C (NaN if unavailable)"""
    smc = _get_smc()
    if smc is None or not smc.cpu_temp_keys:
        return math.nan
    values = [v for v in (smc.read(key) for key in smc.cpu_temp_keys) if MIN_VALID_TEMP < v < MAX_VALID_TEMP]
    return sum(values) / len(values) if values else math.nan


def fan_percent() -> float:
    """Speed of the first fan, in % of its maximum speed (NaN if there is no fan)"""
    smc = _get_smc()
    if smc is None:
        return math.nan
    current_rpm = smc.read("F0Ac")
    max_rpm = smc.read("F0Mx")
    if math.isnan(current_rpm) or math.isnan(max_rpm) or max_rpm <= 0:
        return math.nan
    return min(100.0, max(0.0, current_rpm / max_rpm * 100))
