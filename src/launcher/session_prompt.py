"""Pedido temporário do Synth: só memória, ditado pontual e revisão explícita."""
from concurrent.futures import Future
from copy import deepcopy
import threading

from . import ai_preferences,dictation
from .ai_settings_ui import lines,vertical_cursor

EXAMPLE="Example: A race with the feel of Ayrton Senna's peak years."


class SessionPromptUI:
    def init_session_prompt(self):
        self.session_request=dict(text='',device=self.ai_preferences['voice_device'],cursor=0,
                                  offset=0,editing=False,select_all=False,revision=0)
        self.session_capture=None
        self.session_transcript=None
        self.session_cancelled=None
        self.session_transcript_revision=0

    @property
    def session_audio_busy(self):
        return self.session_capture is not None or self.session_transcript is not None

    def session_prompt_items(self):
        state=self.session_request
        if self.overlay=='session-prompt-full':
            return [self._item('session-prompt-note','text',268,166,940,42,
                        'Temporary prompt / app session only / not saved. A edits; B keeps your text.',disabled=True),
                    self._item('session-prompt','textarea',268,222,896,352,'Session prompt',value=state['text'],
                        cursor=state['cursor'],offset=state['offset'],editing=state['editing'],readonly=False,
                        placeholder=EXAMPLE,text_input=True,line_width=self.session_line_width()),
                    self._item('session-up','button',1176,222,52,44,'↑'),
                    self._item('session-down','button',1176,278,52,44,'↓'),
                    self._item('session-scroll-hint','text',268,594,940,28,
                        'L2 / R2 Scroll when not typing. Clear on the main screen discards this text.',disabled=True)]
        active=self.session_capture is not None;pending=self.session_transcript is not None
        label='Temporary prompt / app session only / not saved'
        if active:
            capture=self.session_capture
            label=f'Recording {int(capture.seconds)}/60 s / audio {capture.captured_seconds:.1f} s / Stop transcribes'
        elif pending:label='Transcribing session prompt / no race is generated yet'
        return [self._item('session-prompt-label','text',248,224,476,28,label,disabled=True),
                self._item('session-microphone','button',744,224,280,32,'Mic: '+(state['device'] or 'System default'),disabled=active or pending),
                self._item('session-dictate','button',1032,224,110,32,'Transcribing' if pending else 'Stop' if active else 'Dictate',disabled=pending),
                self._item('session-clear','button',1150,224,98,32,'Clear'),
                self._item('session-prompt','textarea',248,260,808,32,'Session prompt',value=state['text'],
                    cursor=state['cursor'],offset=state['offset'],editing=state['editing'],readonly=False,placeholder=EXAMPLE,
                    text_input=True,line_width=self.session_line_width()),
                self._item('session-expand','button',1068,260,92,32,'Expand'),
                self._item('session-up','button',1172,260,32,32,'↑'),
                self._item('session-down','button',1216,260,32,32,'↓')]

    def session_visible_lines(self):
        return 13 if self.overlay=='session-prompt-full' else 1

    def scroll_session_prompt(self,delta):
        state=self.session_request
        state['offset']=max(0,min(max(0,len(lines(state['text'],self.session_line_width()))-self.session_visible_lines()),
                                  state['offset']+delta))

    def session_line_width(self):
        return 100 if self.overlay=='session-prompt-full' else 90

    def set_session_text(self,text):
        text=ai_preferences.clean(dict(text=text))['text']
        state=self.session_request
        if text!=state['text']:
            self.cancel_pending_ai('Session prompt changed. No new AI proposal was applied.')
            state['text']=text;state['revision']+=1
        state['cursor']=min(state['cursor'],len(text))

    def insert_session_text(self,text):
        state=self.session_request;old=state['text'];cursor=state['cursor']
        text=text.replace('\r\n','\n').replace('\r','\n')
        updated=text if state['select_all'] else old[:cursor]+text+old[cursor:]
        try:self.set_session_text(updated)
        except ValueError:
            self.message='Session prompt exceeds 8 KiB. Text kept; nothing was cut.'
            return
        state['cursor']=min(len(state['text']),len(text) if state['select_all'] else cursor+len(text))
        state['select_all']=False;state['offset']=max(0,len(lines(updated[:state['cursor']],self.session_line_width()))-self.session_visible_lines())

    def cancel_session_audio(self):
        if self.session_cancelled is not None:self.session_cancelled.set()
        if self.session_capture is not None:self.session_capture.cancel();self.session_capture=None
        self.session_transcript=None

    def clear_session_prompt(self):
        self.cancel_session_audio();self.set_session_text('')
        self.session_request.update(editing=False,cursor=0,offset=0,select_all=False)
        self.message='Session prompt cleared. Generate with AI uses saved Custom prompt or defaults.'

    def change_session_microphone(self,delta):
        if self.session_audio_busy:return
        if self.audio_sdl is None:
            self.message='Microphone unavailable. You can type a session prompt.';return
        try:names=['']+dictation.microphones(self.audio_sdl)
        except (OSError,ValueError,RuntimeError):
            self.message='Could not list microphones. Check the input in SteamOS.';return
        state=self.session_request;current=state['device'];index=names.index(current) if current in names else 0
        state['device']=names[(index+delta)%len(names)]
        self.message='Session microphone selected. A / Left / Right changes input. This choice is not saved.'

    def session_dictate(self):
        if self.session_transcript is not None:return
        if self.session_capture is None:
            if not self.api_key or not self.ai_preferences['voice_enabled'] or not self.ai_preferences['use_generation_key']:
                self.message='Enable Remote dictation and configure the saved API key in AI options first.';return
            if self.audio_sdl is None:
                self.message='Microphone unavailable. You can type a session prompt.';return
            try:self.session_capture=dictation.Capture(self.audio_sdl,device=self.session_request['device']).start()
            except (OSError,ValueError,RuntimeError) as error:
                self.session_capture=None;self.message=dictation.public_message(error);return
            self.session_request['editing']=False
            self.cancel_pending_ai('Session dictation started. No new AI proposal was applied.')
            self.message='Recording. Stop sends audio to OpenAI for paid transcription; Clear discards it.'
            return
        capture=self.session_capture;self.session_capture=None
        try:pcm=capture.take()
        except (OSError,ValueError,RuntimeError) as error:
            capture.cancel();self.message=dictation.public_message(error);return
        if not pcm:
            self.message=dictation.NO_AUDIO;return
        settings=deepcopy(self.ai_preferences);settings.update(text='',voice_device=self.session_request['device'])
        key=self.api_key;future=Future();cancelled=threading.Event()
        self.session_transcript=future;self.session_cancelled=cancelled
        self.session_transcript_revision=self.session_request['revision']
        self.message='Transcribing. Review the session text, then choose Generate with AI. No automatic retry.'
        def work():
            try:future.set_result(dictation.transcribe(pcm,key,settings=settings,cancelled=cancelled))
            except (OSError,ValueError,RuntimeError) as error:future.set_exception(error)
            except Exception:future.set_exception(dictation.DictationError(dictation.FAILURE))
            finally:dictation.wipe(pcm)
        threading.Thread(target=work,daemon=True,name='session-transcription').start()

    def poll_session_prompt(self):
        capture=self.session_capture
        if capture is not None and not capture.active:
            limited=capture.limited;self.cancel_session_audio()
            self.message='60 s limit reached. Audio discarded; session text kept.' if limited else 'Capture failed. Session text kept.'
        future=self.session_transcript
        if future is None or not future.done():return
        self.session_transcript=None
        if self.session_cancelled is None or self.session_cancelled.is_set():return
        try:
            transcript=future.result()
            if self.session_request['revision']!=self.session_transcript_revision:
                self.message='Session text changed. Late transcript discarded; no request was generated.';return
            if not isinstance(transcript,str) or not transcript.strip():
                self.message='No speech was transcribed. Session text kept.';return
            self.set_session_text(transcript)
            self.session_request.update(cursor=len(transcript),offset=0,editing=False,select_all=False)
            self.focus_id='session-prompt'
            self.message='Transcript ready for review. Generate with AI uses it instead of saved Custom prompt; Clear discards it.'
        except (OSError,ValueError,RuntimeError) as error:self.message=dictation.public_message(error)

    def activate_session_prompt(self,identity,delta=1):
        state=self.session_request
        if identity=='session-prompt':
            state['editing']=True;self.message='Temporary prompt replaces saved Custom prompt. B keeps it; Clear or app exit discards it.'
        elif identity=='session-expand':
            state.update(editing=False,offset=0)
            self._open('session-prompt-full','Temporary prompt / full text')
            self.focus_id='session-prompt'
        elif identity=='session-clear':self.clear_session_prompt()
        elif identity=='session-microphone':self.change_session_microphone(delta)
        elif identity=='session-dictate':self.session_dictate()
        elif identity in ('session-up','session-down'):
            self.scroll_session_prompt(-self.session_visible_lines() if identity=='session-up' else self.session_visible_lines())
        else:return False
        return True

    def session_prompt_action(self,action):
        state=self.session_request
        if self.view!='synth' or self.overlay not in (None,'session-prompt-full') or self.ai_panel is not None:return False
        if not state['editing'] and action in ('page_up','page_down') and (self.overlay=='session-prompt-full' or self.focus_id in ('session-prompt','session-up','session-down')):
            self.scroll_session_prompt(-self.session_visible_lines() if action=='page_up' else self.session_visible_lines());return True
        if self.focus_id=='session-microphone' and action in ('left','right'):
            self.change_session_microphone(-1 if action=='left' else 1);return True
        if not state['editing']:return False
        text=state['text'];cursor=state['cursor']
        if action=='back':state['editing']=False
        elif isinstance(action,tuple) and action[0]=='key_text':self.insert_session_text(action[1])
        elif action=='accept':self.insert_session_text('\n')
        elif action=='select_all_text':state['select_all']=True
        elif action in ('erase_key','delete_text'):
            if state['select_all']:self.insert_session_text('')
            elif action=='erase_key' and cursor:
                state['cursor']=cursor-1;self.set_session_text(text[:cursor-1]+text[cursor:])
            elif action=='delete_text':self.set_session_text(text[:cursor]+text[cursor+1:])
        elif action in ('left','right','up','down','cursor_home','cursor_end'):
            if action=='left':cursor=max(0,cursor-1)
            elif action=='right':cursor=min(len(text),cursor+1)
            elif action=='cursor_home':cursor=text.rfind('\n',0,cursor)+1
            elif action=='cursor_end':cursor=text.find('\n',cursor) if '\n' in text[cursor:] else len(text)
            else:cursor=vertical_cursor(text,cursor,-1 if action=='up' else 1,width=self.session_line_width())
            state['cursor']=cursor;state['select_all']=False
            state['offset']=max(0,len(lines(text[:cursor],self.session_line_width()))-self.session_visible_lines())
        elif isinstance(action,tuple) and action[0]=='click' or action in ('tab_next','tab_prev','page_up','page_down'):
            state['editing']=False;return False
        return True

    def close(self):
        self.cancel_session_audio();self.session_request.update(text='',cursor=0,offset=0,editing=False,select_all=False)
        super().close()
