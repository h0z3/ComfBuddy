# ComfBuddy

A tiny floating desktop companion for [ComfyUI](https://github.com/comfyanonymous/ComfyUI).
A pixel-art green ghost that floats on your desktop and gives you quick shortcuts
for the things you do every day with ComfyUI — right from a single right-click.

## Features

- **Floating pixel-art buddy** — frameless, always-on-top, draggable anywhere on screen
- **Idle bob animation** with a soft dynamic shadow
- **Right-click menu** with the shortcuts you actually need:
  - **Clear VRAM** — unloads models from VRAM via the ComfyUI `/free` endpoint
  - **Restart ComfyUI** — kills the ComfyUI Desktop process and relaunches it
  - **Open Output Folder** — opens your output directory in Explorer
  - **Quit**
- **Position is remembered** between runs (saved to `config.json`)
- Single-file Python script — easy to read, easy to hack

## Requirements

- Windows 10 / 11
- Python 3.9+
- [ComfyUI Desktop](https://www.comfy.org/download) running locally (default port `8188`)

## Installation

### Option 1: Standalone (Recommended for non-ComfyUI users)

```bash
git clone https://github.com/teq3l/ComfBuddy.git
cd ComfBuddy
pip install -r requirements.txt
python comfbuddy.py
```

### Option 2: ComfyUI Custom Node (Auto-launches with ComfyUI)

Clone into your ComfyUI's `custom_nodes/` directory:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/teq3l/ComfBuddy.git
cd ComfBuddy
pip install -r requirements.txt
```

Then restart ComfyUI. The buddy will automatically launch in the background.

**To disable auto-launch:**
Set the environment variable before starting ComfyUI:
```bash
set COMFBUDDY_AUTOLAUNCH=0
```

## Usage

- **Left-click + drag** — move the buddy anywhere on screen
- **Right-click** — open the shortcut menu
- The window position is saved to `config.json` whenever you release the buddy

## Configuration

A `config.json` file is created automatically next to `comfbuddy.py` on first
drag. You can edit it to change defaults:

```json
{
  "comfyui_url":   "http://127.0.0.1:8188",
  "output_folder": "C:/Users/YOU/AppData/Roaming/ComfyUI/output",
  "position":      [200, 200],
  "scale":         4
}
```

| Field           | Description                                              |
| --------------- | -------------------------------------------------------- |
| `comfyui_url`   | Base URL of your running ComfyUI instance                |
| `output_folder` | Folder opened by the **Open Output Folder** action       |
| `position`      | Last saved window position (auto-updated on drag)        |
| `scale`         | Pixel scale of the sprite (`4` = 64×64 px window)        |

## How VRAM clearing works

ComfBuddy sends a `POST` request to ComfyUI's built-in `/free` endpoint:

```json
{ "unload_models": true, "free_memory": true }
```

This unloads all currently-loaded models from VRAM without restarting the
server, which is perfect for the "I want to switch workflows but my VRAM is
already full" situation.

## How restart works

ComfBuddy looks for the ComfyUI Desktop process by name (`ComfyUI Desktop.exe`,
`ComfyUI.exe`, `comfyui-electron.exe`), terminates it, waits 2 seconds, and
relaunches it from a list of common install locations. If the executable
isn't found in any of those, it falls back to `start ComfyUI Desktop` via the
shell.

## Roadmap

- [ ] Linux / macOS support
- [ ] Configurable shortcut list
- [ ] More animations (blink, hover reactions)
- [ ] Custom sprite loader (drop in your own PNG / GIF)
- [ ] Notification toast when actions complete

## Contributing

PRs welcome — especially for new buddy sprites, extra menu actions, or
cross-platform support. Open an issue first if you want to discuss a bigger
change.

## Built With

Built with **vibe coding** alongside [Claude](https://claude.ai). The entire project —
from pixel-art sprite to ComfyUI integration — came together in a single session of
rapid iteration, feedback loops, and "let's just try it" energy.

## License

[MIT](LICENSE) © teq3l
