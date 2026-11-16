"""Safe Huawei serial hostname discovery helpers.

Scanning does not send credentials/configuration and never opens already-owned ports.
It may send one CR to ask a device to display an existing CLI/login prompt.
"""
import time
from collections import Counter

from core import prompt_kind, transcript


def read_prompt(port, seconds):
    """Read up to `seconds` waiting for a CLI prompt; no Tk calls."""
    raw = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        waiting = port.in_waiting
        chunk = port.read(min(max(1, waiting), 4096))
        if chunk:
            raw.extend(chunk)
            # Bound memory usage from a noisy, misconfigured serial adapter.
            if len(raw) >= 65536:
                break
            kind, host = prompt_kind(transcript(raw))
            if kind in ('cli', 'username', 'password'):
                return kind, host
        else:
            time.sleep(0.035)
    return prompt_kind(transcript(raw))


def probe_port(device, candidates, attempts=4, listen_seconds=0.65):
    """Wake a serial console using bounded Enter retries, without credentials.

    Stops at any real device output (including MOTD and login banners), not only
    an identified hostname. Each attempt sends one carriage return. Opening a
    port during a scan does NOT create a persistent terminal session.
    """
    import serial
    for baud, parity, stopbits in candidates:
        try:
            with serial.Serial(device, baudrate=baud, bytesize=8, parity=parity,
                               stopbits=stopbits, timeout=0.12, write_timeout=0.5,
                               rtscts=False, xonxoff=False, dsrdtr=False) as port:
                received=bytearray()
                for attempt in range(attempts):
                    # Look for an existing banner before injecting any keystroke.
                    duration=0.2 if attempt == 0 else 0.05
                    deadline=time.monotonic()+duration
                    while time.monotonic()<deadline:
                        chunk=port.read(min(max(1,port.in_waiting),4096))
                        if chunk: received.extend(chunk)
                        else: time.sleep(0.025)
                    if received:
                        break
                    port.write(b'\r')
                    deadline=time.monotonic()+listen_seconds
                    while time.monotonic()<deadline and len(received)<65536:
                        chunk=port.read(min(max(1,port.in_waiting),4096))
                        if chunk:
                            received.extend(chunk)
                            # Let an MOTD finish so any hostname/login prompt is captured.
                            deadline=max(deadline,time.monotonic()+0.25)
                        else: time.sleep(0.025)
                    if received:break
                if received:
                    kind, host=prompt_kind(transcript(received))
                    if kind=='cli':return host, f'CLI prompt at {baud} {parity}/8/{stopbits}'
                    if kind in ('username','password'):
                        return None, f'Login required ({baud}); credentials not sent'
                    return None, f'Response received ({baud}); hostname unknown'
        except (serial.SerialException, OSError, ValueError) as exc:
            reason=str(exc)
            if 'Permission' in reason or 'Access is denied' in reason or 'could not open' in reason:
                return None, 'Unavailable: '+reason[:90]
            continue
    return None, 'No response after bounded Enter attempts'


def candidates_for(port, profiles):
    # Prioritise device settings already associated with this port.
    ordered = [p for p in profiles if p.get('port','').casefold() == port.casefold()]
    ordered += [p for p in profiles if p not in ordered]
    choices=[]
    for p in ordered:
        try:
            setting = (int(p['baud']), p.get('parity','N'), int(p.get('stopbits',1)))
            if setting not in choices:choices.append(setting)
        except (ValueError, TypeError, KeyError):pass
    if (9600,'N',1) not in choices:choices.append((9600,'N',1))
    return choices[:5]  # bounded scan time


def scan_available_ports(profiles, reserved):
    from serial.tools import list_ports
    reserved={port.casefold() for port in reserved}
    result=[]
    for port in list_ports.comports():
        device=port.device
        if device.casefold() in reserved:
            result.append(dict(port=device,hostname=None,detail='Already connected in Console Capture'))
            continue
        host, detail = probe_port(device, candidates_for(device, profiles))
        result.append(dict(port=device,hostname=host,detail=detail))
    return result


def propose_matches(scanned, profiles):
    """Only unique case-insensitive hostnames can be matched and automatically applied."""
    host_counts = Counter((r.get('hostname') or '').casefold() for r in scanned if r.get('hostname'))
    results=[]
    for item in scanned:
        row=dict(item,profile_id=None,profile_name=None,status=item.get('detail','Unknown'))
        host=item.get('hostname')
        if host:
            matches=[p for p in profiles if p.get('hostname','').casefold()==host.casefold()]
            if host_counts[host.casefold()] != 1:
                row['status']='Duplicate hostname; review manually'
            elif len(matches)>1:
                row['status']='Multiple profiles share hostname'
            elif len(matches)==1:
                row['profile_id']=matches[0]['id']
                row['profile_name']=matches[0]['name']
                row['status']='Matched'
            else:
                row['status']='No saved profile matches hostname'
        results.append(row)
    return results
