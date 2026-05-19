import datetime
import os
import sys

IS_PY2 = sys.version_info[0] == 2


def to_unicode(s):
    if s is None:
        return ""
    if IS_PY2:
        if isinstance(s, unicode):  # noqa: F821
            return s
        try:
            return s.decode("utf-8")
        except Exception:
            return s.decode("latin-1", "ignore")
    if isinstance(s, bytes):
        try:
            return s.decode("utf-8")
        except Exception:
            return s.decode("latin-1", "ignore")
    return str(s)


def to_bytes(s):
    if s is None:
        return b""
    if isinstance(s, bytes):
        return s
    return str(s).encode("utf-8")


def ensure_dir(path):
    if path and not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception:
            pass


class MessageLogger:
    def __init__(self, filename, append=True):
        folder = os.path.dirname(os.path.abspath(filename))
        if folder:
            ensure_dir(folder)
        if (not append) and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass
        self.filename = filename

    def log(self, message):
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            timestamp = "0000-00-00 00:00:00"
        line = "{}: {}\n".format(to_unicode(timestamp), to_unicode(str(message)))
        print("LOG: {}".format(line.strip()))
        try:
            with open(self.filename, "ab") as f:
                f.write(to_bytes(line))
        except Exception as e:
            print("ERROR: Failed to write to log {}: {}".format(self.filename, e))
            try:
                ensure_dir(os.path.dirname(self.filename))
                with open(self.filename, "ab") as f:
                    f.write(to_bytes(line))
            except Exception as e2:
                print("ERROR: Retry failed: {}".format(e2))

    def path(self):
        return self.filename

    def add_header(self, header_text):
        self.log("=" * 80)
        self.log(header_text)
        self.log("=" * 80)


def get_logger(scene_path, sync_dir):
    from .katana_constants import LOG_DIR, LOG_FILE
    logger_path = os.path.join(sync_dir, LOG_DIR, LOG_FILE)
    ensure_dir(os.path.dirname(logger_path))
    logger = MessageLogger(logger_path, append=False)
    logger.add_header("Katana Analyzer Script")
    logger.log("Scene path: {}".format(scene_path))
    logger.log("Sync dir: {}".format(sync_dir))
    return logger, logger_path
