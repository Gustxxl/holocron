import sys
from core import archives, diagnostics, keeper
from screens.help_screen import show_help
from ui.interface import clear_screen, dim, haptic, is_back, pause, progress, read_command, red


def diagnostics_screen():
    while True:
        report = _run()
        if report is None:
            return
        haptic('error' if report['failed'] else 'success')
        if keeper.configured():
            _progress(report['total'], report['total'], 'keeper')
        head, rows = diagnostics.system_info()
        while True:
            frame = '\n'.join(_frame(report, head, rows))
            clear_screen()
            print(frame)
            command = read_command('check> ').lower()
            if is_back(command):
                return
            if command == '':
                break
            if command in ('h', 'help'):
                show_help()
            elif command.isdigit() and 1 <= int(command) <= len(report['failed']):
                _details(*report['failed'][int(command) - 1])


def _run():
    clear_screen()
    print(dim('Diagnostics'))
    print()
    try:
        return diagnostics.run(_progress)
    except KeyboardInterrupt:
        return None
    finally:
        sys.stdout.write('\r\033[2K')
        sys.stdout.flush()
        archives.load()


def _progress(done, total, name):
    progress('Running diagnostics', done, total, f'{done}/{total}  {name}')


def _frame(report, head, rows):
    lines = [dim('Diagnostics'), '', dim('System'), f'  {head}']
    for name, value in rows:
        mark = '✓' if value else dim('—')
        lines.append(f'  {name:<11} {mark}' + (f'  {dim(value)}' if value else ''))
    summary = f'  ✓ {report["passed"]} passed'
    if report['failed']:
        summary += '   ' + red(f'{len(report["failed"])} failed')
    if report['skipped']:
        summary += dim(f'   {report["skipped"]} skipped')
    summary += dim(f'   {report["seconds"]:.2f} s')
    lines += ['', dim('Tests'), summary]
    if report['failed']:
        lines.append('')
        digits = len(str(len(report['failed'])))
        for i, (label, tb) in enumerate(report['failed'], 1):
            lines += [f'  {dim(str(i).rjust(digits))} {label}', dim(f'    {diagnostics.reason(tb)}')]
    nav = '  [number] details   ' if report['failed'] else '  '
    lines += ['', dim(nav + '[↵] again   [b] back   [h] help'), '']
    return lines


def _details(label, tb):
    clear_screen()
    print(dim(f'Diagnostics > {label}'))
    print()
    print(tb.rstrip())
    pause(feedback=None)
