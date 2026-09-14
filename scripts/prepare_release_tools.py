"""Download standalone tools for the three release targets (CI only)."""
import argparse
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile


def download(url):
    print(f'Downloading {url}', flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'KLMP3-release'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def unpack_binaries(url, destination, names):
    data = download(url)
    # Extract only named executables, without trusting archive paths.
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in names:
                matches = [p for p in archive.namelist() if p.rsplit('/', 1)[-1] == name]
                if len(matches) != 1:
                    raise ValueError(f'{url}: expected one {name}, found {len(matches)}')
                (destination / name).write_bytes(archive.read(matches[0]))
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for name in names:
                matches = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name == name]
                if len(matches) != 1:
                    raise ValueError(f'{url}: expected one {name}, found {len(matches)}')
                with archive.extractfile(matches[0]) as source, (destination / name).open('wb') as target:
                    shutil.copyfileobj(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['linux-x86_64', 'windows-x86_64', 'macos-x86_64'])
    args = parser.parse_args()
    target = Path('tools') / args.target
    target.mkdir(parents=True, exist_ok=True)
    if args.target == 'linux-x86_64':
        unpack_binaries('https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz', target, ['ffmpeg', 'ffprobe'])
        deno_arch = 'x86_64-unknown-linux-gnu'
        (target / 'appimagetool.AppImage').write_bytes(download('https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage'))
    elif args.target == 'windows-x86_64':
        unpack_binaries('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', target, ['ffmpeg.exe', 'ffprobe.exe'])
        deno_arch = 'x86_64-pc-windows-msvc'
        (target / 'yt-dlp.exe').write_bytes(download('https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'))
    else:
        for name in ['ffmpeg', 'ffprobe']:
            unpack_binaries(f'https://evermeet.cx/ffmpeg/getrelease/{name}/zip', target, [name])
        deno_arch = 'x86_64-apple-darwin'
    suffix = '.exe' if args.target.startswith('windows') else ''
    unpack_binaries(f'https://github.com/denoland/deno/releases/latest/download/deno-{deno_arch}.zip', target, ['deno' + suffix])
    for path in target.iterdir():
        path.chmod(0o755)
    for name in ['ffmpeg', 'ffprobe', 'deno']:
        subprocess.run([str(target / (name + suffix)), '--version' if name == 'deno' else '-version'], check=True)
    if suffix:
        subprocess.run([str(target / 'yt-dlp.exe'), '--version'], check=True)
    # Check that the bundled encoder and decoder actually work.
    with tempfile.TemporaryDirectory() as temporary:
        audio = str(Path(temporary) / 'test.mp3')
        subprocess.run([str(target / ('ffmpeg' + suffix)), '-v', 'error', '-f', 'lavfi', '-i', 'sine=duration=0.1', audio], check=True)
        subprocess.run([str(target / ('ffprobe' + suffix)), '-v', 'error', audio], check=True)


if __name__ == '__main__':
    main()
