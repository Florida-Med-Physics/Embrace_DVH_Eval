"""Build a standalone app and verify GUI + bundled-template export."""
from pathlib import Path
import json
import platform
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'EMBRACE EQD2'
platform_name = platform.system()
if platform_name not in ('Darwin', 'Windows'):
    raise SystemExit('Build on macOS or Windows.')
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
           '--windowed', '--name', NAME, '--distpath', str(ROOT/'dist'),
           '--workpath', str(ROOT/'build'), '--specpath', str(ROOT/'build'),
           '--add-data', str(ROOT/'Matlab/EQD2_with_tolerances_090126.xlsx')+':.',
           '--onefile' if platform_name == 'Windows' else '--onedir']
command += ['--add-data', str(ROOT/'Python/assets')+':assets',
            '--icon', str(ROOT/'Python/assets'/('eqd2.icns' if platform_name == 'Darwin' else 'eqd2.ico'))]
if platform_name == 'Darwin':
    command += ['--osx-bundle-identifier', 'org.floridamedphysics.embrace-eqd2']
command += [str(ROOT/'Python/EMBRACE2_EQD2_Excel_Autogenerator.py')]
subprocess.run(command, cwd=ROOT, check=True)
exe = ROOT/'dist'/('EMBRACE EQD2.exe' if platform_name == 'Windows' else 'EMBRACE EQD2.app/Contents/MacOS/EMBRACE EQD2')
report = ROOT/'build/packaged-smoke-test.json'
report.unlink(missing_ok=True)
subprocess.run([str(exe), '--smoke-test', str(report)], cwd=ROOT/'build', check=True, timeout=90)
result = json.loads(report.read_text())
if result.get('status') != 'passed':
    raise RuntimeError(result)
print('Packaged app smoke test:', result)
if platform_name == 'Darwin':
    archive = ROOT/'dist'/f'EMBRACE-EQD2-macOS-{platform.machine()}.zip'
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent', str(ROOT/'dist'/f'{NAME}.app'),str(archive)],check=True)
else:
    archive = ROOT/'dist/EMBRACE-EQD2-Windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(exe,exe.name)
print('Ready:',archive)
