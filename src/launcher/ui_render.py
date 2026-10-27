"""Composição SDL do menu aprovado; sem navegador, downloads ou ações de sessão.

Os controles e seus limites pertencem ao NativeMenu. Este módulo só desenha a
lista de itens que ele fornece, em coordenadas lógicas de 1280 × 800.
"""
from math import cos, sin, pi
from pathlib import Path
import textwrap


BG = (16, 17, 18)
SURFACE = (26, 27, 29)
RAISED = (34, 35, 38)
LINE = (52, 53, 56)
TEXT = (242, 240, 233)
MUTED = (157, 158, 159)
YELLOW = (243, 205, 85)
DARK = (27, 28, 28)


def _frame(w, x, y, width, height, color=LINE, thickness=1):
    """Borda sem preencher o interior de uma imagem."""
    for xx, yy, ww, hh in ((x, y, width, thickness),
                           (x, y+height-thickness, width, thickness),
                           (x, y, thickness, height),
                           (x+width-thickness, y, thickness, height)):
        w.rect(int(xx), int(yy), max(1, int(ww)), max(1, int(hh)), color)


def _text(w, value, x, y, width, scale=1.4, color=TEXT, lines=1,
          style=None, scroll_key=None):
    """Mantém texto dentro da área do controle, com linhas limitadas."""
    value = str(value) if value is not None else ''
    if not value or width <= 0:
        return
    limit = max(1, int(width/(scale*6.1)))
    rows = textwrap.wrap(value, width=limit, break_long_words=True,
                         break_on_hyphens=False) if lines > 1 else [value]
    for index, row in enumerate(rows[:lines]):
        if index == lines-1 and len(rows) > lines:
            row = row[:max(0, limit-3)]+'...'
        kwargs = {'scale': scale, 'color': color, 'limit': max(1, len(row)),
                  'max_width': int(width)}
        if style is not None:
            kwargs['style'] = style
        if scroll_key is not None:
            kwargs['scroll_key'] = scroll_key
        w.text(row, int(x), int(y+index*(scale*10+6)), **kwargs)


def _clock(w, cx, cy, radius=10, color=YELLOW):
    # Geometria própria: o emblema não depende de uma fonte de ícones.
    for point in range(60):
        angle = point*pi/30
        w.rect(int(cx+radius*cos(angle))-1,
               int(cy+radius*sin(angle))-1, 2, 2, color)
    w.rect(cx-1, cy-radius+4, 2, max(3, radius-3), color)
    w.rect(cx, cy-1, max(3, radius-3), 2, color)


def _nav_icon(w, name, x, y, color):
    if name == 'history':
        _clock(w, x+9, y+10, 8, color)
    elif name == 'settings':
        for index, knob in enumerate((11, 4, 14)):
            yy = y+3+index*7
            w.rect(x, yy, 20, 1, color)
            w.rect(x+knob, yy-2, 3, 5, color)
    elif name == 'events':
        w.rect(x+2, y, 2, 22, color)
        for row in range(3):
            for col in range(4):
                if (row+col)%2==0:w.rect(x+5+col*4,y+row*4,4,4,color)
    elif name == 'synth':
        for xx, yy in ((8, 0), (8, 16), (0, 8), (16, 8)):
            w.rect(x+xx, y+yy, 3, 3, color)
        w.rect(x+7, y+6, 5, 7, color)
    elif name == 'rogue':
        # Brasão em pixels: identidade própria para a sequência de desafios.
        _frame(w, x+1, y, 18, 14, color)
        for offset in range(4):
            w.rect(x+2+offset*2, y+14+offset*2, 16-offset*4, 2, color)
        w.rect(x+6, y+4, 3, 3, color)
        w.rect(x+12, y+4, 3, 3, color)
    else:
        # Pequeno traçado de circuito, distinto do relógio da marca.
        w.rect(x+1, y+2, 15, 2, color)
        w.rect(x, y+3, 2, 13, color)
        w.rect(x+1, y+15, 18, 2, color)
        w.rect(x+17, y+7, 2, 9, color)
        w.rect(x+12, y+6, 7, 2, color)


def _rogue_badge(w, item, focused):
    if item.get('album_card'):
        return _rogue_reward(w, item, focused)
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    earned = bool(item.get('earned'))
    accent = YELLOW if earned else MUTED
    w.rect(x, y, width, height, SURFACE)
    w.rect(x+12, y+12, 70, height-24, (45, 40, 27) if earned else RAISED)
    # Brasão original construído com pixels, sem assets externos.
    sx, sy = x+27, y+20
    _frame(w, sx, sy, 40, 30, accent, 2)
    for index in range(5):
        w.rect(sx+index*4, sy+30+index*4, 40-index*8, 4, accent)
    if earned:
        for dx, dy in ((9, 8), (21, 8), (15, 17)):
            w.rect(sx+dx, sy+dy, 7, 6, accent)
    else:
        _text(w, '?', sx+13, sy+6, 20, 2.2, accent)
    _text(w, item.get('label', ''), x+102, y+16, width-120, 1.8, accent,
          scroll_key='rogue-badge:'+str(item['id']))
    _text(w, item.get('value', item.get('subtitle', '')), x+102, y+47,
          width-120, 1.4, TEXT if earned else MUTED, lines=2)
    _frame(w, x, y, width, height, YELLOW if focused else LINE, 2 if focused else 1)


