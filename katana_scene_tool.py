"""
Katana scene tool wrapper.

Common entry point for SquidNet scene operations. Mirrors the Maya/Blender
wrappers: reads a request JSON describing the operation and the resolved
paths, then dispatches to katana_analyzer or katana_repath.
"""

import json
import os
import shutil
import sys
import traceback


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


ANALYZER_FILE_LIST = "katana_file_list.txt"
ANALYZER_MODULE = "katana_analyzer"
REPATH_MODULE = "katana_repath"
USE_DOUBLE_DASH = True


def _wrapper_args():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    for idx, arg in enumerate(args):
        if arg == "--request" and idx + 1 < len(args):
            return args[idx + 1]
    raise RuntimeError("Expected --request <request.json>")


def _path(request, key, fallback=None):
    return request.get("paths", {}).get(key) or fallback


def _write_status(request, state, exit_code, message, warnings=None, errors=None):
    status_path = _path(request, "statusPath")
    if not status_path:
        return

    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    with open(status_path, "w", encoding="utf-8") as status_file:
        json.dump(
            {
                "schemaVersion": 1,
                "operation": request.get("operation"),
                "state": state,
                "exitCode": exit_code,
                "message": message,
                "warnings": warnings or [],
                "errors": errors or [],
            },
            status_file,
            indent=2,
        )


def _copy_if_needed(source, target):
    if not source or not target:
        return
    if os.path.normcase(os.path.abspath(source)) == os.path.normcase(os.path.abspath(target)):
        return
    if os.path.exists(source):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)


def _normalize_outputs(request):
    renderfarm_dir = _path(request, "renderfarmDir")
    if not renderfarm_dir:
        return

    _copy_if_needed(
        os.path.join(renderfarm_dir, ANALYZER_FILE_LIST),
        _path(request, "fileListPath"),
    )


def _build_analyzer_argv(request):
    argv = [sys.argv[0]]
    if USE_DOUBLE_DASH:
        argv.append("--")
    argv.extend(
        [
            _path(request, "scenePath") or "",
            _path(request, "syncDir") or "",
            _path(request, "profileJsonPath") or "",
            _path(request, "syncDir") or "",
        ]
    )
    return argv


def _run_analyze(request):
    import importlib

    analyzer = importlib.import_module(ANALYZER_MODULE)
    sys.argv = _build_analyzer_argv(request)
    try:
        analyzer.main()
    finally:
        _normalize_outputs(request)


def _run_repath(request):
    import importlib

    repath = importlib.import_module(REPATH_MODULE)
    sys.argv = _build_analyzer_argv(request)
    repath.main()


def main():
    request_path = _wrapper_args()
    with open(request_path, "r", encoding="utf-8") as request_file:
        request = json.load(request_file)

    operation = request.get("operation")
    try:
        if operation == "analyze":
            _run_analyze(request)
        elif operation == "repath":
            _run_repath(request)
        else:
            raise ValueError("Unsupported Katana scene operation: {}".format(operation))

        _write_status(request, "success", 0, "{} completed.".format(operation))
        return 0
    except SystemExit as exc:
        code = int(exc.code or 0)
        state = "success" if code == 0 else "failed"
        _write_status(request, state, code, "{} exited with code {}.".format(operation, code))
        return code
    except Exception as exc:
        _write_status(
            request,
            "failed",
            1,
            "{} failed: {}".format(operation, exc),
            errors=[traceback.format_exc()],
        )
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
