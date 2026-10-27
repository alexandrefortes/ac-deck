"""Parecer local limitado, com origem e aplicação explícitas; sem prompt/chave."""
from pathlib import Path
from . import file_io as safe
from . import event_synthetizer as events

STATES=('idle','pending','complete','partial','no_proposal','error')


def path_for(store):
    return Path(store).parent/'ai-report.json' if store is not None else None


def make(outcome='idle',text='Generate with AI to see its verdict here.', *, origin='app',app_note='',applied=False):
    if outcome not in STATES or origin not in ('app','ai') or type(applied) is not bool:
        raise ValueError('Invalid AI verdict state')
    def line(value,limit):
        if not isinstance(value,str):raise ValueError('Invalid AI verdict text')
        return ' '.join(value.split())[:limit]
    return dict(schema_version=1,outcome=outcome,origin=origin,text=line(text,220),
                app_note=line(app_note,260),applied=applied)


def clean(value):
    if not isinstance(value,dict) or value.get('schema_version')!=1:raise ValueError('Invalid AI verdict')
    return make(value['outcome'],value['text'],origin=value['origin'],app_note=value['app_note'],applied=value['applied'])


def load(path):
    if path is None:return make()
    path=Path(path)
    safe.check_components(path)
    if path.exists() and path.stat().st_size>8192:raise ValueError('Invalid AI verdict size')
    raw=events.load(path)
    try:value=clean(raw) if raw is not None else make()
    except (KeyError,TypeError,AttributeError) as error:raise ValueError('Invalid AI verdict') from error
    if value['outcome']=='pending':
        return make('error','The previous AI request did not finish. No new proposal was applied.')
    return value


def save(path,value):
    value=clean(value)
    if path is not None:events.save(path,value)
    return value
