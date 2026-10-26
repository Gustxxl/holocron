HELP = ('-h', '--help')
USAGE = '''Usage:
  holo                  open Holocron
  holo words            search the archive, or run a command like holo schedule
  holo "nginx; ERR504"  several searches at once, in quotes
  holo -- -words        search for words that start with a dash'''


def parse(args):
    if args and args[0] == '--':
        args = args[1:]
    elif args and args[0] in HELP:
        return 'help', None
    elif args and args[0].startswith('-'):
        return 'unknown', args[0]
    text = ' '.join(args).strip()
    return ('search', text) if text else (None, None)
