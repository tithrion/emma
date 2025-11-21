
# Agent Guidelines for Emagic MIDI Interface Configurator

This document outlines essential information for agents working on the Emagic MIDI Interface Configurator project.

## Project Goal
Develop a Python3 and PyQt6 application to configure Emagic MIDI interfaces (mt4, amt8, Unitor8) via MIDI/SysEx. The application should switch devices to computer mode, read, modify, and save 32 internal patches, and provide device-specific configuration options (MIDI I/O, timecode).

## Technologies Used
- **Python 3**: Primary programming language.
- **PyQt6**: GUI framework for desktop application development.
- **MIDI/SysEx**: For communication with Emagic MIDI interfaces. A Python MIDI library will be required (e.g., `python-rtmidi`, `mido`).
- **Bash**: For device detection (e.g., `lsusb`).

## Project Structure
- `src/`: Contains all Python source code for the application.
  - `main.py`: The main application file, handling GUI setup and overall application flow.
  - (Future files for MIDI communication, device logic, etc.)
- `docs/`: Contains project documentation, including Emagic SysEx specifications.
- `tests/`: Contains unit and integration tests.
- `resources/`: Stores assets like icons.
- `AGENTS.md`: This document.
- `README.md`: Project overview and setup instructions.

## Essential Commands

### Running the Application
```bash
python3 src/main.py
```

### Device Detection (Example)
To detect connected Emagic devices:
```bash
lsusb -d 086a:0001 -v 2>/dev/null|grep iProduct|awk {'print $3'}
```
This command helps identify the product name of Emagic devices. Further parsing may be needed to distinguish between mt4, amt8, and Unitor8 based on their reported features or product IDs.

## Code Organization and Style
- **GUI**: Follow PyQt6 conventions for widget layout, signal/slot connections.
- **Modularity**: Separate concerns into different modules (e.g., GUI logic, MIDI communication, device specific logic).
- **Naming Conventions**:
    - Classes: `CamelCase` (e.g., `EmagicMidiConfig`).
    - Functions/Methods: `snake_case` (e.g., `_create_tool_bar`, `_load_from_device`).
    - Variables: `snake_case`.
- **Comments**: Use comments for complex logic, important decisions, or areas needing further implementation (`TODO`).

## Key Areas for Development
1.  **Device Detection**: Accurately identify Emagic interfaces and their specific capabilities (IN/OUT ports, timecode).
2.  **MIDI Communication**: Implement robust SysEx sending and receiving using a suitable Python MIDI library. This includes:
    - Switching to computer mode.
    - Reading patch data.
    - Writing patch data.
    - Sending "all notes off" (PANIC!) messages.
    - Parsing Emagic SysEx documentation from `docs/` is critical here.
3.  **GUI Logic**:
    - Dynamically update the MIDI matrix in the "Patch Editor View" based on detected device ports.
    - Implement double-click to edit a patch from the "Patch Overview" list.
    - Connect toolbar actions to their respective functionalities.
4.  **Patch Data Management**: Representing and storing patch data in the application (in memory, and potentially for saving/loading to/from files).

## Gotchas and Non-obvious Patterns
- **SysEx Complexity**: Emagic's SysEx implementation can be intricate. Pay close attention to the documentation provided in `docs/` regarding message formats, checksums, and timing.
- **MIDI Port Handling**: Ensure correct opening, closing, and selection of MIDI ports, especially when multiple devices might be connected.
- **Asynchronous MIDI**: MIDI communication might require asynchronous handling to prevent GUI freezes.
- **PyQt6 Threading**: If MIDI communication is blocking, consider using QThread for background processing to keep the UI responsive.

## Testing Approach
- **Unit Tests**: Focus on MIDI message parsing/generation, and individual GUI component logic.
- **Integration Tests**: Verify end-to-end communication with a mock MIDI device or, ideally, a real Emagic interface.
- **GUI Tests**: Ensure UI elements are responsive and correctly reflect application state.
