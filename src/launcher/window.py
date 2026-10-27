"""Menu SDL2 por ctypes: controle, teclado e mouse, sem bindings adicionais.

SDL2 é procurada nas bibliotecas existentes do sistema/Proton. Não instala
dependências. A fonte bitmap abaixo é desenho autoral, não um asset do jogo.
"""
from . import graphics_settings, session_settings
import ctypes as C
import ctypes.util
from pathlib import Path
import struct
import sys
import signal
import time
import unicodedata
import zlib
from concurrent.futures import Future
from collections import OrderedDict
from copy import deepcopy
import threading

from .content import MODES, pp_filters
from .graphics import LABELS as GRAPHICS_LABELS
from . import controls, previews, conditions, comfort, graphics, chase_camera, event_synthetizer, ai_events, api_credentials
from .csp import AI_LABELS, VERSION as CSP_VERSION
from . import driving_haptics, session_process, ai_preferences, ai_usage, ai_report

# Sete linhas de cinco bits por caractere; escala inteira na textura.
FONT = {
 'A':'01110/10001/10001/11111/10001/10001/10001',
 'B':'11110/10001/10001/11110/10001/10001/11110',
 'C':'01111/10000/10000/10000/10000/10000/01111',
 'D':'11110/10001/10001/10001/10001/10001/11110',
 'E':'11111/10000/10000/11110/10000/10000/11111',
 'F':'11111/10000/10000/11110/10000/10000/10000',
 'G':'01111/10000/10000/10111/10001/10001/01111',
 'H':'10001/10001/10001/11111/10001/10001/10001',
 'I':'11111/00100/00100/00100/00100/00100/11111',
 'J':'00111/00010/00010/00010/10010/10010/01100',
 'K':'10001/10010/10100/11000/10100/10010/10001',
 'L':'10000/10000/10000/10000/10000/10000/11111',
 'M':'10001/11011/10101/10101/10001/10001/10001',
 'N':'10001/11001/10101/10011/10001/10001/10001',
 'O':'01110/10001/10001/10001/10001/10001/01110',
 'P':'11110/10001/10001/11110/10000/10000/10000',
 'Q':'01110/10001/10001/10001/10101/10010/01101',
 'R':'11110/10001/10001/11110/10100/10010/10001',
 'S':'01111/10000/10000/01110/00001/00001/11110',
 'T':'11111/00100/00100/00100/00100/00100/00100',
 'U':'10001/10001/10001/10001/10001/10001/01110',
 'V':'10001/10001/10001/10001/10001/01010/00100',
 'W':'10001/10001/10001/10101/10101/10101/01010',
 'X':'10001/10001/01010/00100/01010/10001/10001',
 'Y':'10001/10001/01010/00100/00100/00100/00100',
 'Z':'11111/00001/00010/00100/01000/10000/11111',
 '0':'01110/10001/10011/10101/11001/10001/01110',
 '1':'00100/01100/00100/00100/00100/00100/01110',
 '2':'01110/10001/00001/00010/00100/01000/11111',
 '3':'11110/00001/00001/01110/00001/00001/11110',
 '4':'00010/00110/01010/10010/11111/00010/00010',
 '5':'11111/10000/10000/11110/00001/00001/11110',
 '6':'01110/10000/10000/11110/10001/10001/01110',
 '7':'11111/00001/00010/00100/01000/01000/01000',
 '8':'01110/10001/10001/01110/10001/10001/01110',
 '9':'01110/10001/10001/01111/00001/00001/01110',
 '-':'00000/00000/00000/11111/00000/00000/00000',
 '.':'00000/00000/00000/00000/00000/00110/00110',
 ':':'00000/00110/00110/00000/00110/00110/00000',
 '/':'00001/00010/00100/00100/01000/10000/00000',
 '+':'00000/00100/00100/11111/00100/00100/00000',
 '(':'00010/00100/01000/01000/01000/00100/00010',
 ')':'01000/00100/00010/00010/00010/00100/01000',
 '|':'00100/00100/00100/00100/00100/00100/00100',
 ' ':'00000/00000/00000/00000/00000/00000/00000',
 '?':'01110/10001/00001/00010/00100/00000/00100',
}


class Rect(C.Structure):
    _fields_ = [(name,C.c_int) for name in ('x','y','w','h')]


class Event(C.Union):
    _fields_ = [('type',C.c_uint32),('raw',C.c_ubyte*56),('alignment',C.c_uint64)]


def library(proton=None,explicit=None):
    if explicit:
        return C.CDLL(str(Path(explicit).resolve(strict=True)))
    bundled = getattr(sys, '_MEIPASS', None)
    candidates = ([str(Path(bundled)/'libSDL2-2.0.so.0')] if bundled else [])
    candidates += [ctypes.util.find_library('SDL2-2.0'), ctypes.util.find_library('SDL2'),
                  '/usr/lib/libSDL2-2.0.so.0', '/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0']
    if proton:
        candidates += [str(Path(proton).parent/p) for p in
                       ('files/lib64/libSDL2-2.0.so.0','dist/lib64/libSDL2-2.0.so.0')]
    for name in dict.fromkeys(n for n in candidates if n):
        try:
            return C.CDLL(name)
        except OSError:
            pass
    raise RuntimeError('SDL2 não encontrada nas bibliotecas existentes. Preserve o pacote e informe a falha; não instale ferramentas por tentativa.')


