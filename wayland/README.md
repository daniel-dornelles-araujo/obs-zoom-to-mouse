# How to

- Copy this folder to ~/bin (keep `kwin-cursor-helper.py` next to the lua script)
- Load lua script and set keyboard shortcut Shift + Alt + Z
- Enable web socket and disable authentication
- Add KDE global shortcut and select ~/bin/obs-zoom-toggle.sh. Set shortcut Shift + Alt + Z

## KDE Plasma (Wayland) cursor tracking

KWin doesn't expose the cursor position to other apps, so on KDE the lua script
starts `kwin-cursor-helper.py` on the host. The helper loads a small KWin script
that reports the cursor position and the geometry of a window. It needs
`python3` with PyGObject (`python3-gobject` on Fedora, `python-gobject` on Arch).

When OBS runs as a Flatpak, the helper is started with `flatpak-spawn --host`.
That needs talk access to `org.freedesktop.Flatpak`:

    flatpak override --user --talk-name=org.freedesktop.Flatpak com.obsproject.Studio

## Zooming a window capture ("Screen Capture (PipeWire)" of a single window)

A window capture only contains that window, so the cursor has to be converted
from screen coordinates into window coordinates. Without that, the zoom gets
stuck in a corner. In the script settings:

1. Check **Source captures a single window (KDE)**.
2. In **Window to track**, enter part of the window's app class or title, such
   as `firefox`, `code` or `konsole`. Leave it empty to follow whatever window
   is active.

The window's position, size and HiDPI scaling are tracked live, so you can
move or resize the window while recording.

## Hotkeys don't work outside the OBS Window

On KDE Plasma with Wayland, Hotkeys need to be configured in KDE, not in OBS, or they will only work when the OBS Window is active.

But first KDE need to know those shortcuts exist. Use the `obs-wayland-hotkeys` plugin to create entries in the KDE system settings and bind them to OBS.

1. Install the plugin:
	• Flatpak: Install com.obsproject.Studio.Plugin.WaylandHotkeys via Flathub or your software center.
	• Arch / AUR: Install obs-wayland-hotkeys or obs-wayland-hotkeys-git.
	• Fedora / Other: Install via COPR (obs-studio-plugin-wayland-hotkeys) or build from the GitHub repo.
2. Register shortcuts: Restart OBS; a KDE system prompt will appear asking to register global shortcuts.
3. Bind your keys in KDE: Open KDE System Settings > Keyboard > Shortcuts > OBS Studio to assign your actual key combinations. (Note: If you later add new scenes in OBS, you may need to remove the OBS entry in KDE Shortcuts and restart OBS so it refreshes the list).