"""
Katana scene tool wrapper.

Common entry point for SquidNet scene operations:
    katana --batch --script katana_scene_tool.py -- --request <request.json>
"""

import json
import os
import shutil
import sys
import traceback

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _wrapper_args():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    for idx, arg in enumerate(args):
        if arg == "--request" and idx + 1 < len(args):
            return args[idx + 1]
    raise RuntimeError("Expected --request <request.json>")


def _path(request, key, fallback=None):
    """Look up a path key in request['paths'] then in request directly."""
    return (
        request.get("paths", {}).get(key)
        or request.get(key)
        or fallback
    )


def _write_status(request, state, exit_code, message, warnings=None, errors=None):
    status_path = _path(request, "statusPath")
    if not status_path:
        return
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    with open(status_path, "w", encoding="utf-8") as fh:
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
            fh,
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
        os.path.join(renderfarm_dir, "katana_file_list.txt"),
        _path(request, "fileListPath"),
    )
    _copy_if_needed(
        os.path.join(renderfarm_dir, "analysis_log.txt"),
        _path(request, "analysisLogPath"),
    )


def _run_analyze(request):
    from katana_analyzer import main as analyze_main

    scene_path = _path(request, "scenePath")
    if scene_path:
        scene_path = os.path.realpath(scene_path)

    sync_dir = _path(request, "syncDir")
    profile_json = _path(request, "profileJsonPath")

    analyze_main(scene_path, sync_dir, profile_json)
    _normalize_outputs(request)


def _run_repath(request):
    from katana_repath import main as repath_main

    sync_dir = _path(request, "syncDir")
    scene_rel_path = _path(request, "sceneRelPath")
    web_ui_data_path = _path(request, "webUiDataPath")

    missing = [
        name for name, value in (
            ("syncDir", sync_dir),
            ("sceneRelPath", scene_rel_path),
            ("webUiDataPath", web_ui_data_path),
        )
        if not value
    ]
    if missing:
        raise ValueError("Missing required Katana repath path(s): {}".format(", ".join(missing)))

    repath_main(sync_dir, scene_rel_path, web_ui_data_path)


def main():
    request_path = _wrapper_args()
    with open(request_path, "r", encoding="utf-8") as fh:
        request = json.load(fh)

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
