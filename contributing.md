# Contributing to projectpulsewire

Thank you for your interest in contributing! This project aims to make Linux audio amazing for everyone.

## Ways to Contribute

- **Submit new presets** - Add new EQ or audio profiles
- **Submit new IRS files** - Add impulse response files
- **Report bugs** - Help us improve stability
- **Suggest features** - Share your ideas
- **Improve documentation** - Help others get started
- **Share the project** - Star us on GitHub!

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip
- Linux with EasyEffects installed
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/roshhellwett/projectpulsewire.git
cd projectpulsewire

# Install in development mode
pip install -e .

# Run the project
python -m projectpulsewire start
```

---

## Project Structure

```
projectpulsewire/
├── src/projectpulsewire/
│   ├── __init__.py      # Version and imports
│   ├── __main__.py      # Entry point
│   ├── cli.py           # Interactive menu
│   ├── presets.py       # Preset loading/install logic
│   └── irs_handler.py   # IRS file handling
├── presets/             # JSON preset files (37 files)
├── irs/                # IRS impulse response files (404 files)
├── readme.md           # User documentation
├── contributing.md     # This file
├── security.md          # Security policy
├── license             # MIT License
└── pyproject.toml      # Package configuration
```

---

## Adding New Presets

### JSON Preset Format

1. Add your preset JSON file to the `presets/` folder
2. Use EasyEffects to export your preset as JSON
3. Ensure the file follows this structure:

```json
{
  "output": {
    "equalizer#0": {
      "balance": 0.0,
      "bypass": false,
      "input-gain": 0.0,
      "left": {
        "band0": {
          "frequency": 1000.0,
          "gain": 0.0,
          "mode": "RLC (BT)",
          "mute": false,
          "q": 0.0,
          "slope": "x1",
          "solo": false,
          "type": "Bell",
          "width": 4.0
        }
      },
      "mode": "IIR",
      "num-bands": 1,
      "output-gain": 0.0
    },
    "plugins_order": ["equalizer#0"]
  }
}
```

### Naming Convention

- Use descriptive names: `Bass Boost.json`, `Rock.json`, `Voice Clarity.json`
- Use lowercase with underscores: `my_awesome_preset.json`
- Avoid special characters: `-`, `_` are okay; spaces, emoji, etc. are not

### Preset Categories

Place presets in appropriate category by name:
- **Bass**: Contains "bass", "hb-", "heavy"
- **Loudness**: Contains "loudness", "dynamics", "autogain"
- **Music Genre**: Contains "rock", "lofi", "edm", "classical"
- **Device**: Contains "sony", "bose"
- **Voice**: Contains "dialogue", "clarity"
- **Video**: Contains "video"

---

## Adding New IRS Files

### IRS File Format

1. Add your `.irs` file to the `irs/` folder
2. Use valid impulse response files (WAV, FLAC converted)

### Naming Convention

- Use descriptive names: `BassWaves.irs`, `Dolby Headphone.irs`
- Use lowercase with underscores: `my_room_correction.irs`

### IRS Categories

IRS files are auto-categorized by keywords:
- **Dolby**: Contains "dolby"
- **DFX**: Contains "dfx"
- **Creative**: Contains "creative", "x-fi"
- **Bass**: Contains "bass"
- **Headphone**: Contains "headphone"

---

## Coding Standards

- Use meaningful variable names
- Add comments for complex logic
- Keep functions focused and small (under 50 lines)
- Test your changes before submitting
- Handle errors gracefully with user-friendly messages

### Error Handling

When adding new functions:

```python
def my_function(data):
    # Validate input
    if not data:
        return False, "Error: No data provided"
    
    try:
        # Do something
        return True, "Success!"
    except PermissionError:
        return False, "Permission denied. Check folder permissions."
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
```

---

## Testing Your Changes

### Manual Testing

```bash
# Install your changes
pip install -e .

# Test the CLI
python -m projectpulsewire --version
python -m projectpulsewire list
python -m projectpulsewire start

# Test installation
python -m projectpulsewire install "Bass Boosted"
python -m projectpulsewire remove "Bass Boosted"
```

### Code Tests

```bash
# Test imports
python -c "from projectpulsewire import presets, irs_handler"

# Test preset loading
python -c "from projectpulsewire.presets import get_all_presets; print(len(get_all_presets()))"

# Test IRS loading
python -c "from projectpulsewire.irs_handler import get_all_irs; print(len(get_all_irs()))"
```

---

## Submitting Changes

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/my-new-feature`
3. **Make** your changes
4. **Test** thoroughly
5. **Commit** with clear messages: `git commit -m "Add new Bass Boost preset"`
6. **Push** to your fork: `git push origin feature/my-new-feature`
7. **Submit** a pull request

### Commit Message Format

```
type(scope): description

- Added new feature
- Fixed bug in installer
- Updated documentation
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`

---

## Communication

- **Issues**: Open a GitHub issue for bugs or features
- **Discussions**: Use GitHub Discussions for questions
- **Feedback**: Share your experience!

---

© 2026 [Zenith Open Source Projects](https://zenithopensourceprojects.vercel.app/). All Rights Reserved. Zenith is an Open Source Project Idea by @roshhellwett
