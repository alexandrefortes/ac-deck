"""Execute the actual archived product code; refuse every source fallback."""
import argparse
import contextlib
import ctypes
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import marshal
import os
from pathlib import Path
import sys
import time
from types import CodeType
import unittest

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_NSPKG, PYZ_ITEM_PKG, ZlibArchiveReader

TESTS = tuple('tests.'+name for name in (
    'test_file_io', 'test_assists_config', 'test_practice_session', 'test_community_download',
    'test_install_discovery', 'test_community_install', 'test_steam_install_options',
    'test_csp_community_install', 'test_rogue_variety', 'test_rogue_victory_music',
    'test_first_launch'))

# These source tests launch the test interpreter. In this probe sys.executable
# deliberately identifies the product, and the audit guard forbids subprocesses.
SOURCE_PROCESS_TESTS = frozenset((
    'tests.test_steam_install_options.SteamOptionsTests.test_environment_prefix_reaches_a_synthetic_child_as_literal_values',
    'tests.test_first_launch.FirstSteamLaunchTests.test_prefix_preparation_waits_for_its_adopted_synthetic_child',
))


def compiled_suite(suite):
    selected, source_only = unittest.TestSuite(), []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            child, excluded = compiled_suite(item)
            selected.addTest(child)
            source_only.extend(excluded)
        elif item.id() in SOURCE_PROCESS_TESTS:
            source_only.append(item.id())
        else:
            selected.addTest(item)
    return selected, source_only


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def product(name):
    return name in ('src','scripts') or name.startswith(('src.','scripts.'))


def normalized(code):
    return code.replace(co_filename='<snapshot>', co_consts=tuple(
        normalized(value) if isinstance(value,CodeType) else value for value in code.co_consts))


class ProductArchive(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,bundle,source):
        self.bundle=bundle
        self.binary=bundle/'ac-deck'
        self.archive=CArchiveReader(str(self.binary))
        self.pyz=self.archive.open_embedded_archive('PYZ.pyz')
        if not isinstance(self.pyz,ZlibArchiveReader):
            raise TypeError('Expected real PyInstaller PYZ reader')
        self.origin=str(self.binary)+'!PYZ.pyz/'
        self.loaded={}
        self.compared={}
        for name,row in self.pyz.toc.items():
            if not product(name) or row[0] == PYZ_ITEM_NSPKG:
                continue
            relative=Path(*name.split('.'))
            relative=(relative/'__init__.py') if row[0] == PYZ_ITEM_PKG else relative.with_suffix('.py')
            original=source/relative
            archived=self.pyz.extract(name)
            expected=compile(original.read_bytes(),str(original),'exec',dont_inherit=True,optimize=0)
            if normalized(archived) != normalized(expected):
                raise AssertionError('Archived code differs from snapshot: '+name)
            self.compared[name]=dict(source_path=str(relative),source_sha256=sha(original))
        entry=marshal.loads(self.archive.extract('jogo_deck'))
        original=source/'scripts/jogo_deck.py'
        if normalized(entry) != normalized(compile(original.read_bytes(),str(original),'exec',dont_inherit=True)):
            raise AssertionError('Archived entrypoint differs from snapshot')
        self.compared['entry:jogo_deck']=dict(source_path='scripts/jogo_deck.py',source_sha256=sha(original))

    def find_spec(self,fullname,path=None,target=None):
        if not product(fullname):
            return None
        if fullname not in self.pyz.toc:
            raise ImportError('Source fallback refused: '+fullname)
        package=self.pyz.toc[fullname][0] in (PYZ_ITEM_PKG,PYZ_ITEM_NSPKG)
        spec=importlib.util.spec_from_loader(fullname,self,is_package=package)
        spec.origin=self.origin+fullname
        return spec

    def create_module(self,spec):
        return None

    def exec_module(self,module):
        name=module.__name__
        code=self.pyz.extract(name)
        relative=Path(*name.split('.'))
        if module.__spec__.submodule_search_locations is not None:
            relative/='__init__.py'
            module.__path__=[]
        else:
            relative=relative.with_suffix('.py')
        module.__file__=str(self.bundle/'_internal'/relative)
        if code is not None:
            if not isinstance(code,CodeType):
                raise TypeError('Expected bytecode: '+name)
            exec(code,module.__dict__)
        self.loaded[name]=module.__spec__.origin

    def assert_origins(self):
        for name,module in tuple(sys.modules.items()):
            if product(name) and module is not None:
                if module.__loader__ is not self or module.__spec__.origin != self.origin+name:
                    raise AssertionError('Product imported outside archive: '+name)
        return dict(self.loaded)


