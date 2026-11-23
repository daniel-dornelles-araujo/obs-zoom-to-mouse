#!/usr/bin/env python3
"""
KWin (Plasma 6 Wayland) cursor helper for obs-zoom-to-mouse-wayland.lua

KWin no longer exposes the cursor position over D-Bus and print() output from
KWin scripts is usually not written to the journal, so this helper:
  1. owns a D-Bus name on the session bus,
  2. loads a small KWin script that calls back into this helper (callDBus)
     every time the cursor moves,
  3. writes "cx,cy,wx,wy,ww,wh" (cursor + frame geometry of the tracked window,
     all in global logical coordinates) to the output file.

The tracked window is the first normal window whose resourceClass or caption
contains --window (case-insensitive); if no match / empty, the active window.

Usage: kwin-cursor-helper.py --out FILE [--window MATCH] [--parent-pid PID]
"""

import argparse
import json
import os
import signal
import sys
import tempfile

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

BUS_NAME = "io.github.obszoomtomouse.CursorHelper"
OBJ_PATH = "/io/github/obszoomtomouse/CursorHelper"
IFACE = "io.github.obszoomtomouse.CursorHelper"
KWIN_SCRIPT_NAME = "obs-zoom-to-mouse-cursor"

INTROSPECTION = f"""
<node>
  <interface name="{IFACE}">
    <method name="Update"><arg type="s" name="data" direction="in"/></method>
  </interface>
</node>
"""

KWIN_JS = r"""
var MATCH = %(match)s;
function allWindows() {
    if (workspace.windowList) return workspace.windowList();   // Plasma 6
    if (workspace.clientList) return workspace.clientList();   // Plasma 5
    return [];
}
function findWindow() {
    if (MATCH) {
        var list = allWindows();
        for (var i = 0; i < list.length; i++) {
            var w = list[i];
            if (!w.normalWindow) continue;
            var rc = String(w.resourceClass || "").toLowerCase();
            var cap = String(w.caption || "").toLowerCase();
            if (rc.indexOf(MATCH) !== -1 || cap.indexOf(MATCH) !== -1) return w;
        }
    }
    return workspace.activeWindow || workspace.activeClient || null;
}
function send() {
    var c = workspace.cursorPos;
    var w = findWindow();
    var g = w ? w.frameGeometry : null;
    var s = Math.round(c.x) + "," + Math.round(c.y);
    if (g) s += "," + Math.round(g.x) + "," + Math.round(g.y) + "," + Math.round(g.width) + "," + Math.round(g.height);
    callDBus("%(bus)s", "%(path)s", "%(iface)s", "Update", s);
}
workspace.cursorPosChanged.connect(send);
send();
"""


def kwin_call(bus, method, args, sig):
    return bus.call_sync(
        "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", method,
        GLib.Variant(sig, args) if sig else None, None,
        Gio.DBusCallFlags.NONE, 2000, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--window", default="")
    ap.add_argument("--parent-pid", type=int, default=0)
    opts = ap.parse_args()

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = GLib.MainLoop()
    tmp_out = opts.out + ".tmp"
    last = [None]

    def on_call(_conn, _sender, _path, _iface, method, params, invocation):
        if method == "Update":
            data = params.unpack()[0]
            if data != last[0]:
                last[0] = data
                try:
                    with open(tmp_out, "w") as f:
                        f.write(data + "\n")
                    os.replace(tmp_out, opts.out)
                except OSError:
                    pass
        invocation.return_value(None)

    node = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)
    bus.register_object(OBJ_PATH, node.interfaces[0], on_call, None, None)

    # Replace any previous helper instance (e.g. after reloading the OBS script)
    Gio.bus_own_name_on_connection(
        bus, BUS_NAME,
        Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT | Gio.BusNameOwnerFlags.REPLACE,
        None, lambda *_: loop.quit())

    def unload():
        try:
            kwin_call(bus, "unloadScript", (KWIN_SCRIPT_NAME,), "(s)")
        except GLib.Error:
            pass

    unload()
    js = KWIN_JS % {"match": json.dumps(opts.window.strip().lower()),
                    "bus": BUS_NAME, "path": OBJ_PATH, "iface": IFACE}
    fd, js_path = tempfile.mkstemp(prefix="obs-zoom-kwin-", suffix=".js")
    with os.fdopen(fd, "w") as f:
        f.write(js)
    try:
        kwin_call(bus, "loadScript", (js_path, KWIN_SCRIPT_NAME), "(ss)")
        kwin_call(bus, "start", None, None)
    except GLib.Error as e:
        print(f"Failed to load KWin script: {e.message}", file=sys.stderr)
        os.unlink(js_path)
        return 1

    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        signal_add = GLibUnix.signal_add
    except (ImportError, ValueError):
        signal_add = GLib.unix_signal_add
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])

    if opts.parent_pid > 0:
        def check_parent():
            try:
                os.kill(opts.parent_pid, 0)
                return True
            except ProcessLookupError:
                loop.quit()
                return False
            except PermissionError:
                return True
        GLib.timeout_add_seconds(2, check_parent)

    try:
        loop.run()
    finally:
        unload()
        for p in (js_path, opts.out, tmp_out):
            try:
                os.unlink(p)
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
