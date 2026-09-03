"""Detective Grimoire 한글패치 설치 프로그램.

게임 폴더에 넣고 실행하면 됩니다. 패치 파일은 게임 원본과의 '차이'만 담고
있어서, 원본 파일이 없으면 아무 의미가 없습니다.

  - 원본을 backup_kr_patch/ 에 보관하고, 언제든 되돌릴 수 있습니다.
  - 적용 전에 원본 SHA-256을 확인하고, 적용 후 결과도 다시 확인합니다.
  - 인트로 도중 종료해서 열리지 않게 된 세이브도 고칠 수 있습니다.
"""
import hashlib
import json
import os
import shutil
import struct
import sys
import zlib

MAGIC = b'DGKRPATCH'
APP_NAME = 'Detective Grimoire 한글패치'
BACKUP_DIR = 'backup_kr_patch'
PATCH_NAME = 'DetectiveGrimoire-KR.dgpatch'
GAME_EXE = 'Detective Grimoire.exe'
MAIN_SWF = 'DetectiveGrimoireDesktopSteam.swf'

SAVE_REL = os.path.join(
    'air.com.sfbgames.DetectiveGrimoire', 'Local Store', '#SharedObjects',
    'DetectiveGrimoireDesktopSteam.swf', 'DetectiveGrimoireSave.sol')


# ----------------------------------------------------------------- utilities
def sha(b):
    return hashlib.sha256(b).hexdigest()


def swf_decompress(data):
    """FWS / CWS / ZWS -> uncompressed FWS image."""
    sig, ver = data[:3], data[3]
    length = struct.unpack('<I', data[4:8])[0]
    if sig == b'FWS':
        return data
    if sig == b'CWS':
        body = zlib.decompress(data[8:])
    elif sig == b'ZWS':
        import lzma
        props = data[12:17]
        lc, lp, pb = props[0] % 9, (props[0] // 9) % 5, props[0] // 45
        dict_size = struct.unpack('<I', props[1:5])[0]
        d = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[{'id': lzma.FILTER_LZMA1, 'lc': lc, 'lp': lp,
                      'pb': pb, 'dict_size': dict_size}])
        body = d.decompress(data[17:])
    else:
        raise ValueError('SWF 파일이 아닙니다 (%r)' % sig)
    return b'FWS' + bytes([ver]) + struct.pack('<I', length) + body


def swf_compress(body):
    """Uncompressed FWS image -> CWS (zlib), which the AIR runtime reads."""
    return b'CWS' + body[3:8] + zlib.compress(body[8:], 9)


