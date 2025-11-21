# Emagic MIDI Interface Management (EMMA)

***The state of the current code in this branch is development. Don't expect any of the features working or not frying your hardware. You've been warned!***

This is a Python3 and PyQt6 application designed to configure Emagic MIDI interfaces from the Unitor8 family (mt4, amt8, Unitor8) via MIDI/SysEx.

## Features (Planned/Implemented)

-   **Device Detection**: Automatically detects connected Emagic MIDI interfaces (mt4, amt8, Unitor8) using `lsusb` and lists their capabilities.
-   **Patch Overview**: Displays a list of 32 internal patches with their names and numbers.
-   **Patch Editor**: Allows editing of individual patches, including:
    -   Patch name and storage slot.
    -   MIDI routing matrix (connecting IN ports to OUT ports).
    -   Timecode format settings (LTC SMPTE, LTC AES/EBU, VITC, Off).
-   **Device Communication**: 
    -   Load patches from the connected device.
    -   Save modified patches to the connected device.
    -   PANIC! function (sends all notes off).

## Setup and Installation

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone <repository-url>
    cd emma2
    ```

2.  **Install dependencies**:
    This application requires `PyQt6` and `mido` (with a backend like `python-rtmidi`).
    It's recommended to use a Python virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: .\venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Install `usbutils` (for `lsusb`)**:
    On Debian/Ubuntu-based systems:
    ```bash
    sudo apt-get update
    sudo apt-get install usbutils
    ```
    On Fedora/RHEL-based systems:
    ```bash
    sudo dnf install usbutils
    ```
    Make sure `lsusb` is in your system's PATH.

4.  **Connect your Emagic MIDI Interface**.

## Running the Application

Activate your virtual environment (if you created one) and run the main script:

```bash
source venv/bin/activate
python3 src/main.py
```

## Current Status
- **Device Detection**: Working (via `lsusb`).
- **Firmware Version**: Working (Verified with Unitor8 mkII).
- **Patch Management**: 
    - **Editor**: Functional GUI for editing patch parameters.
    - **Save to Device**: Implemented (needs verification).
    - **Load from Device**: Experimental (Protocol for requesting patches is currently under investigation).
- **SysEx Debugger**: Included for manual testing and reverse engineering.

## Troubleshooting
- **No Devices Detected**: Ensure `lsusb` is installed (`usbutils`) and the device is connected via USB.
- **Permission Denied**: Ensure your user has permission to access MIDI ports (usually `audio` group).
- **SysEx Errors**: Use the "SysEx Debugger" tab to monitor traffic. If "Load from Device" fails, try using the debugger to send manual commands.

## Development
- `src/emagic_sysex.py`: Core SysEx logic.
- `src/main.py`: Main application and GUI.
- `verify_hardware.py`: Script for verifying hardware communication without the GUI.

## License
MIT

## Usage

1.  **Device Detection**: Upon launching, the application will attempt to detect connected Emagic devices and list them in the "Patch Overview" tab.
2.  **Patch Overview**: A list of 32 patches is displayed. Double-click a patch to open it in the "Patch Editor View".
3.  **Patch Editor View**: 
    -   Edit the patch name, select a storage slot, and configure timecode options.
    -   The MIDI routing matrix will dynamically adjust based on the detected device's ports. Click checkboxes to establish connections between IN and OUT ports.
4.  **Toolbar Actions**:
    -   **Load from Device**: Reads all 32 patches from the connected Emagic interface.
    -   **Save to Device**: Writes all 32 patches to the connected Emagic interface.
    -   **PANIC!**: Sends an "All Notes Off" message across all MIDI channels to silence stuck notes.

## Developer Documentation

### Project Structure

-   `src/`: Contains the core application logic.
    -   `main.py`: The main PyQt6 application, including GUI setup, device detection, and overall application flow.
    -   `emagic_sysex.py`: Handles Emagic-specific MIDI SysEx message generation and parsing.
-   `docs/`: Project documentation, including official SysEx specifications (PDFs).
-   `tests/`: Unit and integration tests.
-   `resources/`: Application assets (e.g., icons).

### Key Architectural Decisions

-   **PyQt6 for GUI**: Provides a robust, cross-platform graphical user interface.
-   **Separation of Concerns**: UI logic (`main.py`) is decoupled from MIDI communication and SysEx protocol details (`emagic_sysex.py`).
-   **`EmagicMidiConfig`**: Manages the application's state, including detected devices, a list of `EmagicPatch` objects, and the MIDI communication flow.
-   **`MidiWorker` (`QThread`)**: An asynchronous worker thread dedicated to handling MIDI input and output, preventing the UI from freezing during MIDI operations.
-   **`EmagicPatch`**: A data model class representing an individual Emagic MIDI interface patch, storing its name, MIDI routing matrix, and timecode settings.
-   **`EmagicSysEx`**: A utility class (or module-level functions) for constructing and interpreting Emagic-specific SysEx messages, including device detection and patch data.
-   **SysEx State Machine (`_continue_sysex_sequence`)**: A `QTimer`-based state machine in `EmagicMidiConfig` manages multi-step SysEx operations (like loading or saving all patches) sequentially, ensuring proper message ordering and non-blocking waits for responses.
-   **Nibble Encoding**: All SysEx data (patch names, MIDI matrix, timecode) is encoded and decoded using 7-bit nibbles (two 7-bit bytes represent one 8-bit byte of data).

### SysEx Protocol Details

-   **Manufacturer ID**: `[0x00, 0x20, 0x31]`
-   **Default Device ID**: `0x64`
-   **No Checksums**: Based on analysis of available documentation, Emagic SysEx messages do not use checksums, simplifying implementation.
-   **Key Opcodes**:
    -   `0x0F`: Set Computer Mode
    -   `0x11`: Configure Patches (used for sending/receiving patch data)
    -   `0x12`: Request specific patch data

## Important Note on SysEx Communication

**The current implementation of SysEx communication in `src/emagic_sysex.py` is based on general MIDI SysEx principles and placeholder assumptions. It requires thorough verification against the official Emagic SysEx documentation to be fully and accurately implemented.** The relevant documentation is expected to be found in the `docs/` directory, specifically in files like `SysEx.pdf`, `emagic_MT4-en.pdf`, and `emagic_unitor8_mkII_amt8_manual.pdf`.

**To make the application fully functional, please manually review these PDF documents to extract the correct SysEx message formats, command opcodes, data structures, and checksum algorithms, and then update `src/emagic_sysex.py` accordingly.** Without this, the application cannot fully interact with the hardware.
