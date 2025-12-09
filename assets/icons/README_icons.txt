This directory contains icon assets for the VoiceCapture application.

Files expected by the code:

- app_icon.ico
    Used as the main application icon and for the system tray.
    Path referenced from code:
    - ui.floating_window.FloatingWindow._load_icons() expects: assets/icons/app_icon.ico

- mic_idle.png
    Microphone icon for the "idle" state (Готово).
    Path referenced from code:
    - ui.floating_window.FloatingWindow._load_icons() expects: assets/icons/mic_idle.png

- mic_recording.png
    Microphone icon for the "recording" state (Запись...).
    Path referenced from code:
    - ui.floating_window.FloatingWindow._load_icons() expects: assets/icons/mic_recording.png

- mic_processing.png
    Microphone icon for the "processing" state (Обработка...).
    Path referenced from code:
    - ui.floating_window.FloatingWindow._load_icons() expects: assets/icons/mic_processing.png

Since this environment does not support binary image generation directly, you can generate or download simple icons with the following recommendations:

1) app_icon.ico
   - 256x256 (with downscaled sizes inside .ico: 256, 128, 64, 32, 16).
   - Simple glyph: white microphone or "VC" letters on a dark background (#1E1E1E or #20232A).
   - Transparent background outside the glyph.

2) mic_idle.png
   - 64x64 or 128x128 PNG with transparent background.
   - Gray microphone icon (#B0B0B0) centered.

3) mic_recording.png
   - Same size as mic_idle.png.
   - White microphone icon with a red circular background (#E53935) or red dot indicator.

4) mic_processing.png
   - Same size as mic_idle.png.
   - White microphone icon with an orange or blue circular background (#FF9800 or #2196F3), or a small spinner/clock overlay.

You can quickly create these using any icon generator or editor (Figma, Photoshop, GIMP, online icon generators) and save them with the exact filenames above into this folder.

Once the files are placed here:
- FloatingWindow will automatically pick them up for UI states.
- SystemTrayIcon will use app_icon.ico as the tray icon (via the window icon).