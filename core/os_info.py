import platform

name_sys = platform.system()

def user_os():
    if name_sys == 'Darwin':
        return 'macOS'
    else:
        return platform.system()


def os_version():
    os = user_os()
    if os == 'macOS':
        return platform.mac_ver()[0]
    elif name_sys in ('Windows', 'Linux'):
        return platform.release()
    else:
        return ''