def _rogue_reward(w, item, focused):
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    earned, secret = bool(item.get('earned')), bool(item.get('secret'))
    art_only = bool(item.get('art_only'))
    art_height = height-24 if art_only else 88
    accent = YELLOW if earned else MUTED
    w.rect(x, y, width, height, SURFACE)
    w.rect(x+12, y+10, width-24, art_height, (14, 18, 23))
    image = item.get('image') if earned and not secret else None
    if image:
        try:
            _image(w, image, x+12, y+10, width-24, art_height,
                   fit='contain', background=(14, 18, 23))
        except (OSError, ValueError, RuntimeError):
            image = None
    if not image:
        sx, sy = x+(width-40)//2, y+10+(art_height-54)//2
        if secret:
            _frame(w, sx, sy, 40, 30, accent, 2)
            for index in range(5):
                w.rect(sx+index*4, sy+30+index*4, 40-index*8, 4, accent)
            if earned:
                for dx, dy in ((9, 8), (21, 8), (15, 17)):
                    w.rect(sx+dx, sy+dy, 7, 6, accent)
            else:
                _text(w, '?', sx+13, sy+6, 20, 2.2, accent)
        else:
            _frame(w, sx-4, sy+3, 48, 48, accent, 2)
            _text(w, '*' if earned else '?', sx+10, sy+11, 26, 2.6, accent)
    if not art_only:
        _text(w, item.get('label', ''), x+12, y+102, width-24, 1.55,
              TEXT if earned else MUTED, scroll_key=item['id'])
        _text(w, item.get('value', ''), x+12, y+124, width-24, 1.15, MUTED, lines=2)
        progress = item.get('progress')
        if progress:
            _text(w, 'Discovered' if earned else item.get('progress_label', ''),
                  x+12, y+161, width-24, 1.0, accent)
            target = max(1, progress.get('target', 1))
            fraction = 1 if earned else max(0, min(1, progress.get('current', 0)/target))
            w.rect(x+12, y+height-9, width-24, 3, LINE)
            if fraction:
                w.rect(x+12, y+height-9, max(1, int((width-24)*fraction)), 3, accent)
    _frame(w, x, y, width, height, YELLOW if focused else LINE, 2 if focused else 1)


def _shell(w, menu):
    w.rect(0, 0, 1280, 800, BG)
    # O bordô diminui até o carvão, como a coluna da proposta HTML.
    for y in range(0, 800, 16):
        fade = max(0.0, 1-y/710)**1.7
        for x in range(0, 216, 24):
            side = 1-x/310
            color = tuple(int(base+(top-base)*fade*side)
                          for base, top in zip((24, 22, 25), (111, 47, 57)))
            w.rect(x, y, 24, 16, color)
    w.rect(215, 0, 1, 800, (49, 38, 42))
    _text(w, 'ac-deck', 28, 29, 153, 3.4, TEXT, style='brand')
    _clock(w, 191, 44, 9)
    _text(w, 'ASSETTO CORSA', 29, 84, 166, 1.6, (229, 201, 204))
    _text(w, 'THE NEXT DRIVE', 28, 157, 165, 1.2, (181, 156, 160))
    w.rect(28, 675, 160, 1, (69, 49, 55))
    _text(w, 'ac-deck', 29, 695, 162, 1.2, (209, 191, 193))
    _text(w, 'ASSETTO CORSA', 29, 716, 162, 1.2, (157, 143, 147))
    _text(w, 'Single player', 29, 758, 162, 1.3, (157, 143, 147))
    w.rect(216, 63, 1064, 1, (33, 34, 36))
    view = str(getattr(menu, 'view', 'drive'))
    labels = {'drive': 'DRIVE', 'events': 'EVENTS', 'synth': 'EVENT SYNTHETIZER',
              'history': 'HISTORY', 'settings': 'SETTINGS'}
    _text(w, 'YOUR NEXT DRIVE  /  '+labels.get(view, view.upper()),
          248, 24, 760, 1.4, MUTED)
    kicker, title, subtitle = menu.ui_heading()
    _text(w, kicker, 248, 91, 984, 1.4, YELLOW)
    _text(w, title, 248, 116, 984, 3.0)
    if subtitle and subtitle != getattr(menu, 'message', ''):
        _text(w, subtitle, 248, 153, 984, 1.4, MUTED)


def _selection_label(selection, key):
    value = selection.get(key, '')
    if isinstance(value, dict):
        value = value.get('name') or value.get('id', '')
    return selection.get(key+'_name') or value


