[![License](https://img.shields.io/badge/License-MIT-45b7d1?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-3.0.1-4ecdc4?style=flat-square)](https://pypi.org/project/projectpulsewire/)
[![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?style=flat-square&logo=linux)](https://github.com/roshhellwett/projectpulsewire)

# PROJECT PULSEWIRE

Premium EasyEffects presets for PipeWire/PulseAudio on Linux. Transform your Linux audio experience with one command!

![SAMPLE](https://github.com/roshhellwett/projectpulsewire/blob/050f1eeda9d3a7bb69efa75c78cf3007e3b20ff2/sample/samplezero.png)

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
 1   Browse & Preview Presets (EQ)           ← See all available audio profiles
 2   Browse & Preview IRS (Convolution)      ← See reverb/correction files  
 3   Install Preset(s)                       ← Install presets to EasyEffects
 4   Install IRS(s)                          ← Install IRS files
 5   View Installed (Presets + IRS)          ← See what you installed
 6   Remove Preset(s)/IRS(s)                ← Uninstall
 7   Switch Preset Source                    ← Choose between Legacy or Modern presets
 8   Update projectpulsewire                ← Get new versions
 9   Help & Commands                        ← Learn more
10   IRS Guide                              ← Learn what IRS files are & how to use them
11   Setup Audio Stack                      ← Auto-detect & install audio dependencies
 0   Exit
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
python -m projectpulsewire install "Bass - Punchy Everyday"
python -m projectpulsewire install "Brand - Harman Reference"
python -m projectpulsewire install "Voice - Dialogue Focus"
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
python -m projectpulsewire remove "Bass - Punchy Everyday"
```

### Setup Audio Stack (Auto-Install Dependencies)
```bash
python -m projectpulsewire setup
```

### IRS Guide (What are IRS files?)
```bash
python -m projectpulsewire irs-guide
```

### Update to Latest Version
```bash
python -m projectpulsewire update
```

### Automatic Update Checks

When users open the interactive app, `projectpulsewire` now checks PyPI automatically for new releases once every 24 hours.

- Set `PROJECTPULSEWIRE_DISABLE_AUTO_UPDATE=1` to disable startup checks
- Set `PROJECTPULSEWIRE_AUTO_UPDATE=1` to auto-install new releases without prompting

### Get Help
```bash
python -m projectpulsewire --help
python -m projectpulsewire version
```

---

## 📋 System Requirements

| Requirement | Details |
|-------------|---------|
| OS | Linux (Ubuntu, Fedora, Arch, etc.) |
| Python | 3.10 or higher |
| Audio Server | PipeWire (recommended) or PulseAudio |
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

**Or use the built-in auto-installer:**
```bash
python -m projectpulsewire setup
```

---

## 🔧 Audio Stack Auto-Setup (NEW in v2.0)

ProjectPulsewire can automatically detect and install all essential audio packages for your Linux distribution:

| Package | Purpose | Priority |
|---------|---------|----------|
| `pipewire` | Modern audio server | Critical |
| `pipewire-pulse` | PulseAudio compatibility | Critical |
| `pipewire-alsa` | ALSA compatibility | Critical |
| `wireplumber` | Session manager | Critical |
| `easyeffects` | Audio effects processor | Critical |
| `lsp-plugins` | Audio plugins (EQ, compressor) | Critical |
| `calf-plugins` | Audio plugins (reverb, etc.) | Recommended |
| `zam-plugins` | Maximizer and utilities | Recommended |
| `mda-lv2` | Classic LV2 plugins | Recommended |

Supports: **Ubuntu/Debian**, **Fedora**, **Arch/Manjaro**, **openSUSE**, and **Flatpak**.

---

## 🎵 What's Included?

### 47 Curated EQ Presets

The preset pack is now organized around clear sound families instead of random names, so users can predict the result before installing anything.

All presets use restrained signal chains built from **compressor**, **equalizer**, **bass enhancer**, **bass loudness**, **maximizer**, and **limiter** blocks where appropriate.

**Bass (10 presets)**
- Bass - Punchy Everyday
- Bass - Deep Sub Lift
- Bass - Warm Consumer
- Bass - Tight Kick
- Bass - Club V-Shape
- Bass - Clean Bass Lift
- Bass - Bass + Clarity
- Bass - Bass + Loudness
- Bass - Late Night Bass
- Bass - Speaker Rescue

**Genre (14 presets)**
- Genre - EDM Festival
- Genre - EDM Smooth
- Genre - Rock Arena
- Genre - Rock Classic
- Genre - Classical Wide
- Genre - Classical Warm
- Genre - Lo-Fi Soft
- Genre - Lo-Fi Air
- Genre - Indie Presence
- Genre - Indie Warm
- Genre - K-Pop Sparkle
- Genre - K-Pop Impact
- Genre - Hi-Fi Reference
- Genre - Hi-Fi Rich

**Voice (8 presets)**
- Voice - Dialogue Focus
- Voice - Dialogue Night
- Voice - Podcast Clear
- Voice - Vocal Warmth
- Voice - Gaming Footsteps
- Voice - Gaming Immersion
- Voice - Video Balanced
- Voice - Live Stage

**Brand (8 presets)**
- Brand - Bose Warm
- Brand - Bose Smooth Bass
- Brand - JBL Pure Bass
- Brand - JBL Party V
- Brand - Harman Reference
- Brand - Harman Kardon Lounge
- Brand - Sony Excited
- Brand - Sony Bright

**Dynamics (7 presets)**
- Dynamics - Loudness Light
- Dynamics - Loudness Deep
- Dynamics - Auto Gain Soft
- Dynamics - Auto Gain Punch
- Dynamics - Crystal Detail
- Dynamics - Late Night
- Dynamics - Soft Volume Lift

Brand presets are **brand-inspired voicings**, not official Bose, JBL, Harman, Harman Kardon, or Sony factory profiles.

### 404 IRS Files
- Dolby Surround profiles
- DFX audio enhancements
- Creative X-Fi profiles
- Bass enhancement
- Room correction
- Headphone virtualization

---

## 🎓 IRS Files — What Are They?

**IRS (Impulse Response)** files capture the sonic signature of a real acoustic space or audio device. When loaded into EasyEffects' **Convolver** plugin, they shape your audio to sound like it's being played through that space/device.

### How to Use IRS Files

1. Install an IRS file using the interactive menu (option 4)
2. Open **EasyEffects** → **Output Effects**
3. Click **Add Effect** → Select **Convolver**
4. In Convolver settings, click the **import/file icon**
5. Browse to your IRS directory and select the `.irs` file
6. **Important:** Add a **Limiter** after the Convolver to prevent clipping

### IRS Categories
| Category | Best For |
|----------|----------|
| Bass | Adding deep low-end to weak speakers |
| Dolby | Surround sound on stereo headphones |
| DFX | General audio enhancement & clarity |
| Creative | Gaming 3D audio & spatial sound |

---

## 🔧 Where Do Files Go?

| Type | Native Location | Flatpak Location |
|------|-----------------|-------------------|
| JSON Presets | `~/.config/easyeffects/output/` | `~/.var/app/com.github.wwmm.easyeffects/config/easyeffects/output/` |
| IRS Files | `~/.config/easyeffects/irs/` | `~/.var/app/com.github.wwmm.easyeffects/config/easyeffects/irs/` |

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

### Missing audio plugins
Run the auto-setup to install all required packages:
```bash
python -m projectpulsewire setup
```

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

© 2026 [Zenith Open Source Projects](https://zenithopensourceprojects.vercel.app/). All Rights Reserved. Zenith is an Open Source Project Idea by @roshhellwett
