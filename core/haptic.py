import argparse
import ctypes
import sys
import time

mt = ctypes.CDLL(
    "/System/Library/PrivateFrameworks/MultitouchSupport.framework/MultitouchSupport"
)
cf = ctypes.CDLL(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)

mt.MTDeviceCreateList.restype = ctypes.c_void_p
mt.MTDeviceGetDeviceID.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
mt.MTDeviceGetDeviceID.restype = ctypes.c_int
mt.MTActuatorCreateFromDeviceID.argtypes = [ctypes.c_uint64]
mt.MTActuatorCreateFromDeviceID.restype = ctypes.c_void_p
mt.MTActuatorOpen.argtypes = [ctypes.c_void_p]
mt.MTActuatorOpen.restype = ctypes.c_int
mt.MTActuatorClose.argtypes = [ctypes.c_void_p]
mt.MTActuatorClose.restype = ctypes.c_int
mt.MTActuatorActuate.argtypes = [
    ctypes.c_void_p, ctypes.c_int32, ctypes.c_uint32, ctypes.c_float, ctypes.c_float
]
mt.MTActuatorActuate.restype = ctypes.c_int

cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
cf.CFArrayGetCount.restype = ctypes.c_long
cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p

RESONANCE = {"weak": 3, "medium": 4, "strong": 6}

SEQUENCES = {
    "tap":     [("medium", 0)],
    "soft":    [("weak", 0)],
    "click":   [("strong", 0)],
    "double":  [("medium", 55), ("medium", 0)],
    "toggle":  [("weak", 45), ("strong", 0)],
    "confirm": [("medium", 60), ("strong", 0)],
    "success": [("weak", 45), ("medium", 45), ("strong", 0)],
    "warning": [("strong", 130), ("strong", 0)],
    "error":   [("strong", 90), ("strong", 90), ("strong", 0)],
}


class Holocron:

    def __init__(self, verbose: bool = False):
        self._core = None
        self._verbose = verbose

    def awaken(self) -> "Holocron":
        if self._core is not None:
            return self

        devices = mt.MTDeviceCreateList()
        if not devices:
            raise SystemExit("no multitouch devices available")

        seen = []
        for i in range(cf.CFArrayGetCount(devices)):
            device = cf.CFArrayGetValueAtIndex(devices, i)
            dev_id = ctypes.c_uint64(0)
            mt.MTDeviceGetDeviceID(device, ctypes.byref(dev_id))
            seen.append(hex(dev_id.value))

            core = mt.MTActuatorCreateFromDeviceID(dev_id.value)
            if core and mt.MTActuatorOpen(core) == 0:
                self._core = core
                if self._verbose:
                    print(f"core awakened, device ID = {hex(dev_id.value)}")
                return self

        raise SystemExit(f"no actuator found. Device IDs seen: {seen}")

    def seal(self) -> None:
        if self._core is not None:
            mt.MTActuatorClose(self._core)
            self._core = None

    def __enter__(self) -> "Holocron":
        return self.awaken()

    def __exit__(self, *exc) -> None:
        self.seal()

    def pulse(self, strength: str = "medium") -> None:
        if self._core is None:
            self.awaken()
        mt.MTActuatorActuate(self._core, RESONANCE[strength], 0, 0.0, 0.0)

    def invoke(self, sequence: str, repeat: int = 1, gap_ms: int = 200) -> None:
        steps = SEQUENCES.get(sequence)
        if steps is None:
            raise ValueError(
                f"unknown sequence {sequence!r}. Available: {', '.join(SEQUENCES)}"
            )
        for r in range(repeat):
            for strength, pause in steps:
                self.pulse(strength)
                if pause:
                    time.sleep(pause / 1000)
            if r + 1 < repeat:
                time.sleep(gap_ms / 1000)

    def tap(self, strength: str = "medium"):
        self.pulse(strength)

    def success(self):
        self.invoke("success")

    def error(self):
        self.invoke("error")

    def warning(self):
        self.invoke("warning")

    def confirm(self):
        self.invoke("confirm")

    def toggle(self):
        self.invoke("toggle")

    def double(self):
        self.invoke("double")


def emit(sequence: str = "tap", repeat: int = 1) -> None:
    with Holocron() as core:
        core.invoke(sequence, repeat=repeat)


def main() -> None:
    p = argparse.ArgumentParser(description="Trackpad haptic feedback")
    p.add_argument(
        "sequence", nargs="?", default="tap",
        help=f"sequence: {', '.join(SEQUENCES)} (default: tap)",
    )
    p.add_argument("-s", "--strength", choices=RESONANCE,
                   help="override strength for a single tap")
    p.add_argument("-r", "--repeat", type=int, default=1,
                   help="how many times to repeat the sequence")
    p.add_argument("-g", "--gap", type=int, default=200,
                   help="pause between repeats, ms")
    p.add_argument("-l", "--list", action="store_true",
                   help="list available sequences and exit")
    args = p.parse_args()

    if args.list:
        for name, steps in SEQUENCES.items():
            shape = " ".join(s for s, _ in steps)
            print(f"  {name:<8} {shape}")
        return

    with Holocron(verbose=True) as core:
        if args.strength:
            for r in range(args.repeat):
                core.pulse(args.strength)
                if r + 1 < args.repeat:
                    time.sleep(args.gap / 1000)
        else:
            core.invoke(args.sequence, repeat=args.repeat, gap_ms=args.gap)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
