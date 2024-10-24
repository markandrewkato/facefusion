import os
import shutil
import signal
import subprocess
import sys
import tempfile
from argparse import ArgumentParser, HelpFormatter
from typing import Dict, Tuple

from facefusion import metadata, wording
from facefusion.common_helper import is_linux, is_macos, is_windows

ONNXRUNTIMES : Dict[str, Tuple[str, str]] = {}

if is_macos():
	ONNXRUNTIMES['default'] = ('onnxruntime', '1.19.2')
else:
	ONNXRUNTIMES['default'] = ('onnxruntime', '1.19.2')
	ONNXRUNTIMES['cuda'] = ('onnxruntime-gpu', '1.19.2')
	ONNXRUNTIMES['openvino'] = ('onnxruntime-openvino', '1.19.0')
if is_linux():
	ONNXRUNTIMES['rocm'] = ('onnxruntime-rocm', '1.18.0')
if is_windows():
	ONNXRUNTIMES['directml'] = ('onnxruntime-directml', '1.17.3')


def cli() -> None:
	signal.signal(signal.SIGINT, lambda signal_number, frame: sys.exit(0))
	program = ArgumentParser(formatter_class = lambda prog: HelpFormatter(prog, max_help_position = 50))
	program.add_argument('--onnxruntime', help = wording.get('help.install_dependency').format(dependency = 'onnxruntime'), choices = ONNXRUNTIMES.keys(), required = True)
	program.add_argument('--skip-conda', help = wording.get('help.skip_conda'), action = 'store_true')
	program.add_argument('-v', '--version', version = metadata.get('name') + ' ' + metadata.get('version'), action = 'version')
	run(program)


def run(program : ArgumentParser) -> None:
	args = program.parse_args()
	has_conda = 'MAMBA_ROOT_PREFIX' in os.environ
	onnxruntime_name, onnxruntime_version = ONNXRUNTIMES.get(args.onnxruntime)

	if not args.skip_conda and not has_conda:
		sys.stdout.write(wording.get('conda_not_activated') + os.linesep)
		sys.exit(1)

	subprocess.call([ shutil.which('pip'), 'install', '-r', 'requirements.txt', '--force-reinstall' ])

	if args.onnxruntime == 'rocm':
		python_id = 'cp' + str(sys.version_info.major) + str(sys.version_info.minor)

		if python_id == 'cp310':
			wheel_name = 'onnxruntime_rocm-' + onnxruntime_version +'-' + python_id + '-' + python_id + '-linux_x86_64.whl'
			wheel_path = os.path.join(tempfile.gettempdir(), wheel_name)
			wheel_url = 'https://repo.radeon.com/rocm/manylinux/rocm-rel-6.2/' + wheel_name
			subprocess.call([ shutil.which('curl'), '--silent', '--location', '--continue-at', '-', '--output', wheel_path, wheel_url ])
			subprocess.call([ shutil.which('pip'), 'uninstall', 'onnxruntime', wheel_path, '-y', '-q' ])
			subprocess.call([ shutil.which('pip'), 'install', wheel_path, '--force-reinstall' ])
			os.remove(wheel_path)
	else:
		subprocess.call([ shutil.which('pip'), 'uninstall', 'onnxruntime', onnxruntime_name, '-y', '-q' ])
		subprocess.call([ shutil.which('pip'), 'install', onnxruntime_name + '==' + onnxruntime_version, '--force-reinstall' ])

	if args.onnxruntime == 'cuda' and has_conda:
		library_paths = []

		if is_linux():
			if os.getenv('LD_LIBRARY_PATH'):
				library_paths = os.getenv('LD_LIBRARY_PATH').split(os.pathsep)

			python_id = 'python' + str(sys.version_info.major) + '.' + str(sys.version_info.minor)

			root_prefix = os.getenv('MAMBA_ROOT_PREFIX') or os.getenv('CONDA_PREFIX')
			
			library_paths.extend(
			[
				os.path.join(root_prefix, 'lib'),
				os.path.join(root_prefix, 'lib', python_id, 'site-packages', 'tensorrt_libs')
			])

			# Add specific library paths containing the required libraries
			required_libs = [
				'libcudnn.so.9',  # CUDNN
				'libcublas.so.12',  # CUBLAS
				'libcublasLt.so.12',  # CUBLAS Lt
				'libcudart.so.12',  # CUDA Runtime
			]

			library_paths = [ library_path for library_path in library_paths if os.path.exists(library_path) ]

	        # Debug print to see what we're finding
			print("Debug: Found library paths:")
			for path in library_paths:
				print(f"- {path}")
				if os.path.exists(path):
					files = os.listdir(path)
					print("  Files:", [f for f in files if any(lib in f for lib in required_libs)])

			# subprocess.call([ shutil.which('micromamba'), 'env', 'config', 'vars', 'set', 'LD_LIBRARY_PATH=' + os.pathsep.join(library_paths) ])
			os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(library_paths)

			print("\nDebug: Final LD_LIBRARY_PATH:", os.environ['LD_LIBRARY_PATH'])

		if is_windows():
			if os.getenv('PATH'):
				library_paths = os.getenv('PATH').split(os.pathsep)

			library_paths.extend(
			[
				os.path.join(os.getenv('CONDA_PREFIX'), 'Lib'),
				os.path.join(os.getenv('CONDA_PREFIX'), 'Lib', 'site-packages', 'tensorrt_libs')
			])
			library_paths = [ library_path for library_path in library_paths if os.path.exists(library_path) ]

			subprocess.call([ shutil.which('conda'), 'env', 'config', 'vars', 'set', 'PATH=' + os.pathsep.join(library_paths) ])

	if onnxruntime_version < '1.19.0':
		subprocess.call([ shutil.which('pip'), 'install', 'numpy==1.26.4', '--force-reinstall' ])
