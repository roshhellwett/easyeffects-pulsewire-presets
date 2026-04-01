[![License](https://img.shields.io/badge/License-MIT-45b7d1?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-1.0.7-4ecdc4?style=flat-square)](https://pypi.org/project/projectpulsewire/)
[![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?style=flat-square&logo=linux)](https://github.com/roshhellwett/projectpulsewire)

# PROJECT PULSEWIRE

EasyEffects presets for PipeWire/PulseAudio on Linux. Transform your Linux audio experience with one command!

![SAMPLE](https://github.com/roshhellwett/projectpulsewire/blob/9b142db104c4f05d19cbabf78b11ae46ce332a1d/sample/samplezero.png)

![SAMPLE](https://github.com/roshhellwett/projectpulsewire/blob/9b142db104c4f05d19cbabf78b11ae46ce332a1d/sample/sampleone.png)

---

## 🚀 Quick Install (For Everyone)

### Step 1: Install the package

Open your terminal and run:

```bash
pip install projectpulsewire
```

### Step 2: Open the menu

```bash
python -m projectpulsewire start
```

### Step 3: Choose what to do!

```
1. Browse & Preview Presets (EQ)   ← See all available audio profiles
2. Browse & Preview IRS (Convolution)  ← See reverb/correction files  
3. Install Preset(s)                ← Install presets to EasyEffects
4. Install IRS(s)                   ← Install IRS files
5. View Installed (Presets + IRS)    ← See what you installed
6. Remove Preset(s)/IRS(s)          ← Uninstall
7. Update projectpulsewire          ← Get new versions
8. Help & Commands                  ← Learn more
9. Exit
```

### Step 4: Restart EasyEffects

After installing presets, close and reopen **EasyEffects** app. Your new presets will appear in the preset manager!

---

## 💻 Commands for Power Users

### Interactive Menu (Recommended for Beginners)
```bash
python -m projectpulsewire start
```

### List All Presets
```bash
python -m projectpulsewire list
```

### List All IRS Files  
```bash
python -m projectpulsewire list-irs
```

### Install a Specific Preset
```bash
python -m projectpulsewire install "Bass Boosted"
python -m projectpulsewire install "Rock"
python -m projectpulsewire install "Lofi"
```

### Install an IRS File
```bash
python -m projectpulsewire install-irs "BassWaves"
python -m projectpulsewire install-irs "Dolby Headphone"
```

### View Installed Items
```bash
python -m projectpulsewire installed
```

### Remove a Preset
```bash
python -m projectpulsewire remove "Bass Boosted"
```

### Update to Latest Version
```bash
python -m projectpulsewire update
```

### Get Help
```bash
python -m projectpulsewire help
python -m projectpulsewire version
```

---

## 📋 System Requirements

| Requirement | Details |
|-------------|---------|
| OS | Linux (Ubuntu, Fedora, Arch, etc.) |
| Python | 3.10 or higher |
| Audio Server | PipeWire or PulseAudio |
| Required App | [EasyEffects](https://github.com/wwmm/easyeffects) |

### How to Install EasyEffects

**Ubuntu/Debian:**
```bash
sudo apt install easyeffects
```

**Fedora:**
```bash
sudo dnf install easyeffects
```

**Arch Linux:**
```bash
sudo pacman -S easyeffects
```

---

## 🎵 What's Included?

### 37 EQ Presets
- Bass Boost, Heavy Bass, HB-Flat, HB-Lite, HB-Mid
- Rock, Classical, LoFi, EDM, Indie, K-Pop
- Sony, Bose (device-specific)
- Voice clarity presets
- Video/Movie presets
- Loudness/Auto-gain presets

### 404 IRS Files
- Dolby Surround profiles
- DFX audio enhancements
- Creative X-Fi profiles
- Bass enhancement
- Room correction
- Headphone virtualization

---

## 🔧 Where Do Presets Go?

| Type | Location |
|------|----------|
| JSON Presets | `~/.config/easyeffects/presets/` |
| IRS Files | `~/.config/easyeffects/convolver/` |

*Note: `~` means your home folder (e.g., `/home/username`)*

---

## 🆘 Troubleshooting

### "Command not found" error
Make sure Python is in your PATH. Try:
```bash
python3 -m projectpulsewire start
```

### Presets not appearing
1. Make sure you restart EasyEffects after installing
2. Check if installed: `python -m projectpulsewire installed`

### Permission denied errors
Run terminal as admin for installation:
```bash
sudo pip install projectpulsewire
```

---

## 🙏 Acknowledgments

- [EasyEffects](https://github.com/wwmm/easyeffects) - The amazing audio equalizer
- [PipeWire](https://pipewire.org/) - Modern audio server
- All preset creators in the Linux audio community

---

© 2026 [Zenith Open Source Projects](https://zenithopensourceprojects.vercel.app/). All Rights Reserved. Zenith is a Open Source Project Idea's by @roshhellwett