class Window:
    def __init__(self, proton=None,library_path=None,trace=None):
        self.trace=trace or (lambda *args,**kwargs:None)
        self.sdl = library(proton,library_path)
        self.window = self.renderer = None
        self.controllers, self.textures, self.images, self.fonts = [], {}, OrderedDict(), {}
        self._rumble_controller = None
        self._bind()
        # The native Deck HIDAPI driver disables trackpad mouse emulation even
        # during enumeration. Leave that device to Steam Input; this SDL hint
        # is local to the launcher and is not exported to the Proton child.
        hint=b'SDL_JOYSTICK_HIDAPI_STEAMDECK'
        applied=bool(self.sdl.SDL_SetHintWithPriority(hint,b'0',2))
        disabled=self.sdl.SDL_GetHint(hint)==b'0'
        self.trace('input_policy',steam_deck_hidapi_disabled=disabled,
                   hint_applied=applied)
        if not applied or not disabled:
            raise RuntimeError('Could not preserve Steam Input ownership of the Steam Deck controller')
        if self.sdl.SDL_Init(0x20|0x2000) != 0:
            raise RuntimeError(self.error())
        try:
            self.window = self.sdl.SDL_CreateWindow(b'ac-deck',0x2FFF0000,0x2FFF0000,1280,800,0x24)
            if not self.window:
                raise RuntimeError(self.error())
            # The loop already limits frames. Avoid a compositor vsync wait
            # preventing Steam's close request from reaching the loop.
            self.renderer = self.sdl.SDL_CreateRenderer(self.window,-1,2)
            if not self.renderer:
                self.renderer = self.sdl.SDL_CreateRenderer(self.window,-1,1)
            if not self.renderer:
                raise RuntimeError(self.error())
            self.sdl.SDL_RenderSetLogicalSize(self.renderer,1280,800)
            self.connect()
        except Exception:
            self.close()
            raise

    def _bind(self):
        P, I, U, B = C.c_void_p, C.c_int, C.c_uint32, C.c_uint8
        specs = {
            'SDL_Init':(I,[U]),'SDL_Quit':(None,[]),'SDL_GetError':(C.c_char_p,[]),
            'SDL_SetHintWithPriority':(I,[C.c_char_p,C.c_char_p,I]),
            'SDL_GetHint':(C.c_char_p,[C.c_char_p]),
            'SDL_StartTextInput':(None,[]),'SDL_StopTextInput':(None,[]),
            'SDL_GetClipboardText':(P,[]),'SDL_free':(None,[P]),
            'SDL_CreateWindow':(P,[C.c_char_p,I,I,I,I,U]), 'SDL_DestroyWindow':(None,[P]),
            'SDL_CreateRenderer':(P,[P,I,U]),'SDL_DestroyRenderer':(None,[P]),
            'SDL_RenderSetLogicalSize':(I,[P,I,I]), 'SDL_SetRenderDrawColor':(I,[P,B,B,B,B]),
            'SDL_RenderClear':(I,[P]), 'SDL_RenderFillRect':(I,[P,C.POINTER(Rect)]),
            'SDL_RenderCopy':(I,[P,P,C.POINTER(Rect),C.POINTER(Rect)]),
            'SDL_RenderPresent':(None,[P]),'SDL_RenderReadPixels':(I,[P,P,U,P,I]),
            'SDL_CreateRGBSurfaceFrom':(P,[P,I,I,I,I,U,U,U,U]),
            'SDL_FreeSurface':(None,[P]),'SDL_CreateTextureFromSurface':(P,[P,P]),
            'SDL_SetTextureColorMod':(I,[P,B,B,B]),'SDL_SetTextureBlendMode':(I,[P,I]),
            'SDL_DestroyTexture':(None,[P]),'SDL_PollEvent':(I,[C.POINTER(Event)]),
            'SDL_NumJoysticks':(I,[]),'SDL_IsGameController':(I,[I]),
            'SDL_GameControllerOpen':(P,[I]),'SDL_GameControllerClose':(None,[P]),
            'SDL_GameControllerGetAxis':(C.c_int16,[P,I]),
            'SDL_GameControllerGetButton':(B,[P,I]),
            'SDL_GameControllerGetAttached':(I,[P]),
            'SDL_GameControllerRumble':(I,[P,C.c_uint16,C.c_uint16,U]),
            'SDL_GameControllerName':(C.c_char_p,[P]),
            'SDL_GameControllerGetVendor':(C.c_uint16,[P]),
            'SDL_GameControllerGetProduct':(C.c_uint16,[P]),
            'SDL_GetWindowFlags':(U,[P]),
            'SDL_HideWindow':(None,[P]),'SDL_ShowWindow':(None,[P]),'SDL_RaiseWindow':(None,[P]),
        }
        for name,(result,args) in specs.items():
            func = getattr(self.sdl,name)
            func.restype,func.argtypes = result,args

    def error(self):
        return self.sdl.SDL_GetError().decode('utf-8',errors='replace')

    def connect(self):
        self.driving_rumble(0,0)
        self._rumble_controller = None
        self._trigger_held = set()
        for controller in self.controllers:
            self.sdl.SDL_GameControllerClose(controller)
        self.controllers = [self.sdl.SDL_GameControllerOpen(i) for i in range(self.sdl.SDL_NumJoysticks())
                            if self.sdl.SDL_IsGameController(i)]
        self.controllers = [c for c in self.controllers if c]

    def driving_rumble(self, left, right):
        """Only Steam Input's virtual Deck output; never enable physical HIDAPI."""
        left,right=(max(0.0,min(1.0,value)) for value in (left,right))
        target=getattr(self,'_rumble_controller',None)
        if target is None and (left or right):
            matches=[]
            for controller in self.controllers:
                raw=self.sdl.SDL_GameControllerName(controller)
                name=raw.decode('utf-8',errors='replace').casefold() if isinstance(raw,bytes) else ''
                vendor=self.sdl.SDL_GameControllerGetVendor(controller)
                product=self.sdl.SDL_GameControllerGetProduct(controller)
                if 'steam virtual' in name or (vendor,product)==(0x28de,0x11ff):
                    matches.append(controller)
            if len(matches)==1:
                target=matches[0]
                self._rumble_controller=target
        if target is None:
            return not (left or right)
        return self.sdl.SDL_GameControllerRumble(target,round(left*65535),round(right*65535),40)==0

    def rect(self, x,y,w,h,color):
        self.sdl.SDL_SetRenderDrawColor(self.renderer,*color,255)
        self.sdl.SDL_RenderFillRect(self.renderer,C.byref(Rect(x,y,w,h)))

    def _font(self, scale, style=None):
        from PIL import ImageFont
        key=(scale,style)
        if key not in self.fonts:
            bundled=getattr(sys,'_MEIPASS',None)
            name='DejaVuSans.ttf'
            candidates=([Path(bundled)/'ui'/name] if bundled else [])
            candidates += [Path('/usr/share/fonts/truetype/dejavu')/name,
                           Path('C:/Windows/Fonts/segoeui.ttf')]
            font=next((path for path in candidates if path.is_file()),None)
            size=max(12,int(round(scale*10)))
            self.fonts[key]=ImageFont.truetype(str(font),size) if font else ImageFont.load_default(size=size)
        return self.fonts[key]

    def begin_text_frame(self, context=None, *, now=None):
        """Mantém os relógios somente dos nomes visíveis nesta tela."""
        now = time.monotonic() if now is None else now
        previous = getattr(self, '_text_frame_time', None)
        frame = getattr(self, '_text_frame', 0)
        if (previous is None or context != getattr(self, '_text_context', None)
                or now < previous or now-previous > 1):
            self._text_scrolls = {}
        else:
            self._text_scrolls = {key: value for key, value in self._text_scrolls.items()
                                 if value[2] == frame}
        self._text_frame_time, self._text_frame = now, frame+1
        self._text_context = context

    def text(self, value,x,y,scale=2,color=(221,230,235),limit=90,style=None,max_width=None,
             scroll_key=None):
        value = str(value)
        if scroll_key is not None and max_width is not None:
            if not value or max_width <= 0:
                return
            if not hasattr(self, '_text_scrolls'):
                self.begin_text_frame()
            texture,width,height = self._text_texture(value,scale,style)
            visible = min(width, int(max_width))
            if visible <= 0:
                return
            offset = 0
            if width > visible:
                signature = (value,scale,style,visible)
                state = self._text_scrolls.get(scroll_key)
                now = self._text_frame_time
                start = state[1] if state and state[0] == signature else now
                self._text_scrolls[scroll_key] = (signature,start,self._text_frame)
                distance = width-visible
                # Dois segundos para ler cada extremidade; 36 pixels lógicos/s.
                phase = max(0,now-start) % (4+distance/36)
                offset = int(min(distance,max(0,(phase-2)*36)))
            else:
                self._text_scrolls.pop(scroll_key, None)
            self.sdl.SDL_SetTextureColorMod(texture,*color)
            self.sdl.SDL_RenderCopy(self.renderer,texture,C.byref(Rect(offset,0,visible,height)),
                                    C.byref(Rect(x,y,visible,height)))
            return
        if len(value)>limit:
            value=value[:limit-3]+'...'
        if not value:
            return
        if max_width is not None:
            try:
                font=self._font(scale,style)
                original=value
                while value and font.getlength(value)>max_width:
                    value=value[:-1]
                if value!=original:
                    while value and font.getlength(value+'...')>max_width:
                        value=value[:-1]
                    value=value+'...' if value else ''
            except ImportError:
                cell_width=6*max(1,int(round(scale)))
                value=value[:max(0,int(max_width/cell_width))]
        if not value:
            return
        texture,width,height=self._text_texture(value,scale,style)
        self.sdl.SDL_SetTextureColorMod(texture,*color)
        self.sdl.SDL_RenderCopy(self.renderer,texture,None,C.byref(Rect(x,y,width,height)))

    def _text_texture(self, value, scale, style=None):
        """Reutiliza a textura completa; o recorte da rolagem não cria bitmaps."""
        key=(value,scale,style)
        if key not in self.textures:
            if len(self.textures)>512:
                for texture,_,_ in self.textures.values():
                    self.sdl.SDL_DestroyTexture(texture)
                self.textures.clear()
            try:
                from PIL import Image, ImageDraw
                font=self._font(scale,style)
                left,top,right,bottom=font.getbbox(value)
                width,height=max(1,right-left),max(1,bottom-top)
                bitmap=Image.new('RGBA',(width,height))
                ImageDraw.Draw(bitmap).text((-left,-top),value,font=font,fill='white')
                if style=='brand':
                    # Marca autoral com a mesma fonte livre já distribuída.
                    # Inclinação/peso não exigem outra fonte no runtime.
                    padding=max(2,int(height*.22))
                    branded=Image.new('RGBA',(width+padding+4,height+4))
                    ImageDraw.Draw(branded).text((padding-left+1,1-top),value,font=font,
                        fill='white',stroke_width=1,stroke_fill='white')
                    bitmap=branded.transform(branded.size,Image.Transform.AFFINE,
                        (1,.20,-padding,0,1,0),resample=Image.Resampling.BICUBIC)
                    width,height=bitmap.size
                raw=bytearray(bitmap.tobytes())
            except ImportError:
                # A prévia por fonte ainda abre sem Pillow; o build inclui-o.
                scale=max(1,int(round(scale)))
                value=''.join(c for c in unicodedata.normalize('NFKD',value).upper()
                              if not unicodedata.combining(c))
                width,height=len(value)*6*scale,8*scale
                raw=bytearray(width*height*4)
                for i,char in enumerate(value):
                    for yy,row in enumerate(FONT.get(char,FONT['?']).split('/')):
                        for xx,bit in enumerate(row):
                            if bit=='1':
                                for dy in range(scale):
                                    for dx in range(scale):
                                        offset=((yy*scale+dy)*width+(i*6+xx)*scale+dx)*4
                                        raw[offset:offset+4]=b'\xff\xff\xff\xff'
            pixels=(C.c_ubyte*len(raw)).from_buffer(raw)
            surface=self.sdl.SDL_CreateRGBSurfaceFrom(pixels,width,height,32,width*4,0xff,0xff00,0xff0000,0xff000000)
            if not surface:
                raise RuntimeError(self.error())
            try:
                texture=self.sdl.SDL_CreateTextureFromSurface(self.renderer,surface)
            finally:
                self.sdl.SDL_FreeSurface(surface)
            if not texture:
                raise RuntimeError(self.error())
            self.sdl.SDL_SetTextureBlendMode(texture,1)
            self.textures[key]=(texture,width,height)
        return self.textures[key]

    def events(self):
        event=Event()
        actions=[]
        while self.sdl.SDL_PollEvent(C.byref(event)):
            raw=bytes(event.raw)
            if event.type==0x100 or (event.type==0x200 and raw[12]==14):
                # O gerenciador pode enviar CLOSE sem gerar SDL_QUIT,
                # conforme a política da SDL para a última janela.
                actions.append('quit')
            elif event.type==0x300:
                if raw[13]:  # Repetição de tecla mantida não confirma ações.
                    continue
                key=struct.unpack_from('=i',raw,20)[0]
                action=('paste_key' if key==118 and struct.unpack_from('=H',raw,24)[0]&0xc0 else
                        'select_all_text' if key==97 and struct.unpack_from('=H',raw,24)[0]&0xc0 else
                        'delete_text' if key==127 else 'cursor_home' if key==1073741898 else
                        'cursor_end' if key==1073741901 else
                        {27:'back',13:'accept',8:'erase_key',32:'launch',9:'tab_next',
                        1073741891:'request_quit',
                        1073741906:'up',1073741905:'down',1073741904:'left',1073741903:'right',
                        1073741899:'page_up',1073741902:'page_down',120:'launch',121:'skin'}.get(key))
                if action:
                    actions.append(action)
                    if action in ('back','request_quit'):
                        self.trace('input',source='keyboard',keycode=key,
                                   sdl_timestamp_ms=struct.unpack_from('=I',raw,4)[0])
            elif event.type==0x303:
                actions.append(('key_text',raw[12:44].split(b'\0',1)[0].decode('utf-8',errors='replace')))
            elif event.type==0x651:
                action={0:'accept',1:'back',2:'launch',3:'skin',4:'request_quit',6:'launch',
                        9:'tab_prev',10:'tab_next',11:'up',12:'down',13:'left',14:'right'}.get(raw[12])
                if action:
                    actions.append(action)
                    if action in ('back','request_quit'):
                        self.trace('input',source='controller',button=raw[12],
                                   sdl_timestamp_ms=struct.unpack_from('=I',raw,4)[0])
            elif event.type in (0x653,0x654):
                self.connect()
            elif event.type==0x401 and raw[16]==1:
                actions.append(('click',*struct.unpack_from('=ii',raw,20)))
            elif event.type==0x403:
                actions.append('up' if struct.unpack_from('=i',raw,20)[0]>0 else 'down')
        return actions

    def clipboard(self):
        pointer=self.sdl.SDL_GetClipboardText()
        if not pointer:
            return ''
        try:
            return C.string_at(pointer).decode('utf-8',errors='replace')[:512]
        finally:
            self.sdl.SDL_free(pointer)

    def text_input(self,active):
        (self.sdl.SDL_StartTextInput if active else self.sdl.SDL_StopTextInput)()

    def focused(self):
        """Consulta foco local; não solicita foco nem injeta entrada."""
        return bool(self.sdl.SDL_GetWindowFlags(self.window)&0x200)

    def image(self,candidates,x,y,width,height,fit='contain',background=(10,17,25)):
        if fit not in ('contain','cover'):
            raise ValueError('Unknown image fit')
        key=(tuple(map(str,candidates)),width,height,fit)
        if key not in self.images:
            if len(self.images)>=32:
                _,cached=self.images.popitem(last=False)
                if cached:
                    self.sdl.SDL_DestroyTexture(cached[0])
            entry=None
            for path in candidates:
                loaded=previews.thumbnail(path,(min(2048,width*2),min(2048,height*2)) if fit=='cover' else (width,height))
                if loaded is None:
                    continue
                iw,ih,raw=loaded
                if fit=='cover':
                    from PIL import Image,ImageOps
                    bitmap=ImageOps.fit(Image.frombytes('RGBA',(iw,ih),raw),(width,height),method=Image.Resampling.LANCZOS)
                    iw,ih=bitmap.size
                    raw=bitmap.tobytes()
                pixels=(C.c_ubyte*len(raw)).from_buffer_copy(raw)
                surface=self.sdl.SDL_CreateRGBSurfaceFrom(pixels,iw,ih,32,iw*4,0xff,0xff00,0xff0000,0xff000000)
                if not surface:
                    continue
                try:
                    texture=self.sdl.SDL_CreateTextureFromSurface(self.renderer,surface)
                finally:
                    self.sdl.SDL_FreeSurface(surface)
                if texture:
                    self.sdl.SDL_SetTextureBlendMode(texture,1)
                    entry=(texture,iw,ih)
                    break
            self.images[key]=entry
        self.images.move_to_end(key)
        if background is not None:
            self.rect(x,y,width,height,background)
        entry=self.images[key]
        if entry:
            texture,iw,ih=entry
            self.sdl.SDL_RenderCopy(self.renderer,texture,None,C.byref(Rect(x+(width-iw)//2,y+(height-ih)//2,iw,ih)))
        else:
            self.text('No preview',x+16,y+height//2-8,2,color=(135,155,174))

    def stick(self):
        for controller in self.controllers:
            if self.sdl.SDL_GameControllerGetAttached(controller):
                axis=self.sdl.SDL_GameControllerGetAxis(controller,1)
                if abs(axis)>16000:
                    return 'down' if axis>0 else 'up'
        return None

    def shoulders(self):
        held=set()
        for controller in self.controllers:
            if self.sdl.SDL_GameControllerGetAttached(controller):
                for button,action in ((9,'tab_prev'),(10,'tab_next')):
                    if self.sdl.SDL_GameControllerGetButton(controller,button):
                        held.add(action)
        return held

    def triggers(self):
        # SDL controller axes are normalized to 0..32767. Hysteresis avoids
        # treating noise near the press threshold as another press.
        previous=getattr(self,'_trigger_held',set())
        held=set()
        actions=set()
        for controller in self.controllers:
            if self.sdl.SDL_GameControllerGetAttached(controller):
                for axis,action in ((4,'page_up'),(5,'page_down')):
                    value=self.sdl.SDL_GameControllerGetAxis(controller,axis)
                    if value>=(8000 if (controller,axis) in previous else 16000):
                        held.add((controller,axis))
                        actions.add(action)
        self._trigger_held=held
        return actions

    def screenshot(self,path):
        width,height=1280,800
        data=(C.c_ubyte*(width*height*4))()
        if self.sdl.SDL_RenderReadPixels(self.renderer,None,0x16762004,data,width*4):
            raise RuntimeError(self.error())
        pixels=bytes(data)
        def chunk(kind,value):
            return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value))
        scanlines=b''.join(b'\0'+pixels[y*width*4:(y+1)*width*4] for y in range(height))
        raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))
        raw+=chunk(b'IDAT',zlib.compress(scanlines))+chunk(b'IEND',b'')
        with Path(path).open('xb') as output:
            output.write(raw)

    def close(self):
        self.driving_rumble(0,0)
        for cached in self.images.values():
            if cached:
                self.sdl.SDL_DestroyTexture(cached[0])
        for texture,_,_ in self.textures.values():
            self.sdl.SDL_DestroyTexture(texture)
        for controller in self.controllers:
            self.sdl.SDL_GameControllerClose(controller)
        if self.renderer:
            self.sdl.SDL_DestroyRenderer(self.renderer)
        if self.window:
            self.sdl.SDL_DestroyWindow(self.window)
        self.sdl.SDL_Quit()


