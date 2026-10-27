"""Interface nativa aprovada, sobre os contratos do menu e catálogo existentes.

Nenhum dado da prévia HTML é importado. Navegação e origem da sessão têm
estados independentes; cada página inicia apenas a própria seleção.
"""
from . import graphics_settings
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from . import content, event_synthetizer, graphics, previews, controls, comfort, chase_camera, ai_events, driving_haptics
from .window import Menu
from . import ai_usage
from . import session_settings, catalogue, favorites
from .ai_settings_ui import AISettingsUI
from .one_shot_ui import OneShotUI
from .session_prompt import SessionPromptUI
from .campaign_ui import CampaignUI
from .rogue_ui import RogueUI
from . import campaigns


VIEWS = ('drive', 'events', 'synth', 'rogue', 'history', 'settings')
LABELS = ('Drive', 'Events', 'Event Synthetizer', 'Rogue', 'History', 'Settings')


class NativeMenu(RogueUI,CampaignUI,OneShotUI,SessionPromptUI,AISettingsUI,Menu):
    def __init__(self, *args, **kwargs):
        campaign_cfg = kwargs.pop('campaign_cfg', None)
        kwargs.setdefault('catalog_cache',True)
        super().__init__(*args, **kwargs)
        self.init_ai_settings()
        self.init_session_prompt()
        self.ai_request_draft = ''
        self.ai_request_inflight = False
        self.view = 'drive'
        self.overlay = None
        self.overlay_title = ''
        self.focus_id = 'car'
        self.source = 'manual'
        self.installed_selection = None
        self.category = 'graphics'
        self.query = ''
        self.search_edit_id = None
        self.brand_filter = ''
        self.brand_state = None
        self.content_filter = catalogue.clean_filter({})
        self.favorites_only = False
        self.favorites_path = favorites.path_for(self.synthesis_store) if self.synthesis_store else None
        self.favorites_error = False
        self.favorites_revision = 0
        self._set_favorites(favorites.clean())
        if self.favorites_path is not None:
            try:
                self._set_favorites(favorites.load(self.favorites_path))
            except (OSError, ValueError, RuntimeError, TypeError):
                self.favorites_error = True
                self.message = 'Favorites unavailable. Original file kept; use Recover favorites.'
        self.catalogue_panel = None
        self.browse_states = {}
        self.filter_cache = None
        self.tag_cache = {}
        self.picker_kind = None
        self.picker_pin = False
        self.picker_index = 0
        self.picker_skin = None
        self.picker_car = None
        self.picker_skin_explicit = False
        self.livery_state = None
        self.livery_names = {}
        self.picker_page = 0
        self.history_page = 0
        self.history_rows = []
        self.history_record = None
        self.return_focus = 'car'
        self.editing = None
        self.session_running = False
        self.verdict_offset = 0
        self.ui_state_path = Path(self.synthesis_store).parent/'ui-state.json' if self.synthesis_store else None
        if self.ui_state_path is not None:
            try:
                saved = event_synthetizer.load(self.ui_state_path)
                if isinstance(saved, dict) and saved.get('schema_version') == 1:
                    if isinstance(saved.get('catalogue'), dict):
                        self.browse_states = {key: value for key, value in saved['catalogue'].items()
                                              if key in ('cars','tracks','events') and isinstance(value,dict)}
                    source = saved.get('source')
                    if source == 'generated':
                        self.source = source
                    elif source == 'installed' and isinstance(saved.get('installed_selection'), dict):
                        restored = saved['installed_selection']
                        if any(row['id'] == restored.get('event') for row in self.catalog['events']):
                            self.installed_selection = restored
                            self.source = source
            except (OSError, ValueError, RuntimeError):
                self.message = 'Saved interface state unavailable. Manual choices are preserved.'
        self.init_campaigns(campaign_cfg)
        self.init_rogue()
        self.refresh_history()
        if self.message=='Choose your race. Press X or Start to drive.':self.message=''

    @property
    def searching(self):
        if self.view=='synth' and self.overlay in (None,'session-prompt-full') and self.session_request['editing']:
            return self.focus_id=='session-prompt'
        if self.ai_panel is not None:
            return self.focus_id=='custom-prompt' and self.ai_panel['editing']
        if self.catalogue_panel is not None:
            return (self.catalogue_panel['kind']=='filters' and self.focus_id=='tag-search'
                    and self.search_edit_id=='tag-search')
        return (self.brand_state is None and self.livery_state is None and self.overlay in ('cars', 'tracks', 'events')
                and self.focus_id=='search' and self.search_edit_id=='search')

    def _remember_source(self):
        if self.ui_state_path is not None:
            try:
                event_synthetizer.save(self.ui_state_path, dict(schema_version=1, source=self.source,
                    installed_selection=self.installed_selection, catalogue=self.browse_states))
            except (OSError, ValueError, RuntimeError):
                self.message = 'Session prepared. Could not save the interface state.'

    def select_source(self, source):
        self.source = source
        self._remember_source()

    def refresh_history(self):
        from . import history_records
        try:
            self.history_rows = history_records.load(self.synthesis_store) if self.synthesis_store else []
        except (OSError, ValueError, RuntimeError):
            self.history_rows = []
        self.history_page = min(self.history_page, max(0, (len(self.history_rows)-1)//5))
        self._warm_previews()
        if hasattr(self,'campaign_cfg'):self.refresh_campaigns()

    def effective_selection(self):
        if self.source == 'rogue':
            chosen = self.rogue_effective_selection()
            if not chosen:return {}
        else:
            chosen = None
        if self.source == 'generated' and self.synthesis is None:return {}
        if self.source == 'installed' and self.installed_selection is None:return {}
        if self.source == 'generated' and self.synthesis is not None:
            chosen = dict(self.synthesis['selection'])
        elif self.source == 'installed' and self.installed_selection is not None:
            chosen = dict(self.installed_selection)
        elif chosen is None:
            chosen = dict(self.selection)
        chosen=session_settings.restore(chosen,self.selection)
        car = next((row for row in self.catalog['cars'] if row['id'] == chosen.get('car')), None)
        track = next((row for row in self.catalog['tracks']
                      if (row['id'],row['layout']) == (chosen.get('track'),chosen.get('layout',''))), None)
        chosen.update(car_name=car['name'] if car else str(chosen.get('car','Unavailable')),
                      track_name=track['name'] if track else str(chosen.get('track','Unavailable')),
                      track_layout=track.get('layout','') if track else '',
                      mode_name=chosen.get('event_mode_name') or content.MODES[chosen.get('mode',0)][0])
        return chosen

    def ui_heading(self):
        if self.overlay:
            return ('CONTENT' if self.overlay in ('cars','tracks','events') else 'SESSION',
                    self.overlay_title, self.message)
        return {
            'drive': ('MANUAL SETUP', 'Your next drive.', self.message),
            'events': ('INSTALLED CAMPAIGNS', 'Choose your event.', self.message),
            'synth': ('EVENT SYNTHETIZER', '' if self.synthesis else 'Find your next drive.', self.message),
            'rogue': ('ROGUE / RACE RESULT' if self.rogue_result_visible() else 'ROGUE / NEXT CHALLENGE',
                      '' if self.rogue_result_visible() or self.rogue_run else 'One more race.', self.message),
            'history': ('LOCAL HISTORY', 'Every drive has a story.', self.message),
            'settings': ('YOUR PREFERENCES', 'Make it feel right.', self.message),
        }[self.view]

    def _image(self, chosen, kind):
        if self.game is None:
            return ()
        group = 'cars' if kind == 'car' else 'tracks'
        item = next((row for row in self.catalog[group] if row['id'] == chosen.get(kind)
            and (kind == 'car' or row['layout'] == chosen.get('layout',''))), None)
        if item is None:
            return ()
        key = (kind,item['id'],item.get('layout',''),chosen.get('skin'))
        if key not in self.preview_cache:
            self.preview_cache[key] = previews.paths(self.game,item,kind,chosen.get('skin') if kind=='car' else None)
        return self.preview_cache[key]

    def _outline(self, track):
        if self.game is None or not track:return ()
        key=('outline',track['id'],track.get('layout',''))
        if key not in self.preview_cache:
            self.preview_cache[key]=previews.paths(self.game,track,'outline')
        return self.preview_cache[key]

    def _warm_previews(self):
        selections=[self.selection,self.effective_selection()]
        if self.synthesis is not None:selections.append(self.synthesis['selection'])
        selections.extend(record['selection'] for record in self.history_rows)
        for chosen in selections:
            self._image(chosen,'car')
            self._image(chosen,'track')
            track=next((row for row in self.catalog['tracks']
                if (row['id'],row['layout'])==(chosen.get('track'),chosen.get('layout',''))),None)
            self._outline(track)

    @staticmethod
    def _item(identity, kind, x, y, width, height, label, **kwargs):
        return dict(id=identity,kind=kind,x=x,y=y,w=width,h=height,label=str(label),**kwargs)

    def _base_items(self):
        rows = [self._item('nav:'+view,'nav',16,214+index*78,184,68,label,
                          **(dict(subtitle='Build your run') if view=='rogue' else {}),
                          selected=self.view==view) for index,(view,label) in enumerate(zip(VIEWS,LABELS))]
        rows.append(self._item('exit','button',1128,21,120,34,'Exit',disabled=self.session_running))
        if self.rogue_result_visible():
            return rows if self.overlay else rows+self.rogue_result_footer()
        blocked = (self.session_running or self.editing is not None or self.ai_panel is not None
                   or self.session_audio_busy or self.session_request['editing']
                   or self.source == 'generated' and self.synthesis is None
                   or self.source == 'rogue' and self.rogue_block() is not None
                   or self.source == 'installed' and self._campaign_block() is not None)
        rows += [self._item('details','button',884,708,130,52,'Session details',disabled=not bool(self.effective_selection())),
                 self._item('start','button',1034,708,214,52,
                            'Finishing session' if getattr(self,'session_ending',False) else
                            'Session running' if self.session_running else 'Start race',disabled=blocked)]
        return rows

    def _cards(self, chosen):
        car = next((row for row in self.catalog['cars'] if row['id']==chosen.get('car')), {})
        track = next((row for row in self.catalog['tracks']
                      if (row['id'],row['layout'])==(chosen.get('track'),chosen.get('layout',''))), {})
        return [self._item('car','car',248,170,648,360,car.get('name','Car unavailable'),
                    value=car.get('brand',''), subtitle=chosen.get('skin',''), image=self._image(chosen,'car')),
                self._item('track','track',912,170,336,360,track.get('name','Circuit unavailable'),
                    value=track.get('layout',''),subtitle=track.get('country',''), image=self._image(chosen,'track'),
                    outline=self._outline(track))]

    def _binding(self, tab, index, x, y, width=234, height=76):
        identity=f'edit:{tab}:{index}'
        manual=self.selection
        if tab==3 and index in (0,1,2,3,4,5,6,8) and self.source=='installed' and self.installed_selection is not None:
            self.selection=self.installed_selection
        try:
            source=self.editing['menu'] if self.editing and self.editing['id']==identity else self
            name = source.rows(tab)[index]['name']
        finally:
            self.selection=manual
        label, separator, value = name.partition(' : ')
        return self._item(identity,'field',x,y,width,height,label,
                          value=value if separator else '', binding=(tab,index),editable=True)

    def _event_binding(self, index, x, y, width=234, height=76):
        source=self.editing['menu'] if self.editing and self.editing['id']==f'event:{index}' else self
        name = source.rows(6)[index]['name']
        label,_,value = name.partition(' : ')
        disabled=index==9 and self.synthesis is None
        return self._item(f'event:{index}','field',x,y,width,height,label,value=value,
                          editable=not disabled,disabled=disabled)

    def _usage_binding(self,key,x,y,width=766,height=62):
        identity='usage:'+key
        source=self.editing['menu'] if self.editing and self.editing['id']==identity else self
        value=str(source.ai_usage['limits'][key]) if source.ai_usage is not None else 'Unavailable'
        label='Max completed races per '+('car' if key=='car' else 'track / layout')
        return self._item(identity,'setting',x,y,width,height,label,value=value,
                          editable=source.ai_usage is not None,disabled=source.ai_usage is None)

    def open_ai_usage(self):
        if self.ai_panel is not None and (self.voice_capture is not None or self.voice_pending is not None):return
        self.ai_limits_return=self.ai_panel
        self.ai_panel=None
        try:self.ai_usage=ai_usage.load(self.ai_usage_path) if self.ai_usage_path else self.ai_usage
        except (OSError,ValueError,RuntimeError):self.ai_usage=None
        self._open('usage-options','AI usage limits')
        self.focus_id='usage:car' if self.ai_usage is not None else 'ai-reset-usage'

    def _editing_items(self, rows):
        for item in rows:
            identity=item['id']
            if identity=='effort':
                item['editable']=True
            if self.editing and identity==self.editing['id']:
                item['editing']=True
                if identity=='effort':item['value']=self.editing['menu'].ai_effort
        if self.editing:
            rows=[item for item in rows if item['id'] not in
                  ('confirm-content','captured-base','conditions-label','session','generated-info','use-event','graphics-fixed',
                   'ai-adjust-request','ai-reset-usage')]
            if self._editing_profile():
                rows.append(self._item('profile-reset-notice','text',482,632,432,44,
                    'Changing profile replaces custom graphics.\nA loads defaults / B keeps current settings.',
                    scale=1.2,color=(230,212,154),disabled=True))
            else:
                rows.append(self._item('editing-hint','text',268,645,638,30,
                    'Editing: arrows adjust. A confirms / B cancels.',disabled=True))
            rows += [self._item('edit-confirm','button',932,638,140,38,'Confirm',primary=True),
                     self._item('edit-cancel','button',1088,638,140,38,'Cancel')]
        return rows

    def _setting_groups(self):
        result = {
            'graphics': [('Graphics & Display',[(4,i) for i in range(len(self.graphics_keys))])],
            'controls': [('Controls',[])], 'assists': [('Driving Assists',[(3,7),(3,9)])],
            'camera': [('Camera & View',[])], 'interface': [('Race Interface',[])],
            'opponents': [('Opponent AI',[(3,10),(3,11)] if self.csp else [])],
            'ai': [('AI',[])],
        }
        for index,key in enumerate(self.control_keys):
            target = ('camera' if key in chase_camera.SETTINGS or key in ('hide_driver_arms','virtual_steer_degrees')
                      else 'assists' if key in ('car_damage_pct','abs_mode','traction_control','stability_control')
                      else 'interface' if key in comfort.SETTINGS else 'controls')
            result[target][0][1].append((5,index))
        return result

    def ui_items(self):
        rows = self._base_items()
        if self.ai_panel is not None:
            return rows+self.ai_settings_items()
        if self.catalogue_panel is not None:
            return rows + self._catalogue_panel_items()
        if self.brand_state is not None:
            return rows + self._overlay_items() + self._brand_items()
        if self.overlay:
            return self._editing_items(rows + self._overlay_items())
        if self.view == 'drive':
            chosen = self.effective_selection()
            rows += self._cards(chosen)
            indices = [0,5,4,3] if content.MODES[self.selection['mode']][1]==3 else [0,6,8,2]
            if self.selection['mode'] != 0 and content.MODES[self.selection['mode']][1] != 3:
                indices=[0,1,8,2]
            rows += [self._binding(3,index,248+column*250,546,250) for column,index in enumerate(indices)]
            when = chosen.get('time_minutes')
            conditions = ('From session' if when is None else f'{when//60:02}:{when%60:02}')+' / '+chosen.get('weather','')+' / Track Optimum'
            rows += [self._item('conditions-label','text',248,638,730,36,conditions,disabled=True),
                     self._item('session','button',1010,634,238,40,'Conditions & session')]
        elif self.view == 'events':
            rows += self._campaign_items()
        elif self.view == 'rogue':
            rows += self.rogue_items()
        elif self.view == 'synth':
            rows += [self._item('generate','button',248,166,248,46,'Generate without AI',primary=True),
                     self._item('generate-ai','button',510,166,248,46,'Generating...' if self.ai_pending else 'Generate with AI',disabled=self.ai_pending is not None or self.session_audio_busy),
                     self._item('ai-activity','activity',772,166,72,46,'AI activity',disabled=True,visible=self.ai_pending is not None),
                     self._item('pin-car','button',870,166,182,46,'Pin car: '+('On' if self.event_options['pins']['car'] else 'Off')),
                     self._item('pin-track','button',1066,166,182,46,'Pin track: '+('On' if self.event_options['pins']['track'] else 'Off'))]
            rows+=self.session_prompt_items()
            if self.synthesis:
                for item in self._cards(self.synthesis['selection']):
                    item.update(x=248 if item['id']=='car' else 756,y=300,w=492,h=208,synthesis_card=True)
                    rows.append(item)
            else:
                rows.append(self._item('empty','text',268,370,930,82,
                    'A different way to choose.',value='Generate a race from the content installed on this device.',disabled=True))
            rows += [dict(self._event_binding(index,248+column*250,520,height=56),compact=True) for column,index in enumerate((6,7,8,9))]
            rows.append(self._item('ai-options','button',998,114,250,36,'AI options'))
            rows.append(self._item('usage-options','button',744,114,238,36,'AI usage limits'))
            report=self.ai_report
            rows.append(self._item('ai-verdict','verdict',248,584,1000,52,
                'AI verdict' if report['origin']=='ai' else 'App status',value=report['text'],
                app_note=report['app_note'],outcome=report['outcome'],compact=True))
            rows += [self._item('ai-adjust-request','button',248,642,230,34,'Adjust custom prompt'),
                     self._item('ai-reset-usage','button',494,642,230,34,'Reset usage counters')]
            if self.ai_pending is not None:
                rows.append(self._item('cancel-ai-generation','button',740,642,254,34,'Cancel generation'))
            if self.synthesis:
                proposal=self.synthesis
                rows.append(self._item('proposal-info','button',248,114,280,36,
                    ('Previous proposal' if report['outcome'] in ('pending','no_proposal','error') else
                     proposal.get('generator_label','Local event'))+' / Details'))

        elif self.view == 'settings':
            groups = self._setting_groups()
            for index,(key,group) in enumerate(groups.items()):
                rows.append(self._item('category:'+key,'category',248,174+index*66,208,54,group[0][0],selected=self.category==key))
            bindings=groups[self.category][0][1]
            start=getattr(self,'settings_page',0)*6
            for index,(tab,position) in enumerate(bindings[start:start+6]):
                item=self._binding(tab,position,482,174+index*66,766,58)
                item['kind']='setting'
                rows.append(item)
            if self.category == 'ai':
                rows += [self._item('api-key','setting',482,174,766,62,'API key',value='Configured (hidden)' if self.api_key else 'Not set'),
                         self._item('effort','setting',482,246,766,62,'Reasoning effort',value=self.ai_effort),
                         self._usage_binding('car',482,318),self._usage_binding('track',482,390),
                         self._item('model','text',500,464,720,28,'OpenAI / gpt-6-luna',disabled=True)]
                rows.append(self._item('ai-options','button',482,506,766,54,'Main prompt / Custom prompt / Dictation'))
                rows.append(self._item('ai-reset-usage','button',482,574,766,42,'Reset usage counters / keep history'))
            if not bindings and self.category != 'ai':
                rows.append(self._item('settings-empty','text',500,210,700,90,'No options for this profile.',disabled=True))
            if len(bindings)>6:
                rows += [self._item('settings-prev','button',482,584,120,42,'L2 Previous'),
                         self._item('settings-next','button',1128,584,120,42,'Next R2')]
            if self.category=='graphics':
                pages=max(1,(len(bindings)+5)//6)
                rows.append(self._item('graphics-page','text',620,584,490,40,f"Graphics {getattr(self,'settings_page',0)+1} / {pages} · {('CSP active' if graphics.uses_csp(self.selection['graphics_profile']) else 'CSP inactive')}",disabled=True))
                rows.append(self._item('graphics-fixed','text',482,625,766,28,'Mirrors Off / Linear color Off',disabled=True))
            if self.category=='controls' and self.csp:
                rows += [self._item('haptics_left','button',650,584,190,42,'Test left haptics',disabled=self.session_running),
                         self._item('haptics_right','button',860,584,190,42,'Test right haptics',disabled=self.session_running)]
            if self.source=='generated' and self.category!='graphics':
                rows.append(self._item('captured-base','text',482,638,760,28,'Race conditions stay fixed. All modes use your current preferences.',disabled=True))
            if self.category=='opponents' and self.csp:
                rows.append(self._item('opponent-ai-note','text',482,330,766,80,
                    'Experimental AI requires Improved AI.\nBoth require a CSP graphics profile. Applies to all modes.',disabled=True))
        elif self.view == 'history':
            if not self.history_rows:
                rows.append(self._item('history-empty','text',270,230,930,100,'No sessions recorded yet.',
                                      value='Results from your next sessions will appear here.',disabled=True))
            for index,record in enumerate(self.history_rows[self.history_page*5:self.history_page*5+5]):
                selected=record['selection']
                car=next((c['name'] for c in self.catalog['cars'] if c['id']==selected.get('car')),selected.get('car',''))
                track=next((t['name'] for t in self.catalog['tracks'] if (t['id'],t['layout'])==(selected.get('track'),selected.get('layout',''))),selected.get('track',''))
                rows.append(self._item('history:'+str(self.history_page*5+index),'history',248,174+index*84,1000,74,
                    car+' / '+track,value=record['summary'],subtitle=record['id'],image=self._image(selected,'car')))
            if len(self.history_rows)>5:
                rows += [self._item('history-prev','button',248,614,130,40,'L2 Previous'),
                         self._item('history-next','button',1118,614,130,40,'Next R2')]
        return self._editing_items(rows)

    def _filtered_content(self):
        key={'cars':'cars','tracks':'tracks','events':'events'}[self.overlay]
        values=self.catalog[key]
        query=self.query.casefold().strip()
        selected=catalogue.clean_filter(self.content_filter)
        key=(len(values),query,self.brand_filter,selected['origin'],tuple(selected['tags']),selected['match'],
             self.favorites_only,self.favorites_revision)
        cached=self.filter_cache
        if cached is not None and cached[0] is self.catalog and cached[1] is values and cached[2]==key:
            return cached[3]
        result=[row for row in values if (not query or query in (' '.join(str(row.get(name,'')) for name in ('name','id','brand','country','layout','group','author'))).casefold())
                and (not self.brand_filter or row.get('brand','')==self.brand_filter)
                and catalogue.matches(row,selected)
                and (not self.favorites_only or self._is_favorite(row))]
        self.filter_cache=(self.catalog,values,key,result)
        return result

    def _set_favorites(self, value):
        self.favorites = value
        self.favorite_cars = set(value['cars'])
        self.favorite_tracks = {(row['id'], row['layout']) for row in value['tracks']}

    def _is_favorite(self, row):
        if self.overlay == 'cars':return row['id'] in self.favorite_cars
        if self.overlay == 'tracks':return (row['id'],row.get('layout','')) in self.favorite_tracks
        return False

    def _favorite_button(self, row):
        return self._item('favorite-toggle','button',268,642,360,34,
            'Recover favorites' if self.favorites_error else
            'Remove from favorites' if row and self._is_favorite(row) else 'Add to favorites',
            disabled=not row and not self.favorites_error)

    def _toggle_favorite(self):
        if self.overlay not in ('cars','tracks'):return
        if self.favorites_error:
            self.catalogue_panel=dict(kind='favorites-recovery',previous=self.catalogue_panel,
                return_focus='favorite-toggle')
            self.focus_id='catalogue-back'
            return
        values=self._filtered_content()
        row=(self.catalogue_panel['row'] if self.catalogue_panel and self.catalogue_panel['kind']=='detail'
             else values[self.picker_index] if values else None)
        if row is None:return
        changed=favorites.toggle(self.favorites,self.overlay,row)
        try:
            if self.favorites_path is not None:changed=favorites.save(self.favorites_path,changed)
        except (OSError,ValueError,RuntimeError,TypeError):
            self.message='Could not save favorites. Previous favorite kept.'
            return
        self._set_favorites(changed)
        self.favorites_revision+=1
        previous=self.picker_index
        values=self._filtered_content()
        self.picker_index=next((i for i,item in enumerate(values)
            if (item['id'],item.get('layout',''))==(row['id'],row.get('layout',''))),
            max(0,min(previous,len(values)-1)))
        self.picker_page=self.picker_index//6
        if self.catalogue_panel is not None:
            self.catalogue_panel['return_focus']='pick:'+str(self.picker_index) if values else 'filter-open'
        elif not values:self.focus_id='filter-open'
        self.message='Favorite saved.' if self._is_favorite(row) else 'Favorite removed.'
        self._remember_picker()

    def _filter_summary(self):
        chosen=self.content_filter
        parts=[catalogue.ORIGINS[chosen['origin']]]
        if self.brand_filter:parts.append(self.brand_filter)
        if chosen['tags']:
            parts.append(('All tags: ' if chosen['match']=='all' else 'Any tag: ')+', '.join(chosen['tags']))
        else:parts.append('All tags')
        if self.query:parts.append('Search: '+self.query)
        if self.favorites_only:parts.append('Favorites only')
        return ' · '.join(parts)

    def _remember_picker(self):
        if self.overlay not in ('cars','tracks','events'):return
        values=self._filtered_content()
        row=values[min(self.picker_index,len(values)-1)] if values else {}
        self.browse_states[self.overlay]=dict(query=self.query,brand=self.brand_filter,
            filters=deepcopy(self.content_filter),favorites_only=self.favorites_only,
            identity=[row.get('id'),row.get('layout','')])
        self._remember_source()

    def _restore_picker(self):
        saved=self.browse_states.get(self.overlay,{})
        if not saved:return
        self.query=catalogue.text(saved.get('query'),100)
        self.brand_filter=catalogue.text(saved.get('brand')) if self.overlay=='cars' else ''
        self.content_filter=catalogue.clean_filter(saved.get('filters'))
        self.favorites_only=saved.get('favorites_only') is True and not self.favorites_error
        values=self._filtered_content()
        identity=saved.get('identity')
        self.picker_index=next((i for i,row in enumerate(values)
            if [row['id'],row.get('layout','')]==identity),0)
        self.picker_page=self.picker_index//6

    def _anchor_picker(self, identity=None):
        values=self._filtered_content()
        self.picker_index=next((i for i,row in enumerate(values)
            if [row['id'],row.get('layout','')]==identity),0)
        self.picker_page=self.picker_index//6

    def _open_catalogue_panel(self, kind):
        self.search_edit_id=None
        values=self._filtered_content()
        row=values[self.picker_index] if values else {}
        if kind=='detail' and not row:return
        self.catalogue_panel=dict(kind=kind,draft=deepcopy(self.content_filter),page=0,query='',
            favorites_only=self.favorites_only,
            row=deepcopy(row),return_focus='pick:'+str(self.picker_index) if kind=='detail' else 'filter-open')
        self.focus_id='filter-origin:all' if kind=='filters' else 'catalogue-back'

    def _close_catalogue_panel(self):
        self.search_edit_id=None
        if self.catalogue_panel['kind']=='favorites-recovery':
            panel=self.catalogue_panel
            self.catalogue_panel=panel['previous']
            self.focus_id=panel['return_focus']
            return
        self.focus_id=self.catalogue_panel['return_focus']
        self.catalogue_panel=None

    def _catalogue_tags(self):
        values=self.catalog[self.overlay]
        cached=self.tag_cache.get(self.overlay)
        if cached is None or cached[0] is not self.catalog or cached[1] is not values or cached[2]!=len(values):
            labels={}
            for row in values:
                for tag in row.get('tags',[]):
                    key=catalogue.tag_key(tag)
                    if key:labels.setdefault(key,catalogue.text(tag,64))
            cached=(self.catalog,values,len(values),labels)
            self.tag_cache[self.overlay]=cached
        labels=dict(cached[3])
        panel=self.catalogue_panel
        # Keep unavailable selections removable after content is removed.
        for key in panel['draft']['tags']:labels.setdefault(key,key+' (not installed)')
        query=panel['query'].casefold().strip()
        return sorted(((key,label) for key,label in labels.items() if not query or query in label.casefold()))

    def _catalogue_panel_items(self):
        panel=self.catalogue_panel
        rows=[self._item('catalogue-back','button',1120,98,110,38,'Back')]
        if panel['kind']=='favorites-recovery':
            return rows+[
                self._item('favorites-warning','text',268,190,936,140,'Favorites unavailable',
                    value='Keep the original in a separate local file and start a new empty favorites list?',disabled=True),
                self._item('favorites-recover','button',268,400,440,46,'Back up and reset favorites')]
        if panel['kind']=='detail':
            row=panel['row']
            rows.append(self._item('catalogue-name','text',268,168,940,45,row['name'],disabled=True))
            fields=[('Origin',catalogue.ORIGINS.get(row.get('origin'),'Unknown origin')),
                    ('Author (declared)',row.get('author') or 'Unavailable')]
            if self.overlay=='cars':
                fields += [('Power',row.get('power_display','Unavailable')),
                    ('Power source',row.get('power_source','Not supplied'))]
            else:
                fields += [('Layout',row.get('layout') or 'Default'),('Country',row.get('country') or 'Unavailable'),
                           ('Pit boxes',str(row.get('pitboxes','?'))),('AI lane','Available' if row.get('ai') else 'Unavailable')]
            for index,(label,value) in enumerate(fields):
                rows.append(self._item('catalogue-field:'+str(index),'info',268+(index%2)*480,224+(index//2)*88,
                    456,78,label,value=value,disabled=True))
            rows += [self._item('catalogue-tags','info',268,412 if self.overlay=='cars' else 500,
                         936,164 if self.overlay=='cars' else 76,'Tags',
                         value=' · '.join(row.get('tags',[])) or 'No tags supplied',
                         value_scale=1.3,value_lines=6 if self.overlay=='cars' else 2,disabled=True),
                     self._item('catalogue-origin-source','text',268,588,936,32,row.get('origin_source','Origin unavailable'),disabled=True),
                     self._item('catalogue-limit','text',268,614,936,24,'IDs classify content; installed files are not authenticated. Missing data stays unavailable.',disabled=True),
                     self._favorite_button(row)]
            return rows
        draft=panel['draft']
        for index,(value,label) in enumerate(catalogue.ORIGINS.items()):
            rows.append(self._item('filter-origin:'+value,'button',268+index*240,170,224,46,label,selected=draft['origin']==value))
        rows += [self._item('filter-all','button',268,230,224,42,'Match all selected tags',selected=draft['match']=='all'),
                 self._item('filter-any','button',508,230,224,42,'Match any selected tag',selected=draft['match']=='any'),
                 self._item('filter-favorites','button',748,230,224,42,'Favorites only: '+('On' if panel['favorites_only'] else 'Off'),
                            selected=panel['favorites_only'],disabled=self.favorites_error),
                 self._item('filter-selected','text',988,238,216,28,f"{len(draft['tags'])} tags selected",disabled=True),
                 self._item('tag-search','setting',268,286,936,42,'Search tags',
                            value=panel['query'] or ('Type to filter tags' if self.search_edit_id=='tag-search' else 'A / Enter to search tags'),
                            editable=True,text_input=True,editing=self.search_edit_id=='tag-search')]
        tags=self._catalogue_tags()
        pages=max(1,(len(tags)+7)//8)
        panel['page']=min(panel['page'],pages-1)
        for index,(key,label) in enumerate(tags[panel['page']*8:panel['page']*8+8],panel['page']*8):
            position=index%8
            rows.append(self._item('filter-tag:'+str(index),'button',268+(position%2)*480,344+(position//2)*54,456,44,
                ('[x] ' if key in draft['tags'] else '[ ] ')+label,selected=key in draft['tags']))
        if not tags:rows.append(self._item('tags-empty','text',268,366,936,40,'No matching tags. Untagged content remains available without tag filters.',disabled=True))
        rows += [self._item('filter-prev','button',268,584,144,42,'L2 Previous'),
                 self._item('filter-page','text',432,594,450,28,f'{len(tags)} tags / page {panel["page"]+1} of {pages}',disabled=True),
                 self._item('filter-next','button',1068,584,160,42,'Next R2'),
                 self._item('filter-draft-reset','button',268,642,224,34,'Reset filters'),
                 self._item('filter-apply','button',932,642,288,34,'Apply filters',primary=True)]
        return rows

    def _activate_catalogue(self, identity):
        panel=self.catalogue_panel
        if identity=='catalogue-back':self._close_catalogue_panel()
        elif identity=='favorite-toggle':self._toggle_favorite()
        elif identity=='favorites-recover' and panel['kind']=='favorites-recovery':
            try:
                value=favorites.recover(self.favorites_path)
            except (OSError,ValueError,RuntimeError,TypeError):
                self.message='Could not recover favorites. Original file kept.'
                return
            self._set_favorites(value)
            self.favorites_error=False
            self.favorites_revision+=1
            self._close_catalogue_panel()
            self.message='Original favorites backed up. New empty list ready.'
        elif panel['kind']=='filters':
            draft=panel['draft']
            if identity=='tag-search':self.search_edit_id='tag-search'
            elif identity=='filter-favorites' and not self.favorites_error:panel['favorites_only']=not panel['favorites_only']
            elif identity.startswith('filter-origin:'):
                draft['origin']=identity.split(':',1)[1]
            elif identity in ('filter-all','filter-any'):draft['match']=identity.split('-')[1]
            elif identity.startswith('filter-tag:'):
                key=self._catalogue_tags()[int(identity.split(':')[1])][0]
                if key in draft['tags']:draft['tags'].remove(key)
                else:draft['tags'].append(key)
            elif identity in ('filter-prev','filter-next'):
                pages=max(1,(len(self._catalogue_tags())+7)//8)
                panel['page']=(panel['page']+(-1 if identity.endswith('prev') else 1))%pages
                self.focus_id='filter-tag:'+str(panel['page']*8) if self._catalogue_tags() else 'tag-search'
            elif identity=='filter-draft-reset':
                panel['draft']=catalogue.clean_filter({})
                panel['favorites_only']=False
            elif identity=='filter-apply':
                row=panel['row']
                self.content_filter=catalogue.clean_filter(draft)
                self.favorites_only=panel['favorites_only']
                self._anchor_picker([row.get('id'),row.get('layout','')])
                self._close_catalogue_panel()
                self._remember_picker()

    def _catalogue_action(self, action):
        if action=='back':self._close_catalogue_panel()
        elif action=='accept':self._activate_catalogue(self.focus_id)
        elif action in ('up','down','left','right'):self._move_focus(action)
        elif action in ('page_up','page_down') and self.catalogue_panel['kind']=='filters':
            self._activate_catalogue('filter-prev' if action=='page_up' else 'filter-next')
        elif isinstance(action,tuple) and action[0]=='key_text' and self.searching:
            self.catalogue_panel['query']=(self.catalogue_panel['query']+action[1])[:100]
            self.catalogue_panel['page']=0
        elif action=='erase_key' and self.searching:
            self.catalogue_panel['query']=self.catalogue_panel['query'][:-1]
            self.catalogue_panel['page']=0
        elif isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            for item in reversed(self._catalogue_panel_items()):
                if item.get('disabled') or item['kind']=='text':continue
                if item['x']<=x<item['x']+item['w'] and item['y']<=y<item['y']+item['h']:
                    self.focus_id=item['id']
                    return self._activate_catalogue(item['id'])

    def _overlay_items(self):
        rows=[self._item('close','button',1120,98,110,38,'Back')]
        rogue_rows=self.rogue_overlay_items()
        if rogue_rows is not None:return rows+rogue_rows
        if self.overlay=='session-prompt-full':return rows+self.session_prompt_items()
        if self.overlay=='ai-verdict':
            report=self.ai_report
            return rows+[
                self._item('verdict-full','textarea',268,178,896,400,'Full AI verdict',
                    value=report['text']+('\n\n'+report['app_note'] if report['app_note'] else ''),
                    offset=self.verdict_offset,readonly=True),
                self._item('verdict-up','button',1176,178,52,44,'↑'),
                self._item('verdict-down','button',1176,234,52,44,'↓'),
                self._item('verdict-hint','text',268,598,940,28,'L2 / R2 Scroll / B Back to your event.',disabled=True)]
        if self.overlay=='campaign-info':return rows+self._campaign_details()
        if self.overlay=='proposal-info' and self.synthesis:
            proposal=self.synthesis
            sources=', '.join(key+': '+value for key,value in proposal.get('field_sources',{}).items())
            report=self.ai_report
            previous=report['outcome'] in ('pending','no_proposal','error')
            rows += [self._item('proposal-origin','text',268,178,940,60,
                               ('Previous proposal / ' if previous else '')+proposal.get('generator_label','Local event'),
                               value=('Previous proposal preference status' if previous else 'Preference status')+
                               ' (model report): '+proposal.get('preference_status','unreported'),disabled=True),
                     self._item('proposal-ids','text',268,234,940,24,
                               'Selected IDs: car='+proposal['selection']['car']+' / track='+
                               proposal['selection']['track']+'|'+proposal['selection'].get('layout',''),disabled=True),
                     self._item('proposal-sources','text',268,262,940,126,'Field sources',value=sources or 'Local generation.',disabled=True),
                     self._item('proposal-reason','verdict',268,414,940,124,
                               'AI verdict' if report['origin']=='ai' else 'App status',value=report['text'],
                               app_note=report['app_note'],outcome=report['outcome'],disabled=True)]
            if type(proposal.get('ai_suggested')) is int:
                rows.append(self._item('proposal-difficulty','text',268,388,940,26,
                    'AI level: '+str(proposal['selection']['ai'])+'% / AI suggestion: '+str(proposal['ai_suggested'])+'%',disabled=True))
            refs=proposal.get('references',[])
            if refs:
                rows.append(self._item('proposal-references','text',268,582,940,76,
                    'Previous proposal references' if previous else 'References',
                    value='; '.join(ref['kind']+' '+ref['id']+' / '+ref['field'] for ref in refs),disabled=True))
            return rows
        if self.overlay in ('cars','tracks','events'):
            values=self._filtered_content()
            self.picker_index=max(0,min(self.picker_index,len(values)-1))
            extended=self.overlay in ('cars','tracks')
            rows.append(self._item('search','setting',268,158,580 if extended else 770,42,'Search',
                value=self.query or ('Type to filter' if self.search_edit_id=='search' else 'A / Enter to search'),
                editable=True,text_input=True,editing=self.search_edit_id=='search'))
            if extended:
                active=(self.content_filter['origin']!='all')+len(self.content_filter['tags'])+self.favorites_only
                rows += [self._item('filter-open','button',620,98,150,38,f'Filters ({active})'),
                         self._item('filter-reset','button',784,98,138,38,'Clear filters'),
                         self._item('filter-count','text',936,106,176,28,f'{len(values)} results',disabled=True),
                         self._item('content-info','button',1048,158,180,42,'Car details' if self.overlay=='cars' else 'Track details',disabled=not values),
                         self._item('filter-summary','text',268,207,960,23,self._filter_summary(),disabled=True)]
            if self.overlay=='cars':
                rows.append(self._item('brand-filter','button',860,158,176,42,self.brand_filter or 'All brands'))
            first=self.picker_page*6
            if first>=len(values):
                self.picker_page=0
                first=0
            for index,item in enumerate(values[first:first+6]):
                chosen=dict(car=item.get('id') if self.overlay=='cars' else item.get('car'),
                            track=item.get('id') if self.overlay=='tracks' else item.get('track'),
                            layout=item.get('layout',''))
                if self.overlay=='cars':
                    chosen['skin']=self._picker_livery(item) if self.picker_index==first+index else item['skins'][0]
                kind='track' if self.overlay=='tracks' else 'car'
                rows.append(self._item('pick:'+str(first+index),'catalogue',268+(index%3)*322,(240 if extended else 216)+(index//3)*(170 if extended else 186),
                    306,156 if extended else 174,item['name'],value=item.get('layout') or item.get('brand') or item.get('group',''),
                    subtitle=' · '.join([item.get('power_display','Unavailable'),
                        *item.get('tags',[])]) if self.overlay=='cars' else item.get('layout',''),
                    compact_tags=self.overlay=='cars',
                    favorite=self._is_favorite(item),
                    image=self._image(chosen,kind),image_kind=kind,selected=self.picker_index==first+index))
            if not values:
                rows.append(self._item('empty-catalogue','text',290,300,900,90,
                    'No favorites match these filters.' if self.favorites_only else 'No matching content.',disabled=True))
            if extended:
                rows.append(self._favorite_button(values[self.picker_index] if values else None))
            rows += [self._item('picker-prev','button',268,592,112,42,'L2 Previous'),
                     self._item('picker-next','button',1108,592,112,42,'Next R2')]
            if self.overlay=='cars' and values:
                item=values[self.picker_index]
                skin=self._picker_livery(item)
                editing=self.livery_state is not None
                rows.append(self._item('picker-livery','setting',448 if editing else 396,592,396 if editing else 500,42,'Livery',
                    value=self.livery_names.get((item['id'],skin),skin),select=not editing,editing=editing))
                if editing:rows += self._livery_items()
            else:
                rows.append(self._item('picker-count','text',396,598,500,28,f'{len(values)} entries / page {self.picker_page+1}',disabled=True))
            if values:
                rows.append(self._item('confirm-content','button',932,642,288,34,'Pin for next event' if self.picker_pin else 'Confirm selection',primary=True,disabled=self.livery_state is not None))
        elif self.overlay=='session':
            if self.source=='manual':
                indices=[0,1,2,8]
                if content.MODES[self.selection['mode']][1]==3:
                    indices += [3,4,5]+([10] if self.csp else [])
                elif self.selection['mode']==0:indices += [6]
                for index,position in enumerate(indices):
                    rows.append(self._binding(3,position,268+(index%2)*480,170+(index//2)*94,454,78))
            else:
                rows += self._detail_items()
        elif self.overlay in ('details','history-detail'):
            rows += self._detail_items()
            if self.overlay=='history-detail' and self.history_record:
                rows.append(self._item('repeat','button',988,608,232,48,'Repeat setup',primary=True))
        elif self.overlay=='usage-options':
            rows += [self._usage_binding('car',268,184,940,70),self._usage_binding('track',268,270,940,70),
                     self._item('usage-explanation','text',268,366,940,88,'Only confirmed completed races count.',
                         value='Pins bypass their limit. Car and track cycles restart independently. Reset keeps history and settings.',disabled=True),
                     self._item('ai-reset-usage','button',268,488,940,54,'Reset usage counters / keep history')]
        elif self.overlay=='ai-options':
            rows += [self._item('api-key','setting',268,188,940,70,'API key',value='Configured (hidden)' if self.api_key else 'Not set'),
                     self._item('effort','setting',268,272,940,70,'Reasoning effort',value=self.ai_effort),
                     self._item('ai-contract','text',290,382,900,90,'OpenAI / gpt-6-luna',
                                value='Generate explicitly. No automatic calls or paid retries.',disabled=True)]
        return rows

    def _detail_items(self):
        selected=self.history_record['selection'] if self.overlay=='history-detail' and self.history_record else self.effective_selection()
        car=next((c['name'] for c in self.catalog['cars'] if c['id']==selected.get('car')),selected.get('car',''))
        track=next((t['name'] for t in self.catalog['tracks'] if (t['id'],t['layout'])==(selected.get('track'),selected.get('layout',''))),selected.get('track',''))
        when=selected.get('time_minutes')
        values=[('Car',car),('Circuit / layout',track+' / '+selected.get('layout','')),
                ('Session',content.MODES[selected.get('mode',0)][0]),('Laps / opponents',f"{selected.get('laps','-')} / {selected.get('opponents','-')}"),
                ('AI level',str(selected.get('ai','-'))),('Time / weather',(selected.get('event_time_label','From session') if when is None else f'{when//60:02}:{when%60:02}')+' / '+selected.get('weather','')),
                ('Graphics profile',graphics.LABELS.get(selected.get('graphics_profile'),'')),
                ('Resolution',' x '.join(map(str,selected.get('resolution',[])))),('FPS and frametime','On' if selected.get('hud') else 'Off'),('Track condition','Optimum')]
        rows=[self._item('detail:'+str(index),'setting',268+(index%2)*480,174+(index//2)*76,454,64,label,value=str(value),disabled=True)
              for index,(label,value) in enumerate(values)]
        if self.history_record and self.overlay=='history-detail':
            rows.append(self._item('history-summary','text',268,568,900,40,self.history_record['summary'],disabled=True))
        return rows

    def _navigate(self, view):
        self.cancel_session_audio();self.session_request['editing']=False
        self.message=''
        self.search_edit_id=None
        self.view=view
        self.overlay=None
        source={'drive':'manual','events':'installed','synth':'generated','rogue':'rogue'}.get(view)
        if source:self.select_source(source)
        if view=='events':self.refresh_campaigns()
        if view=='rogue':self.refresh_rogue()
        self.focus_id=('car' if view=='drive' else 'generate' if view=='synth' else
                       'rogue-next' if view=='rogue' and self.rogue_run and self.rogue_run.get('status')=='active' and not self.rogue_run.get('challenge') else
                       'start' if view=='rogue' and not self.rogue_block() else 'rogue-new-local' if view=='rogue' else
                       'campaign-group:'+str(self.campaign_group_page*5) if view=='events' and self.campaign_groups else
                       'nav:events' if view=='events' else 'category:'+self.category if view=='settings' else 'nav:history')
        if view=='rogue' and self.rogue_result_visible():self.focus_id='rogue-result-next'

    def _open(self, overlay, title):
        self.cancel_session_audio();self.session_request['editing']=False
        self.search_edit_id=None
        self.return_focus=self.focus_id
        self.overlay=overlay
        self.overlay_title=title
        self.focus_id='close'

    def _close_overlay(self):
        if self.overlay=='usage-options' and getattr(self,'ai_limits_return',None) is not None:
            self.ai_panel,self.ai_limits_return=self.ai_limits_return,None
            self.overlay='ai-settings';self.overlay_title='AI settings / OpenAI gpt-6-luna'
            self.focus_id='usage-options'
            return
        self.search_edit_id=None
        if self.catalogue_panel is not None:
            self._close_catalogue_panel()
            return
        self._remember_picker()
        self.brand_state=None
        self.livery_state=None
        self.overlay=None
        self.focus_id=self.return_focus
        self.query=''
        self.brand_filter=''
        self.history_record=None

    def _open_picker(self, kind):
        if self.source=='rogue':
            self.message='Rogue locks the car and circuit. Reset the run to choose a new event.'
            return
        if self.source=='installed' and self.view!='synth':
            self._open('details','Event rules')
            return
        self.picker_kind=kind
        self.picker_pin=self.view=='synth' or self.source=='generated'
        self.query=self.brand_filter=''
        self.content_filter=catalogue.clean_filter({})
        self.favorites_only=False
        shown=self.synthesis['selection'] if self.view=='synth' and self.synthesis else self.effective_selection()
        entries=self.catalog['cars' if kind=='car' else 'tracks']
        self.picker_index=next((index for index,item in enumerate(entries) if item['id']==shown.get(kind)
            and (kind=='car' or item['layout']==shown.get('layout',''))),0)
        self.picker_page=self.picker_index//6
        self.picker_skin=shown.get('skin') if kind=='car' else None
        self.picker_car=shown.get('car') if kind=='car' else None
        self.picker_skin_explicit=False
        if kind=='car' and self.picker_pin and self.event_options['pins']['car'] is not None:
            self.picker_car=self.event_options['pins']['car']
            self.picker_index=next((index for index,item in enumerate(entries) if item['id']==self.picker_car),self.picker_index)
            self.picker_page=self.picker_index//6
            if self.picker_car!=shown.get('car'):self.picker_skin=None
            self.picker_skin=self.event_options['pins'].get('skin',self.picker_skin)
            self.picker_skin_explicit='skin' in self.event_options['pins']
        self._open('cars' if kind=='car' else 'tracks','Pin content for next event' if self.picker_pin else 'Choose your '+kind)
        self._restore_picker()
        self.focus_id='pick:'+str(self.picker_index)

    def _picker_livery(self, car):
        if self.livery_state is not None and self.livery_state['car']==car['id']:
            return self.livery_state['skins'][self.livery_state['index']]
        return self.picker_skin if self.picker_car==car['id'] and self.picker_skin in car['skins'] else car['skins'][0]

    def _select_picker_card(self, identity):
        self.picker_index=int(identity.split(':')[1])
        if self.overlay=='cars':
            item=self._filtered_content()[self.picker_index]
            if self.picker_car!=item['id']:self.picker_skin_explicit=False
            self.picker_skin=self._picker_livery(item)
            self.picker_car=item['id']

    def _open_brand(self):
        brands=['']+sorted({row.get('brand','') for row in self.catalog['cars'] if row.get('brand')})
        index=brands.index(self.brand_filter) if self.brand_filter in brands else 0
        self.brand_state=dict(brands=brands,index=index,page=index//6)
        self.focus_id='brand:'+str(index)

    def _brand_items(self):
        state=self.brand_state
        rows=[]
        first=state['page']*6
        for index,brand in enumerate(state['brands'][first:first+6],first):
            rows.append(self._item('brand:'+str(index),'button',918,210+(index-first)*46,304,42,
                brand or 'All brands',selected=brand==self.brand_filter))
        footer_y=210+min(6,len(state['brands'])-first)*46+6
        if len(state['brands'])>6:
            rows += [self._item('brand-prev','button',918,footer_y,146,36,'L2 Previous'),
                     self._item('brand-next','button',1076,footer_y,146,36,'Next R2')]
            footer_y+=48
        rows.append(self._item('brand-back','button',918,footer_y,304,36,'Cancel'))
        return rows

    def _close_brand(self, confirm=False):
        state=self.brand_state
        if confirm:
            self.brand_filter=state['brands'][state['index']]
            self.picker_page=self.picker_index=0
        self.brand_state=None
        self.focus_id='brand-filter'

    def _brand_activate(self, identity):
        state=self.brand_state
        if identity=='brand-back':self._close_brand()
        elif identity.startswith('brand:'):
            state['index']=int(identity.split(':')[1])
            self._close_brand(True)
        elif identity in ('brand-prev','brand-next'):
            pages=max(1,(len(state['brands'])+5)//6)
            state['page']=(state['page']+(-1 if identity.endswith('prev') else 1))%pages
            state['index']=state['page']*6
            self.focus_id='brand:'+str(state['index'])

    def _brand_action(self, action):
        state=self.brand_state
        if action=='back':self._close_brand()
        elif action=='accept':self._brand_activate(self.focus_id)
        elif action in ('up','down','left','right'):
            state['index']=(state['index']+(-1 if action in ('up','left') else 1))%len(state['brands'])
            state['page']=state['index']//6
            self.focus_id='brand:'+str(state['index'])
        elif action in ('page_up','page_down'):
            self._brand_activate('brand-prev' if action=='page_up' else 'brand-next')
        elif isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            for item in self._brand_items():
                if item['x']<=x<item['x']+item['w'] and item['y']<=y<item['y']+item['h']:
                    return self._brand_activate(item['id'])
            self._close_brand()

    def _open_livery(self):
        values=self._filtered_content()
        if self.overlay!='cars' or not values:return
        before=dict(car=self.picker_car,skin=self.picker_skin,explicit=self.picker_skin_explicit)
        self._select_picker_card('pick:'+str(self.picker_index))
        car=values[self.picker_index]
        for skin in car['skins']:
            key=(car['id'],skin)
            if key not in self.livery_names:
                info=content.metadata(self.game/'content/cars'/car['id']/'skins'/skin/'ui_skin.json') if self.game else {}
                self.livery_names[key]=content.label(info.get('skinname'),skin)
        index=car['skins'].index(self._picker_livery(car))
        self.livery_state=dict(car=car['id'],name=car['name'],skins=list(car['skins']),index=index,
                               mode='inline',before=before)
        self.focus_id='picker-livery'

    def _livery_items(self):
        return [self._item('livery-less','button',396,592,44,42,'<'),
                self._item('livery-more','button',852,592,44,42,'>')]

    def _close_livery(self, confirm=False):
        state=self.livery_state
        if confirm:
            self.picker_car=state['car']
            self.picker_skin=state['skins'][state['index']]
            self.picker_skin_explicit=True
        else:
            before=state['before']
            self.picker_car,self.picker_skin,self.picker_skin_explicit=before['car'],before['skin'],before['explicit']
        self.livery_state=None
        self.focus_id='picker-livery'
        if confirm:self._image(dict(car=state['car'],skin=self.picker_skin),'car')

    def _adjust_livery(self, delta):
        state=self.livery_state
        state['index']=(state['index']+delta)%len(state['skins'])
        self.focus_id='picker-livery'

    def _livery_action(self, action):
        if action=='back':self._close_livery()
        elif action=='accept':self._close_livery(True)
        elif action in ('left','right'):self._adjust_livery(-1 if action=='left' else 1)
        elif isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            for item in self._livery_items():
                if item['x']<=x<item['x']+item['w'] and item['y']<=y<item['y']+item['h']:
                    return self._adjust_livery(-1 if item['id']=='livery-less' else 1)
            field=next(item for item in self._overlay_items() if item['id']=='picker-livery')
            if field['x']<=x<field['x']+field['w'] and field['y']<=y<field['y']+field['h']:
                self._close_livery(True)
            elif 1120<=x<1230 and 98<=y<136:
                self._close_livery()

    def _editing_profile(self):
        if not self.editing or not self.editing['id'].startswith('edit:4:'):
            return False
        return self.graphics_keys[int(self.editing['id'].split(':')[2])]=='graphics_profile'

    def _begin_edit(self, identity):
        """Um Menu sem destinos de gravação fornece as mesmas regras no rascunho."""
        installed=(identity in tuple('edit:3:'+str(i) for i in (0,1,2,3,4,5,6,8))
                   and self.source=='installed' and self.installed_selection is not None)
        selected=self.installed_selection if installed else self.selection
        draft=Menu(self.catalog,deepcopy(selected),csp=self.csp,game=self.game,
                   catalog_cache=self.catalog_cache,pp_filter_cache=self.pp_filters)
        draft.event_options=deepcopy(self.event_options)
        draft.synthesis=deepcopy(self.synthesis)
        draft.pending_event_base=deepcopy(self.pending_event_base)
        draft.ai_effort=self.ai_effort
        draft.ai_usage=deepcopy(self.ai_usage)
        self.editing=dict(id=identity,menu=draft,before=deepcopy(draft.selection),installed=installed)
        self.focus_id=identity
        self.message='Editing. Use arrows to adjust, A / Enter to confirm, B / Esc to cancel.'

    def _adjust_edit(self, delta):
        edit=self.editing
        draft=edit['menu']
        identity=edit['id']
        if identity.startswith('edit:'):
            _,tab,index=identity.split(':')
            draft.tab=int(tab)
            draft.indices[draft.tab]=int(index)
            draft.change(delta)
        elif identity.startswith('event:'):
            draft.change_event_option(int(identity.split(':')[1]),delta)
        elif identity=='effort':draft.change_effort(delta)
        elif identity.startswith('usage:'):draft.change_ai_limit(identity.split(':')[1],delta)
        self.message=('Previewing profile. Confirm replaces custom graphics; B cancels.'
                      if self._editing_profile() else draft.message)

    def _finish_edit(self, confirm):
        edit=self.editing
        if edit is None:return
        identity=edit['id']
        draft=edit['menu']
        profile_edit=self._editing_profile()
        profile_changed=False
        if confirm:
            if identity.startswith('edit:'):
                target=self.installed_selection if edit['installed'] else self.selection
                changed={key:deepcopy(value) for key,value in draft.selection.items() if edit['before'].get(key)!=value}
                profile_changed=profile_edit and bool(changed)
                previous=deepcopy(target)
                previous_smart_shadows=self.selection['smart_shadows']
                previous_shadow=self.selection['shadow_distance_m']
                previous_hud=self.selection['hud']
                previous_haptics={key:self.selection[key] for key in driving_haptics.DEFAULTS}
                target.update(changed)
                try:
                    for key in driving_haptics.DEFAULTS:
                        if key in changed:self.selection[key]=changed[key]
                    if 'smart_shadows' in changed:
                        self.selection['smart_shadows']=changed['smart_shadows']
                    if 'shadow_distance_m' in changed:
                        self.selection['shadow_distance_m']=changed['shadow_distance_m']
                    if 'hud' in changed:
                        # O medidor continua global, inclusive ao editar um evento instalado.
                        if edit['installed']:self.selection['hud']=changed['hud']
                        self.sync_event_hud()
                    if edit['installed'] and changed:self._remember_source()
                except (OSError,ValueError,RuntimeError):
                    target.clear()
                    target.update(previous)
                    self.selection['smart_shadows']=previous_smart_shadows
                    self.selection['shadow_distance_m']=previous_shadow
                    self.selection['hud']=previous_hud
                    self.selection.update(previous_haptics)
                    raise
            elif identity.startswith('usage:'):
                if draft.ai_usage is not None and self.ai_usage is not None and draft.ai_usage['limits']!=self.ai_usage['limits']:
                    if not self.set_ai_limits(draft.ai_usage['limits']):return
            elif identity=='event:9':
                if self.synthesis is not None and draft.synthesis is not None:
                    minutes=draft.synthesis['selection']['time_minutes']
                    if self.synthesis['selection']['time_minutes']!=minutes:
                        self.set_event_time(minutes)
                        if self.synthesis['selection']['time_minutes']!=minutes:return
            elif identity.startswith('event:') and self.event_options!=draft.event_options:
                self.set_event_options(deepcopy(draft.event_options))
                if self.event_options!=draft.event_options:return
            elif identity=='effort' and self.ai_effort!=draft.ai_effort:
                delta=ai_events.EFFORTS.index(draft.ai_effort)-ai_events.EFFORTS.index(self.ai_effort)
                self.change_effort(delta)
                if self.ai_effort!=draft.ai_effort:return
        self.editing=None
        self.focus_id=identity
        if profile_edit:
            self.message=(graphics.LABELS.get(self.selection['graphics_profile'],'Graphics profile')+
                          ' applied. Graphics reset to profile defaults.' if confirm and profile_changed else
                          'Profile unchanged. Current graphics kept.' if confirm else
                          'Profile change cancelled. Current graphics kept.')
        else:
            self.message='Changes confirmed. Press X / Start when ready.' if confirm else 'Edit cancelled. Previous value kept.'

    def _editing_action(self, action):
        if action=='back':self._finish_edit(False)
        elif action=='accept':self._finish_edit(True)
        elif action in ('up','down','left','right'):
            self._adjust_edit(1 if action in ('up','right') else -1)
        elif isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            for item in self.ui_items():
                if not (item['x']<=x<item['x']+item['w'] and item['y']<=y<item['y']+item['h']):continue
                if item['id']=='edit-confirm':return self._finish_edit(True)
                if item['id']=='edit-cancel':return self._finish_edit(False)
                if item['id']==self.editing['id']:
                    left=item['x']+(max(120,int(item['w']*.56)) if item['kind']=='setting' else 0)
                    if left<=x<left+35:self._adjust_edit(-1)
                    elif x>=item['x']+item['w']-35:self._adjust_edit(1)
                    return
        elif action=='launch':
            self.message='Confirm or cancel the current edit before starting a race.'

    def _confirm_content(self):
        values=self._filtered_content()
        if not values:return
        item=values[min(self.picker_index,len(values)-1)]
        if self.overlay=='events':
            self.installed_selection=self._installed_event(item)
            self.select_source('installed')
        elif self.picker_pin:
            settings=deepcopy(self.event_options)
            settings['pins'][self.picker_kind]=item['id'] if self.picker_kind=='car' else [item['id'],item['layout']]
            if self.picker_kind=='car':
                skin=self._picker_livery(item)
                if self.picker_skin_explicit or skin!=item['skins'][0]:settings['pins']['skin']=skin
                else:settings['pins'].pop('skin',None)
            self.set_event_options(settings)
            if self.event_options!=settings:return
            self.view='synth'
            self.message=('Car/livery pinned. Generate again to use it.' if self.picker_kind=='car' else
                          'Track pinned. Generate again to use it.')
        elif self.picker_kind=='car':
            self.selection.update(car=item['id'],skin=self._picker_livery(item),event='')
            self.select_source('manual')
        else:
            self.selection.update(track=item['id'],layout=item['layout'],event='')
            self.select_source('manual')
        self._close_overlay()
        if not self.picker_pin:self.message='Selection confirmed. Press X / Start when ready.'

    def _installed_event(self, item):
        chosen=dict(self.selection,event=item['id'],car=item['car'],track=item['track'],layout=item['layout'],time_minutes=None)
        chosen.pop('session_date',None)
        car=next(row for row in self.catalog['cars'] if row['id']==item['car'])
        chosen['skin']=car['skins'][0]
        if self.game is not None:
            event=content.read_ini(self.game/item['id'])
            race=event['RACE']
            sessions=[event[name] for name in event.sections() if name.startswith('SESSION_')]
            session=next((row for row in reversed(sessions) if row.get('TYPE','').strip()=='3'),sessions[-1])
            chosen.update(opponents=max(0,int(race.get('CARS','1'))-1),ai=int(float(race.get('AI_LEVEL',chosen['ai']))),
                          laps=int(session.get('LAPS',chosen['laps'])),minutes=int(float(session.get('DURATION_MINUTES',chosen['minutes']))))
            mode=int(session.get('TYPE','3'))
            chosen['mode']=next((i for i,row in enumerate(content.MODES) if row[1]==mode),0)
            chosen['event_mode_name']={1:'Practice',2:'Qualifying',3:'Race',4:'Hotlap',5:'Time Attack',6:'Drift',7:'Drag'}.get(mode,'Event')
            chosen['skin']=event.get('CAR_0','SKIN',fallback=race.get('SKIN',chosen['skin'])) or chosen['skin']
            chosen['weather']=event.get('WEATHER','NAME',fallback='3_clear')
            try:
                native_minutes=round(13*60+float(event.get('LIGHTING','SUN_ANGLE',fallback='-48'))*3.75)
                chosen['event_time_label']=f'{native_minutes//60:02}:{native_minutes%60:02} (event)'
            except ValueError:chosen['event_time_label']='From event'
        return chosen

    def _repeat(self):
        record=self.history_record
        if not record:return
        selected=session_settings.restore(record['selection'],self.selection)
        if not any(car['id']==selected.get('car') and selected.get('skin') in car['skins'] for car in self.catalog['cars']):
            raise ValueError('The recorded car or livery is not installed.')
        track=next((track for track in self.catalog['tracks'] if (track['id'],track['layout'])==(selected.get('track'),selected.get('layout',''))),None)
        if track is None:raise ValueError('The recorded circuit/layout is not installed.')
        if selected.get('event') and not any(row['id']==selected['event'] and row.get('available',True) for row in self.catalog['events']):
            raise ValueError('The recorded installed event is no longer available.')
        normalized=Menu(self.catalog,selected,csp=self.csp,game=self.game,
                        catalog_cache=self.catalog_cache,pp_filter_cache=self.pp_filters)
        selected=normalized.selection
        if not selected.get('event') and content.MODES[selected['mode']][1]==3:
            content.integer(selected['opponents'],0,min(47,track['pitboxes']-1),'Opponents')
            if selected['opponents'] and not track['ai']:raise ValueError('This circuit has no AI lane.')
        proposal=deepcopy(record.get('proposal'))
        if proposal:
            event_synthetizer.validate(self.game,proposal,**self.event_catalog_args())
            for key in ('base','selection'):
                proposal[key]=session_settings.restore(proposal[key],self.selection)
            proposal=self.event_with_current_hud(proposal)
            settings=event_synthetizer.options(proposal['selection'],dict(pins=event_synthetizer.pins(proposal.get('pins')),
                laps=proposal['selection']['laps'],ai=proposal['selection']['ai'],opponents=proposal['selection']['opponents']))
            event_synthetizer.save_state(self.synthesis_store,proposal,self.event_options_file,settings)
            self.synthesis=proposal
            self.event_options=settings
            self.select_source('generated')
        elif selected.get('event'):
            item=next(row for row in self.catalog['events'] if row['id']==selected['event'])
            self.installed_selection=self._installed_event(item)
            self.select_source('installed')
        else:
            self.selection=selected
            self.select_source('manual')
        self._close_overlay()
        self._navigate({'manual':'drive','generated':'synth','installed':'events'}[self.source])
        if self.source=='installed':self._anchor_campaign(selected['event'])
        self.focus_id='start'
        self.message='Recorded setup restored. Starting remains a separate action.'

    def generate_event(self):
        self.cancel_session_audio()
        previous=self.synthesis
        super().generate_event()
        if self.synthesis is not previous and self.synthesis is not None:
            if self.view=='synth':self.source='generated'
            self._remember_source()

    def generate_ai_event(self,instruction=None):
        if self.rogue_pending is not None:
            self.message='Wait for the Rogue request or cancel it before generating with AI.'
            return False
        if self.session_audio_busy:
            self.message='Finish transcription and review the session prompt before generating.'
            return False
        self.session_request['editing']=False
        return super().generate_ai_event(instruction=instruction)

    def poll_ai(self):
        self.poll_rogue()
        if self.editing is not None or self.livery_state is not None or self.brand_state is not None or self.catalogue_panel is not None:return
        previous=self.synthesis
        super().poll_ai()
        if self.synthesis is not previous and self.synthesis is not None:
            if self.view=='synth':self.source='generated'
            else:
                adjustments=self.message if self.message.startswith('AI with local adjustments:') else ''
                self.message='AI event ready in Event Synthetizer.'+(' '+adjustments if adjustments else '')
            self._remember_source()

    def launch_selection(self):
        if self.source=='rogue':return self.rogue_launch_selection()
        if self.source=='generated':
            old=self.tab
            self.tab=6
            try:return super().launch_selection()
            finally:self.tab=old
        if self.source=='installed':
            if self.installed_selection is None:raise ValueError('Select an installed event first.')
            error=self._campaign_block()
            if error:raise ValueError(error)
            return session_settings.restore(self.installed_selection,self.selection)
        return dict(self.selection)

    def _activate(self, identity, delta=1):
        if self.ai_panel is not None:return self.ai_settings_activate(identity)
        if self.rogue_activate(identity):return
        if self._campaign_activate(identity):return
        if self.catalogue_panel is not None:return self._activate_catalogue(identity)
        if identity=='filter-open':return self._open_catalogue_panel('filters')
        if identity=='content-info':return self._open_catalogue_panel('detail')
        if identity=='favorite-toggle':return self._toggle_favorite()
        if identity=='filter-reset':
            values=self._filtered_content()
            row=values[self.picker_index] if values else {}
            self.query=self.brand_filter=''
            self.content_filter=catalogue.clean_filter({})
            self.favorites_only=False
            self._anchor_picker([row.get('id'),row.get('layout','')])
            self._remember_picker()
            self.focus_id='filter-open'
            return
        if identity.startswith(('edit:','event:')) or identity=='effort':
            return self._begin_edit(identity)
        if identity.startswith('nav:'):self._navigate(identity.split(':',1)[1])
        elif identity=='exit':
            if not self.session_running:return super().action('request_quit')
        elif identity=='start':
            if self.session_audio_busy or self.session_request['editing']:return
            if self.session_running or self.editing is not None:return
            if self.source=='rogue' and self.rogue_block():
                self.message=self.rogue_block()
                return
            if self.source=='generated' and self.synthesis is None:
                self.message='Generate an event first.'
                return
            if self.source=='installed' and self._campaign_block():
                self.message=self._campaign_block()
                return
            return 'launch'
        elif identity in ('haptics_left','haptics_right'):
            if not self.session_running:return identity
        elif identity in ('car','track'):self._open_picker(identity)
        elif identity in ('details','session'):self._open(identity,'Session details' if identity=='details' else 'Conditions & session')
        elif identity=='close':self._close_overlay()
        elif identity.startswith('category:'):
            self.category=identity.split(':',1)[1]
            self.settings_page=0
        elif identity.startswith('session-') and self.activate_session_prompt(identity,delta):return
        elif identity=='generate':self.generate_event()
        elif identity=='generate-ai':self.generate_ai_event()
        elif identity=='cancel-ai-generation' and self.ai_pending is not None:
            self.cancel_pending_ai('AI request cancelled. Previous proposal kept.')
            self.message='AI request cancelled. An already sent request may be charged.'
            self.focus_id='generate-ai'
        elif identity in ('pin-car','pin-track'):self.change_event_option(4 if identity=='pin-car' else 5,delta)
        elif identity in ('ai-options','ai-adjust-request'):self.open_ai_settings()
        elif identity=='usage-options':self.open_ai_usage()
        elif identity=='ai-reset-usage':self.reset_ai_usage()
        elif identity=='ai-verdict':
            self.verdict_offset=0
            self._open('ai-verdict','AI verdict / full text' if self.ai_report['origin']=='ai' else 'App status / full text')
            self.focus_id='verdict-full'
        elif identity in ('verdict-up','verdict-down'):
            from .ai_settings_ui import lines
            report=self.ai_report
            count=len(lines(report['text']+'\n\n'+report['app_note']))
            self.verdict_offset=max(0,min(max(0,count-15),self.verdict_offset+(-15 if identity=='verdict-up' else 15)))
        elif identity.startswith('usage:'):self._begin_edit(identity)
        elif identity=='proposal-info':self._open('proposal-info','Generated event details')
        elif identity=='api-key':self.open_key()
        elif identity=='picker-livery':self._open_livery()
        elif identity.startswith('pick:'):
            self._select_picker_card(identity)
        elif identity=='confirm-content':self._confirm_content()
        elif identity in ('picker-prev','picker-next'):
            pages=max(1,(len(self._filtered_content())+5)//6)
            self.picker_page=(self.picker_page+(-1 if identity.endswith('prev') else 1))%pages
            self.picker_index=self.picker_page*6
            self.focus_id='pick:'+str(self.picker_index)
        elif identity=='brand-filter':self._open_brand()
        elif identity=='search':self.search_edit_id='search'
        elif identity.startswith('history:'):
            self.history_record=self.history_rows[int(identity.split(':')[1])]
            self._open('history-detail','A previous drive')
        elif identity=='repeat':self._repeat()
        elif identity in ('history-prev','history-next'):
            pages=max(1,(len(self.history_rows)+4)//5)
            self.history_page=(self.history_page+(-1 if identity.endswith('prev') else 1))%pages
        elif identity in ('settings-prev','settings-next'):
            count=len(self._setting_groups()[self.category][0][1])
            self.settings_page=(getattr(self,'settings_page',0)+(-1 if identity.endswith('prev') else 1))%max(1,(count+5)//6)

    def _move_focus(self, direction):
        self.search_edit_id=None
        candidates=[item for item in self.ui_items() if not item.get('disabled') and item['kind']!='text'
                    and (not self.overlay or item['id'] not in ('start','details','exit') and not item['id'].startswith('nav:'))]
        current=next((item for item in candidates if item['id']==self.focus_id),None)
        if current is None:
            if candidates:self.focus_id=candidates[0]['id']
            return
        cx,cy=current['x']+current['w']/2,current['y']+current['h']/2
        possible=[]
        for item in candidates:
            dx=item['x']+item['w']/2-cx
            dy=item['y']+item['h']/2-cy
            distance={'left':-dx,'right':dx,'up':-dy,'down':dy}[direction]
            if distance>2:
                cross=abs(dy if direction in ('left','right') else dx)
                possible.append((distance+cross*3,item['id']))
        if possible:
            self.focus_id=min(possible)[1]
            if self.overlay in ('cars','tracks','events') and self.focus_id.startswith('pick:'):
                self._select_picker_card(self.focus_id)

    def action(self, action):
        if self.session_running and action in ('quit','request_quit'):
            self.message='Session running. Close the game before exiting the launcher.'
            return
        if action=='quit':return 'quit'
        if self.key_dialog or self.quit_confirmation or action=='request_quit':return super().action(action)
        if self.ai_panel is not None:
            return self.ai_settings_action(action)
        if self.session_prompt_action(action):return
        if self.rogue_result_action(action):return
        if self.rogue_album_action(action):return
        if self.search_edit_id is not None and self.searching and action in ('accept','back'):
            self.search_edit_id=None
            self.message='Search text kept. A / Enter edits again; arrows browse.'
            return
        if (isinstance(action,tuple) and action[0]=='click') or action in ('page_up','page_down','tab_next','tab_prev'):
            self.search_edit_id=None
        if self.catalogue_panel is not None:
            try:return self._catalogue_action(action)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError,IndexError) as error:
                self.message='Content browser unchanged. '+str(error)
                return
        if self.brand_state is not None:
            try:return self._brand_action(action)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError,IndexError) as error:
                self.message='Brand filter unchanged. '+str(error)
                return
        if self.livery_state is not None:
            try:return self._livery_action(action)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError,IndexError) as error:
                self.message='Livery unchanged. '+str(error)
                return
        if self.editing is not None:
            try:return self._editing_action(action)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError,IndexError) as error:
                self.message='Could not apply the edit. '+str(error)
                return
        if isinstance(action,tuple) and action[0]=='key_text':
            if self.searching:
                self.query=(self.query+action[1])[:100]
                self.picker_page=self.picker_index=0
            return
        if action=='erase_key' and self.searching:
            self.query=self.query[:-1]
            self.picker_page=self.picker_index=0
            return
        if action=='back':
            if self.overlay:self._close_overlay()
            elif self.view=='events':self.focus_id='campaign-group:'+str(self.campaign_group_page*5) if self.campaign_groups else 'nav:events'
            elif self.view!='drive':self.focus_id='nav:'+self.view
            else:self.message='Use Exit, View or F10 to close the menu.'
            return
        if action in ('tab_next','tab_prev'):
            if not self.overlay:self._navigate(VIEWS[(VIEWS.index(self.view)+(1 if action=='tab_next' else -1))%len(VIEWS)])
            return
        if action=='launch':
            if self.overlay or self.searching:return
            return self._activate('start')
        if action=='skin':
            if self.searching:
                return
            if self.overlay=='cars':
                self._open_livery()
            elif not self.overlay and self.source=='manual':
                skins=self.car()['skins']
                self.selection['skin']=skins[(skins.index(self.selection['skin'])+1)%len(skins)]
            return
        try:
            if isinstance(action,tuple) and action[0]=='click':
                _,x,y=action
                for item in reversed(self.ui_items()):
                    if item.get('disabled') or item['kind']=='text':continue
                    if self.overlay and (item['id'].startswith('nav:') or item['id'] in ('exit','start','details')):continue
                    if item['x']<=x<item['x']+item['w'] and item['y']<=y<item['y']+item['h']:
                        self.focus_id=item['id']
                        return self._activate(item['id'])
            elif action=='accept':
                if self.overlay in ('cars','tracks','events') and self.focus_id.startswith('pick:'):
                    self._select_picker_card(self.focus_id)
                    return self._confirm_content()
                return self._activate(self.focus_id)
            elif action in ('up','down','left','right'):self._move_focus(action)
            elif action in ('page_up','page_down'):
                if self.overlay=='ai-verdict':
                    return self._activate('verdict-up' if action=='page_up' else 'verdict-down')
                suffix='prev' if action=='page_up' else 'next'
                pages={prefix+'-'+suffix for prefix in ('picker','history','settings','campaign')}
                identity=next((item['id'] for item in self.ui_items()
                               if item['id'] in pages and not item.get('disabled')),None)
                if identity:self._activate(identity)
        except (OSError,ValueError,RuntimeError,KeyError,TypeError,IndexError) as error:
            self.message='Selection unchanged. '+str(error)

    def draw(self, window):
        from .ui_render import draw
        draw(self,window)
