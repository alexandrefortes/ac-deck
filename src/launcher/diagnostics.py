"""Registro local de abertura/saída; não coleta ambiente, conta ou comandos Steam."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import traceback
import uuid

from . import file_io as safe


@contextmanager
def opening(root):
    folder=Path(root)/'local/diagnostico'
    safe.check_components(folder)
    folder.mkdir(parents=True,exist_ok=True)
    safe.check_components(folder)
    path=folder/('abertura-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.jsonl')
    with path.open('x',encoding='utf-8') as stream:
        safe.require_reference(os.fstat(stream.fileno()),path)
        lock=threading.Lock()
        def emit(event,**values):
            with lock:
                stream.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),event=event,**values),ensure_ascii=False)+'\n')
                stream.flush()
        print('Diagnóstico: '+str(path),file=sys.stderr,flush=True)
        emit('launcher_started')
        try:
            yield emit
        except BaseException as error:
            emit('launcher_error',error_type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
            emit('launcher_exited',exit_code=130 if isinstance(error,KeyboardInterrupt) else 1)
            raise
        else:
            emit('launcher_exited',exit_code=0)
