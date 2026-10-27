"""Usos confirmados independentes do histórico e filtros determinísticos da IA."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time

from . import file_io as safe
from . import event_synthetizer as events
from . import results

_LOCK = threading.RLock()
LIMIT_MIN, LIMIT_MAX = 1, 99
MAX_BYTES = 16*1024*1024


def path_for(store):
    return Path(store).parent/'ai-usage.json' if store is not None else None


def fresh():
    return dict(schema_version=1, activated_ns=time.time_ns(), limits=dict(car=1,track=1),
                cars={}, tracks={}, cycles=dict(car=0,track=0), seen=[], resets=0)


def _number(value, low=0, high=2**63-1):
    if type(value) is not int or not low<=value<=high:
        raise ValueError('Invalid AI usage number; original file kept.')
    return value


def clean(value):
    if not isinstance(value,dict) or value.get('schema_version')!=1:
        raise ValueError('Invalid AI usage file; original file kept.')
    _number(value.get('activated_ns'),1)
    for key in ('car','track'):
        _number(value['limits'][key],LIMIT_MIN,LIMIT_MAX)
        _number(value['cycles'][key])
    _number(value['resets'])
    for key in ('cars','tracks'):
        if not isinstance(value[key],dict):raise ValueError('Invalid AI usage entries.')
        for identity,count in value[key].items():
            if not isinstance(identity,str) or not identity or len(identity)>512:
                raise ValueError('Invalid AI usage identity.')
            _number(count)
    if (not isinstance(value['seen'],list) or any(not isinstance(token,str) or len(token)!=64
            or any(c not in '0123456789abcdef' for c in token) for token in value['seen'])
            or len(set(value['seen']))!=len(value['seen'])):
        raise ValueError('Invalid AI usage receipts.')
    return deepcopy(value)


@contextmanager
def _locked(path):
    with _LOCK:
        if path is None:
            yield
            return
        safe.check_components(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        lock=path.with_suffix('.lock')
        safe.check_components(lock)
        with lock.open('a+b') as stream:
            safe.require_reference(os.fstat(stream.fileno()),lock)
            if os.name=='nt':
                import msvcrt
                if stream.seek(0,2)==0:stream.write(b'0');stream.flush()
                stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX)
            try:yield
            finally:
                if os.name=='nt':
                    stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(stream,fcntl.LOCK_UN)


def _load(path):
    if path is None or not path.exists():return fresh()
    stream,info=safe.open_reference(path)
    with stream:
        if info.st_size>MAX_BYTES:raise ValueError('AI usage storage limit reached; original file kept.')
        try:return clean(json.load(stream))
        except (KeyError,TypeError,AttributeError) as error:raise ValueError('Invalid AI usage file; original file kept.') from error


def _save(path,value):
    if path is None:return
    raw=(json.dumps(clean(value),ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    if len(raw)>MAX_BYTES:raise ValueError('AI usage storage limit reached; original file kept.')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.ai-usage-',suffix='.tmp',dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name);stream.write(raw);stream.flush();os.fsync(stream.fileno())
        safe.check_components(path)
        if path.exists():safe.require_reference(path.lstat(),path)
        temporary.replace(path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def load(path):
    path=safe.absolute(path) if path is not None else None
    with _locked(path):
        value=_load(path)
        if path is not None and not path.exists():_save(path,value)
        return value


def update(path, *, limits=None, reset=False, state=None):
    path=safe.absolute(path) if path is not None else None
    if reset and path is not None:sync(path)
    with _locked(path):
        value=_load(path) if path is not None else clean(state) if state is not None else fresh()
        if limits is not None:
            value['limits']={key:_number(limits[key],LIMIT_MIN,LIMIT_MAX) for key in ('car','track')}
        if reset:
            value.update(cars={},tracks={},cycles=dict(car=0,track=0),resets=value['resets']+1)
        _save(path,value)
        return value


def _ingest(value,record):
    """Não infere conclusão. Exige a conclusão já confirmada pelo coletor."""
    if (not isinstance(record,dict) or record.get('schema_version')!=1 or record.get('status')!='imported'
            or type(record.get('started_ns')) is not int or record['started_ns']<value['activated_ns']):return
    result,expected=record.get('result'),record.get('expected')
    identity=record.get('session_id')
    if not isinstance(identity,str) or not identity or len(identity)>160:return
    if not isinstance(result,dict) or not isinstance(expected,dict):return
    if any(result.get(key)!=expected.get(key) for key in ('car','track','layout')):return
    if not all(isinstance(result.get(key),str) and len(result[key])<=160 for key in ('car','track','layout')):return
    if not result['car'] or not result['track'] or not isinstance(result.get('sessions'),list):return
    seen=set(value['seen'])
    for index,row in enumerate(result['sessions']):
        if (not isinstance(row,dict) or type(row.get('type')) is not int or row['type']!=3 or row.get('race_completed') is not True
                or type(row.get('target_laps')) is not int or row['target_laps']<1
                or type(row.get('completed_laps')) is not int or row['completed_laps']<0):continue
        if row['completed_laps']<row['target_laps'] and not (
                row.get('completion_evidence')=='csp_player_finished' and results.captured_finish(record,row)):continue
        token=hashlib.sha256((identity+'#'+str(index)).encode('utf-8')).hexdigest()
        if token in seen:continue
        for key,item in (('cars',result['car']),('tracks',result['track']+'|'+result['layout'])):
            value[key][item]=value[key].get(item,0)+1
        value['seen'].append(token);seen.add(token)


def record(path,record):
    path=safe.absolute(path)
    with _locked(path):
        value=_load(path);before=deepcopy(value);_ingest(value,record)
        if value!=before or not path.exists():_save(path,value)
        return value


def sync(path):
    """Recupera gravação interrompida antes da retenção; nunca importa corridas antigas."""
    path=safe.absolute(path)
    with _locked(path):
        value=_load(path);before=deepcopy(value);root=path.parent/'sessions'
        safe.check_components(root)
        if root.is_dir():
            for folder in root.iterdir():
                try:
                    p=folder/'result.json';safe.check_components(p)
                    if not folder.is_dir() or not p.exists() or p.stat().st_size>256*1024:continue
                    entry=safe.read_json(p)
                    if not isinstance(entry,dict) or entry.get('session_id')!=folder.name:continue
                    _ingest(value,entry)
                except (OSError,ValueError,RuntimeError,KeyError,TypeError):continue
        if value!=before or not path.exists():_save(path,value)
        return value


def restrict(catalog,cars,tracks):
    value=deepcopy(catalog)
    value['cars']=[row for row in value['cars'] if row['id'] in cars]
    value['tracks']=[row for row in value['tracks'] if row['key'] in tracks]
    value['synthesis_classes']=[dict(row,cars=[car for car in row['cars'] if car in cars])
                                for row in value['synthesis_classes'] if any(car in cars for car in row['cars'])]
    return value


def select(catalog,base, *, fixed=None,previous=None,state=None):
    value=clean(state) if state is not None else fresh()
    fixed=events.pins(fixed)
    events.candidates(catalog,base,fixed)  # Pins indisponíveis continuam impedindo a geração.
    groups,tracks=events.candidates(catalog,base)
    pools=dict(car={car for group in groups for car in group['cars']},track={row['key'] for row in tracks})
    pinned=dict(car=fixed['car'],track='|'.join(fixed['track']) if fixed['track'] is not None else None)
    selected=previous.get('selection',{}) if isinstance(previous,dict) else {}
    prior=dict(car=selected.get('car'),track=str(selected.get('track',''))+'|'+str(selected.get('layout','')))
    allowed,info={},{}
    for kind,counts in (('car','cars'),('track','tracks')):
        pool=pools[kind];limit=value['limits'][kind];restart=False
        if pinned[kind] is None and all(value[counts].get(item,0)>=limit for item in pool):
            value[counts]={};value['cycles'][kind]+=1;restart=True
        available={item for item in pool if value[counts].get(item,0)<limit}
        limited=len(pool-available)
        eligible={pinned[kind]} if pinned[kind] is not None else available
        avoided=pinned[kind] is None and prior[kind] in eligible and len(eligible)>1
        if avoided:eligible=eligible-{prior[kind]}
        allowed[kind]=eligible
        info[kind]=dict(limit=limit,eligible=len(pool),excluded_by_limit=limited,
            excluded_previous=bool(avoided),cycle=value['cycles'][kind],cycle_restarted=restart,
            pinned=pinned[kind] is not None,previous_may_repeat=bool(prior[kind] in eligible))
    return restrict(catalog,allowed['car'],allowed['track']),dict(info=info,allowed=allowed),value


def prepare(path,catalog,base, *, fixed=None,previous=None,state=None):
    if path is None:return select(catalog,base,fixed=fixed,previous=previous,state=state)
    sync(path)
    path=safe.absolute(path)
    with _locked(path):
        value=_load(path);before=deepcopy(value)
        filtered,policy,value=select(catalog,base,fixed=fixed,previous=previous,state=value)
        if value!=before:_save(path,value)
        return filtered,policy,value


def note(info):
    parts=[]
    for kind,label in (('car','car'),('track','track/layout')):
        row=info[kind]
        if row['pinned']:parts.append('Pinned '+label+' bypasses its limit.')
        elif row['cycle_restarted']:parts.append(label.capitalize()+' usage cycle restarted.')
        elif row['excluded_by_limit']:parts.append(str(row['excluded_by_limit'])+' '+label+' choices at the usage limit.')
        if not row['pinned'] and row['previous_may_repeat']:parts.append('No other '+label+' available; it may repeat.')
    return ' '.join(parts)
