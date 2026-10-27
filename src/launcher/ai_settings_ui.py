"""Campos de prompt e ditado nas configurações da IA, sem comandos de corrida."""
from concurrent.futures import Future
from copy import deepcopy
import threading
import textwrap

from . import ai_events, ai_preferences, dictation


def layout(text, width=100):
    rows=[]
    start=0
    for paragraph in text.split('\n'):
        for line in textwrap.wrap(paragraph,width=width,expand_tabs=False,replace_whitespace=False,
                                  drop_whitespace=False,break_on_hyphens=False) or ['']:
            rows.append((line,start))
            start+=len(line)
        start+=1
    return rows


def lines(text, width=100):
    return [line for line,_ in layout(text,width)]


def vertical_cursor(text,cursor,delta,width=100):
    rows=layout(text,width)
    index=max(i for i,(_,start) in enumerate(rows) if start<=cursor)
    column=cursor-rows[index][1]
    line,start=rows[max(0,min(len(rows)-1,index+delta))]
    return start+min(column,len(line))


class AISettingsUI:
    def init_ai_settings(self):
        self.ai_panel = None
        self.ai_limits_return = None
        self.audio_sdl = None
        self.voice_capture = None
        self.voice_pending = None
        self.voice_cancelled = None

    def open_ai_settings(self):
        self.ai_panel = dict(draft=deepcopy(self.ai_preferences),main_offset=0,custom_offset=0,
                             editing=False,cursor=len(self.ai_preferences['text']),select_all=False)
        self._open('ai-settings','AI settings / OpenAI gpt-6-luna')
        self.focus_id='custom-prompt'

    def ai_settings_items(self):
        if self.ai_panel.get('scope')=='once':return self.one_shot_items()
        panel=self.ai_panel
        draft=panel['draft']
        active=self.voice_capture is not None
        pending=self.voice_pending is not None
        status='Review and edit the transcript before Save.'
        if active:
            capture=self.voice_capture
            level=round(capture.level*100/32768)
            signal='<1' if capture.level and not level else str(level)
            status=(f'Recording {int(capture.seconds)} / 60 s | audio {capture.captured_seconds:.1f} s'
                    if capture.captured_seconds else f'Waiting for audio / {int(capture.seconds)} s')
            status+=f' | Mic level: {signal}%'
        rows=[self._item('api-key','button',268,166,420,42,'API key: '+('Configured (hidden)' if self.api_key else 'Not set')),
              self._item('ai-effort','button',706,166,244,42,'Reasoning effort: '+self.ai_effort),
              self._item('usage-options','button',968,166,260,42,'Usage limits',disabled=active or pending),
              self._item('main-label','text',268,222,930,24,'Main prompt / read only',disabled=True),
              self._item('main-prompt','textarea',268,248,916,116,'Main prompt',
                         value=ai_events.INSTRUCTIONS,offset=panel['main_offset'],readonly=True),
              self._item('main-up','button',1192,248,36,52,'↑'),
              self._item('main-down','button',1192,312,36,52,'↓'),
              self._item('custom-label','text',268,380,930,24,
                         'Custom prompt / '+str(len(draft['text'].encode('utf-8')))+' / 8192 bytes',disabled=True),
              self._item('custom-prompt','textarea',268,406,916,124,'Custom prompt',
                         value=draft['text'],offset=panel['custom_offset'],cursor=panel['cursor'],
                         editing=panel['editing'],readonly=False),
              self._item('custom-up','button',1192,406,36,54,'↑'),
              self._item('custom-down','button',1192,476,36,54,'↓'),
              self._item('voice-input','button',268,538,520,30,
                         'Microphone: '+(draft['voice_device'] or 'System default'),
                         disabled=active or pending or not draft['voice_enabled']),
              self._item('context-budget','text',806,541,422,26,
                         'Context: 768 KiB max; excess refused.',disabled=True),
              self._item('prompt-save','button',268,578,120,42,'Save',primary=True,disabled=active or pending),
              self._item('prompt-cancel','button',400,578,120,42,'Cancel'),
              self._item('dictate','button',538,578,250,42,
                         'Transcribing...' if pending else 'Stop / Transcribe' if active else 'Dictate',
                         disabled=pending or not draft['voice_enabled'] or not self.api_key),
              self._item('voice-status','text',806,579,422,42,
                         status,disabled=True),
              self._item('voice-enable','button',268,634,960,32,
                         'Remote dictation: '+('On' if draft['voice_enabled'] else 'Off')+
                         ' / OpenAI / paid / uses saved API key / Stop sends audio',disabled=active or pending)]
        return rows

    def close_ai_settings(self):
        once=self.ai_panel is not None and self.ai_panel.get('scope')=='once'
        self.cancel_dictation()
        self.ai_panel=None
        self._close_overlay()
        if once:
            self.ai_request_draft=''
            self.message='One-time request discarded. Your saved custom prompt is unchanged.'

    def ai_settings_activate(self,identity):
        panel=self.ai_panel
        if identity=='api-key':self.open_key()
        elif identity=='usage-options':self.open_ai_usage()
        elif identity=='ai-effort':self.change_effort(1)
        elif identity=='main-prompt':panel['editing']=False
        elif identity=='custom-prompt':
            panel['editing']=True
            self.cancel_pending_ai('Custom prompt is being edited. No new proposal was applied.')
        elif identity in ('main-up','main-down','custom-up','custom-down'):
            key='main_offset' if identity.startswith('main') else 'custom_offset'
            text=ai_events.INSTRUCTIONS if key=='main_offset' else panel['draft']['text']
            panel[key]=max(0,min(max(0,len(lines(text))-4),panel[key]+(-3 if identity.endswith('up') else 3)))
            panel['editing']=False
        elif identity=='prompt-save':
            if panel.get('scope')=='once':return self.generate_one_shot()
            if self.voice_capture is not None or self.voice_pending is not None:return
            try:
                self.save_ai_preferences(panel['draft'])
                self.close_ai_settings()
                self.message='Custom prompt saved. It applies to the next Generate with AI.'
            except (OSError,ValueError,RuntimeError):
                self.message='Could not save custom prompt. Draft kept; check the 8 KiB limit and local permissions.'
        elif identity=='prompt-cancel':self.close_ai_settings()
        elif identity=='voice-enable':
            enabled=not panel['draft']['voice_enabled']
            panel['draft'].update(voice_enabled=enabled,use_generation_key=enabled)
            panel['editing']=False
        elif identity=='dictate':self.start_or_stop_dictation()
        elif identity=='voice-input':self.change_microphone(1)

    def change_microphone(self,delta):
        if self.voice_capture is not None or self.voice_pending is not None:return
        if not self.ai_panel['draft']['voice_enabled']:return
        if self.audio_sdl is None:
            self.message='Microphone unavailable. You can still type.'
            return
        try:
            names=['']+dictation.microphones(self.audio_sdl)
        except (OSError,ValueError,RuntimeError):
            self.message='Could not list microphones. Check the input in SteamOS.'
            return
        draft=self.ai_panel['draft']
        current=draft['voice_device']
        index=names.index(current) if current in names else 0
        draft['voice_device']=names[(index+delta)%len(names)]
        self.ai_panel['editing']=False
        self.message=('Microphone selected for this request; saved preferences unchanged.'
                      if self.ai_panel.get('scope')=='once' and len(names)>1 else
                      'Microphone selected. A / Left / Right changes input; Save keeps this choice.' if len(names)>1 else
                      'Only the default input is available. Check its microphone/mute in SteamOS.')

    def _insert_prompt(self,text):
        panel=self.ai_panel
        text=text.replace('\r\n','\n').replace('\r','\n')
        original=panel['draft']['text']
        cursor=panel['cursor']
        updated=text if panel['select_all'] else original[:cursor]+text+original[cursor:]
        try:ai_preferences.clean(dict(text=updated))
        except ValueError:
            self.message=('Request' if panel.get('scope')=='once' else 'Custom prompt')+' exceeds 8 KiB. Draft kept; shorten the text.'
            return False
        panel['draft']['text']=updated
        panel['cursor']=len(text) if panel['select_all'] else cursor+len(text)
        panel['select_all']=False
        panel['custom_offset']=max(0,len(lines(updated[:panel['cursor']]))-4)
        return True

    def ai_settings_action(self,action):
        panel=self.ai_panel
        if action=='back':
            if panel['editing']:panel['editing']=False
            else:self.close_ai_settings()
            return
        if isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            for item in reversed(self.ai_settings_items()):
                if not item.get('disabled') and item['kind']!='text' and item['x']<=x<item['x']+item['w'] and item['y']<=y<item['y']+item['h']:
                    self.focus_id=item['id']
                    if item['id']!='custom-prompt':panel['editing']=False
                    return self.ai_settings_activate(item['id'])
            return
        if panel['editing'] and self.focus_id=='custom-prompt':
            text=panel['draft']['text'];cursor=panel['cursor']
            if isinstance(action,tuple) and action[0]=='key_text':self._insert_prompt(action[1])
            elif action=='accept':self._insert_prompt('\n')
            elif action=='select_all_text':panel['select_all']=True
            elif action in ('erase_key','delete_text'):
                if panel['select_all']:panel['draft']['text']='';panel['cursor']=0
                elif action=='erase_key' and cursor:panel['draft']['text']=text[:cursor-1]+text[cursor:];panel['cursor']-=1
                elif action=='delete_text':panel['draft']['text']=text[:cursor]+text[cursor+1:]
                panel['select_all']=False
            elif action in ('left','right','up','down','cursor_home','cursor_end'):
                panel['select_all']=False
                if action=='left':cursor=max(0,cursor-1)
                elif action=='right':cursor=min(len(text),cursor+1)
                elif action=='cursor_home':cursor=text.rfind('\n',0,cursor)+1
                elif action=='cursor_end':cursor=text.find('\n',cursor) if '\n' in text[cursor:] else len(text)
                else:
                    cursor=vertical_cursor(text,cursor,-1 if action=='up' else 1)
                panel['cursor']=cursor
                panel['custom_offset']=max(0,len(lines(text[:cursor]))-4)
            elif action not in ('tab_next','tab_prev','page_up','page_down'):return
            else:panel['editing']=False
            if panel['editing']:return
        if action=='accept':return self.ai_settings_activate(self.focus_id)
        if self.focus_id=='ai-effort' and action in ('left','right'):
            return self.change_effort(-1 if action=='left' else 1)
        if self.focus_id=='voice-input' and action in ('left','right'):
            return self.change_microphone(-1 if action=='left' else 1)
        if action in ('up','down','left','right'):return self._move_focus(action)
        if action in ('tab_next','tab_prev'):
            items=[item['id'] for item in self.ai_settings_items() if not item.get('disabled')]
            index=items.index(self.focus_id) if self.focus_id in items else 0
            self.focus_id=items[(index+(-1 if action=='tab_prev' else 1))%len(items)]
        elif action in ('page_up','page_down'):
            kind='custom' if panel.get('scope')=='once' or self.focus_id.startswith('custom') else 'main'
            self.ai_settings_activate(kind+('-up' if action=='page_up' else '-down'))

    def start_or_stop_dictation(self):
        if self.voice_pending is not None:return
        if self.voice_capture is None:
            if not self.ai_panel['draft']['voice_enabled'] or not self.ai_panel['draft']['use_generation_key'] or not self.api_key:
                self.message='Enable remote dictation and API key reuse first.'
                return
            if self.audio_sdl is None:
                self.message='Microphone unavailable. You can still type.'
                return
            try:
                self.voice_capture=dictation.Capture(self.audio_sdl,device=self.ai_panel['draft']['voice_device']).start()
                self.ai_panel['editing']=False
                self.message='Recording. Stop sends this audio to OpenAI for paid transcription; Cancel discards it.'
            except (OSError,ValueError,RuntimeError) as error:
                self.voice_capture=None
                self.message=(dictation.public_message(error) if isinstance(error,dictation.DictationError)
                              and str(error)==dictation.MISSING_INPUT else 'Microphone unavailable. You can still type.')
            return
        capture=self.voice_capture
        self.voice_capture=None
        try:pcm=capture.take()
        except (OSError,ValueError,RuntimeError) as error:
            capture.cancel()
            self.message=dictation.public_message(error)
            return
        settings=deepcopy(self.ai_panel['draft']);key=self.api_key
        future=Future();cancelled=threading.Event()
        self.voice_pending=future;self.voice_cancelled=cancelled
        self.message='Transcribing. Cancel preserves your saved prompt; an already sent request may be charged.'
        def work():
            try:future.set_result(dictation.transcribe(pcm,key,settings=settings,cancelled=cancelled))
            except dictation.DictationError as error:future.set_exception(error)
            except Exception:future.set_exception(dictation.DictationError(dictation.FAILURE))
        threading.Thread(target=work,daemon=True,name='preference-transcription').start()

    def poll_dictation(self):
        self.poll_session_prompt()
        if self.voice_capture is not None and not self.voice_capture.active:
            limited=self.voice_capture.limited
            self.voice_capture.cancel();self.voice_capture=None
            self.message='60 s limit reached. Audio discarded; record a shorter prompt.' if limited else 'Capture failed. Draft kept; you can still type.'
        future=self.voice_pending
        if future is None or not future.done():return
        self.voice_pending=None
        if self.ai_panel is None or self.voice_cancelled.is_set():return
        try:
            transcript=future.result()
            if transcript:
                # Não sobrescrever o texto digitado enquanto a rede estava pendente.
                self.ai_panel['cursor']=len(self.ai_panel['draft']['text'])
                self.ai_panel['select_all']=False
                added=self._insert_prompt(('\n' if self.ai_panel['draft']['text'] else '')+transcript)
                self.focus_id='custom-prompt';self.ai_panel['editing']=True
                self.message=(('Transcript added. Review/edit, then Generate or Cancel.' if self.ai_panel.get('scope')=='once' else
                               'Transcript added to the draft. Review/edit, then Save or Cancel.') if added else
                              'Transcript could not fit within 8 KiB. Draft kept; no text was cut.')
        except (OSError,ValueError,RuntimeError) as error:self.message=dictation.public_message(error)

    def cancel_dictation(self):
        if self.voice_cancelled is not None:self.voice_cancelled.set()
        if self.voice_capture is not None:
            self.voice_capture.cancel();self.voice_capture=None
        self.voice_pending=None

    def close(self):
        self.cancel_dictation()
        super().close()
