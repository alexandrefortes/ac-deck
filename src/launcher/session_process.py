"""Own only the current launch tree, including orphaned Proton helpers.

No process names, global Wine commands or Steam client signals are used.
"""
import ctypes
import errno
import os
from pathlib import Path
import signal
import select
import threading
from time import monotonic


def _libc_pidfd(name, types, *args):
    library = ctypes.CDLL(None, use_errno=True)
    try:
        operation = getattr(library, name)
    except AttributeError:
        raise OSError(errno.ENOSYS, 'Session pidfd operations are unavailable') from None
    operation.argtypes, operation.restype = types, ctypes.c_int
    result = operation(*args)
    if result < 0:
        raise OSError(ctypes.get_errno(), 'Session pidfd operation failed')
    return result


def _open_pidfd(pid):
    operation = getattr(os, 'pidfd_open', None)
    return operation(pid) if operation is not None else _libc_pidfd(
        'pidfd_open', [ctypes.c_int, ctypes.c_uint], pid, 0)


def _send_pidfd(fd, number):
    operation = getattr(signal, 'pidfd_send_signal', None)
    if operation is not None:
        return operation(fd, number)
    return _libc_pidfd('pidfd_send_signal',
                       [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint], fd, number, None, 0)


def snapshot():
    rows={}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            fields=(path/'stat').read_text().rsplit(')',1)[1].split()
            rows[int(path.name)]=(int(fields[1]),int(fields[2]),int(fields[19]),fields[0])
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return rows


class Owner:
    """Adopt descendants even when a runtime wrapper exits or calls setsid."""
    def __enter__(self):
        self.libc=ctypes.CDLL(None,use_errno=True)
        previous=ctypes.c_int()
        if self.libc.prctl(37,ctypes.byref(previous),0,0,0):
            raise OSError(ctypes.get_errno(),'Cannot inspect child supervision')
        self.previous=previous.value
        if self.libc.prctl(36,1,0,0,0):
            raise OSError(ctypes.get_errno(),'Cannot supervise session descendants')
        return self

    def __exit__(self,*args):
        self.libc.prctl(36,self.previous,0,0,0)


class Session:
    def __init__(self,process,before,*,trace=None,clock=monotonic):
        self.process=process
        self.pid=process.pid
        self.before=before
        self.trace=trace or (lambda *a,**k:None)
        self.clock=clock
        self.stop_at=None
        self.known={}
        self.signalled={}
        self.lock=threading.RLock()
        self.last_scan=0
        self.live={}
        self._scan()

    def _scan(self):
        rows=snapshot()
        owned={pid for pid,row in rows.items() if
               (pid in self.known and self.known[pid]==row[2]) or
               ((row[1]==self.pid or row[0]==os.getpid()) and
                (pid not in self.before or self.before[pid][2]!=row[2]))}
        # Adopted children can still have live descendants in another group.
        while True:
            more={pid for pid,row in rows.items() if row[0] in owned}
            if more<=owned:break
            owned|=more
        self.known.update({pid:rows[pid][2] for pid in owned})
        self.live={pid:rows[pid] for pid in owned if rows[pid][3] not in ('Z','X')}
        for pid in owned:
            if pid!=self.pid and rows[pid][0]==os.getpid() and rows[pid][3]=='Z':
                try:os.waitpid(pid,os.WNOHANG)
                except ChildProcessError:pass
        self.last_scan=self.clock()

    def _signal(self,number):
        for pid,row in list(self.live.items()):
            identity=(pid,row[2])
            if self.signalled.get(identity)==number:continue
            try:
                # pidfd pins identity; checking stat after opening rejects PID reuse.
                fd=_open_pidfd(pid)
                try:
                    current=snapshot().get(pid)
                    if current is not None and current[2]==row[2]:
                        _send_pidfd(fd,number)
                        self.signalled[identity]=number
                finally:os.close(fd)
            except ProcessLookupError:pass

    def request_stop(self):
        with self.lock:
            if self.stop_at is None:
                self.stop_at=self.clock()
                self.trace('session_stop_requested',pid=self.pid)
            self._scan()
            number=signal.SIGKILL if self.clock()-self.stop_at>=2 else signal.SIGTERM
            self._signal(number)

    def poll(self):
        with self.lock:
            code=self.process.poll()
            if code is not None or self.stop_at is not None or self.clock()-self.last_scan>=0.25:
                self._scan()
            if self.stop_at is not None:
                self._signal(signal.SIGKILL if self.clock()-self.stop_at>=2 else signal.SIGTERM)
            # Neither a timeout nor a missing game window makes Start safe.
            return code if code is not None and not self.live else None


class CloseGuard:
    """A native SDL call must not swallow an external application stop.

    The pipe is written by Python's low level signal handler, even while the
    UI thread is in ctypes. The worker never calls SDL or starts a session.
    """
    def __init__(self,request,on_stop,on_stalled,*,timeout=3):
        self.request=request
        self.on_stop=on_stop
        self.on_stalled=on_stalled
        self.timeout=timeout
        self.closed=threading.Event()
        self.read,self.write=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
        self.previous=signal.set_wakeup_fd(self.write,warn_on_full_buffer=False)
        self.worker=threading.Thread(target=self._watch,daemon=True,name='steam-close')
        self.worker.start()

    def _watch(self):
        requested_at=None
        while not self.closed.is_set():
            ready,_,_=select.select([self.read],[],[],0.1)
            if ready:
                for number in os.read(self.read,4096):
                    if number in (signal.SIGTERM,signal.SIGINT):
                        self.request.request('signal',number)
            if self.request.reason is None:continue
            if requested_at is None:requested_at=monotonic()
            try:
                self.on_stop()
                if monotonic()-requested_at>=self.timeout and self.on_stalled():
                    os._exit(0)
            except (OSError,ValueError,RuntimeError):
                # Keep the lock and retry; failed cleanup cannot permit a new race.
                pass

    def close(self):
        signal.set_wakeup_fd(self.previous)
        self.closed.set()
        self.worker.join()
        os.close(self.read)
        os.close(self.write)