class Menu:
    tabs=('CARS','TRACKS','EVENTS','SESSION','GRAPHICS','SETTINGS','Event Synthetizer')
    options=('Mode','Livery','Weather','Opponents','AI level','Laps','Minutes',
             'Automatic gearbox','Time of day','Automatic clutch')
    graphics_options=('Profile','Resolution','FPS and frametime','PP filter')

    def __init__(self,catalog,selection=None,*,csp=False,game=None,synthesis_store=None,catalog_cache=False,pp_filter_cache=None):
        self.catalog_cache=bool(catalog_cache)
        if self.catalog_cache and game is not None and not all(key in catalog for key in ('synthesis_classes','synthesis_weather')):
            # O catálogo básico já foi lido ao abrir o app. Acrescentar os
            # metadados uma vez; trocar de área não deve reler a instalação.
            catalog=event_synthetizer.discover(game,catalog=catalog)
        self.catalog=catalog
        self.game=Path(game) if game is not None else None
        self.preview_cache={}
        self.csp=csp
        self.graphics_labels={key:value for key,value in GRAPHICS_LABELS.items() if csp or not graphics.uses_csp(key)}
        self.pp_filters=(list(pp_filter_cache) if pp_filter_cache is not None else
                         [None]+(pp_filters(self.game) if self.game is not None else []))
        self.tabs=type(self).tabs
        self.graphics_keys=('graphics_profile','resolution','hud','pp_filter','frame_limiter')+(('smart_shadows','shadow_distance_m') if csp else ())+graphics_settings.keys(csp)
        self.graphics_options=type(self).graphics_options+('Frame limiter',)+(('Smart Shadows (CSP)','Shadow distance (CSP)') if csp else ())+graphics_settings.labels(csp)
        self.control_keys=tuple(chase_camera.SETTINGS if csp else ())+(('control_mode',) if csp else ())+tuple(controls.FIELDS)+(
            'steer_gamma_tenths','hide_driver_arms','virtual_steer_degrees',*controls.BINDINGS,
            'car_damage_pct','abs_mode','traction_control','stability_control')+tuple(comfort.SETTINGS if csp else ())+tuple(driving_haptics.SETTINGS if csp else ())
        self.options=type(self).options+(('Improved AI (CSP)','Experimental AI (CSP)') if csp else ())
        if not catalog['cars'] or not catalog['tracks'] or not catalog['weather']:
            raise ValueError('No usable cars, tracks or weather in the catalog')
        self.selection=dict(car=catalog['cars'][0]['id'],track=catalog['tracks'][0]['id'],
            layout=catalog['tracks'][0]['layout'],mode=0,opponents=5,ai=90,laps=5,minutes=20,
            automatic=True,resolution=[1280,800],hud=True,weather=catalog['weather'][0],event='',
            graphics_profile='csp_performance' if csp else 'performance',control_mode='assisted' if csp else 'original',
            graphics_profiles_version=2,time_minutes=None,pp_filter=None,
            ai_behavior='improved' if csp else 'original',ai_experimental=False,
            **(dict.fromkeys(controls.FIELDS)|controls.DEFAULTS|comfort.DEFAULTS|chase_camera.DEFAULTS|driving_haptics.DEFAULTS))
        self.selection.update(graphics.normalize(selection or {},csp_available=csp))
        if (self.selection['chase_camera'] in chase_camera.BACC
                and not any(key in (selection or {}) for key in chase_camera.GEOMETRY)):
            self.selection.update(chase_camera.geometry_defaults(self.selection['chase_camera']))
        if (selection or {}).get('controls_version') != 1 and self.selection['steer_deadzone_pct'] is None:
            self.selection['steer_deadzone_pct']=0
        self.selection['controls_version']=1
        if isinstance(self.selection.get('mirrors'),str) and self.selection['mirrors'] in comfort.MIRRORS:
            self.selection['mirrors']='off'
        if self.selection.get('graphics_profile') not in self.graphics_labels:
            value=self.selection.get('graphics_profile')
            self.selection['graphics_profile']=graphics.base_profile(value) if value in GRAPHICS_LABELS else 'performance'
        if self.selection.get('pp_filter') not in self.pp_filters:
            self.selection['pp_filter']=None
        if self.selection.get('control_mode') not in controls.MODES:
            self.selection['control_mode']='assisted' if csp else 'original'
        controls.validate(self.selection)
        comfort.validate(self.selection)
        chase_camera.validate(self.selection)
        conditions.validate(self.selection)
        if self.selection.get('ai_behavior') not in AI_LABELS:
            self.selection['ai_behavior']='improved' if csp else 'original'
        if type(self.selection.get('ai_experimental')) is not bool:
            self.selection['ai_experimental']=False
        car,track=self.car(),self.track()
        self.selection.update(car=car['id'],track=track['id'],layout=track['layout'])
        if self.selection.get('skin') not in car['skins']:
            self.selection['skin']=car['skins'][0]
        self.tab,self.indices,self.offset=0,[catalog['cars'].index(car),catalog['tracks'].index(track)]+[0]*(len(self.tabs)-2),0
        self.message='Choose your race. Press X or Start to drive.'
        self.quit_confirmation=False
        self.quit_selected=False
        self.synthesis_store=synthesis_store
        self.ai_usage_path=ai_usage.path_for(synthesis_store)
        self.ai_report_path=ai_report.path_for(synthesis_store)
        try:self.ai_usage=ai_usage.load(self.ai_usage_path)
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):self.ai_usage=None
        try:self.ai_report=ai_report.load(self.ai_report_path)
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            self.ai_report=ai_report.make('error','Saved AI verdict is unavailable. Previous selection kept.')
        self.synthesis=None
        self.pending_event_base=None
        self.event_options=event_synthetizer.options(self.selection)
        self.event_options_file=Path(synthesis_store).parent/'event-options.json' if synthesis_store is not None else None
        event_state_unavailable=False
        options_loaded=False
        legacy_opponents=False
        if self.event_options_file is not None:
            try:
                event_synthetizer.recover_state(synthesis_store,self.event_options_file)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError):
                event_state_unavailable=True
                self.message='Pending event update unavailable. Original files kept; manual settings preserved.'
        if self.event_options_file is not None and not event_state_unavailable:
            try:
                stored=event_synthetizer.load(self.event_options_file)
                if stored is not None:
                    self.event_options=event_synthetizer.options(self.selection,stored)
                    options_loaded=True
                    legacy_opponents='opponents' not in stored
            except (OSError,ValueError,RuntimeError,KeyError,TypeError):
                self.message='Saved event settings unavailable. Manual settings preserved.'
        self.api_key=''
        self.ai_preferences=ai_preferences.clean()
        self.ai_preferences_path=ai_preferences.path_for(synthesis_store) if synthesis_store is not None else None
        if self.ai_preferences_path is not None:
            try:self.ai_preferences=ai_preferences.load(self.ai_preferences_path)
            except (OSError,ValueError,RuntimeError):
                self.message='Saved AI preferences unavailable. Edit them in AI settings.'
        self.key_dialog=False
        self.key_buffer=''
        self.key_focus=0
        self.ai_pending=None
        self.ai_effort=ai_events.EFFORT
        self.ai_settings=Path(synthesis_store).parent/'ai-settings.json' if synthesis_store is not None else None
        if self.ai_settings is not None:
            try:
                settings=event_synthetizer.load(self.ai_settings)
                if isinstance(settings,dict) and settings.get('effort') in ai_events.EFFORTS:
                    self.ai_effort=settings['effort']
            except (OSError,ValueError,RuntimeError):
                self.message='AI effort reset to low. Other settings are preserved.'
        self.key_path=api_credentials.path_for(synthesis_store) if synthesis_store is not None else None
        if self.key_path is not None:
            try:
                self.api_key=api_credentials.load(self.key_path)
            except (OSError,ValueError,RuntimeError):
                self.message='Local API key unavailable. Paste it again in Event Synthetizer.'
        if synthesis_store is not None and not event_state_unavailable:
            try:
                proposal=event_synthetizer.load(synthesis_store)
                if proposal is not None:
                    self.replace_catalog(event_synthetizer.validate(self.game,proposal,**self.event_catalog_args()))
                    updated=self.event_with_current_hud(proposal)
                    hud_changed=updated!=proposal
                    proposal=updated
                    self.pending_event_base=deepcopy(proposal['base'])
                    if not options_loaded:
                        self.event_options=event_synthetizer.options(proposal['selection'],
                            dict(pins=event_synthetizer.pins(proposal.get('pins')),
                                 laps=proposal['selection']['laps'],ai=proposal['selection']['ai']))
                    elif legacy_opponents:
                        self.event_options['opponents']=proposal['selection']['opponents']
                    if event_synthetizer.matches(proposal,self.event_options):
                        if hud_changed:
                            event_synthetizer.save_state(synthesis_store,proposal,self.event_options_file,self.event_options)
                        self.synthesis=proposal
            except (OSError,ValueError,KeyError,TypeError):
                self.message='Saved generated event unavailable. Generate a new event; manual choices are preserved.'

    def car(self):
        return next((p for p in self.catalog['cars'] if p['id']==self.selection['car']),self.catalog['cars'][0])

    def track(self):
        return next((p for p in self.catalog['tracks'] if (p['id'],p['layout'])==(self.selection['track'],self.selection['layout'])),self.catalog['tracks'][0])

    def replace_catalog(self,catalog):
        changed=catalog!=self.catalog
        focused=[]
        groups=(('cars',('id',)),('tracks',('id','layout')),('events',('id',)))
        for tab,(group,keys) in enumerate(groups):
            previous=self.catalog[group]
            index=self.indices[tab]
            focused.append(tuple(previous[index][key] for key in keys) if 0<=index<len(previous) else None)
        self.catalog=catalog
        car,track=self.car(),self.track()
        self.selection.update(car=car['id'],track=track['id'],layout=track['layout'])
        if self.selection.get('skin') not in car['skins']:
            self.selection['skin']=car['skins'][0]
        if self.selection['weather'] not in catalog['weather']:
            self.selection['weather']=catalog['weather'][0]
        if self.selection.get('event') and not any(row['id']==self.selection['event'] and row.get('available',True) for row in catalog['events']):
            self.selection['event']=''
        for tab,(group,keys) in enumerate(groups):
            self.indices[tab]=next((index for index,row in enumerate(catalog[group])
                if tuple(row[key] for key in keys)==focused[tab]),
                max(0,min(self.indices[tab],len(catalog[group])-1)))
        if changed:self.preview_cache.clear()

    def event_catalog_args(self):
        if self.catalog_cache and 'synthesis_classes' in self.catalog and 'synthesis_weather' in self.catalog:
            return dict(catalog=self.catalog)
        return {}

    def clamp_index(self,tab):
        self.indices[tab]=max(0,min(self.indices[tab],len(self.rows(tab))-1))

    def rows(self,tab=None):
        tab=self.tab if tab is None else tab
        if tab==6:
            rows=[dict(name='Generate without AI'),
                  dict(name='Generate with AI'+(' : generating...' if self.ai_pending else '')),
                  dict(name='API key : '+('configured (hidden)' if self.api_key else 'not set')),
                  dict(name='Reasoning effort : '+self.ai_effort)]
            fixed=self.event_options['pins']
            car=next((c['name'] for c in self.catalog['cars'] if c['id']==fixed['car']),fixed['car'])
            track=next((t['name'] for t in self.catalog['tracks'] if [t['id'],t['layout']]==fixed['track']),
                       ' / '.join(fixed['track']) if fixed['track'] else None)
            when=self.synthesis['selection']['time_minutes'] if self.synthesis else None
            rows.extend(dict(name=value) for value in (
                'Pin car : '+('On / '+car if fixed['car'] else 'Off (A pins shown car)'),
                'Pin track : '+('On / '+track if fixed['track'] else 'Off (A pins shown track)'),
                'Laps : '+str(self.event_options['laps']),
                'AI level : '+str(self.event_options['ai'])+'%',
                'Opponents : '+str(self.event_options['opponents']),
                'Time of the Day : '+(f'{when//60:02}:{when%60:02}' if when is not None else 'Generate first')))
            if self.synthesis:
                p=self.synthesis
                s=p['selection']
                rows.extend(dict(name=value) for value in (
                    'Class : '+p['class_name'], 'Car : '+p['car_name'], 'Track : '+p['track_name'],
                    'Weather : '+s['weather'],
                    f"Race : {s['opponents']} opponents / AI {s['ai']} / {s['laps']} laps",
                    'Current preferences apply. X / Start to drive.'))
            else:
                rows.append(dict(name='Generate a race from installed content.'))
            return rows
        if tab==3:
            s=self.selection
            values=(MODES[s['mode']][0],s['skin'],s['weather'],s['opponents'],s['ai'],s['laps'],
                    s['minutes'],'On' if s['automatic'] else 'Off',
                    'From session' if s['time_minutes'] is None else
                    f"{s['time_minutes']//60:02}:{s['time_minutes']%60:02}",
                    'On' if s['automatic_clutch'] else 'Off')
            if self.csp:
                values+=('On' if s['ai_behavior']=='improved' else 'Off',
                         'On' if s['ai_experimental'] else 'Off')
            return [dict(name=key+' : '+str(value)) for key,value in zip(self.options,values)]
        if tab==4:
            s=self.selection
            values=(GRAPHICS_LABELS[s['graphics_profile']], ' x '.join(map(str,s['resolution'])),
                    'On' if s['hud'] else 'Off',s['pp_filter'] or 'Keep current')
            values+=(comfort.LIMITERS[s['frame_limiter']],)
            if self.csp:
                values+=('On' if s['smart_shadows'] else 'Off',str(s['shadow_distance_m'])+' m')
            values+=graphics_settings.rows(s,self.csp)
            return [dict(name=key+' : '+str(value)) for key,value in zip(self.graphics_options,values)]
        if tab==5:
            rows=[]
            if self.csp:
                for key,label in chase_camera.SETTINGS.items():
                    value=self.selection[key]
                    choices=chase_camera.CHOICES[key]
                    shown=choices[value] if isinstance(choices,dict) else format(value,'.2f')
                    if key=='chase_fov' and self.selection['chase_camera']==chase_camera.GT5:
                        shown='45 (GT5 fixed)'
                    elif key=='chase_fov' and self.selection['chase_camera'] in chase_camera.BACC:
                        shown='Dynamic (BACC script)'
                    rows.append(dict(name=label+' : '+shown))
                rows.append(dict(name='Steering : '+controls.MODES[self.selection['control_mode']]))
            for key,(_,label) in controls.FIELDS.items():
                value=self.selection.get(key)
                rows.append(dict(name=label+' : '+('Keep current' if value is None else str(value)+'%')))
            gamma=self.selection['steer_gamma_tenths']
            degrees=self.selection['virtual_steer_degrees']
            rows.extend((dict(name='Steering gamma : '+('Keep current' if gamma is None else format(gamma/10,'.1f'))),
                dict(name='Hide driver arms : '+('On' if self.selection['hide_driver_arms'] else 'Off')),
                dict(name='Virtual steering : '+('Unlimited' if degrees==0 else str(degrees)+' degrees'))))
            rows.extend(dict(name=label+' : '+controls.BUTTONS[self.selection[key]])
                        for key,(_,label,_) in controls.BINDINGS.items())
            damage=self.selection['car_damage_pct']
            rows.append(dict(name='Car damage : '+('Keep current' if damage is None else str(damage)+'%')))
            rows.append(dict(name='ABS : '+comfort.ASSIST_LABELS[self.selection['abs_mode']]))
            rows.append(dict(name='Traction control : '+comfort.ASSIST_LABELS[self.selection['traction_control']]))
            rows.append(dict(name='Stability control : '+str(self.selection['stability_control'])+'%'))
            if self.csp:
                rows.extend(dict(name=label+' : '+(str(round(self.selection[key]*100))+'%' if key=='csp_ui_scale'
                    else 'On' if self.selection[key] else 'Off')) for key,label in comfort.SETTINGS.items())
                rows.extend(dict(name=label+' : '+(('On' if self.selection[key] else 'Off') if key=='driving_haptics'
                    else str(self.selection[key])+'%')) for key,label in driving_haptics.SETTINGS.items())
            return rows
        return self.catalog[('cars','tracks','events')[tab]]

    def change(self,delta):
        s=self.selection
        keys=(self.control_keys if self.tab==5 else
              self.graphics_keys if self.tab==4 else
              ('mode','skin','weather','opponents','ai','laps','minutes','automatic','time_minutes','automatic_clutch')+
              (('ai_behavior','ai_experimental') if self.csp else ()))
        key=keys[self.indices[self.tab]]
        if key=='hud':
            previous=s[key]
            s[key]=not previous
            try:
                self.sync_event_hud()
                self.message='FPS and frametime: '+('On' if s[key] else 'Off')+'. Applies to manual and generated races.'
            except (OSError,ValueError,RuntimeError):
                s[key]=previous
                self.message='Could not save FPS and frametime setting. Previous value kept.'
            return
        if key=='chase_camera':
            values=list(chase_camera.MODES)
            chase_camera.switch_style(s,values[(values.index(s[key])+delta)%len(values)])
            self.message='Use CSP Performance or CSP Quality, then start and use Change view. Camera style restores its saved framing; first use loads recommended values. Driving controls stay unchanged.'
            return
        if key=='chase_fov' and s['chase_camera'] in chase_camera.BACC:
            self.message='BACC controls its own dynamic FOV. Your adjustable camera FOV stays saved.'
            return
        if key=='chase_fov' and s['chase_camera']==chase_camera.GT5:
            self.message='GT5 Spec 2.0 fixes FOV at 45 degrees. Your adjustable camera FOV stays saved.'
            return
        if key=='stability_control':
            s[key]=max(0,min(100,s[key]+delta))
            self.message='Stability control: 0% off, 100% maximum assistance. Applies next session.'
            return
        if key=='car_damage_pct':
            if s[key] is None:
                s[key]=0 if delta>0 else 100
            else:
                value=((s[key]//10+1)*10 if delta>0 else ((s[key]-1)//10)*10)
                s[key]=value if 0<=value<=100 else None
            self.message='Car damage: 0% off, 100% normal. Keep current preserves the existing value. Applies next session.'
            return
        if key=='time_minutes':
            if s[key] is None:
                s[key]=600
            else:
                value=s[key]+15*delta
                s[key]=value if conditions.MINUTES_MIN<=value<=conditions.MINUTES_MAX else None
            self.message='Time of day, 08:00 to 18:00. From session preserves event conditions.'
            return
        if key in controls.FIELDS:
            defaults=dict(steer_speed_pct=20,steer_filter_pct=60,speed_sensitivity_pct=50,
                          steer_deadzone_pct=5,rumble_pct=100)
            if s[key] is None:
                s[key]=defaults[key]
            else:
                value=s[key]+5*delta
                s[key]=value if 0<=value<=100 else None
            self.message='Applies next session. Keep current preserves the existing value.'
            return
        if key=='steer_gamma_tenths':
            values=[None,*range(1,51)]
            s[key]=values[(values.index(s[key])+delta)%len(values)]
            self.message='Steering gamma. Keep current preserves the existing value.'
            return
        if key.startswith('gfx:'):
            graphics_settings.change(s,key[4:],delta)
            self.message='Saved for the next session. Choosing a profile replaces graphics values.'
            return
        if key=='smart_shadows':
            s[key]=not s[key]
            self.message='Smart Shadows: '+('On. Saved shadow distance applies next CSP session.' if s[key] else 'Off. Native shadows remain; saved CSP shadow distance is inactive.')
            return
        if key=='shadow_distance_m':
            s[key]=max(graphics.SHADOW_DISTANCE_MIN,min(graphics.SHADOW_DISTANCE_MAX,s[key]+10*delta))
            self.message='Shadow distance: 50 to 400 m. Saved; applies to CSP profiles next session. Enable Smart Shadows to use it; resolution can limit the visible range.'
            return
        if key=='virtual_steer_degrees':
            s[key]=max(0,min(1080,s[key]+10*delta))
            self.message='Steering wheel animation only. Physics are unchanged.'
            return
        if key in controls.BINDINGS:
            values=list(controls.BUTTONS)
            controls.set_binding(s,key,values[(values.index(s[key])+delta)%len(values)])
            self.message='In-race buttons. X/Start still starts the race from this menu.'
            return
        choices={'mode':list(range(len(MODES))),'skin':self.car()['skins'],'weather':self.catalog['weather'],
                 'driving_haptics':[True,False], 'haptics_left_pct':list(range(0,101,5)),
                 'haptics_right_pct':list(range(0,101,5)),
                 'automatic':[True,False],'resolution':[[1280,800],[1920,1200]],
                 **{key:[True,False] for key,value in comfort.DEFAULTS.items() if type(value) is bool},
                 'frame_limiter':list(comfort.LIMITERS),
                 'abs_mode':list(comfort.ASSIST_MODES),
                 'traction_control':list(comfort.ASSIST_MODES),
                 'csp_ui_scale':list(comfort.SCALES),
                 **{key:list(values) for key,values in chase_camera.choices(s).items()},
                 'hide_driver_arms':[True,False],
                 'pp_filter':self.pp_filters,
                 'graphics_profile':list(self.graphics_labels),'control_mode':list(controls.MODES),
                 'ai_behavior':list(AI_LABELS),'ai_experimental':[False,True]}
        if key in choices:
            values=choices[key]
            s[key]=values[(values.index(s[key])+delta)%len(values)]
            if key=='graphics_profile':
                graphics_settings.reset(s,s[key])
                self.message=GRAPHICS_LABELS[s[key]]+(': CSP enabled.' if graphics.uses_csp(s[key]) else ': base game, CSP disabled.')+' Graphics values replaced with this profile. Controls and comfort stay saved.'
            elif key=='control_mode':
                self.message=('Assisted: CSP Gamepad Force; R3 switches Race/Drift.' if s[key]=='assisted'
                              else 'Original: CSP steering assist off. Analog settings are separate.')
            elif key=='ai_behavior':
                self.message='AI '+AI_LABELS[s[key]]+'. Applies next session; level and grid are unchanged.'
            elif key=='ai_experimental':
                self.message='Alternative CSP AI. Requires Improved AI and a CSP profile. Applies next session.'
            elif key=='pp_filter':
                self.message='Choose an installed native filter, such as default. Sol/Pure are not included.'
            elif key=='automatic_clutch':
                self.message='Automatic clutch is independent of automatic gear shifting. Manual gears still use B/X.'
            elif key in ('abs_mode','traction_control'):
                label='ABS' if key=='abs_mode' else 'Traction control'
                self.message=label+': Off, Factory (only if fitted), or On. Applies next session.'
            elif key=='frame_limiter':
                self.message='Game 60 FPS: disable the Steam external cap. External: game cap off; use your own limiter.'
            elif key in comfort.SETTINGS:
                self.message='Saved preference for CSP profiles. Base profiles keep it saved without applying CSP.'
            elif key in driving_haptics.SETTINGS:
                self.message='Driving feedback: brake left, throttle right. Applies to the next CSP session.'
            elif key in chase_camera.SETTINGS:
                self.message=('GT5 Spec 2.0: installs and repairs from the included archive. FOV is fixed at 45; Change view selects chase views.'
                              if s['chase_camera']==chase_camera.GT5 else
                              'Use CSP Performance or CSP Quality, choose CSP Adjustable or another chase camera, then start and use Change view. Original disables it.')
        else:
            low,high={'opponents':(0,min(47,self.track()['pitboxes']-1)),
                      'ai':(70,100),'laps':(1,99),'minutes':(0,180)}[key]
            s[key]=max(low,min(high,s[key]+delta))
            if key=='opponents':
                self.message=('Opponents are used in Race mode. Choose Mode: Race.'
                    if MODES[s['mode']][1]!=3 else
                    'This track has '+str(self.track()['pitboxes'])+' pit boxes; up to '+str(high)+' opponents.')

    def action(self,action):
        if action=='quit':
            return 'quit'
        if self.key_dialog:
            return self.key_action(action)
        if action=='request_quit':
            self.quit_confirmation=True
            self.quit_selected=False
            return
        if self.quit_confirmation:
            if action=='back':
                self.quit_confirmation=False
            elif action in ('left','right','up','down'):
                self.quit_selected=not self.quit_selected
            elif action=='accept':
                if self.quit_selected:
                    return 'quit_confirmed'
                self.quit_confirmation=False
            elif isinstance(action,tuple) and action[0]=='click':
                _,x,y=action
                if 414<=y<470:
                    if 440<=x<620:
                        self.quit_confirmation=False
                    elif 660<=x<840:
                        return 'quit_confirmed'
            return
        if action=='back':
            if self.tab==0:
                self.message='Use Exit, View or F10 to close the menu.'
            self.tab=0
        elif action in ('tab_next','tab_prev'):
            self.tab=(self.tab+(1 if action=='tab_next' else -1))%len(self.tabs)
        elif action in ('up','down','page_up','page_down'):
            amount=(-1 if action in ('up','page_up') else 1)*(10 if action.startswith('page_') else 1)
            self.indices[self.tab]=(self.indices[self.tab]+amount)%max(1,len(self.rows()))
        elif action in ('left','right'):
            if self.tab==6 and 3<=self.indices[6]<=9:
                if self.indices[6]==3:
                    self.change_effort(1 if action=='right' else -1)
                else:
                    self.change_event_option(self.indices[6],1 if action=='right' else -1)
            elif self.tab in (3,4,5):
                self.change(1 if action=='right' else -1)
            else:
                self.tab=(self.tab+(1 if action=='right' else -1))%len(self.tabs)
        elif action=='skin' and self.tab!=6:
            values=self.car()['skins']
            self.selection['skin']=values[(values.index(self.selection['skin'])+1)%len(values)]
        elif action=='accept':
            rows=self.rows()
            if not rows:
                return
            item=rows[self.indices[self.tab]]
            if self.tab==0:
                self.selection.update(car=item['id'],skin=item['skins'][0],event='')
                if self.event_options['pins']['car'] is not None:
                    settings=deepcopy(self.event_options)
                    if settings['pins']['car']!=item['id']:
                        settings['pins'].pop('skin',None)
                    settings['pins']['car']=item['id']
                    self.set_event_options(settings)
                self.tab=1
            elif self.tab==1:
                self.selection.update(track=item['id'],layout=item['layout'],event='')
                self.selection['opponents']=min(self.selection['opponents'],item['pitboxes']-1)
                if self.event_options['pins']['track'] is not None:
                    settings=deepcopy(self.event_options)
                    settings['pins']['track']=[item['id'],item['layout']]
                    self.set_event_options(settings)
                self.tab=3
            elif self.tab==2:
                self.selection.update(event=item['id'],car=item['car'],track=item['track'],layout=item['layout'])
                self.selection['skin']=self.car()['skins'][0]
                self.message='Event selected. Press X or Start to begin.'
            elif self.tab==6:
                if self.indices[self.tab]==0:
                    self.generate_event()
                elif self.indices[self.tab]==1:
                    self.generate_ai_event()
                elif self.indices[self.tab]==2:
                    self.open_key()
                elif self.indices[self.tab]==3:
                    self.change_effort(1)
                elif 4<=self.indices[self.tab]<=9:
                    self.change_event_option(self.indices[self.tab],1)
            else:
                self.change(1)
        elif action=='launch':
            if self.tab==6 and not self.synthesis:
                self.message='Generate an event first.'
                return
            return 'launch'
        elif isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            if 1104<=x<1248 and 50<=y<100:
                return self.action('request_quit')
            elif 144<=y<192:
                self.tab=max(0,min(len(self.tabs)-1,(x-32)//(1216//len(self.tabs))))
            elif 226<=y<666 and 32<=x<822:
                index=self.offset+(y-226)//40
                if index<len(self.rows()):
                    self.indices[self.tab]=index
                    return self.action('accept')
            elif 698<=y<750:
                return self.action('launch')

    def generate_event(self):
        self.ai_pending=None  # Resultado antigo não pode substituir um novo sorteio explícito.
        self.set_ai_report(ai_report.make(text='Local generator selected. No AI request was sent.'))
        try:
            if self.game is None:
                raise ValueError('Installed game path is required to generate an event.')
            base=self.event_base()
            catalog=event_synthetizer.discover(self.game)
            proposal,catalog=event_synthetizer.generate(self.game,base,fixed=self.event_options['pins'],catalog=catalog)
            event_synthetizer.save_state(self.synthesis_store,proposal,self.event_options_file,self.event_options)
            self.replace_catalog(catalog)
            self.synthesis=proposal
            self.indices[3:]=[0]*(len(self.tabs)-3)
            self.message='Event generated. Fixed settings kept. Press X or Start to drive.'
        except (OSError,ValueError,KeyError,TypeError) as error:
            self.message=str(error)

    def open_key(self):
        self.key_dialog=True
        self.key_buffer=''
        self.key_focus=0

    def key_action(self,action):
        if action=='back':
            self.key_dialog=False
            self.key_buffer=''
        elif isinstance(action,tuple) and action[0]=='key_text':
            self.key_buffer=(self.key_buffer+action[1])[:512]
        elif action=='erase_key':
            self.key_buffer=self.key_buffer[:-1]
        elif action in ('tab_next','down','right','tab_prev','up','left'):
            self.key_focus=(self.key_focus+(-1 if action in ('tab_prev','up','left') else 1))%3
        elif action=='accept':
            if self.key_focus==2:
                self.key_action('back')
            else:
                self.save_key()
        elif isinstance(action,tuple) and action[0]=='click':
            _,x,y=action
            if 365<=y<410 and 230<=x<1050:
                self.key_focus=0
            elif 460<=y<512:
                if 460<=x<640:
                    self.save_key()
                elif 680<=x<860:
                    self.key_action('back')

    def save_key(self):
        try:
            value=api_credentials.validate(self.key_buffer) if self.key_buffer.strip() else ''
            if self.key_path is not None:
                if value:
                    api_credentials.save(self.key_path,value)
                else:
                    api_credentials.forget(self.key_path)
            self.api_key=value
            self.key_action('back')
            self.message='API key saved locally.' if value else 'API key removed.'
        except (OSError,ValueError,RuntimeError):
            self.message='Could not save the API key. Check the key and local file permissions.'

    def generate_ai_event(self,instruction=None):
        if self.ai_pending is not None:
            return False
        try:
            instruction=ai_events.clean_instruction(instruction)
        except ai_events.AIError as error:
            self.message=ai_events.public_message(error)
            self.set_ai_report(ai_report.make('error',self.message))
            return False
        if not self.api_key:
            self.open_key()
            self.message='Paste your API key, save it, then choose Generate with AI.'
            self.set_ai_report(ai_report.make('error','Configure the API key, then generate explicitly. No request was sent.'))
            return False
        if self.game is None:
            self.message='Installed game path is required to generate an event.'
            self.set_ai_report(ai_report.make('error',self.message))
            return False
        base=self.event_base()
        fixed=deepcopy(self.event_options['pins'])
        key=self.api_key
        effort=self.ai_effort
        preferences=deepcopy(self.ai_preferences)
        previous=deepcopy(self.synthesis)
        current=deepcopy(self.synthesis['selection'] if self.synthesis else base)
        usage_state=deepcopy(self.ai_usage)
        session_request=getattr(self,'session_request',{}).get('text','')
        future=Future()
        self.ai_pending=future
        self.message='Generating with AI. You can still use Generate without AI.'
        self.set_ai_report(ai_report.make('pending','Generating a new AI verdict. The previous proposal has not been replaced.'))
        def work():
            try:
                future.set_result(ai_events.generate(self.game,base,key,
                    effort=effort,fixed=fixed,results=ai_events.performance(self.synthesis_store),
                    preferences=preferences,previous=previous,current=current,
                    usage_path=self.ai_usage_path,usage_state=usage_state,session_request=session_request,
                    **(dict(instruction=instruction) if instruction else {})))
            except ai_events.AIError as error:
                future.set_exception(error)
            except Exception:
                # Mensagem fixa: exceções de transporte nunca chegam a logs ou à UI.
                future.set_exception(ai_events.AIError('AI generation failed. Previous event kept; check key, connection or quota.'))
        try:
            threading.Thread(target=work,daemon=True,name='event-ai').start()
        except RuntimeError:
            self.ai_pending=None
            self.message='AI worker could not start. Previous event kept; try again explicitly.'
            self.set_ai_report(ai_report.make('error',self.message))
            return False
        return True

    def set_ai_report(self,value):
        value=ai_report.clean(value)
        try:ai_report.save(self.ai_report_path,value)
        except (OSError,ValueError,RuntimeError):
            value['app_note']='Verdict could not be saved on this device. '+value['app_note']
        self.ai_report=value

    def cancel_pending_ai(self,reason='AI settings changed. No new proposal was applied.'):
        if self.ai_pending is not None:
            self.ai_pending=None
            self.set_ai_report(ai_report.make('error',reason,app_note='An already sent request may be charged.'))

    def set_ai_limits(self,limits):
        try:
            value=ai_usage.update(self.ai_usage_path,limits=limits,state=self.ai_usage)
            self.ai_usage=value
            self.cancel_pending_ai()
            report=dict(self.ai_report,app_note='Usage limits saved. No new API request was sent.')
            self.set_ai_report(report)
            self.message=report['app_note']
            return True
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            self.message='AI usage limits unchanged. Check local storage.'
            return False

    def change_ai_limit(self,key,delta):
        if self.ai_usage is None:
            self.message='AI usage file unavailable; original file kept.'
            return
        limits=deepcopy(self.ai_usage['limits'])
        limits[key]=max(ai_usage.LIMIT_MIN,min(ai_usage.LIMIT_MAX,limits[key]+delta))
        self.set_ai_limits(limits)

    def reset_ai_usage(self):
        try:
            self.ai_usage=ai_usage.update(self.ai_usage_path,reset=True,state=self.ai_usage)
            self.cancel_pending_ai('Usage counters reset. No new proposal was applied.')
            self.set_ai_report(dict(self.ai_report,app_note='Usage counters reset. History and settings kept. No new API request sent.'))
            self.message=self.ai_report['app_note']
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            self.message='Usage counters could not be reset; original file kept.'

    def event_base(self):
        base=deepcopy(self.synthesis['base'] if self.synthesis else self.pending_event_base or self.selection)
        base.update(laps=self.event_options['laps'],ai=self.event_options['ai'],opponents=self.event_options['opponents'],
                    hud=self.selection['hud'])
        return base

    def event_with_current_hud(self,proposal):
        if proposal['base'].get('hud')==self.selection['hud'] and proposal['selection'].get('hud')==self.selection['hud']:
            return proposal
        proposal=deepcopy(proposal)
        proposal['base']['hud']=proposal['selection']['hud']=self.selection['hud']
        return proposal

    def sync_event_hud(self):
        if self.synthesis is not None:
            proposal=self.event_with_current_hud(self.synthesis)
            if proposal!=self.synthesis and self.synthesis_store is not None:
                event_synthetizer.save_state(self.synthesis_store,proposal,self.event_options_file,self.event_options)
            self.synthesis=proposal
        if self.pending_event_base is not None:
            self.pending_event_base['hud']=self.selection['hud']

    def change_event_option(self,index,delta):
        if index==9:
            if self.synthesis is None:
                self.message='Generate an event before editing Time of the Day.'
                return
            when=self.synthesis['selection']['time_minutes']+15*delta
            self.set_event_time(max(conditions.MINUTES_MIN,min(conditions.MINUTES_MAX,when)))
            return
        settings=deepcopy(self.event_options)
        display=self.synthesis['selection'] if self.synthesis else self.selection
        if index==4:
            settings['pins']['car']=display['car'] if settings['pins']['car'] is None else None
            settings['pins'].pop('skin',None)
            car=next((row for row in self.catalog['cars'] if row['id']==display['car']),None)
            if settings['pins']['car'] is not None and car and display.get('skin') in car['skins'][1:]:
                settings['pins']['skin']=display['skin']
        elif index==5:
            settings['pins']['track']=[display['track'],display['layout']] if settings['pins']['track'] is None else None
        else:
            key,low,high={6:('laps',1,99),7:('ai',70,100),8:('opponents',0,47)}[index]
            settings[key]=max(low,min(high,settings[key]+delta))
        self.set_event_options(settings)

    def set_event_time(self,minutes):
        if self.synthesis is None:
            self.message='Generate an event before editing Time of the Day.'
            return
        try:
            proposal=event_synthetizer.tune(self.synthesis,time_minutes=minutes)
            event_synthetizer.validate(self.game,proposal,catalog=self.catalog)
            event_synthetizer.save_state(self.synthesis_store,proposal,self.event_options_file,self.event_options)
            self.synthesis=proposal
            self.cancel_pending_ai('Time of day changed. No new AI proposal was applied.')
            self.message='Time of the Day saved. Generate with AI keeps it; Generate without AI may choose another time.'
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            self.message='Time of the Day unchanged. Could not validate or save the event.'

    def set_event_options(self,settings):
        try:
            settings=event_synthetizer.options(self.selection,settings)
            grid_changed=settings['opponents']!=self.event_options['opponents']
            catalog=self.catalog
            if self.game is not None and settings['pins']!=self.event_options['pins']:
                catalog=self.catalog if self.catalog_cache else event_synthetizer.discover(self.game)
                event_synthetizer.candidates(catalog,self.event_base(),settings['pins'])
            proposal=None
            if self.synthesis:
                proposal=event_synthetizer.tune(self.synthesis,
                    laps=settings['laps'] if settings['laps']!=self.event_options['laps'] else None,
                    ai=settings['ai'] if settings['ai']!=self.event_options['ai'] else None,
                    opponents=settings['opponents'] if settings['opponents']!=self.event_options['opponents'] else None)
                proposal.update(schema_version=2,pins=deepcopy(settings['pins']))
                try:
                    # Gerar/iniciar continuam relendo o jogo; editar usa o catalogo em memoria.
                    event_synthetizer.validate(self.game,proposal,catalog=catalog)
                except ValueError:
                    if settings['opponents']!=self.event_options['opponents'] and settings['pins']['track'] is not None:
                        raise ValueError('Fixed track cannot fit this grid. Reduce Opponents or unpin the track.')
                    proposal=None
            event_synthetizer.save_state(self.synthesis_store,proposal,self.event_options_file,settings)
            self.event_options=settings
            if self.synthesis is not None:
                self.pending_event_base=deepcopy(self.synthesis['base'])
            self.synthesis=proposal
            self.clamp_index(6)
            self.cancel_pending_ai()
            self.message=('Grid changed. Generate again for a compatible track.' if proposal is None and grid_changed
                          else 'Event settings saved. Generate again.' if proposal is None else
                          'Event settings saved. Press X / Start to drive.')
        except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
            self.message='Event settings unchanged. '+str(error)

    def change_effort(self,delta):
        value=ai_events.EFFORTS[(ai_events.EFFORTS.index(self.ai_effort)+delta)%len(ai_events.EFFORTS)]
        try:
            if self.ai_settings is not None:
                event_synthetizer.save(self.ai_settings,dict(effort=value))
            self.ai_effort=value
            self.cancel_pending_ai()
            self.message='AI effort saved. Higher effort can increase response time and token cost.'
        except (OSError,ValueError,RuntimeError):
            self.message='Could not save AI effort. Previous value kept.'

    def save_ai_preferences(self,value):
        value=ai_preferences.clean(value)
        if self.ai_preferences_path is not None:
            value=ai_preferences.save(self.ai_preferences_path,value)
        self.ai_preferences=value
        self.cancel_pending_ai()

    def poll_ai(self):
        future=self.ai_pending
        if future is None or not future.done():
            return
        self.ai_pending=None
        try:
            proposal,catalog=future.result()
            revision=proposal.get('preferences_revision')
            if revision is not None and revision!=ai_preferences.revision(self.ai_preferences):
                self.message='AI preferences changed. Old response discarded; generate again.'
                self.set_ai_report(ai_report.make('error',self.message))
                return
            if proposal.get('no_proposal'):
                self.set_ai_report(proposal['ai_report'])
                self.message='No new AI proposal applied. Previous selection kept.'
                return
            catalog=event_synthetizer.validate(self.game,proposal,**(dict(catalog=catalog) if self.catalog_cache else {}))
            settings=dict(self.event_options,ai=proposal['selection']['ai'])
            if not event_synthetizer.matches(proposal,settings):
                raise ValueError('Stale AI proposal')
            proposal=self.event_with_current_hud(proposal)
            event_synthetizer.save_state(self.synthesis_store,proposal,self.event_options_file,settings)
            self.event_options=settings
            self.replace_catalog(catalog)
            self.synthesis=proposal
            self.set_ai_report(proposal.get('ai_report') or ai_report.make('complete','New proposal applied.',applied=True))
            self.clamp_index(6)
            self.message=('AI event ready. Difficulty is editable. X / Start to drive.' if proposal.get('difficulty_history_samples') else
                          'AI event ready. No verified race history: current difficulty kept. X / Start to drive.')
            if proposal.get('adjustments'):
                labels={'car_id':'car','class_id':'class','track_key':'track/layout','weather':'weather',
                        'time_minutes':'time','ai_level':'difficulty','extra_fields':'extra settings ignored'}
                self.message='AI with local adjustments: '+', '.join(labels[k] for k in proposal['adjustments'] if k in labels)+'.'
        except ai_events.AIError as error:
            self.message=ai_events.public_message(error)
            self.set_ai_report(ai_report.make('error',self.message))
        except (OSError,ValueError,RuntimeError):
            self.message='AI generation failed. Previous event kept; check key, connection or quota.'
            self.set_ai_report(ai_report.make('error',self.message))

    def close(self):
        self.ai_pending=None
        self.api_key=self.key_buffer=''

    def launch_selection(self):
        if self.tab!=6:
            return dict(self.selection)
        if self.synthesis is None:
            raise ValueError('Generate an event first.')
        if not event_synthetizer.matches(self.synthesis,self.event_options):
            raise ValueError('Event settings changed. Generate again.')
        self.replace_catalog(event_synthetizer.validate(self.game,self.synthesis,**self.event_catalog_args()))
        self.sync_event_hud()
        return dict(session_settings.restore(self.synthesis['selection'],self.selection),event_synthetizer=self.synthesis)

    def draw(self,w):
        bg,panel,accent,muted=(13,20,29),(21,32,45),(70,224,177),(135,155,174)
        w.rect(0,0,1280,800,bg)
        w.rect(32,32,6,72,accent)
        w.text('ac-deck',56,36,4)
        w.text('MOD / BASE GAME + DLCS'+(' / CSP '+CSP_VERSION if graphics.uses_csp(self.selection['graphics_profile']) else ' / NO CSP'),58,88,2,color=muted)
        w.rect(1104,50,144,50,panel)
        w.text('Exit',1140,66,2,color=muted)
        for i,name in enumerate(self.tabs):
            step=1216//len(self.tabs)
            x=32+i*step
            w.rect(x,144,step-12,48,accent if self.tab==i else panel)
            w.text(name,x+(6 if len(name)>12 else 12),160,1 if len(name)>12 else 2,color=bg if self.tab==i else muted)
        w.rect(32,208,790,474,panel)
        w.rect(846,208,402,474,panel)
        rows=self.rows()
        index=self.indices[self.tab]
        self.offset=max(0,min(index-5,max(0,len(rows)-11)))
        for number,item in enumerate(rows[self.offset:self.offset+11]):
            yy=226+number*40
            selected=self.offset+number==index
            if selected:
                w.rect(44,yy-4,766,34,(34,66,72))
                w.rect(44,yy-4,4,34,accent)
            w.text(item['name'],62,yy+4,2,color=accent if selected else (221,230,235),limit=60)
        if not rows:
            w.text('No events available',62,250,2,color=muted)
        w.text(str(index+1 if rows else 0)+' / '+str(len(rows)),62,658,1,color=muted)
        car=rows[index] if self.tab==0 and rows else self.car()
        track=rows[index] if self.tab==1 and rows else self.track()
        display=self.synthesis['selection'] if self.tab==6 and self.synthesis else self.selection
        if self.tab==6 and self.synthesis:
            car=next(row for row in self.catalog['cars'] if row['id']==display['car'])
            track=next(row for row in self.catalog['tracks'] if (row['id'],row['layout'])==(display['track'],display['layout']))
        def candidates(item,kind,skin=None):
            key=(kind,item['id'],item.get('layout',''),skin)
            if key not in self.preview_cache:
                paths=previews.paths(self.game,item,kind,skin) if self.game is not None else ()
                if kind=='track' and self.game is not None:
                    paths+=previews.paths(self.game,item,'outline')
                self.preview_cache[key]=paths
            return self.preview_cache[key]
        skin=display['skin'] if car['id']==display['car'] else car['skins'][0]
        w.text('CONTENT PREVIEW',870,234,2,color=accent)
        w.text(car['name'],870,270,2,limit=29)
        w.image(candidates(car,'car',skin),870,296,354,112)
        w.text(track['name'],870,424,2,limit=29)
        w.image(candidates(track,'track'),870,450,354,112)
        w.text('INSTALLED EVENT' if display.get('event') else MODES[display['mode']][0],870,580,2,color=accent)
        w.text('FPS + FRAMETIME : '+('ON' if display['hud'] else 'OFF'),870,612,1)
        w.text('PROFILE : '+GRAPHICS_LABELS[display['graphics_profile']],870,634,1,color=accent)
        w.text('RESOLUTION : '+' x '.join(map(str,display['resolution'])),870,654,1,color=muted)
        w.rect(32,698,1216,52,accent)
        w.text('START RACE   X / START',58,714,3,color=bg)
        w.text('A SELECT   LB/RB TABS   Y LIVERY   B BACK   VIEW/F10 EXIT',32,770,2,color=muted,limit=98)
        w.text(self.message,32,114,2,color=muted,limit=100)
        if self.quit_confirmation:
            w.rect(390,300,500,194,panel)
            w.text('Exit launcher?',440,330,3,color=accent)
            for x,label,selected in ((440,'Cancel',not self.quit_selected),(660,'Exit',self.quit_selected)):
                w.rect(x,414,180,56,accent if selected else bg)
                w.text(label,x+24,432,2,color=bg if selected else muted)
        if self.key_dialog:
            w.rect(200,290,880,252,panel)
            w.text('API key',230,314,3,color=accent)
            w.rect(230,365,820,45,bg)
            w.text('*'*min(60,len(self.key_buffer)) if self.key_buffer else 'Type or paste with Ctrl+V',244,378,2,color=accent if self.key_focus==0 else muted)
            w.text('Saved only on this device. Save an empty field to remove it.',230,426,2,color=muted)
            for x,label,focus in ((460,'Save',1),(680,'Cancel',2)):
                w.rect(x,460,180,52,accent if self.key_focus==focus else bg)
                w.text(label,x+24,476,2,color=bg if self.key_focus==focus else muted)


class ShutdownRequest:
    """Intenção de saída externa, processada e gravada pelo loop normal."""
    def __init__(self):
        self.reason=None
        self.signum=None
        self.handlers={}

    def request(self,reason,signum=None):
        if self.reason is None:
            self.reason=reason
            self.signum=signum

    def _signal(self,signum,frame):
        # Sem SDL, persistência, logs ou operações sobre o filho no handler.
        self.request('signal',signum)

    def __enter__(self):
        if threading.current_thread() is threading.main_thread():
            try:
                for signum in (signal.SIGTERM,signal.SIGINT):
                    self.handlers[signum]=signal.signal(signum,self._signal)
            except Exception:
                self.__exit__(None,None,None)
                raise
        return self

    def __exit__(self,*args):
        for signum,previous in self.handlers.items():
            signal.signal(signum,previous)
        self.handlers.clear()


def run(catalog,selection,start,*,proton=None,capture=None,library_path=None,preview=False,csp=False,game=None,trace=None,synthesis_store=None,on_exit=None,menu_class=None,on_tick=None,on_stop=None,on_stalled=None,on_selection=None):
    # Antes da SDL: ela normalmente traduz SIGTERM em um SDL_QUIT sem origem.
    # O handler próprio conserva o pedido mesmo durante/finalizando a sessão.
    with ShutdownRequest() as shutdown:
        guard=(session_process.CloseGuard(shutdown,on_stop,on_stalled)
               if on_stalled is not None else None)
        try:
            return _run(catalog,selection,start,proton=proton,capture=capture,
                library_path=library_path,preview=preview,csp=csp,game=game,trace=trace,
                synthesis_store=synthesis_store,on_exit=on_exit,menu_class=menu_class,
                shutdown=shutdown,on_tick=on_tick,on_stop=on_stop,on_selection=on_selection)
        finally:
            if guard is not None:guard.close()


def _run(catalog,selection,start,*,proton=None,capture=None,library_path=None,preview=False,csp=False,game=None,trace=None,synthesis_store=None,on_exit=None,menu_class=None,on_tick=None,shutdown,on_stop=None,on_selection=None):
    trace=trace or (lambda *args,**kwargs:None)
    menu=(menu_class or Menu)(catalog,selection,csp=csp,game=game,synthesis_store=synthesis_store)
    if preview:
        menu.message='Menu preview. To drive, launch through Steam on the Deck.'
    window=Window(proton,library_path,trace=trace)
    if hasattr(menu,'audio_sdl'):menu.audio_sdl=window.sdl
    trace('menu_opened')
    process=None
    menu.session_running=False
    stick_action=None
    next_repeat=0.0
    previous_shoulders=set()
    previous_triggers=set()
    text_active=False
    test_until=0.0
    test_side=None
    paused=False
    lost_focus=False
    exit_reported=False
    try:
        while True:
            if on_selection is not None:on_selection(dict(menu.selection))
            menu.poll_ai()
            if hasattr(menu,'poll_dictation'):menu.poll_dictation()
            ended=False
            if process is not None:
                code=process.poll()
                if code is not None:
                    trace('session_exited',exit_code=code)
                    process=None
                    ended=True
                    message=None
                    try:
                        if on_exit is not None:
                            message=on_exit(code)
                    except (OSError,ValueError,RuntimeError) as error:
                        trace('session_finish_error',error_type=type(error).__name__)
                        message='Session ended. Could not collect the result; check local storage.'
                    menu.message=message or ('Session ended. Code '+str(code)+'. Choose the next race.')
                    if hasattr(menu,'refresh_history'):
                        try:
                            menu.refresh_history()
                        except (OSError,ValueError,RuntimeError) as error:
                            trace('session_history_error',error_type=type(error).__name__)
                    if hasattr(menu,'refresh_rogue'):
                        try:
                            menu.refresh_rogue()
                        except (OSError,ValueError,RuntimeError) as error:
                            trace('rogue_refresh_error',error_type=type(error).__name__)
                    menu.session_running=False
            # Keep the window mapped. No Hide/Show transition can stall return.
            actions=window.events()
            if 'quit' in actions:
                shutdown.request('window_close')
            if shutdown.reason is not None:
                if not exit_reported:
                    trace('menu_close_requested',reason=shutdown.reason,signum=shutdown.signum,
                          session_running=process is not None)
                    exit_reported=True
                if process is None:
                    trace('menu_exit',reason=shutdown.reason)
                    return dict(menu.selection)
                menu.quit_confirmation=False
                menu.message='Closing application. Finishing the current session.'
                if on_stop is not None:on_stop()
                actions=[]
            focused=window.focused() if hasattr(window,'focused') else True
            if process is not None and not focused:lost_focus=True
            restored=paused and shutdown.reason is None and (process is None or focused)
            if restored:
                paused=False
                menu.session_ending=process is not None and lost_focus
                if menu.session_ending:
                    menu.message='Finishing session. Start race is available after the game has closed.'
                trace('menu_restored',session_running=process is not None)
            if process is None:menu.session_ending=False
            if process is not None and not focused:paused=True
            wants_text=(process is None and focused and shutdown.reason is None
                        and (menu.key_dialog or getattr(menu,'searching',False)))
            if wants_text!=text_active:
                text_active=wants_text
                window.text_input(text_active)
            shoulders=window.shoulders()
            triggers=window.triggers() if hasattr(window,'triggers') else set()
            stick=window.stick()
            now=time.monotonic()
            if ended and hasattr(window,'driving_rumble'):window.driving_rumble(0,0)
            fast_haptics=bool(on_tick(window)) if on_tick is not None else False
            if test_side is not None:
                gain=menu.selection.get('haptics_'+test_side+'_pct',50)/100
                window.driving_rumble(gain if now<test_until and test_side=='left' else 0,
                                      gain if now<test_until and test_side=='right' else 0)
                if now>=test_until:test_side=None
            if process is not None or ended or restored or not focused or shutdown.reason is not None:
                pending=actions
                if process is not None:
                    for action in pending:
                        if action=='launch':trace('session_start_blocked',reason='session_running')
                        elif action=='request_quit':trace('menu_exit_blocked',reason='session_running')
                # Descartar navegação da corrida; o fechamento externo já foi
                # preservado acima e não depende de outro gesto ou do foco.
                actions=[]
                if ended and len(pending)!=len(actions):
                    trace('pending_input_discarded',count=len(pending)-len(actions))
                # Não transformar um botão já mantido na corrida em um novo
                # pressionamento ao recuperar o foco do launcher.
                next_repeat=now+0.35
            else:
                for action in sorted(shoulders-previous_shoulders):
                    if action not in actions:
                        actions.append(action)
                for action in sorted(triggers-previous_triggers):
                    if action not in actions:
                        actions.append(action)
                if stick and (stick!=stick_action or now>=next_repeat):
                    actions.append(stick)
                    next_repeat=now+(0.35 if stick!=stick_action else 0.12)
            previous_shoulders=shoulders
            previous_triggers=triggers
            stick_action=stick
            for action in actions:
                if process is not None and action in ('quit','request_quit'):
                    menu.quit_confirmation=False
                    menu.message='A session is running. Close the game before exiting the launcher.'
                    trace('menu_exit_blocked',reason='session_running')
                    continue
                if action=='paste_key' and menu.key_dialog:
                    menu.key_buffer=window.clipboard().strip()
                    continue
                if action=='paste_key' and getattr(menu,'searching',False):
                    menu.action(('key_text',window.clipboard()))
                    continue
                result=menu.action(action)
                if result in ('haptics_left','haptics_right') and process is None and not capture and not preview:
                    test_side=result.removeprefix('haptics_')
                    test_until=now+0.20
                    gain=menu.selection.get('haptics_'+test_side+'_pct',50)/100
                    ok=window.driving_rumble(gain if test_side=='left' else 0,gain if test_side=='right' else 0)
                    menu.message=('Testing '+test_side+' haptics.' if ok else 'Steam Input haptics output unavailable. Controls are unchanged.')
                    trace('haptics_side_test',side=test_side,output_available=ok)
                    continue
                if action in ('back','request_quit'):
                    trace('menu_action',action=action)
                if result in ('quit','quit_confirmed'):
                    if process is not None:
                        menu.quit_confirmation=False
                        menu.message='A session is running. Close the game before exiting the launcher.'
                        trace('menu_exit_blocked',reason='session_running')
                        continue
                    trace('menu_exit',reason='window_close' if result=='quit' else 'confirmed')
                    return dict(menu.selection)
                if process is not None and menu.quit_confirmation:
                    menu.quit_confirmation=False
                    menu.message='A session is running. Close the game before exiting the launcher.'
                    trace('menu_exit_blocked',reason='session_running')
                if result=='launch':
                    if capture:
                        continue
                    if process is not None:
                        menu.message='A session is already running. Close it before starting another.'
                        trace('session_start_blocked',reason='session_running')
                        continue
                    if test_side is not None:
                        window.driving_rumble(0,0)
                        test_side=None
                    try:
                        chosen=menu.launch_selection()
                        if shutdown.reason is not None:
                            break
                        paused=True
                        lost_focus=False
                        trace('menu_render_paused')
                        process=start(chosen)
                    except (OSError,ValueError,RuntimeError) as error:
                        menu.message='Could not start the session. See the launcher log for details.'
                        trace('session_start_error',error_type=type(error).__name__,message=str(error))
                        if hasattr(menu,'refresh_rogue'):
                            try:menu.refresh_rogue()
                            except (OSError,ValueError,RuntimeError):
                                trace('rogue_refresh_error',reason='start_failed')
                    else:
                        menu.session_running=True
                        menu.quit_confirmation=False
                        menu.message='Session running. The launcher will return when the game closes.'
                        trace('session_started',pid=process.pid)
                        break
            if on_selection is not None:on_selection(dict(menu.selection))
            if paused:
                # No draw/present while the simulator has focus. Keep polling
                # events, process ownership and haptics without stealing focus.
                time.sleep(0.01 if fast_haptics or process is None else 0.05)
                continue
            menu.draw(window)
            if capture:
                window.screenshot(capture)
                trace('menu_exit',reason='preview_capture')
                return dict(menu.selection)
            window.sdl.SDL_RenderPresent(window.renderer)
            time.sleep(0.01 if fast_haptics or test_side is not None else 0.016)
    finally:
        menu.close()
        window.close()
