"""Pedido pontual em memória; reutiliza texto e ditado das preferências da IA."""
from copy import deepcopy


class OneShotUI:
    def open_one_shot(self):
        if self.ai_pending is not None:
            return
        draft = deepcopy(self.ai_preferences)
        draft['text'] = self.ai_request_draft
        self.ai_panel = dict(scope='once', draft=draft, main_offset=0, custom_offset=0,
                             editing=False, cursor=len(draft['text']), select_all=False)
        self._open('ai-request', 'Request an event / this generation only')
        self.focus_id = 'custom-prompt'

    def one_shot_items(self):
        panel = self.ai_panel
        draft = panel['draft']
        active, pending = self.voice_capture is not None, self.voice_pending is not None
        status = 'Dictation uses your saved OpenAI key. Stop sends audio; review the text before Generate.'
        if active:
            capture = self.voice_capture
            level = round(capture.level*100/32768)
            status = (f'Recording {int(capture.seconds)} / 60 s | audio {capture.captured_seconds:.1f} s'
                      if capture.captured_seconds else f'Waiting for audio / {int(capture.seconds)} s')
            status += f' | Mic level: {"<1" if capture.level and not level else level}%'
        elif pending:
            status = 'Transcribing. You can keep typing or Cancel; no event request has been sent.'
        note = ('Previous request failed. Draft kept for an explicit new attempt.' if self.ai_request_draft else
                'Used once. The active session prompt remains for later generations.' if self.session_request['text'] else
                'Used once. Your saved custom prompt stays unchanged.')
        return [self._item('request-note','text',268,166,960,42,note,disabled=True),
                self._item('custom-label','text',268,218,960,24,
                           'One-time request / '+str(len(draft['text'].encode('utf-8')))+' / 8192 bytes',disabled=True),
                self._item('custom-prompt','textarea',268,246,916,202,'One-time request',value=draft['text'],
                           offset=panel['custom_offset'],cursor=panel['cursor'],editing=panel['editing'],readonly=False,
                           placeholder='Describe the event you want for this generation.'),
                self._item('custom-up','button',1192,246,36,94,'↑'),
                self._item('custom-down','button',1192,354,36,94,'↓'),
                self._item('request-catalogue','text',268,462,960,32,
                           'AI uses installed content only and reports when it cannot match the request.',disabled=True),
                self._item('voice-input','button',268,506,420,40,
                           'Microphone: '+(draft['voice_device'] or 'System default'),
                           disabled=active or pending or not draft['voice_enabled']),
                self._item('dictate','button',706,506,244,40,
                           'Transcribing...' if pending else 'Stop / Transcribe' if active else 'Dictate',
                           disabled=pending or not draft['voice_enabled'] or not self.api_key),
                self._item('voice-status','text',268,552,960,42,status,disabled=True),
                self._item('prompt-save','button',268,612,250,42,'Generate this event',primary=True,
                           disabled=active or pending or self.ai_pending is not None or not draft['text'].strip()),
                self._item('prompt-cancel','button',534,612,142,42,'Cancel'),
                self._item('voice-enable','button',706,612,522,42,
                           'Remote dictation: '+('On' if draft['voice_enabled'] else 'Off')+' / paid / Stop sends audio',
                           disabled=active or pending)]

    def generate_one_shot(self):
        if self.voice_capture is not None or self.voice_pending is not None or self.ai_pending is not None:
            return
        text = self.ai_panel['draft']['text']
        if not text.strip():
            self.message = 'Describe the event before generating. Your saved prompt is unchanged.'
            return
        if not self.generate_ai_event(instruction=text):
            return
        self.ai_request_draft = text
        self.ai_request_inflight = True
        self.cancel_dictation()
        self.ai_panel = None
        self._close_overlay()

    def generate_event(self):
        self.ai_request_draft = ''
        self.ai_request_inflight = False
        return super().generate_event()

    def generate_ai_event(self, instruction=None):
        started = super().generate_ai_event(instruction=instruction)
        if started and not (instruction or '').strip():
            self.ai_request_draft = ''
            self.ai_request_inflight = False
        return started

    def poll_ai(self):
        pending = self.ai_pending
        super().poll_ai()
        if self.ai_request_inflight and pending is not None and self.ai_pending is None:
            self.ai_request_inflight = False
            if self.ai_report['outcome'] != 'error':
                self.ai_request_draft = ''

    def cancel_pending_ai(self, reason='AI settings changed. No new proposal was applied.'):
        super().cancel_pending_ai(reason)
        self.ai_request_draft = ''
        self.ai_request_inflight = False

    def close(self):
        self.ai_request_draft = ''
        self.ai_request_inflight = False
        super().close()