def _footer(w, menu):
    w.rect(216, 684, 1064, 116, (23, 24, 26))
    w.rect(216, 684, 1064, 1, (56, 57, 58))
    if getattr(menu, 'rogue_result_visible', lambda: False)():
        result = menu.rogue_result
        _text(w, 'ROGUE / '+('RUN SUMMARY' if result['tone'] == 'over' else
                            'RESULT UNCONFIRMED' if result['tone'] == 'unconfirmed' else 'RESULT SAVED'),
              248, 706, 590, 1.35, YELLOW)
        _text(w, 'Your XP and achievements are permanent.', 248, 732, 590, 1.65, TEXT)
        _text(w, 'B / Esc Return to result' if menu.overlay else 'A Continue    B Back to Rogue    Arrows Navigate',
              248, 762, 590, 1.3, MUTED)
        return
    selection = menu.effective_selection() or {}
    source = {'manual': 'MANUAL SETUP', 'generated': 'GENERATED EVENT',
              'installed': 'INSTALLED EVENT', 'rogue': 'ROGUE CHALLENGE'}.get(getattr(menu, 'source', ''), '')
    _text(w, source, 248, 700, 610, 1.4, (183, 174, 143))
    title = ' · '.join(str(value) for value in
                       (_selection_label(selection, 'car'),
                        _selection_label(selection, 'track')) if value)
    _text(w, title or {'installed':'Choose an event','generated':'Generate an event',
                      'rogue':'Prepare your next challenge'}.get(getattr(menu,'source',''),'Choose a car and circuit'), 248, 726, 598, 1.8,
          scroll_key='footer-content')
    meta = []
    mode = selection.get('mode_name') or selection.get('mode') or selection.get('session')
    if mode:
        meta.append(str(mode).title())
    if str(mode).lower() == 'race':
        for key, suffix in (('laps', 'laps'), ('opponents', 'opponents')):
            if selection.get(key) is not None:
                meta.append(f'{selection[key]} {suffix}')
        difficulty = selection.get('ai_level', selection.get('ai'))
        if difficulty is not None:
            meta.append(f'AI {difficulty}%')
    elif str(mode).lower() == 'practice':
        if selection.get('minutes') is not None:
            meta.append(f'{selection["minutes"]} minutes')
    elif mode:
        meta.append('Solo')
    _text(w, ' · '.join(meta), 248, 752, 598, 1.4, MUTED)
    hints = 'Arrows Navigate     A / Enter Select or edit     B Back'
    if getattr(menu, 'view', '') == 'drive' and getattr(menu, 'source', '') == 'manual':
        hints = 'A Select     B Back     Y Livery     LB / RB Sections'
    if getattr(menu, 'editing', None):
        hints = 'Arrows Adjust     A / Enter Confirm     B / Esc Cancel'
    if getattr(menu, 'livery_state', None) is not None:
        hints = 'Left / Right Preview livery     A Confirm     B Cancel'
    if getattr(menu, 'brand_state', None) is not None:
        hints = 'Up / Down Browse brands     A Confirm     B Cancel'
    panel=getattr(menu,'catalogue_panel',None)
    if panel is not None:
        hints=('A Toggle / select     L2 / R2 Pages     Apply to confirm     B Cancel'
               if panel['kind']=='filters' else 'B Back to the same list and selection')
    if getattr(menu,'search_edit_id',None) is not None and getattr(menu,'searching',False):
        hints='Type to search     A / Enter Finish     B Back to list'
    ai_panel=getattr(menu,'ai_panel',None)
    if ai_panel is not None:
        hints=('Arrows Move cursor     Enter New line     B Finish typing' if ai_panel['editing'] else
               'A Select / edit     L2 / R2 Scroll     Generate / Cancel' if ai_panel.get('scope')=='once' else
               'A Select / edit     L2 / R2 Scroll     Save / Cancel')
    if getattr(menu,'session_request',{}).get('editing'):
        hints='Arrows Move cursor     Enter New line     B Finish typing / keep text'
    elif getattr(menu,'overlay',None) in ('session-prompt-full','ai-verdict'):
        hints='L2 / R2 Scroll     A Select / edit     B Back'
    elif getattr(menu,'view',None)=='synth' and getattr(menu,'focus_id',None) in ('session-prompt','session-up','session-down'):
        hints='A Edit     L2 / R2 Scroll prompt     Expand for full text'
    _text(w, hints,
          248, 779, 600, 1.4, MUTED)
    _text(w, 'X / Start unavailable while editing' if (getattr(menu, 'editing', None) or
          getattr(menu, 'livery_state', None) or getattr(menu, 'brand_state', None) or panel is not None or ai_panel is not None
          or getattr(menu,'session_request',{}).get('editing') or getattr(menu,'session_audio_busy',False)) else
          'Session running' if getattr(menu, 'session_running', False) else 'Arrows · Enter · Esc · Tab · X',
          947, 779, 310, 1.4, (151, 153, 149))


def _image(w, candidates, x, y, width, height, fit='contain',
           background=(10, 17, 25)):
    if isinstance(candidates, (str, Path)):
        candidates = (candidates,)
    w.image(candidates or (), int(x), int(y), max(1, int(width)),
            max(1, int(height)), fit=fit, background=background)


