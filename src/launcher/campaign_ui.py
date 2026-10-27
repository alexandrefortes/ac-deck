"""Events: grupos nativos, seleção e progresso separado de Drive e Synth."""
from . import campaigns


class CampaignUI:
    def init_campaigns(self, cfg):
        self.campaign_cfg = cfg
        self.campaign_group = None
        self.campaign_inspected = None
        self.campaign_group_page = 0
        self.campaign_event_page = 0
        self.campaign_progress = campaigns.load(cfg)
        if self.installed_selection is None and self.selection.get('event'):
            self.installed_selection = dict(self.selection)
        self.selection['event'] = ''
        self.refresh_campaigns()
        if self.installed_selection:
            event = next((e for e in self.catalog['events'] if e['id'] == self.installed_selection.get('event')), None)
            if event and event.get('available',True):
                self.installed_selection=self._installed_event(event)
                self.campaign_group = event.get('group_id', event.get('group', 'Events'))
                self._anchor_campaign(event['id'])
        self.view = {'manual': 'drive', 'generated': 'synth', 'installed': 'events'}[self.source]
        self.focus_id = 'car' if self.view == 'drive' else 'generate' if self.view == 'synth' else 'nav:events'

    def refresh_campaigns(self):
        self.campaign_progress = campaigns.load(self.campaign_cfg)
        self.campaign_groups = campaigns.groups(self.catalog, self.campaign_progress)
        if not any(g['id'] == self.campaign_group for g in self.campaign_groups):
            self.campaign_group = self.campaign_groups[0]['id'] if self.campaign_groups else None
        self.campaign_group_page = min(self.campaign_group_page, max(0, (len(self.campaign_groups)-1)//5))
        self.campaign_event_page = min(self.campaign_event_page, max(0, (len(self.campaign_events())-1)//5))

        selected = self._selected_campaign()
        if self.installed_selection and (selected is None or not selected.get('available',True)):
            self.campaign_inspected = selected['id'] if selected else None
            self.installed_selection = None
            self.message = 'The selected event is unavailable. Check Events for required content.'
            self._remember_source()

    def replace_catalog(self, catalog):
        super().replace_catalog(catalog)
        if hasattr(self,'campaign_cfg'):self.refresh_campaigns()

    def campaign_events(self):
        return next((g['events'] for g in self.campaign_groups if g['id'] == self.campaign_group), [])

    def _anchor_campaign(self, event_id):
        group_index = next((i for i, g in enumerate(self.campaign_groups) if any(e['id'] == event_id for e in g['events'])), None)
        if group_index is not None:
            group = self.campaign_groups[group_index]
            self.campaign_group = group['id']
            self.campaign_group_page = group_index//5
            self.campaign_event_page = next(i for i, e in enumerate(group['events']) if e['id'] == event_id)//5

    def _selected_campaign(self):
        identity = (self.installed_selection or {}).get('event')
        return next((e for e in self.catalog['events'] if e['id'] == identity), None)

    def _campaign_info_event(self):
        return next((e for e in self.catalog['events'] if e['id']==self.campaign_inspected),self._selected_campaign())

    def _campaign_block(self):
        event = self._selected_campaign()
        if event is None:return 'Select an event first.'
        return campaigns.playable(event, self.campaign_progress, self.catalog)

    def _campaign_items(self):
        rows = []
        groups = self.campaign_groups
        current = next((g for g in groups if g['id'] == self.campaign_group), None)
        if not groups:
            return [self._item('campaign-empty','text',268,224,940,118,'No installed events.',
                value='Install a campaign, then reopen the launcher.',disabled=True)]
        rows += [self._item('groups-label','text',248,165,288,22,'SERIES / GROUPS'+(f' / {self.campaign_group_page+1} of {(len(groups)+4)//5}' if len(groups)>5 else ''),disabled=True),
                 self._item('events-label','text',556,165,692,22,current['name'],disabled=True)]
        for index, group in enumerate(groups[self.campaign_group_page*5:self.campaign_group_page*5+5], self.campaign_group_page*5):
            series = group['series']
            summary = ('Completed' if group['completed'] else 'Locked' if group['locked'] else 'In progress' if group['completed_events'] else 'Not started')
            if self.campaign_progress['status']=='unavailable' and series:summary='Progress unavailable'
            if series:
                summary += f" / {group['completed_events']}/{len(group['events'])} events"
            else:summary = 'Steam achievements / not read'
            rows.append(self._item('campaign-group:'+str(index),'campaign-group',248,194+(index%5)*76,288,66,
                (series.get('code','')+' / ' if series and series.get('code') else '')+group['name'],
                value=summary,selected=group['id']==self.campaign_group,completed=group['completed']))
        entries = self.campaign_events()
        for index, event in enumerate(entries[self.campaign_event_page*5:self.campaign_event_page*5+5], self.campaign_event_page*5):
            status = campaigns.event_status(event, self.campaign_progress)
            block = campaigns.playable(event, self.campaign_progress, self.catalog)
            car = next((c['name'] for c in self.catalog['cars'] if c['id']==event['car']),event['car'])
            track = next((t['name'] for t in self.catalog['tracks'] if (t['id'],t['layout'])==(event['track'],event.get('layout',''))),event['track'])
            rows.append(self._item('campaign-event:'+str(index),'campaign-event',556,194+(index%5)*76,692,66,
                event['name'],value=block or status['label'],subtitle=car+' / '+track,
                selected=bool(self.installed_selection and self.installed_selection.get('event')==event['id']),
                completed=status['completed'],locked=bool(block)))
        if len(groups)>5:
            rows += [self._item('groups-prev','button',248,582,136,36,'Prev groups'),
                     self._item('groups-next','button',400,582,136,36,'Next groups')]
        rows.append(self._item('campaign-pages','text',556,588,420,28,
            f"{len(entries)} events / page {self.campaign_event_page+1} of {max(1,(len(entries)+4)//5)}",disabled=True))
        if len(entries)>5:
            rows += [self._item('campaign-prev','button',982,582,126,36,'L2 Previous'),
                     self._item('campaign-next','button',1122,582,126,36,'Next R2')]
        selected = self._selected_campaign()
        note = 'Select an event. X / Start begins the selected session.'
        if self.campaign_progress['status']=='unavailable':note=self.campaign_progress.get('error','Progress unavailable')
        elif current and current['locked']:note='Required series: '+', '.join(current['series']['requires'])
        elif selected:note='Selected: '+selected['name']
        elif self._campaign_info_event():note=campaigns.playable(self._campaign_info_event(),self.campaign_progress,self.catalog) or note
        rows += [self._item('campaign-note','text',248,638,740,30,note,disabled=True),
                 self._item('campaign-info','button',1010,634,238,40,'Event details',disabled=self._campaign_info_event() is None)]
        return rows

    def _campaign_details(self):
        event = self._campaign_info_event()
        if event is None:return []
        series = event.get('series')
        status = campaigns.event_status(event, self.campaign_progress)
        description = event.get('description') or (series or {}).get('description') or 'No description supplied.'
        result = status['label']
        if series and series['championship']:
            section=self.campaign_progress['sections'].get(series['id'].casefold(),{})
            result+=' / '+section.get('POINTS','0')+' championship points'
        def goal(condition):
            value=condition['objective'];kind=condition['type']
            if kind=='POSITION':return 'P'+str(value)+' or better'
            if kind=='TIME':return f'{value//60000}:{(value%60000)/1000:06.3f} or faster'
            if kind=='POINTS':return str(value)+' points or more'
            return 'Unsupported goal'
        rule = ('Native championship / points by place: '+', '.join(map(str,series['points'])) if series and series['championship'] else
                ' / '.join(campaigns.MEDALS.get(i+1,'')+': '+goal(c)
                           for i,c in enumerate(event.get('conditions',[]))))
        note = campaigns.playable(event,self.campaign_progress,self.catalog) or ('Replaying a completed round keeps its recorded points.' if series and series['championship'] and status['completed'] else
                                        'The game event defines its car, track and session rules.')
        return [self._item('campaign-name','text',268,174,940,60,event['name'],value=event.get('group',''),disabled=True),
                self._item('campaign-result','text',268,258,940,62,result,value=rule or 'No supported medal rule supplied.',disabled=True),
                self._item('campaign-description','text',268,348,940,128,description,disabled=True),
                self._item('campaign-start-note','text',268,528,940,86,note,value='Return with B / Back. Start race or X / Start remains a separate action.',disabled=True)]

    def _campaign_activate(self, identity):
        if identity.startswith('campaign-group:'):
            group = self.campaign_groups[int(identity.split(':')[1])]
            if self.campaign_group != group['id']:
                self.installed_selection = None
                self.campaign_inspected = None
                self._remember_source()
            self.campaign_group = group['id']
            self.campaign_event_page = 0
            self.focus_id = 'campaign-event:0' if group['events'] else identity
            return True
        if identity.startswith('campaign-event:'):
            event = self.campaign_events()[int(identity.split(':')[1])]
            self.campaign_inspected=event['id']
            error = campaigns.playable(event, self.campaign_progress, self.catalog)
            if error:
                self.installed_selection=None
                self._remember_source()
                self.message = error+'.'
                return True
            self.installed_selection = self._installed_event(event)
            self.select_source('installed')
            self.message = campaigns.event_status(event,self.campaign_progress)['label']+'. Press X / Start when ready.'
            return True
        if identity in ('groups-prev','groups-next'):
            pages=max(1,(len(self.campaign_groups)+4)//5)
            self.campaign_group_page=(self.campaign_group_page+(-1 if identity.endswith('prev') else 1))%pages
            self.focus_id='campaign-group:'+str(self.campaign_group_page*5)
            return True
        if identity in ('campaign-prev','campaign-next'):
            pages=max(1,(len(self.campaign_events())+4)//5)
            self.campaign_event_page=(self.campaign_event_page+(-1 if identity.endswith('prev') else 1))%pages
            self.focus_id='campaign-event:'+str(self.campaign_event_page*5)
            return True
        if identity=='campaign-info':
            self._open('campaign-info','Event details')
            return True
        return False
