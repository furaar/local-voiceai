# screenshot.py — MCP tool: take screenshot and return as image for the AI to see
"""Single tool: take_screenshot. Uses gnome-screenshot, scrot, or ImageMagick import."""

import base64
import io
import os
import shutil
import subprocess
import tempfile

# Ensure display is set when run as MCP subprocess (inherit or try :0, :1)
if "DISPLAY" not in os.environ:
    for d in (":0", ":1"):
        os.environ["DISPLAY"] = d
        break

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("screenshot")

# Return only a string (data URL or error). Pipecat injects data URLs as vision in user messages.
# Avoid tuple[Image, str] — fastmcp/pydantic cannot schema Image, which crashes the tool at load.
_DATA_URL_PREFIX_JPEG = "data:image/jpeg;base64,"
_DATA_URL_PREFIX_PNG = "data:image/png;base64,"


def _find_cmd(*names: str) -> str | None:
    """Return first existing executable path (check PATH then /usr/bin)."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
        full = f"/usr/bin/{name}"
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


def _capture_to_path(path: str) -> tuple[bool, str]:
    """Capture full screen to path. Returns (success, hint message on failure)."""
    env = os.environ.copy()
    # Prefer existing DISPLAY; ensure it's set for child
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    # 1. gnome-screenshot (Ubuntu GNOME; works with X11 and often Wayland via portal)
    cmd = _find_cmd("gnome-screenshot")
    if cmd:
        try:
            r = subprocess.run(
                [cmd, "-f", path],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
                cwd="/",
            )
            if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                return (True, "")
            hint = (r.stderr or r.stdout or "").strip()[:200] or "non-zero exit"
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            hint = str(e)
    else:
        hint = "gnome-screenshot not found"

    # 2. scrot
    cmd = _find_cmd("scrot")
    if cmd:
        try:
            r = subprocess.run(
                [cmd, path],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
                cwd="/",
            )
            if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                return (True, "")
            hint = (r.stderr or r.stdout or "").strip()[:200] or "non-zero exit"
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            hint = str(e)
    else:
        hint = hint or "scrot not found"

    # 3. ImageMagick import -window root
    cmd = _find_cmd("import")
    if cmd:
        try:
            r = subprocess.run(
                [cmd, "-window", "root", path],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
                cwd="/",
            )
            if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                return (True, "")
            hint = (r.stderr or r.stdout or "").strip()[:200] or "non-zero exit"
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            hint = str(e)
    else:
        hint = hint or "import (ImageMagick) not found"

    return (False, hint)


def _friendly_hint(raw: str) -> str:
    """Turn tool stderr into a short, actionable hint."""
    raw_lower = raw.lower()
    if "unable to read x window" in raw_lower or "resource temporarily unavailable" in raw_lower or "ximportimage" in raw_lower:
        return (
            "X11 root grab failed (common on Wayland). "
            "On Ubuntu GNOME: install gnome-screenshot (works on Wayland), or scrot (X11 only): "
            "sudo apt install gnome-screenshot  or  sudo apt install scrot"
        )
    if "not found" in raw_lower or "no such file" in raw_lower:
        return "Capture tool missing. Install one: sudo apt install gnome-screenshot  or  sudo apt install scrot"
    return raw.strip()[:300] or "Unknown error"


def _image_to_data_url_jpeg(raw_bytes: bytes, png: bool = True) -> str:
    """Prefer JPEG (smaller) if Pillow is available; otherwise use PNG base64."""
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60, optimize=True)
        return _DATA_URL_PREFIX_JPEG + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        pass
    prefix = _DATA_URL_PREFIX_PNG if png else _DATA_URL_PREFIX_JPEG
    return prefix + base64.b64encode(raw_bytes).decode("ascii")


@mcp.tool()
def take_screenshot() -> str:
    """
    Take a screenshot of the current screen. Returns a data URL (image) or an error message string.
    Use this to see the current workflow, desktop, or application state.
    """
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        ok, hint = _capture_to_path(tmp_path)
        if not ok:
            return "Screenshot failed: " + _friendly_hint(hint)
        with open(tmp_path, "rb") as f:
            data = f.read()
        return _image_to_data_url_jpeg(data, png=True)
    except Exception as e:
        return f"Screenshot failed: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


if __name__ == "__main__":
    mcp.run()