def _card(w, item, focused, track=False):
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    w.rect(x, y, width, height, SURFACE)
    if item.get('synthesis_card'):
        image_height=height-72
        _image(w,item.get('image'),x+1,y+1,width-2,image_height,
               fit='cover' if track else 'contain',background=(8,10,12))
        w.rect(x+1,y+image_height,width-2,71,(20,22,24))
        _text(w,item.get('label',''),x+16,y+image_height+10,width-32,2.4,
              scroll_key='card:'+item['id'])
        metadata=' / '.join(str(value) for value in (item.get('value'),item.get('subtitle')) if value)
        _text(w,metadata,x+16,y+image_height+44,width-32,1.4,MUTED,
              scroll_key='layout:'+item['id'] if track else 'car-meta:'+item['id'])
        _frame(w,x,y,width,height,YELLOW if focused else LINE,2 if focused else 1)
        return
    if item.get('compact'):
        photo=100 if track else 160
        _image(w,item.get('image'),x+1,y+1,photo,height-2,fit='cover' if track else 'contain',background=(8,10,12))
        xx=x+photo+14;space=width-photo-28
        _text(w,item.get('eyebrow') or ('YOUR CIRCUIT' if track else 'YOUR CAR'),xx,y+8,space,1.2,MUTED)
        _text(w,item.get('label',''),xx,y+29,space,1.9,scroll_key='card:'+item['id'])
        _text(w,item.get('value',''),xx,y+54,space,1.3,MUTED,scroll_key='layout:'+item['id'] if track else None)
        _text(w,item.get('subtitle',''),xx,y+73,space,1.2,MUTED)
        _frame(w,x,y,width,height,YELLOW if focused else LINE,2 if focused else 1)
        return
    caption_height = 76
    image_height = max(1, height-caption_height)
    # A carroceria inteira tem prioridade sobre preencher uma faixa panorâmica.
    _image(w, item.get('image'), x+1, y+1, width-2, image_height,
           fit='cover' if track else 'contain', background=(8, 10, 12))
    w.rect(x+1, y+height-caption_height, width-2, caption_height-1,
           SURFACE if track else (17, 19, 21))
    w.rect(x+12, y+10, 140 if track else 110, 26, (17, 19, 21))
    _text(w, item.get('eyebrow') or ('YOUR CIRCUIT' if track else 'YOUR CAR'),
          x+18, y+16, width-36, 1.4)
    if track:
        outline = item.get('outline')
        text_width = width-144 if outline else width-36
        _text(w, item.get('label', ''), x+18, y+height-70,
              width-36, 2.8, scroll_key='card:'+item['id'])
        _text(w, item.get('value', ''), x+18, y+height-37,
              text_width, 1.4, scroll_key='layout:'+item['id'])
        _text(w, item.get('subtitle', ''), x+18, y+height-19,
              text_width, 1.4, MUTED)
        if outline:
            _image(w, outline, x+width-108, y+height-41, 90, 38,
                   background=None)
    else:
        _text(w, item.get('value', ''), x+18, y+height-70,
              width-36, 1.4, MUTED)
        _text(w, item.get('label', ''), x+18, y+height-49,
              width-36, 2.8, scroll_key='card:'+item['id'])
        _text(w, item.get('subtitle', ''), x+18, y+height-19,
              width-36, 1.4, MUTED)
    _frame(w, x, y, width, height, YELLOW if focused else LINE, 2 if focused else 1)


