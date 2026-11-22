from . import ekctl, remindctl, swiftbar

ALL = [ekctl, remindctl, swiftbar]
BLOCKS = {'calendar': 'events', 'reminders': 'tasks'}


def supported():
    return [s for s in ALL if s.supported()]


def active(kind):
    return next((s for s in ALL if s.KIND == kind and s.supported()), None)


def block(key):
    return active(BLOCKS[key]) if key in BLOCKS else None
