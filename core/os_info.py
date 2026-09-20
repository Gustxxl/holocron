import platform


def user_os():
    name_sys = platform.system()
    if name_sys == 'Darwin':
        return 'macOS'
    return name_sys


def os_version():
    os = user_os()
    if os == 'macOS':
        return platform.mac_ver()[0]
    elif name_sys in ('Windows', 'Linux'):
        return platform.release()
    else:
        return ''
