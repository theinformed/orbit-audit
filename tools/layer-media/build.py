"""Build only the thermosphere lesson, without browser, network, or GPU.

Consumer/current reference: src/layer-pages.ts imports exactly one MP4/WebP pair.
Budget: delivered pair <= 4 MiB; manifest <= 32 KiB; scratch <= 128 MiB.
Retention: overwrite the pair; TemporaryDirectory removes scratch on exit. No archive.
Dry run (default): print the plan. Pass --write to render, OCR-check, and replace.
Requires Python with manim, ffmpeg and tesseract. Use a CPU renderer, one encoder thread.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    if not args.write:
        print('Render one 1280×720 / 10 fps / 20.9 s CPU clip; OCR poster and three frames; replace src/media/thermosphere.{mp4,webp,render.json}. No network. Scratch <= 128 MiB, delivered pair <= 4 MiB.')
        return
    spec = json.loads((HERE/'thermosphere.json').read_text())
    with tempfile.TemporaryDirectory(prefix='thermosphere-media-') as directory:
        scratch = Path(directory)
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        config = scratch/'manim.cfg'
        config.write_text('[CLI]\nnotify_outdated_version = False\nffmpeg_loglevel = ERROR\n')
        run(sys.executable, '-m', 'manim', '--renderer=cairo', '--disable_caching',
            '--config_file', str(config), '--media_dir', directory, '-r', '1280,720', '--fps', '10',
            str(HERE/'thermosphere.py'), 'Thermosphere', env=env)
        rendered = next(scratch.glob('videos/**/Thermosphere.mp4'))
        video = scratch/'thermosphere.mp4'
        run('ffmpeg', '-v', 'error', '-y', '-i', str(rendered), '-an', '-c:v', 'libx264',
            '-threads', '1', '-crf', '23', '-pix_fmt', 'yuv420p',
            '-vf', 'tpad=stop_mode=clone:stop_duration=1', '-t', str(spec['durationSeconds']),
            '-movflags', '+faststart', str(video))
        probe = run('ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'json', str(video), capture_output=True, text=True)
        duration = float(json.loads(probe.stdout)['format']['duration'])
        assert abs(duration - spec['durationSeconds']) < 0.01, duration
        poster = scratch/'thermosphere.webp'
        run('ffmpeg', '-v', 'error', '-y', '-ss', str(spec['posterSeconds']), '-i', str(video),
            '-frames:v', '1', '-threads', '1', '-quality', '90', str(poster))
        samples = []
        for second in [0, spec['posterSeconds'], 20]:
            frame = scratch/f'frame-{second}.png'
            run('ffmpeg', '-v', 'error', '-y', '-ss', str(second), '-i', str(video),
                '-frames:v', '1', '-threads', '1', str(frame))
            result = run('tesseract', str(frame), 'stdout', '--psm', '11', capture_output=True, text=True)
            words = ' '.join(result.stdout.split())
            assert spec['headline'].lower() in words.lower(), words
            assert 'five orders' not in words.lower(), words
            samples.append({'second': second, 'ocr': words})
        result = run('tesseract', str(poster), 'stdout', '--psm', '11', capture_output=True, text=True)
        poster_words = ' '.join(result.stdout.split())
        assert spec['headline'].lower() in poster_words.lower(), poster_words
        assert sum(p.stat().st_size for p in scratch.rglob('*') if p.is_file()) <= 128*1024**2
        assert video.stat().st_size + poster.stat().st_size <= 4*1024**2
        provenance = {
            'inputs': {str(p.relative_to(ROOT)): sha(p) for p in [HERE/'thermosphere.json', HERE/'thermosphere.py', Path(__file__).resolve()]},
            'outputs': {f'src/media/{p.name}': sha(p) for p in [video, poster]},
            'samples': samples, 'posterOcr': poster_words, 'durationSeconds': duration,
        }
        manifest = json.dumps(provenance, indent=2) + '\n'
        assert len(manifest.encode()) <= 32*1024
        for p in [video, poster]:
            (ROOT/'src/media'/p.name).write_bytes(p.read_bytes())
        (ROOT/'src/media/thermosphere.render.json').write_text(manifest)
        print('Built and OCR-verified poster + video:', video.stat().st_size + poster.stat().st_size, 'bytes')

if __name__ == '__main__':
    main()