def _button(w, item, focused):
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    disabled = item.get('disabled', False)
    primary = item.get('primary') or item.get('id') == 'start'
    selected = item.get('selected', False)
    background = YELLOW if primary and not disabled else RAISED if (focused or selected) else SURFACE
    foreground = DARK if primary and not disabled else MUTED if disabled else YELLOW if selected else TEXT
    w.rect(x, y, width, height, background)
    _frame(w, x, y, width, height, YELLOW if focused else LINE,
           2 if focused else 1)
    # Os seletores compactos mantêm os nomes completos em 16 px.
    inset = 5 if width < 160 else 14
    label_width = width-inset*2
    if item.get('id') == 'brand-filter':
        label_width -= 20
        _text(w, 'v', x+width-24, y+(height-16)//2, 16, 1.6,
              YELLOW if focused else MUTED)
    start = item.get('id') == 'start'
    if start and width >= 210 and not disabled:
        label_width = width-114
        _frame(w, x+width-86, y+(height-24)//2, 72, 24, (133, 112, 48))
        _text(w, 'X / START', x+width-81, y+(height-12)//2, 64, 1.3,
              foreground)
    scale = 1.8 if start else 1.6
    _text(w, item.get('label', ''), x+inset, y+max(8, (height-scale*10)//2),
          label_width, scale, foreground)


def _livery_field(w, item, focused):
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    editing = item.get('editing', False)
    w.rect(x, y, width, height, (51, 46, 29) if editing else SURFACE)
    _text(w, 'Livery', x+12, y+4, width-24, 1.3, MUTED)
    _text(w, item.get('value', ''), x+12, y+21, width-24, 1.6,
          YELLOW if focused or editing else TEXT)
    _frame(w, x, y, width, height, YELLOW if focused or editing else LINE,
           3 if editing else 2 if focused else 1)


def _field(w, item, focused, setting=False):
    if item.get('id') == 'picker-livery':
        return _livery_field(w, item, focused)
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    disabled = item.get('disabled', False)
    editing = item.get('editing', False)
    editable = item.get('editable', False)
    fg = MUTED if disabled else TEXT
    w.rect(x, y, width, height, (51, 46, 29) if editing else (35, 35, 32) if focused else SURFACE)
    if setting:
        label_width = max(120, int(width*.56))
        _text(w, item.get('label', ''), x+16, y+(8 if height<55 else 12),
              label_width-24, 1.6, fg)
        _text(w, item.get('subtitle', ''), x+16, y+40,
              label_width-24, 1.4, MUTED)
        value_x = x+label_width
        value_width = width-label_width-17
        if item.get('select'):value_width-=26
        value_inset=34 if editing and not item.get('text_input') else 0
        _text(w, item.get('value', ''), value_x+value_inset, y+max(10, (height-20)//2),
              value_width-value_inset*2, 2.0, YELLOW if focused and not disabled else fg,
              lines=1)
        if editing and not item.get('text_input'):
            for xx,symbol in ((value_x+4,'-'),(x+width-34,'+')):
                _frame(w,xx,y+(height-26)//2,22,26,YELLOW)
                _text(w,symbol,xx+7,y+(height-26)//2+5,14,1.4,YELLOW)
        if item.get('select'):
            _text(w,'v',x+width-30,y+max(12,(height-16)//2),18,1.6,YELLOW if focused else MUTED)
        w.rect(x+14, y+height-1, width-28, 1, LINE)
    else:
        _text(w, item.get('label', ''), x+14, y+10, width-28, 1.6, MUTED)
        inset = 48 if editing else 14
        _text(w, item.get('value', ''), x+inset, y+33, width-inset*2, 2.0,
              YELLOW if focused and not disabled else fg)
        if editing:
            for xx, symbol in ((x+12, '-'), (x+width-34, '+')):
                _frame(w, xx, y+30, 22, 26, YELLOW)
                _text(w, symbol, xx+7, y+35, 14, 1.4, YELLOW)
    if editable and focused and not editing and not item.get('compact'):
        _text(w,'A / Enter: edit',x+14,y+height-17,label_width-24 if setting else width-28,1.4,MUTED)
    if item.get('select') and focused:
        _text(w,'A / Enter: choose',x+14,y+height-17,label_width-24 if setting else width-28,1.4,MUTED)
    if focused:
        _frame(w, x, y, width, height, YELLOW, 3 if editing else 2)
    elif not setting:
        _frame(w, x, y, width, height)


def _entry(w, item, focused, catalogue=False):
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    selected = bool(item.get('selected'))
    w.rect(x, y, width, height, RAISED if focused else SURFACE)
    if catalogue and width < 390:
        compact_tags = item.get('compact_tags', False)
        picture_height = max(40, height-(80 if compact_tags else 54))
        _image(w, item.get('image'), x+1, y+1, width-2, picture_height,
               fit='cover' if item.get('image_kind') == 'track' else 'contain',
               background=(8, 10, 12))
        _text(w, item.get('label', ''), x+12, y+picture_height+7,
              width-24, 1.8, scroll_key='entry:'+item['id'])
        _text(w, item.get('subtitle') or item.get('value', ''), x+12, y+picture_height+29,
              width-24, 1.2 if compact_tags else 1.4, MUTED,
              lines=3 if compact_tags else 1,
              scroll_key='entry-layout:'+item['id'] if item.get('image_kind')=='track' else None)
    else:
        has_image = bool(item.get('image'))
        picture_width = min(132, max(80, height*3//2)) if has_image else 0
        if has_image:
            _image(w, item['image'], x+1, y+1, picture_width, height-2,
                   fit='cover' if item.get('image_kind') == 'track' else 'contain',
                   background=(8, 10, 12))
        text_x = x+picture_width+16
        label_width = width-picture_width-32
        value_width = min(200, width//3) if item.get('value') else 0
        label_width -= value_width+16 if value_width else 0
        _text(w, item.get('label', ''), text_x, y+14, label_width, 1.8,
              scroll_key='entry:'+item['id'])
        _text(w, item.get('subtitle', ''), text_x, y+43, label_width, 1.4, MUTED,
              lines=2 if height >= 99 else 1)
        if value_width:
            _text(w, item['value'], x+width-value_width-16,
                  y+max(12, (height-36)//2), value_width, 1.4, YELLOW,
                  lines=2)
    if selected:
        w.rect(x+width-12, y+8, 5, 5, YELLOW)
    if catalogue and item.get('favorite'):
        w.rect(x+8,y+8,86,24,(17,19,21))
        _text(w,'Favorite',x+14,y+13,74,1.4,YELLOW)
    _frame(w, x, y, width, height, YELLOW if focused else LINE,
           2 if focused else 1)


def _rogue_objective(w, item):
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    w.rect(x, y, width, height, (36, 33, 24))
    w.rect(x, y, 4, height, YELLOW)
    _text(w, item['label'], x+20, y+14, width-40, 3.7, YELLOW)


def _rogue_result(w, item):
    import time
    data, outcome = item['data'], item['data']['outcome']
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    now = getattr(w, '_text_frame_time', None)
    elapsed = max(0, (time.monotonic() if now is None else now)-item['started'])
    progress = min(1, elapsed/.15)
    ease = 1-(1-progress)**3
    victory = data['tone'] == 'victory'
    accent = YELLOW if victory else (197, 140, 122) if data['tone'] in ('retry', 'over') else MUTED
    w.rect(x, y, width, height, (28, 28, 27) if victory else (27, 26, 27))
    _frame(w, x, y, width, height, (round(66+12*ease), round(60+9*ease), 43) if victory else LINE)
    w.rect(x, y, 4, height, accent)
    _text(w, 'CHALLENGE '+str(data['stage'])+'  /  '+('PERFECT STREAK' if data['milestone'] else 'FIRST PLACE' if victory and outcome['position'] == 1 else 'RACE RESULT'),
          x+24, y+16, 350, 1.35, accent)
    _text(w, data['car_name']+' / '+data['track_name'], x+380, y+16, width-404, 1.3, MUTED,
          scroll_key='rogue-result-content')
    _text(w, data['title'], x+24, y+45, width-48, 3.65, TEXT if victory else (220, 205, 198))
    unconfirmed = data['tone'] == 'unconfirmed'
    _text(w, data['reason'], x+24, y+(94 if unconfirmed else 98), width-48, 1.5, TEXT if unconfirmed else MUTED)
    if unconfirmed:
        _text(w, 'Reason: '+data['reason_code'] if data.get('reason_code') else 'Reason unavailable',
              x+24, y+116, width-48, 1.25, YELLOW)
    w.rect(x+24, y+135, width-48, 1, LINE)
    _text(w, 'FINAL POSITION', x+24, y+153, 276, 1.25, MUTED)
    position = outcome.get('position')
    _text(w, 'P'+str(position) if position is not None else '--', x+24, y+179, 276, 5.6, accent)
    _text(w, 'TARGET  /  P'+str(outcome['target_position'])+' OR BETTER', x+336, y+153, width-364, 2.0, TEXT)
    confirmed = outcome['status'] in ('won', 'lost') and position is not None
    finished = confirmed or outcome.get('reason') == 'final_position_missing'
    checks = [('Race finished' if finished else 'Finish not confirmed', finished),
              ('Position target achieved' if victory else 'Position target missed' if confirmed else 'Target not confirmed', victory)]
    for index, (label, passed) in enumerate(checks):
        yy = y+191+index*27
        w.rect(x+337, yy, 14, 14, accent if passed else RAISED)
        if passed:
            w.rect(x+340, yy+6, 3, 5, DARK)
            w.rect(x+343, yy+3, 5, 3, DARK)
        _text(w, label, x+364, yy-1, width-394, 1.5,
              TEXT if passed else MUTED)
    for index, mastery in enumerate(data['mastery']):
        xx, yy, bar_width = x+24+index*486, y+256, 442
        after, before = mastery['after'], mastery['before']
        w.rect(xx, yy, bar_width, 66, (33, 34, 34))
        _text(w, mastery['label']+'  +'+str(mastery['awarded'])+' XP', xx+12, yy+10, bar_width-24, 1.75, TEXT)
        xp_label = str(after['xp'])+'/'+str(after['next_xp'])+' XP' if after['next_xp'] is not None else str(after['xp'])+' XP / MAX'
        _text(w, f"Lv {after['level']} / {after['title']} / {xp_label}", xx+12, yy+35, bar_width-24, 1.2, MUTED)
        if after['level'] > before['level']:
            _text(w, 'LEVEL UP', xx+bar_width-96, yy+12, 84, 1.1, accent)
        target = after['next_xp'] or max(1, after['xp'])
        fill = min(1, (before['xp']+(after['xp']-before['xp'])*ease)/target)
        w.rect(xx, yy+61, bar_width, 5, LINE)
        if fill > 0:w.rect(xx, yy+61, max(1, int(bar_width*fill)), 5, accent)
    stats = f"{outcome['wins']} {'WIN' if outcome['wins'] == 1 else 'WINS'}    /    PERFECT STREAK {outcome['streak']}    /    SPARE LIVES {outcome['lives']}"
    _text(w, stats, x+24, y+340, width-48, 1.6, TEXT)
    note = ('Progress saved. Your next challenge is waiting.' if victory else
            f"Run rewards: +{data['run_xp']} car XP / +{data['run_xp']} circuit XP / {data['run_rewards']} discoveries. Permanent progress kept." if data['tone'] == 'over' else
            '1 spare life used. Perfect streak reset. Continue to the next event.' if data.get('advance') else
            '1 spare life used. Perfect streak reset. You can retry the same challenge.' if data['tone'] == 'retry' else
            'Lives, XP and your perfect streak are unchanged. Retry the same challenge.')
    _text(w, note, x+24, y+371, width-48, 1.35, MUTED)
    rewards = data['rewards']
    if rewards:
        w.rect(x+24, y+401, width-48, 28, (46, 42, 29))
        names = ' / '.join(reward['name'] for reward in rewards[:2])
        if len(rewards) > 2:names += f" / +{len(rewards)-2} more in Achievements"
        art = next((reward['image'] for reward in rewards if reward['image']), None)
        if art:_image(w, art, x+28, y+402, 28, 26, fit='contain', background=None)
        _text(w, 'UNLOCKED  '+names, x+(66 if art else 34), y+407, width-(100 if art else 68), 1.4, accent)
    else:
        _text(w, 'XP AND ACHIEVEMENTS STAY WITH YOU', x+24, y+407, width-48, 1.2, MUTED)


def _item(w, item, focus_id):
    kind = item.get('kind', 'button')
    focused = item.get('id') == focus_id and not item.get('disabled')
    x, y, width, height = (int(item[key]) for key in ('x', 'y', 'w', 'h'))
    if kind == 'rogue-conditions':
        return _text(w, item['label'], x, y, width, 1.65, TEXT, scroll_key='rogue-conditions')
    if kind == 'rogue-mastery':
        return _text(w, item['compact_label'], x, y, width, 1.2, MUTED)
    if kind == 'rogue-objective':
        return _rogue_objective(w, item)
    if kind == 'rogue-result':
        return _rogue_result(w, item)
    if kind=='info':
        w.rect(x,y,width,height,SURFACE)
        _text(w,item.get('label',''),x+16,y+10,width-32,1.3,MUTED)
        _text(w,item.get('value',''),x+16,y+34,width-32,item.get('value_scale',1.6),TEXT,
              lines=1 if item.get('label')=='Layout' else item.get('value_lines',2),
              scroll_key=item.get('value_scroll') or (item['id'] if item.get('label')=='Layout' else None))
        return
    if kind == 'nav':
        selected = item.get('selected', False)
        if selected or focused:
            w.rect(x, y, width, height, (65, 44, 48) if selected else (49, 36, 41))
        if selected:
            w.rect(x, y, 3, height, YELLOW)
        color = YELLOW if selected or focused else (193, 185, 186)
        name = str(item.get('id', '')).split(':')[-1]
        _nav_icon(w, name, x+14, y+20, color)
        _text(w, item.get('label', ''), x+43, y+13, width-48,
              1.5 if name == 'synth' else 1.6, color)
        hints = {'drive': 'Prepare a session', 'events': 'Play a campaign', 'synth': 'Find a new event',
                 'rogue': 'Build your run',
                 'history': 'Revisit a drive', 'settings': 'Make it yours'}
        _text(w, item.get('subtitle', hints.get(name, '')), x+43, y+39,
              width-48, 1.4, (185, 164, 164))
        if focused:
            _frame(w, x, y, width, height, YELLOW, 1)
    elif kind == 'rogue-badge':
        _rogue_badge(w, item, focused)
    elif kind == 'rogue-sticker':
        _rogue_reward(w, item, focused)
    elif kind in ('car', 'track'):
        _card(w, item, focused, track=kind == 'track')
    elif kind == 'field':
        _field(w, item, focused)
    elif kind == 'setting' and str(item.get('id', '')).startswith('detail:'):
        w.rect(x, y, width, height, SURFACE)
        _text(w, item.get('label', ''), x+14, y+10, width-28, 1.6, MUTED)
        _text(w, item.get('value', ''), x+14, y+34, width-28, 2.0,
              scroll_key=item['id'] if item['id'] in ('detail:0','detail:1') else None)
        w.rect(x+14, y+height-1, width-28, 1, LINE)
    elif kind == 'setting':
        _field(w, item, focused, setting=True)
    elif kind == 'category':
        if focused or item.get('selected'):
            w.rect(x, y, width, height, (35, 35, 29))
            w.rect(x, y, 2, height, YELLOW)
        _text(w, item.get('label', ''), x+12, y+(height-15)//2,
              width-24, 1.6, YELLOW if focused or item.get('selected') else MUTED)
        if focused:
            _frame(w, x, y, width, height, YELLOW)
    elif kind in ('campaign-group','campaign-event'):
        selected=item.get('selected')
        w.rect(x,y,width,height,(40,39,30) if selected else SURFACE)
        if selected:w.rect(x,y,3,height,YELLOW)
        if focused:_frame(w,x,y,width,height,YELLOW,2)
        mark='OK' if item.get('completed') else '>' if selected else ''
        if mark:_text(w,mark,x+width-38,y+9,30,1.3,YELLOW)
        _text(w,item.get('label',''),x+12,y+8,width-58,1.6,TEXT,scroll_key='campaign-label:'+str(item['id']))
        if kind=='campaign-event':
            _text(w,item.get('subtitle',''),x+12,y+29,width-24,1.3,MUTED,scroll_key='campaign-content:'+str(item['id']))
            _text(w,item.get('value',''),x+12,y+47,width-24,1.2,YELLOW if item.get('completed') else MUTED)
        else:_text(w,item.get('value',''),x+12,y+37,width-24,1.3,YELLOW if item.get('completed') else MUTED)
    elif kind in ('catalogue', 'history'):
        _entry(w, item, focused, catalogue=kind == 'catalogue')
    elif kind == 'verdict':
        w.rect(x,y,width,height,SURFACE)
        _frame(w,x,y,width,height,YELLOW if focused else LINE,2 if focused else 1)
        state={'idle':'No AI request','pending':'Generating','complete':'Applied',
               'partial':'Partial','no_proposal':'No new proposal','error':'Generation failed'}[item['outcome']]
        _text(w,item['label']+' / '+state,x+12,y+8,width-200,1.3,YELLOW)
        if item.get('compact'):
            _text(w,'A / Read full text',x+width-172,y+8,160,1.3,MUTED)
            _text(w,item.get('value',''),x+12,y+29,width-24,1.4,TEXT)
        else:
            _text(w,item.get('value',''),x+12,y+26,width-24,1.4,TEXT,lines=3)
            _text(w,item.get('app_note',''),x+12,y+90,width-24,1.2,MUTED,lines=2)
    elif kind == 'activity':
        if item.get('visible'):
            from . import ai_activity
            import time
            now=getattr(w,'_text_frame_time',None)
            ai_activity.draw(w,x+(width-48)//2,y+(height-28)//2,time.monotonic() if now is None else now)
    elif kind == 'text':
        _text(w, item.get('label', ''), x, y, width,
              item.get('scale', 1.4), item.get('color', MUTED),
              lines=1 if item['id'] in ('catalogue-name','campaign-name') else max(1, min(8, height//21)),
              scroll_key=item['id'] if item['id'] in ('catalogue-name','campaign-name') else None)
        if item.get('value'):
            _text(w, item['value'], x, y+24, width, 1.6, TEXT,
                  lines=max(1, min(8, (height-24)//23)))
    elif kind == 'textarea':
        from .ai_settings_ui import lines as prompt_lines
        w.rect(x,y,width,height,SURFACE)
        _frame(w,x,y,width,height,YELLOW if focused else LINE,2 if focused else 1)
        value=item.get('value','')
        if item.get('editing'):
            cursor=item.get('cursor',len(value))
            value=value[:cursor]+'│'+value[cursor:]
        rows=prompt_lines(value or (item.get('placeholder','Type or paste your preferences.') if not item.get('readonly') else ''),item.get('line_width',100))
        count=max(1,(height-18)//24)
        offset=max(0,min(item.get('offset',0),max(0,len(rows)-count)))
        for index,row in enumerate(rows[offset:offset+count]):
            _text(w,row,x+12,y+10+index*24,width-24,1.4,MUTED if item.get('readonly') else TEXT)
        if len(rows)>count:
            w.rect(x+width-4,y+3,2,height-6,LINE)
            thumb=max(4,(height-6)*count//len(rows))
            top=y+3+int((height-6-thumb)*offset/max(1,len(rows)-count))
            w.rect(x+width-4,top,2,thumb,YELLOW)
    else:
        _button(w, item, focused)


def _modal(w, title, subtitle='', title_width=974):
    # A área do modal conserva sidebar e footer, para manter o contexto.
    w.rect(232, 89, 1032, 591, (11, 12, 13))
    _frame(w, 232, 89, 1032, 591, (85, 83, 74))
    _text(w, title, 254, 101, title_width, 2.8)
    if subtitle:
        _text(w, subtitle, 254, 142, 970, 1.4, MUTED)


def _key_dialog(w, menu):
    w.rect(232, 80, 1032, 588, (11, 12, 13))
    _frame(w, 232, 80, 1032, 588, (85, 83, 74))
    _text(w, 'OpenAI API key', 270, 126, 900, 2.8)
    _text(w, 'Stored only on this device. Save an empty field to remove it.',
          270, 180, 900, 1.6, MUTED)
    _text(w, 'Type or paste with Ctrl+V. The key stays hidden.',
          270, 216, 900, 1.4, MUTED)
    focused = getattr(menu, 'key_focus', 0)
    # Mesmo contrato de clique de Menu.key_action, conservado pelo NativeMenu.
    w.rect(244, 365, 800, 45, SURFACE)
    _frame(w, 244, 365, 800, 45, YELLOW if focused == 0 else LINE,
           2 if focused == 0 else 1)
    masked = '*'*min(76, len(getattr(menu, 'key_buffer', '')))
    _text(w, masked or 'Type or paste your key', 260, 380, 768,
          1.8, TEXT if masked else MUTED)
    for index, (identity, label, xx) in enumerate(
            (('key:save', 'Save key', 460), ('key:cancel', 'Cancel', 680)), 1):
        _button(w, {'id': identity, 'label': label, 'x': xx, 'y': 460,
                    'w': 180, 'h': 52, 'primary': index == 1}, focused == index)
    _text(w, 'B Cancel     A Confirm     Tab / D-pad Change focus',
          270, 550, 915, 1.4, MUTED)


def _brand_popup(w, items, focus_id):
    if not items:
        return
    x = min(item['x'] for item in items)-8
    y = min(item['y'] for item in items)-8
    width = max(item['x']+item['w'] for item in items)-x+8
    height = max(item['y']+item['h'] for item in items)-y+8
    w.rect(x+5, y+5, width, height, (5, 6, 7))
    w.rect(x, y, width, height, (24, 26, 28))
    _frame(w, x, y, width, height, (100, 97, 83))
    for item in items:
        _item(w, item, focus_id)


def draw(menu, w):
    """Desenha o estado atual; não altera seleção, foco, chave ou histórico."""
    if hasattr(w, 'begin_text_frame'):
        panel = getattr(menu, 'catalogue_panel', None)
        w.begin_text_frame((getattr(menu, 'view', None), getattr(menu, 'overlay', None),
                            panel.get('kind') if panel else None))
    _shell(w, menu)
    _footer(w, menu)
    items = menu.ui_items()
    overlay = getattr(menu, 'overlay', None)
    if overlay:
        title = getattr(menu, 'overlay_title', '') or str(overlay).replace('_', ' ').title()
        panel=getattr(menu,'catalogue_panel',None)
        if panel is not None:title='Content filters' if panel['kind']=='filters' else 'Content details'
        _modal(w, title, title_width=340 if overlay in ('cars','tracks') and panel is None else 850)
    brand_items = []
    for item in items:
        if item['kind']=='activity' and (getattr(menu,'key_dialog',False) or getattr(menu,'quit_confirmation',False)):
            continue
        if getattr(menu, 'brand_state', None) is not None and (str(item.get('id', '')).startswith('brand:') or
                item.get('id') in ('brand-prev', 'brand-next', 'brand-back')):
            brand_items.append(item)
        else:
            _item(w, item, getattr(menu, 'focus_id', None))
    _brand_popup(w, brand_items, getattr(menu, 'focus_id', None))
    message = getattr(menu, 'message', '')
    if message:
        w.rect(216, 65, 1064, 24, (45, 40, 27))
        w.rect(216, 65, 3, 24, YELLOW)
        _text(w, message, 248, 70, 1000, 1.4, (230, 212, 154))
    if getattr(menu, 'key_dialog', False):
        _key_dialog(w, menu)
    if getattr(menu, 'quit_confirmation', False):
        w.rect(366, 270, 680, 242, (25, 26, 28))
        _frame(w, 366, 270, 680, 242, YELLOW)
        _text(w, 'Close ac-deck?', 398, 310, 610, 2.6)
        _text(w, 'Your saved selection and settings are preserved.',
              398, 366, 610, 1.4, MUTED)
        for xx, label, selected in ((440, 'Cancel', not menu.quit_selected),
                                    (660, 'Exit', menu.quit_selected)):
            _button(w, {'id': 'quit:'+label, 'label': label, 'x': xx,
                        'y': 414, 'w': 180, 'h': 56, 'primary': selected}, selected)
        _text(w, 'A Confirm     B Keep preparing', 398, 487, 610, 1.4, MUTED)
