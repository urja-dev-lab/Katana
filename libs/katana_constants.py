CACHE_EXTENSIONS = {
    ".abc", ".vdb", ".bgeo", ".bgeo.sc", ".cache", ".sim",
    ".usd", ".usda", ".usdc", ".usdz",
}
GEOMETRY_EXTENSIONS = {".obj", ".fbx", ".ass", ".rib", ".bphys", ".geo"}
TEXTURE_EXTENSIONS = {
    ".exr", ".tx", ".tex", ".tif", ".tiff", ".png", ".jpg", ".jpeg",
    ".hdr", ".rat", ".bmp", ".tga", ".dpx", ".cin", ".sgi", ".psd",
}
LIGHT_PROFILE_EXTENSIONS = {".ies", ".ldt", ".eulumdat"}
LUT_EXTENSIONS = {".ocio", ".cube", ".lut", ".cc", ".ccc", ".cdl"}
SCENE_EXTENSIONS = {".katana"}

ALL_ASSET_EXTENSIONS = (
    CACHE_EXTENSIONS | GEOMETRY_EXTENSIONS | TEXTURE_EXTENSIONS
    | LIGHT_PROFILE_EXTENSIONS | LUT_EXTENSIONS | SCENE_EXTENSIONS
)

# UDIM tile token patterns
UDIM_TOKENS = ("<UDIM>", "<udim>", "%(UDIM)d", "$(UDIM)")

# Numeric UDIM/frame sequence pattern (e.g. texture.1001.tx or frame.0001.exr)
UDIM_DIGIT_PATTERN = r"\.\d{4}\."

# Frame sequence patterns in file names
SEQ_PATTERNS = [r"\.\d{4,}\.", r"\.\d{3,}$"]

LOG_DIR = "renderfarm"
LOG_FILE = "analysis_log.txt"
FILE_LIST = "katana_file_list.txt"
WEB_JSON_FILE = "web_ui_data.json"
REPATH_LOG_FILE = "repath_log.txt"
REPATH_REPORT_FILE = "repath_report.json"

# Katana parameter name keywords that suggest file paths
FILE_PARAM_KEYWORDS = {
    "filename", "file", "path", "texture", "image", "cache", "source",
    "asset", "scene", "lut", "icc", "env", "hdri", "map", "volume",
    "geo", "archive", "look", "lightfile", "profile", "url",
}