def base_dir():
    """Folder the program is running from (PyInstaller-aware)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource(name):
    """A bundled file, whether frozen or run from source."""
    for d in (getattr(sys, '_MEIPASS', None), base_dir(),
              os.path.join(base_dir(), '..', 'release')):
        if not d:
            continue
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def find_game(start):
    """Walk up from `start` looking for the game folder."""
    d = os.path.abspath(start)
    for _ in range(4):
        if os.path.exists(os.path.join(d, MAIN_SWF)) and \
           os.path.isdir(os.path.join(d, 'assets', 'swf-dsk')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def read_patch(path):
    data = open(path, 'rb').read()
    if data[:len(MAGIC)] != MAGIC:
        raise ValueError('패치 파일 형식이 아닙니다')
    p = len(MAGIC)
    version, mlen = struct.unpack('<II', data[p:p + 8])
    p += 8
    manifest = json.loads(data[p:p + mlen].decode('utf-8'))
    blobs = data[p + mlen:]
    return manifest, blobs


# -------------------------------------------------------------------- actions
def do_patch(game, manifest, blobs):
    import zstandard as zstd

    entries = manifest['entries']
    backup = os.path.join(game, BACKUP_DIR)

    print('원본 파일을 확인합니다...')
    missing, mismatched, already = [], [], []
    for e in entries:
        f = os.path.join(game, e['path'].replace('/', os.sep))
        if not os.path.exists(f):
            missing.append(e['path'])
            continue
        h = sha(open(f, 'rb').read())
        if h == e['orig_sha']:
            continue
        try:
            if sha(swf_decompress(open(f, 'rb').read())) == e['new_body_sha']:
                already.append(e['path'])
                continue
        except Exception:
            pass
        mismatched.append(e['path'])

    if missing:
        print('\n[!] 게임 파일이 없습니다 (%d개). 경로를 확인해 주세요.' % len(missing))
        for m in missing[:5]:
            print('    - ' + m)
        return 1
    if already and len(already) == len(entries):
        print('\n이미 한글패치가 적용되어 있습니다.')
        return 0
    if mismatched:
        print('\n[!] 원본과 다른 파일이 %d개 있습니다.' % len(mismatched))
        for m in mismatched[:5]:
            print('    - ' + m)
        print('\n    Steam에서 [속성 → 설치된 파일 → 게임 파일 무결성 확인]을')
        print('    한 번 실행해 원본으로 되돌린 뒤 다시 시도해 주세요.')
        return 1

    print('원본 백업 중... (%s)' % BACKUP_DIR)
    for e in entries:
        src = os.path.join(game, e['path'].replace('/', os.sep))
        dst = os.path.join(backup, e['path'].replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)

    print('패치 적용 중...')
    done = 0
    for e in entries:
        f = os.path.join(game, e['path'].replace('/', os.sep))
        orig_body = swf_decompress(open(f, 'rb').read())
        if sha(orig_body) != e['orig_body_sha']:
            print('\n[!] %s 내용이 예상과 다릅니다. 중단합니다.' % e['path'])
            return 1
        delta = blobs[e['off']:e['off'] + e['len']]
        d = zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(orig_body))
        new_body = d.decompress(delta, max_output_size=e['new_body_size'] + 1024)
        if sha(new_body) != e['new_body_sha']:
            print('\n[!] %s 패치 결과가 손상되었습니다. 중단합니다.' % e['path'])
            return 1
        with open(f, 'wb') as fh:
            fh.write(swf_compress(new_body))
        done += 1
        pct = 100 * done // len(entries)
        print('\r  %3d%%  (%d/%d)' % (pct, done, len(entries)), end='', flush=True)

    print('\n\n한글패치가 적용되었습니다. (%d개 파일)' % done)
    return 0


def do_restore(game):
    backup = os.path.join(game, BACKUP_DIR)
    if not os.path.isdir(backup):
        print('백업 폴더가 없습니다: %s' % backup)
        print('Steam에서 [게임 파일 무결성 확인]으로도 원본을 되돌릴 수 있습니다.')
        return 1
    n = 0
    for root, _, files in os.walk(backup):
        for name in files:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, backup)
            shutil.copy2(src, os.path.join(game, rel))
            n += 1
    print('원본으로 되돌렸습니다. (%d개 파일)' % n)
    return 0


def do_fix_save():
    """Repair a slot that renders but will not load.

    AreaList.currentAreaID starts at -1 and only becomes a real id once the
    player enters an area. A save written during the intro therefore records
    areaCurrent = -1; on load, Area(byID(-1)) is null, reading .screen throws,
    and the game swallows it -- the slot just does nothing when clicked.
    """
    sol = os.path.join(os.environ.get('APPDATA', ''), SAVE_REL)
    if not os.path.exists(sol):
        print('세이브 파일을 찾을 수 없습니다:\n  %s' % sol)
        return 1
    try:
        from solfix import repair
    except ImportError:
        print('세이브 복구 모듈을 불러오지 못했습니다.')
        return 1
    print('세이브 파일: %s' % sol)
    ok = repair(sol, area_id=0)
    print('완료되었습니다.' if ok else '고칠 항목이 없습니다.')
    return 0


# ----------------------------------------------------------------------- menu
def prompt(msg, default=''):
    """input() that survives a closed stdin (double-clicked, piped, CI)."""
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print(default)
        return default


def pause():
    try:
        input('\nEnter 를 누르면 닫힙니다...')
    except (EOFError, KeyboardInterrupt):
        pass


def main():
    print('=' * 58)
    print('  ' + APP_NAME)
    print('=' * 58)
    print()

    args = [a.lower() for a in sys.argv[1:]]
    batch = any(a in ('--apply', '--restore', '--fix-save') for a in args)

    game = find_game(base_dir())
    if not game:
        print('[!] 게임 폴더를 찾지 못했습니다.')
        print('    이 프로그램을 "%s" 가 있는 폴더에 넣고 실행해 주세요.' % GAME_EXE)
        if not batch:
            pause()
        return 1
    print('게임 폴더: %s' % game)

    if '--restore' in args:
        return do_restore(game)
    if '--fix-save' in args:
        return do_fix_save()

    patch_path = resource(PATCH_NAME)
    if not patch_path:
        print('[!] 패치 파일(%s)을 찾지 못했습니다.' % PATCH_NAME)
        print('    이 프로그램과 같은 폴더에 두어야 합니다.')
        if not batch:
            pause()
        return 1

    manifest, blobs = read_patch(patch_path)
    print('패치 데이터: %d개 파일' % len(manifest['entries']))
    print()

    if '--apply' in args:
        return do_patch(game, manifest, blobs)

    print('  1) 한글패치 적용')
    print('  2) 원본으로 되돌리기')
    print('  3) 열리지 않는 세이브 슬롯 고치기')
    print('  0) 닫기')
    print()
    choice = prompt('번호를 입력하세요: ', '0')

    print()
    if choice == '1':
        rc = do_patch(game, manifest, blobs)
    elif choice == '2':
        rc = do_restore(game)
    elif choice == '3':
        rc = do_fix_save()
    else:
        rc = 0

    pause()
    return rc


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('\n[!] 오류가 발생했습니다: %s' % exc)
        input('\nEnter 를 누르면 닫힙니다...')
        sys.exit(1)
