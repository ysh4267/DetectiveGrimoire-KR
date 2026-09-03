"""Build the single-file Windows patcher.

The .dgpatch is bundled into the exe, so the user only has to drop one file
into the game folder. Deltas alone are useless without the game's own files,
so nothing of the publisher's is redistributed.
"""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATCH = os.path.join(ROOT, 'release', 'DetectiveGrimoire-KR.dgpatch')
OUTDIR = os.path.join(ROOT, 'release')
NAME = 'DetectiveGrimoire-KR-Patch'


def main():
    if not os.path.exists(PATCH):
        raise SystemExit('패치 파일이 없습니다. 먼저 python work/makepatch.py 를 실행하세요.')

    sep = ';' if os.name == 'nt' else ':'
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile', '--console',
        '--name', NAME,
        '--distpath', OUTDIR,
        '--workpath', os.path.join(HERE, 'build'),
        '--specpath', os.path.join(HERE, 'build'),
        '--add-data', '%s%s.' % (PATCH, sep),
        '--paths', HERE,
        '--hidden-import', 'solfix',
        '--collect-all', 'zstandard',
        os.path.join(HERE, 'dgkr_patch.py'),
    ]
    print(' '.join(cmd))
    r = subprocess.run(cmd)
    if r.returncode:
        raise SystemExit('PyInstaller 실패')

    exe = os.path.join(OUTDIR, NAME + ('.exe' if os.name == 'nt' else ''))
    print('\n생성됨: %s  (%.2f MB)' % (exe, os.path.getsize(exe) / 1048576))
    shutil.rmtree(os.path.join(HERE, 'build'), ignore_errors=True)


if __name__ == '__main__':
    main()
