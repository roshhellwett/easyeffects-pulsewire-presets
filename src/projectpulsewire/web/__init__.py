"""
ProjectPulsewire Web Server Module.

Provides a local web server and browser dashboard to manage EasyEffects presets,
IRS convolution files, audio stack dependencies, and system configuration.
"""

from projectpulsewire.web.server import PulsewireServer, start_server

__all__ = ["PulsewireServer", "start_server"]
