import platform

name_sys = platform.system()

def user_os():
    if name_sys == 'Darwin':
        return 'macOS'
    else:
        return platform.system()
