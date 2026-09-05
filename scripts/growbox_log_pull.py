#!/usr/bin/env python3
import argparse, base64, hashlib, os, re, sys, time, zlib
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("pyserial is required: python3 -m pip install pyserial", file=sys.stderr); raise SystemExit(2)
FILE_RE=re.compile(r"sdlog_file name=([0-9A-Fa-f]{8}\.JL) size=(\d+)")
CHUNK_RE=re.compile(r"sdlog_chunk name=([0-9A-Fa-f]{8}\.JL) offset=(\d+) size=(\d+) file_size=(\d+) eof=(\d) crc32=([0-9A-Fa-f]{8}) b64=(\S*)")

def choose_port(explicit):
    if explicit: return explicit
    ports=list(list_ports.comports())
    preferred=[p.device for p in ports if any(x in p.device.lower() for x in ('usb','acm','serial','modem'))]
    if len(preferred)==1: return preferred[0]
    if not preferred: raise SystemExit('No likely USB serial port found; pass --port')
    raise SystemExit('Multiple USB serial ports found; pass --port: '+', '.join(preferred))

class Console:
    def __init__(self, port, baud, timeout):
        self.ser=serial.Serial(port, baudrate=baud, timeout=0.2, write_timeout=2)
        self.deadline=timeout
        time.sleep(0.25); self.ser.reset_input_buffer()
    def command_lines(self, command, terminal_prefix):
        self.ser.write((command+'\n').encode()); self.ser.flush(); end=time.monotonic()+self.deadline; lines=[]
        while time.monotonic()<end:
            raw=self.ser.readline()
            if not raw: continue
            line=raw.decode('utf-8','replace').strip()
            if line.startswith('sdlog_error') or line.startswith('sdlog_selftest ok=0'):
                raise RuntimeError(line)
            if line.startswith('sdlog_'): lines.append(line)
            if line.startswith(terminal_prefix): return lines
        raise TimeoutError(f'timeout waiting for {terminal_prefix!r} after {command!r}')
    def status(self):
        lines=self.command_lines('sdlog status','sdlog_status'); return lines[-1]
    def selftest(self):
        lines=self.command_lines('sdlog selftest','sdlog_selftest'); return lines[-1]
    def list_files(self):
        lines=self.command_lines('sdlog list','sdlog_list_end'); out=[]
        for line in lines:
            m=FILE_RE.fullmatch(line)
            if m: out.append((m.group(1),int(m.group(2))))
        return out
    def chunk(self,name,offset,length):
        lines=self.command_lines(f'sdlog read {name} {offset} {length}','sdlog_chunk')
        for line in reversed(lines):
            m=CHUNK_RE.fullmatch(line)
            if m:
                data=base64.b64decode(m.group(7),validate=True)
                if len(data)!=int(m.group(3)): raise RuntimeError('chunk size mismatch')
                if (zlib.crc32(data)&0xffffffff)!=int(m.group(6),16): raise RuntimeError('chunk CRC32 mismatch')
                if int(m.group(2))!=offset: raise RuntimeError('chunk offset mismatch')
                return data,int(m.group(4)),bool(int(m.group(5)))
        raise RuntimeError('missing sdlog_chunk response')

def pull(console,name,expected_size,outdir):
    os.makedirs(outdir,exist_ok=True); partial=os.path.join(outdir,name+'.partial'); final=os.path.join(outdir,name)
    offset=os.path.getsize(partial) if os.path.exists(partial) else 0
    if offset>expected_size: os.remove(partial); offset=0
    mode='ab' if offset else 'wb'
    with open(partial,mode) as f:
        while offset<expected_size:
            data,file_size,eof=console.chunk(name,offset,min(384,expected_size-offset))
            if file_size<expected_size: raise RuntimeError(f'{name}: board size shrank {file_size} < {expected_size}')
            if not data: raise RuntimeError(f'{name}: zero-length chunk at {offset}')
            f.write(data); f.flush(); os.fsync(f.fileno()); offset+=len(data)
    if offset!=expected_size: raise RuntimeError(f'{name}: final size {offset} != {expected_size}')
    os.replace(partial,final)
    digest=hashlib.sha256(open(final,'rb').read()).hexdigest()
    print(f'pulled {name} size={expected_size} sha256={digest}')

def main():
    ap=argparse.ArgumentParser(description='Read Growbox GBLOG files over the service-console USB serial link')
    ap.add_argument('action',choices=['status','list','selftest','pull','pull-all'])
    ap.add_argument('name',nargs='?'); ap.add_argument('--port'); ap.add_argument('--baud',type=int,default=115200); ap.add_argument('--timeout',type=float,default=5.0); ap.add_argument('--out',default='growbox-logs')
    args=ap.parse_args(); port=choose_port(args.port); c=Console(port,args.baud,args.timeout)
    if args.action=='status': print(c.status()); return
    if args.action=='selftest': print(c.selftest()); return
    files=c.list_files()
    if args.action=='list':
        for name,size in files: print(f'{name}\t{size}')
        return
    selected=files
    if args.action=='pull':
        if not args.name: raise SystemExit('pull requires filename')
        selected=[x for x in files if x[0].lower()==args.name.lower()]
        if not selected: raise SystemExit(f'{args.name}: not listed by board')
    for name,size in selected: pull(c,name,size,args.out)
if __name__=='__main__': main()
