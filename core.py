"""Pure parsing and configuration helpers (no device access)."""
import json
import re
import textwrap
import uuid
from pathlib import Path

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)')
PAGER = re.compile(r'-+\s*More\s*-+', re.I)
ERROR = re.compile(r'(?:^|\n)\s*(?:Error\s*:|%\s*(?:Error|Unknown|Invalid)|Unrecognized command|Wrong parameter|Incomplete command)', re.I)

def transcript(raw):
    """Render the serial byte stream as a text terminal with cursor-aware edits.

    Recognises CR, BS, destructive DEL, ANSI cursor moves and erase-in-line.
    Retains full output independently of the window size. This is not a full VT100.
    """
    value = raw.decode('utf-8', errors='replace') if isinstance(raw,(bytes,bytearray)) else raw
    lines = [[]]
    x = 0
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == '\x1b':
            match = re.match(r'\x1b\[([0-9;?]*)([A-Za-z~])', value[i:])
            if match:
                params, cmd = match.groups()
                n = int((params.split(';')[0] or '1')) if params.lstrip('0123456789;') == '' else 1
                line = lines[-1]
                if cmd == 'D': x = max(0,x-n)
                elif cmd == 'C': x = min(len(line),x+n)
                elif cmd == 'G': x = max(0,n-1)
                elif cmd == 'K':
                    mode = int(params or 0)
                    if mode == 0: del line[x:]
                    elif mode == 1:
                        for j in range(min(x+1,len(line))): line[j]=' '
                    elif mode == 2: line.clear(); x=0
                i += len(match.group(0));continue
            osc = re.match(r'\x1b\][^\x07]*(?:\x07|\x1b\\)',value[i:])
            if osc: i+=len(osc.group(0));continue
            i+=1;continue
        if ch == '\r': x=0
        elif ch == '\n':
            lines.append([]); x=0
        elif ch == '\b':
            # Both bare BS and the widespread BS-SP-BS erase convention.
            # Consuming the triplet avoids deleting two characters.
            if value[i:i+3] == '\b \b':
                if x:
                    x -= 1
                    if x < len(lines[-1]): del lines[-1][x]
                i += 2
            elif x:
                x -= 1
                if x < len(lines[-1]): del lines[-1][x]
        elif ch == '\x7f':
            if x < len(lines[-1]):del lines[-1][x]
        elif ch == '\t':
            for _ in range(8-(x%8)):
                line=lines[-1]
                if x<len(line):line[x]=' '
                else:line.append(' ')
                x+=1
        elif ord(ch)>=32:
            line=lines[-1]
            if x>len(line):line.extend(' '*(x-len(line)))
            if x<len(line):line[x]=ch
            else:line.append(ch)
            x+=1
        i+=1
    return PAGER.sub('', '\n'.join(''.join(line).rstrip() for line in lines))

def prompt_kind(value):
    tail = value.rstrip().split('\n')[-1] if value.rstrip() else ''
    if re.fullmatch(r'\s*(?:username|user name|login)\s*:\s*', tail, re.I): return 'username', None
    if re.fullmatch(r'\s*(?:password|.*\bpassword)\s*:\s*', tail, re.I): return 'password', None
    match = re.fullmatch(r'\s*(?:<([^<>]+)>|\[([^\[\]]+)\])\s*', tail)
    if match: return 'cli', (match.group(1) or match.group(2)).lstrip('~*')
    return 'unknown', None

def validate_profile(profile):
    if not profile['name'].strip():
        raise ValueError('A profile or session name is required.')
    if not profile['port'].strip(): raise ValueError('Select a COM port.')
    if int(profile['baud']) <= 0: raise ValueError('Baud rate must be positive.')
    if not 5 <= int(profile['timeout']) <= 600: raise ValueError('Timeout must be 5–600 seconds.')
    return profile

def command_text(template, profile):
    """Validate one interactive console command without restricting CLI abbreviations.

    Pipes are allowed for Huawei output filters such as ``| i Serial``.
    A single command is required: no control characters or command chaining.
    """
    if not isinstance(template, str):
        raise ValueError('Enter one console command.')
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in template):
        raise ValueError('Enter one command per line (no newlines or control characters).')
    text = template.strip()
    if not text or len(text) > 1024:
        raise ValueError('Enter a console command (maximum 1024 characters).')
    if re.search(r'\{[^{}]+\}', text.replace('{interface}', '')) or '{' in text.replace('{interface}', '') or '}' in text.replace('{interface}', ''):
        raise ValueError('Only the {interface} placeholder is supported.')
    if '{interface}' in text:
        interface = str(profile.get('interface', '')).strip()
        if not interface or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 /_.:-]*', interface):
            raise ValueError('This command uses {interface}. Enter an interface name in Target Interface.')
        text = text.replace('{interface}', interface)
    if any(ch in text for ch in (';', '&', '>', '<', '`', '$', '\\')):
        raise ValueError('Command chaining and shell redirection are not supported.')
    # A pipe must be a Huawei display-output filter, not an arbitrary second command.
    segments = [part.strip() for part in text.split('|')]
    if len(segments) > 1:
        if not re.match(r'^(?:display|dis|show|sh)\s+', segments[0], re.I):
            raise ValueError('Pipe filtering is supported for display/dis/show output only.')
        for segment in segments[1:]:
            if not re.fullmatch(r'(?:i|include|e|exclude|b|begin)\s+[^|]+', segment, re.I):
                raise ValueError('Use a filter such as | i Serial or | include Serial.')
    return text

def wrap_output(value, columns):
    lines = []
    for line in value.expandtabs(8).split('\n'):
        lines.extend(textwrap.wrap(line, width=columns, expand_tabs=False, replace_whitespace=False,
                                   drop_whitespace=False, break_long_words=True, break_on_hyphens=False) or [''])
    return lines

def new_profile(role='WAC'):
    return dict(id=uuid.uuid4().hex, name=role, role=role, hostname='',
                ip='', port='', baud=9600, interface='MultiGE 1/0/1', username='', auto_login=False,
                timeout=60, parity='N', stopbits=1, flow='None')

def defaults():
    return dict(version=2, profiles=[new_profile('WAC'), new_profile('Switch')],
                groups=[dict(name='Display WAC', target='WAC', commands=['display ap all','display vap all','display station all']),
                        dict(name='Display Switch', target='Switch', commands=['display interface {interface}', 'display poe power interface {interface}']),
                        dict(name='Burn In', target='Any', commands=['display clock', 'display version', 'display device esn', 'display cpu-usage', 'display memory all', 'display device power system', 'display device temperature', 'display device fan', 'display alarm active'])])

def save_json(path, value):
    path = Path(path); tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8'); tmp.replace(path)

def safe_name(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('_')[:90] or 'capture'