def guards():
    def audit(event,args):
        if event == 'subprocess.Popen':
            command=args[1]
            if (isinstance(command,(list,tuple)) and list(command) in
                    (['/sbin/ldconfig','-p'],['/usr/sbin/ldconfig','-p'])):
                return
            raise RuntimeError('Only read-only ldconfig discovery allowed in compiled synthetic probe')
        if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'):
            raise RuntimeError('Network forbidden in compiled synthetic probe')
    sys.addaudithook(audit)
    original_cdll=ctypes.CDLL
    forbidden=('SDL_InitSubSystem','SDL_CreateWindow','SDL_CreateRenderer','SDL_OpenAudio',
               'SDL_OpenAudioDevice','SDL_GetNumAudioDevices','SDL_NumJoysticks',
               'SDL_GameControllerOpen','SDL_JoystickOpen')
    class GuardedSDL:
        def __init__(self,library):
            self.library=library
        def __getattr__(self,name):
            if name == 'SDL_Init':
                def init(flags):
                    if flags:
                        raise RuntimeError('Only SDL_Init(0) for a software surface is allowed')
                    return self.library.SDL_Init(0)
                return init
            if name in forbidden:
                def blocked(*args,**kwargs):
                    raise RuntimeError('Real device/window refused: '+name)
                return blocked
            return getattr(self.library,name)
    def cdll(name,*args,**kwargs):
        lib=original_cdll(name,*args,**kwargs)
        return GuardedSDL(lib) if 'sdl2' in str(name).lower() else lib
    ctypes.CDLL=cdll


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--tests',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    bundle=args.bundle.resolve(strict=True)
    source=args.snapshot.resolve(strict=True)
    output=args.output.resolve()
    output.mkdir()
    binary_before=sha(bundle/'ac-deck')
    if any(product(name) for name in sys.modules):
        raise AssertionError('Runtime imported before archive loader')
    finder=ProductArchive(bundle,source)
    sys.meta_path.insert(0,finder)
    # Fixtures are copied alone to an unrelated directory. Every src/scripts
    # import is owned by the finder, including names absent from the archive.
    sys.path=[str(args.tests.resolve())]+[p for p in sys.path if p and
        not Path(p).resolve().is_relative_to(source) and
        not (Path(p)/'src/launcher').exists() and not (Path(p)/'scripts/jogo_deck.py').exists()]
    sys._MEIPASS=str(bundle/'_internal')
    sys.frozen=True
    sys.executable=str(bundle/'ac-deck')
    os.chdir(output)
    guards()
    for name in sorted(name for name in finder.pyz.toc if product(name)):
        importlib.import_module(name)
    try:
        importlib.import_module('src.launcher.source_fallback_must_fail')
    except ImportError as error:
        if 'Source fallback refused' not in str(error):
            raise
    else:
        raise AssertionError('Missing product module did not fail closed')
    for name in ('src.launcher.community_install','src.launcher.community_download',
                 'src.launcher.install_discovery','src.launcher.steam_install_options'):
        if name not in finder.loaded:
            raise AssertionError('Required installer module missing')
    tests_started=time.perf_counter()
    with (output/'tests.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        suite=unittest.defaultTestLoader.loadTestsFromNames(TESTS)
        suite,source_only=compiled_suite(suite)
        if set(source_only) != SOURCE_PROCESS_TESTS:
            raise AssertionError('Expected source subprocess fixtures were not found')
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    test_seconds=time.perf_counter()-tests_started
    if not result.wasSuccessful() or result.skipped:
        print((output/'tests.log').read_text()[-16000:],file=sys.stderr)
        raise AssertionError('Compiled synthetic tests failed/skipped')
    capture_spec=importlib.util.spec_from_file_location('community_capture_helper',source/'scripts/render_readme_screenshots.py')
    capture=importlib.util.module_from_spec(capture_spec)
    capture_spec.loader.exec_module(capture)
    # Use the production explicit-library argument for this offscreen helper.
    # Avoid system discovery: its fallback may invoke ldconfig/gcc despite the
    # bundle already providing the selected SDL library.
    from src.launcher import window as archived_window
    capture.library=lambda: archived_window.library(explicit=bundle/'_internal/libSDL2-2.0.so.0')
    capture_started=time.perf_counter()
    captures=output/'offscreen'
    capture.main(['--output',str(captures)])
    capture_seconds=time.perf_counter()-capture_started
    images=json.loads((captures/'manifest.json').read_text())['images']
    if len(images) != 10:
        raise AssertionError('Expected both sizes for five views')
    sdl=ctypes.CDLL(str(bundle/'_internal/libSDL2-2.0.so.0'))
    class Version(ctypes.Structure):
        _fields_=[(n,ctypes.c_uint8) for n in ('major','minor','patch')]
    v=Version()
    sdl.SDL_GetVersion(ctypes.byref(v))
    if sha(bundle/'ac-deck') != binary_before:
        raise AssertionError('Executable changed during compiled probe')
    report=dict(method='Existing archive loader adapted for ac-deck; actual archived CodeType under matching SDK',
                limitation='Synthetic archive execution is separate from bootloader CLI and physical Deck behavior',
                tests=result.testsRun,skips=len(result.skipped),failures=len(result.failures),errors=len(result.errors),
                source_process_tests=source_only,
                test_modules=TESTS,compiled_test_seconds=test_seconds,offscreen_seconds=capture_seconds,
                loaded_product_modules=finder.assert_origins(),source_product_imports=0,
                archived_code_compared_to_snapshot=finder.compared,
                executable_sha256=binary_before,sdl_version=[v.major,v.minor,v.patch],
                sdl_sha256=sha(bundle/'_internal/libSDL2-2.0.so.0'),
                font_sha256=sha(next((bundle/'_internal/ui').glob('*.ttf'))),images=images,
                real_game=False,steam=False,window=False,audio=False,microphone=False,network=False)
    (output/'compiled.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('loaded_product_modules','archived_code_compared_to_snapshot','images','test_modules')}))


if __name__=='__main__':
    main()
