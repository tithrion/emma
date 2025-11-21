
import sys
import subprocess
import re
import mido
from src.emagic_sysex import EMAGIC_MANUFACTURER_ID, DEFAULT_DEVICE_ID, SYSEX_COMMAND_COMPUTER_MODE, SYSEX_COMMAND_REQUEST_PATCH, SYSEX_COMMAND_SEND_PATCH, SYSEX_COMMAND_CONFIGURE_PATCHES, SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS, SYSEX_COMMAND_FIRMWARE_VERSION_REQUEST, EmagicPatch, EmagicSysEx, EmagicGlobalSettings, TIMECODE_OFF, TIMECODE_LTC_SMPTE, TIMECODE_LTC_AES_EBU, TIMECODE_VITC

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QLineEdit, QComboBox, QGridLayout, QCheckBox, QToolBar, QStatusBar, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QObject

from src.emagic_sysex import (create_identity_request, parse_identity_reply)

class MidiHandler(QObject):
    """Simplified MIDI handler that opens ports on-demand to avoid threading conflicts"""
    message_received = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, midi_in_port_name, midi_out_port_name):
        super().__init__()
        self.midi_in_port_name = midi_in_port_name
        self.midi_out_port_name = midi_out_port_name
        self.receive_timer = None
        self.timeout_timer = None
        self._in_port = None
        self._out_port = None
        print(f"DEBUG: MidiHandler created for IN='{midi_in_port_name}', OUT='{midi_out_port_name}'")
    
    def start(self):
        """Start the handler (no-op for compatibility)"""
        print("DEBUG: MidiHandler.start called")
    
    def isRunning(self):
        """Always return True for compatibility"""
        return True
    
    def send_and_wait_for_response(self, msg, timeout_ms=2000):
        """Send a message and wait for response using timers"""
        print(f"DEBUG: send_and_wait_for_response called")
        try:
            # Open ports temporarily
            print(f"DEBUG: Opening ports: IN={self.midi_in_port_name}, OUT={self.midi_out_port_name}")
            self._in_port = mido.open_input(self.midi_in_port_name)
            self._out_port = mido.open_output(self.midi_out_port_name)
            
            # Send message
            print(f"DEBUG: Sending message: {bytearray(msg.bytes()).hex()}")
            self._out_port.send(msg)
            
            # Set up receive polling
            self.receive_timer = QTimer()
            self.receive_timer.timeout.connect(self._check_for_messages)
            self.receive_timer.start(50)  # Check every 50ms
            
            # Set up timeout
            self.timeout_timer = QTimer()
            self.timeout_timer.setSingleShot(True)
            self.timeout_timer.timeout.connect(self._on_timeout)
            self.timeout_timer.start(timeout_ms)
            
        except Exception as e:
            print(f"ERROR: Failed to send message: {e}")
            self.error_occurred.emit(f"Failed to send: {e}")
            self._cleanup()
    
    def _check_for_messages(self):
        """Check for incoming messages"""
        if self._in_port:
            try:
                for msg in self._in_port.iter_pending():
                    print(f"DEBUG: Received message: {msg}")
                    self.message_received.emit(msg)
                    self._cleanup()  # Stop after first message
                    return
            except Exception as e:
                print(f"ERROR: Error reading port: {e}")
                self.error_occurred.emit(f"Read error: {e}")
                self._cleanup()
    
    def _on_timeout(self):
        """Handle timeout"""
        print("DEBUG: Response timeout")
        self._cleanup()
    
    def _cleanup(self):
        """Stop timers and close ports"""
        print("DEBUG: MidiHandler cleanup")
        if self.receive_timer:
            self.receive_timer.stop()
            self.receive_timer = None
        if self.timeout_timer:
            self.timeout_timer.stop()
            self.timeout_timer = None
        if self._in_port:
            self._in_port.close()
            self._in_port = None
        if self._out_port:
            self._out_port.close()
            self._out_port = None
    
    def stop(self):
        """Stop and cleanup"""
        print("DEBUG: MidiHandler.stop called")
        self._cleanup()


class DeviceScanner(QObject):
    """Scanner for detecting connected MIDI devices on Unitor8 ports"""
    scan_progress = pyqtSignal(int, str, str)  # port_num, status, device_info
    scan_complete = pyqtSignal()
    
    def __init__(self, base_port_name):
        super().__init__()
        self.base_port_name = base_port_name  # e.g., "Unitor8:Unitor8 MIDI"
        self.current_port = 0
        self.scan_timer = None
        self.results = []
        
    def start_scan(self, num_ports=8):
        """Start scanning all ports"""
        print(f"DEBUG: DeviceScanner: Starting scan of {num_ports} ports")
        self.current_port = 0
        self.num_ports = num_ports
        self.results = []
        
        # Start scanning first port
        self.scan_timer = QTimer()
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self._scan_next_port)
        self.scan_timer.start(100)  # Start immediately
    
    def _scan_next_port(self):
        """Scan the next port in sequence"""
        if self.current_port >= self.num_ports:
            # Scanning complete
            print("DEBUG: DeviceScanner: Scan complete")
            self.scan_complete.emit()
            return
        
        port_num = self.current_port + 1  # 1-based for user display
        print(f"DEBUG: DeviceScanner: Scanning port {port_num}")
        self.scan_progress.emit(port_num, "Scanning...", "")
        
        # Construct port name (e.g., "Unitor8:Unitor8 MIDI 1 24:0")
        port_name = f"{self.base_port_name} {port_num} 24:{self.current_port}"
        
        try:
            # Open ports
            in_port = mido.open_input(port_name)
            out_port = mido.open_output(port_name)
            
            # Send Identity Request
            identity_request = create_identity_request()
            out_port.send(identity_request)
            print(f"DEBUG: Sent Identity Request to port {port_num}")
            
            # Wait for response (500ms)
            import time
            time.sleep(0.5)
            
            # Check for response
            device_found = False
            device_info = ""
            
            for msg in in_port.iter_pending():
                if msg.type == 'sysex':
                    # Try to parse as identity reply
                    identity = parse_identity_reply(bytearray(msg.bytes()))
                    if identity:
                        print(f"DEBUG: Port {port_num} - Identity reply: {identity}")
                        device_info = identity['manufacturer_name']
                        if identity.get('device_family') or identity.get('device_member'):
                            device_info += f" (Family:{identity.get('device_family', '?')}, Member:{identity.get('device_member', '?')})"
                        device_found = True
                        break
            
            # Close ports
            in_port.close()
            out_port.close()
            
            # Report result
            if device_found:
                self.scan_progress.emit(port_num, "Connected", device_info)
                self.results.append((port_num, "Connected", device_info))
            else:
                self.scan_progress.emit(port_num, "No Response", "-")
                self.results.append((port_num, "No Response", "-"))
                
        except Exception as e:
            print(f"ERROR: DeviceScanner: Port {port_num} error: {e}")
            self.scan_progress.emit(port_num, "Error", str(e))
            self.results.append((port_num, "Error", str(e)))
        
        # Move to next port
        self.current_port += 1
        self.scan_timer.start(100)  # Small delay before next port

class EmagicMidiConfig(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emagic MIDI Interface Configurator")
        self.setGeometry(100, 100, 1024, 768)

        self.emagic_devices = []
        self.midi_in_port = None # These will now be managed by MidiWorker
        self.midi_out_port = None # These will now be managed by MidiWorker
        self.midi_worker = None # Instance of MidiWorker QThread
        self.patches = [EmagicPatch(name=f"Unnamed Patch {i+1}", slot=i) for i in range(32)]
        self.global_settings = EmagicGlobalSettings() # Initialize global settings
        self.current_patch_index = 0 # Currently selected patch slot
        self.current_device_mode = "Unknown" # Can be "Computer Mode", "Patch Mode", "Unknown"

        self._create_tool_bar()
        self._create_status_bar()
        self._create_tabs()
        self._detect_devices_on_startup()

        # Initialize a QTimer for managing sequential SysEx requests/responses
        self.sysex_sequence_timer = QTimer(self)
        self.sysex_sequence_timer.setSingleShot(True)
        self.sysex_sequence_timer.timeout.connect(self._continue_sysex_sequence)
        self.sysex_sequence_state = {"active": False, "current_patch_idx": 0, "operation": None, "last_received_msg": None}

    def _connect_selected_midi_ports(self):
        selected_in = self.midi_in_combo.currentText()
        selected_out = self.midi_out_combo.currentText()
        if selected_in and selected_out:
            self._open_midi_ports(selected_in, selected_out)
        else:
            self.statusBar.showMessage("Please select both MIDI IN and OUT ports.", 5000)

    def _create_tool_bar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        load_action = QAction(QIcon.fromTheme("document-open"), "Load from Device", self)
        load_action.triggered.connect(self._load_from_device)
        toolbar.addAction(load_action)

        save_action = QAction(QIcon.fromTheme("document-save"), "Save to Device", self)
        save_action.triggered.connect(self._save_to_device)
        toolbar.addAction(save_action)

        panic_action = QAction(QIcon.fromTheme("media-playback-stop"), "PANIC! (All Notes Off)", self)
        panic_action.triggered.connect(self._panic)
        toolbar.addAction(panic_action)

        toolbar.addSeparator()

        computer_mode_action = QAction(QIcon.fromTheme("computer"), "Computer Mode", self)
        computer_mode_action.triggered.connect(self._switch_to_computer_mode)
        toolbar.addAction(computer_mode_action)

        patch_mode_action = QAction(QIcon.fromTheme("document-properties"), "Patch Mode", self)
        patch_mode_action.triggered.connect(self._switch_to_patch_mode)
        toolbar.addAction(patch_mode_action)

    def _create_status_bar(self):
        self.statusBar = self.statusBar()
        self.statusBar.showMessage("Ready")
        self.device_mode_label = QLabel(f"Mode: {self.current_device_mode}")
        self.statusBar.addPermanentWidget(self.device_mode_label)
        self.statusBar.addPermanentWidget(QLabel("Emagic Configurator"))

    def _create_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self._create_patch_overview_tab()
        self._create_patch_editor_tab()
        self._create_device_settings_tab()
        self._create_connected_devices_tab()
        self._create_sysex_debugger_tab()
        
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        current_widget = self.tab_widget.widget(index)
        if current_widget == self.patch_editor_tab:
            print(f"DEBUG: Tab changed to Patch Editor. Populating matrix for patch {self.current_patch_index}")
            self._populate_midi_matrix(self.current_patch_index)

    def _create_sysex_debugger_tab(self):
        self.sysex_debugger_tab = QWidget()
        self.tab_widget.addTab(self.sysex_debugger_tab, "SysEx Debugger")
        layout = QVBoxLayout()

        # Input Area
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Send SysEx (Hex):"))
        self.sysex_input = QLineEdit()
        self.sysex_input.setPlaceholderText("e.g., F0 00 20 31 64 0F F7")
        input_layout.addWidget(self.sysex_input)
        
        self.send_sysex_button = QPushButton("Send")
        self.send_sysex_button.clicked.connect(self._send_manual_sysex)
        input_layout.addWidget(self.send_sysex_button)
        layout.addLayout(input_layout)

        # Log Area
        layout.addWidget(QLabel("SysEx Log:"))
        self.sysex_log = QListWidget()
        layout.addWidget(self.sysex_log)

        # Clear Log Button
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.sysex_log.clear)
        layout.addWidget(self.clear_log_button)

        self.sysex_debugger_tab.setLayout(layout)

    def _send_manual_sysex(self):
        hex_str = self.sysex_input.text().strip()
        try:
            # Remove spaces and parse hex
            clean_hex = hex_str.replace(" ", "")
            data = bytearray.fromhex(clean_hex)
            
            # Basic validation
            if not data.startswith(b'\xF0') or not data.endswith(b'\xF7'):
                self.statusBar.showMessage("Invalid SysEx: Must start with F0 and end with F7", 5000)
                return

            msg = mido.Message('sysex', data=list(data[1:-1])) # mido excludes F0/F7 from data
            if self.midi_worker and self.midi_worker.isRunning():
                self.midi_worker.send_message(msg)
                self.sysex_log.addItem(f"SENT: {hex_str}")
                self.sysex_input.clear()
            else:
                self.statusBar.showMessage("MIDI worker not running.", 5000)

        except ValueError:
            self.statusBar.showMessage("Invalid Hex String", 5000)


    def _create_patch_overview_tab(self):
        self.patch_overview_tab = QWidget()
        self.tab_widget.addTab(self.patch_overview_tab, "Patch Overview")
        layout = QVBoxLayout()

        # Device Info
        self.device_info_label = QLabel("Connected Device(s): Detecting...")
        layout.addWidget(self.device_info_label)

        # MIDI Port Selection
        port_selection_layout = QHBoxLayout()
        port_selection_layout.addWidget(QLabel("MIDI IN Port:"))
        self.midi_in_combo = QComboBox()
        port_selection_layout.addWidget(self.midi_in_combo)
        port_selection_layout.addWidget(QLabel("MIDI OUT Port:"))
        self.midi_out_combo = QComboBox()
        port_selection_layout.addWidget(self.midi_out_combo)

        self.connect_midi_button = QPushButton("Connect MIDI")
        self.connect_midi_button.clicked.connect(self._connect_selected_midi_ports)
        port_selection_layout.addWidget(self.connect_midi_button)

        layout.addLayout(port_selection_layout)

        # Patch List
        self.patch_list_widget = QListWidget()
        for i, patch in enumerate(self.patches):
            self.patch_list_widget.addItem(f"Patch {patch.slot+1}: {patch.name}")
        self.patch_list_widget.doubleClicked.connect(self._open_patch_editor)
        layout.addWidget(self.patch_list_widget)

        self.patch_overview_tab.setLayout(layout)

    def _close_midi_ports(self):
        if self.midi_worker and self.midi_worker.isRunning():
            self.midi_worker.stop()
            self.midi_worker = None
        self.statusBar.showMessage("MIDI ports closed.")

    def _open_midi_ports(self, in_port_name, out_port_name):
        print(f"DEBUG: _open_midi_ports called with IN='{in_port_name}', OUT='{out_port_name}'")
        self._close_midi_ports() # Stop any existing worker
        try:
            self.midi_worker = MidiHandler(midi_in_port_name=in_port_name, midi_out_port_name=out_port_name)
            self.midi_worker.message_received.connect(self._handle_midi_message)
            self.midi_worker.error_occurred.connect(self._handle_midi_worker_error)
            self.midi_worker.start()
            print(f"DEBUG: _open_midi_ports: MidiHandler started. isRunning: {self.midi_worker.isRunning()}")
            self.statusBar.showMessage(f"MIDI ports configured: {in_port_name} (IN/OUT)")
            return True
        except Exception as e:
            self.statusBar.showMessage(f"Failed to configure MIDI handler: {e}", 5000)
            return False

    def _handle_midi_worker_error(self, error_str):
        self.statusBar.showMessage(f"MIDI Error: {error_str}", 5000)

    def _handle_midi_worker_status(self, status_str):
        self.statusBar.showMessage(status_str)

    def _handle_midi_worker_finished(self):
        self.statusBar.showMessage("MIDI worker unexpectedly stopped.", 5000)

    def _handle_midi_message(self, msg):
        # Log to debugger
        if hasattr(self, 'sysex_log') and msg.type == 'sysex':
            raw_bytes = msg.bytes()
            hex_str = ' '.join([f"{b:02X}" for b in raw_bytes])
            self.sysex_log.addItem(f"RECV: {hex_str}")
            self.sysex_log.scrollToBottom()
        
        # Check if it's a firmware response
        if msg.type == 'sysex':
            print(f"DEBUG: Received SysEx message: {bytearray(msg.bytes()).hex()}")
            # Try to parse as firmware response
            raw_sysex_bytes = bytearray(msg.bytes())
            self.global_settings.parse_firmware_response(raw_sysex_bytes)
            if self.global_settings.firmware_version and self.global_settings.firmware_version != "Unknown":
                print(f"DEBUG: Parsed firmware version: {self.global_settings.firmware_version}")
                self.firmware_version_label.setText(self.global_settings.firmware_version)
                self.statusBar.showMessage(f"Firmware Version: {self.global_settings.firmware_version}")
            else:
                self.statusBar.showMessage("Received SysEx message (not firmware or parse failed)", 2000)


    def _load_from_device(self):
        """Load patches from device - Currently disabled due to unknown patch request protocol"""
        self.statusBar.showMessage("Load from Device: Feature disabled - patch request protocol unknown. Use SysEx Debugger for manual exploration.", 5000)
        print("DEBUG: _load_from_device called - feature disabled (unknown patch request protocol)")
        # The Emagic device doesn't respond to standard patch request commands (0x12)
        # Further reverse engineering or MIDI sniffing needed to discover the correct command

    def _save_to_device(self):
        """Save patches to device"""
        print(f"DEBUG: _save_to_device called.")
        if not self.emagic_devices:
            self.statusBar.showMessage("No Emagic device detected. Cannot save.", 5000)
            return
        
        self.statusBar.showMessage("Saving patches to device...")
        
        # Get port names
        first_device = self.emagic_devices[0]
        out_port_name = first_device['out_ports'][0]  # Use first port for SysEx
        
        try:
            # Open port temporarily
            out_port = mido.open_output(out_port_name)
            
            # Send computer mode first
            computer_mode_msg = EmagicSysEx.get_computer_mode_message()
            out_port.send(computer_mode_msg)
            print("DEBUG: Sent Computer Mode")
            
            # Small delay
            import time
            time.sleep(0.1)
            
            # Send each patch
            for idx, patch in enumerate(self.patches):
                sysex_msg = patch.get_sysex_message(
                    command=SYSEX_COMMAND_CONFIGURE_PATCHES,
                    num_in_ports=len(first_device['in_ports']),
                    num_out_ports=len(first_device['out_ports'])
                )
                out_port.send(sysex_msg)
                print(f"DEBUG: Sent patch {idx + 1}: {patch.name}")
                time.sleep(0.05)  # Small delay between patches
            
            # Close port
            out_port.close()
            
            self.statusBar.showMessage(f"Successfully saved {len(self.patches)} patches to device.", 3000)
            print("DEBUG: Patch save complete")
            
        except Exception as e:
            print(f"ERROR: Failed to save patches: {e}")
            self.statusBar.showMessage(f"Error saving patches: {e}", 5000)

    def _panic(self):
        """Send All Notes Off to all MIDI channels"""
        if not self.emagic_devices:
            self.statusBar.showMessage("No device connected for Panic.", 3000)
            return
        
        try:
            # Open output port temporarily
            first_device = self.emagic_devices[0]
            out_port_name = first_device['out_ports'][0]
            out_port = mido.open_output(out_port_name)
            
            # Send All Notes Off (CC 123) to all 16 channels
            for channel in range(16):
                msg = mido.Message('control_change', channel=channel, control=123, value=0)
                out_port.send(msg)
            
            out_port.close()
            self.statusBar.showMessage("Panic: All Notes Off sent.", 2000)
            print("DEBUG: Panic - All Notes Off sent to all channels")
            
        except Exception as e:
            print(f"ERROR: Panic failed: {e}")
            self.statusBar.showMessage(f"Panic failed: {e}", 3000)

    def _send_computer_mode_message(self):
        if self.midi_worker and self.midi_worker.isRunning():
            print("DEBUG: _send_computer_mode_message: MidiWorker is running. Getting computer mode message.")
            computer_mode_msg = EmagicSysEx.get_computer_mode_message()
            self.midi_worker.send_message(computer_mode_msg)
            self.statusBar.showMessage("Sent Computer Mode SysEx message.", 2000)
            return True
        else:
            self.statusBar.showMessage("MIDI worker not running. Cannot send Computer Mode message.", 5000)
            print("DEBUG: _send_computer_mode_message: MIDI worker not running.")
            return False

    def _detect_devices_on_startup(self):
        self._detect_emagic_devices()
        # Optionally, set up a timer to periodically check for devices
        # self.device_detection_timer = QTimer(self)
        # self.device_detection_timer.timeout.connect(self._detect_emagic_devices)
        # self.device_detection_timer.start(5000) # Check every 5 seconds

    def _detect_emagic_devices(self):
        self.emagic_devices = []
        all_input_ports = mido.get_input_names()
        all_output_ports = mido.get_output_names()
        print(f"DEBUG: All available MIDI IN ports: {all_input_ports}")
        print(f"DEBUG: All available MIDI OUT ports: {all_output_ports}")
        available_midi_ports = all_input_ports + all_output_ports
        
        try:
            command = "lsusb -d 086a: -v 2>/dev/null | grep 'iProduct' | awk {'print $3'} | sort | uniq"
            output = subprocess.check_output(command, shell=True, text=True).strip()
            
            detected_products = output.split('\n') if output else []
            
            device_info_text = "Connected Device(s):\n"
            if detected_products:
                for product_name in detected_products:
                    device_type = "Unknown Emagic Device"
                    in_ports = []
                    out_ports = []

                    # Heuristic for device type and associated MIDI ports
                    if "AMT8" in product_name.upper() or "UNITOR8" in product_name.upper(): # Treat AMT8 and Unitor8 similarly for port detection
                        device_type = product_name + " (8 IN, 8 OUT)"
                        # Assume ports named something like "Unitor8 MIDI 1", etc., regardless of product_name from lsusb
                        for i in range(1, 9):
                            port_name_candidate = f"Unitor8 MIDI {i}" # Check for Unitor8-style naming
                            print(f"DEBUG: Checking for Unitor8/AMT8 port: {port_name_candidate}")
                            for mido_port_name in available_midi_ports:
                                if port_name_candidate in mido_port_name:
                                    in_ports.append(mido_port_name)
                                    out_ports.append(mido_port_name)
                                    break # Found a match, move to next constructed port_name
                    elif "MT4" in product_name.upper():
                        device_type = "MT4 (2 IN, 4 OUT)"
                        # MT4 has fewer ports, adjust naming convention if known
                        for i in range(1, 3):
                            in_port_name = f"MT4 MIDI In {i}"
                            print(f"DEBUG: Checking for MT4 IN port: {in_port_name}")
                            for mido_port_name in available_midi_ports:
                                if in_port_name in mido_port_name:
                                    in_ports.append(mido_port_name)
                                    break
                        for i in range(1, 5):
                            out_port_name = f"MT4 MIDI Out {i}"
                            print(f"DEBUG: Checking for MT4 OUT port: {out_port_name}")
                            for mido_port_name in available_midi_ports:
                                if out_port_name in mido_port_name:
                                    out_ports.append(mido_port_name)
                                    break

                    self.emagic_devices.append({"name": product_name, "type": device_type, "in_ports": in_ports, "out_ports": out_ports})
                    device_info_text += f"- {product_name} ({device_type})\n"
                    if in_ports or out_ports:
                        device_info_text += f"  MIDI IN: {', '.join(in_ports) or 'None'}\n"
                        device_info_text += f"  MIDI OUT: {', '.join(out_ports) or 'None'}\n"
                    else:
                        device_info_text += "  No associated MIDI ports found.\n"
                
                self.device_info_label.setText(device_info_text)
                self.statusBar.showMessage(f"Detected {len(self.emagic_devices)} Emagic device(s).")
                print(f"DEBUG: _detect_emagic_devices - Detected Emagic devices: {self.emagic_devices}")
                
                # For now, automatically try to open the first detected device's ports
                # if self.emagic_devices and self.emagic_devices[0]["in_ports"] and self.emagic_devices[0]["out_ports"]:
                #     first_in = self.emagic_devices[0]["in_ports"][0]
                #     first_out = self.emagic_devices[0]["out_ports"][0]
                #     self._open_midi_ports(first_in, first_out)
                # else:
                #     self.statusBar.showMessage("No suitable MIDI ports found for Emagic devices.", 5000)

                # Populate port selection combos
                self.midi_in_combo.clear()
                self.midi_out_combo.clear()
                all_in_ports = mido.get_input_names()
                all_out_ports = mido.get_output_names()
                self.midi_in_combo.addItems(all_in_ports)
                self.midi_out_combo.addItems(all_out_ports)

                # Pre-select first detected Emagic ports if any
                if self.emagic_devices and self.emagic_devices[0]["in_ports"] and self.emagic_devices[0]["out_ports"]:
                    first_emagic_in = self.emagic_devices[0]["in_ports"][0]
                    first_emagic_out = self.emagic_devices[0]["out_ports"][0]
                    in_index = self.midi_in_combo.findText(first_emagic_in)
                    out_index = self.midi_out_combo.findText(first_emagic_out)
                    if in_index != -1: self.midi_in_combo.setCurrentIndex(in_index)
                    if out_index != -1: self.midi_out_combo.setCurrentIndex(out_index)
                    self._connect_selected_midi_ports()

            else:
                self.device_info_label.setText("Connected Device(s): None detected.")
                self.statusBar.showMessage("No Emagic devices detected.")
                self.midi_in_combo.clear() # Clear combos if no devices found
                self.midi_out_combo.clear()
                self.midi_in_combo.addItems(mido.get_input_names())
                self.midi_out_combo.addItems(mido.get_output_names())

        except subprocess.CalledProcessError as e:
            self.statusBar.showMessage(f"Error detecting devices: {e}", 5000)
            self.device_info_label.setText("Connected Device(s): Error during detection.")
        except FileNotFoundError:
            self.statusBar.showMessage("lsusb command not found. Please install usbutils.", 5000)
            self.device_info_label.setText("Connected Device(s): `lsusb` not found.")
        except Exception as e:
            self.statusBar.showMessage(f"An unexpected error occurred during device detection: {e}", 5000)
            self.device_info_label.setText("Connected Device(s): An error occurred.")


    def _open_patch_editor(self, index):
        patch_number = index.row()  # 0-based index
        self.current_patch_index = patch_number
        self.tab_widget.setCurrentWidget(self.patch_editor_tab)
        
        # Load patch data into editor fields
        current_patch = self.patches[patch_number]
        self.patch_name_input.setText(current_patch.name)
        self.patch_slot_combo.setCurrentIndex(current_patch.slot)
        
        # Map timecode format to combo box index
        timecode_map = {
            TIMECODE_OFF: 0,
            TIMECODE_LTC_SMPTE: 1,
            TIMECODE_LTC_AES_EBU: 2,
            TIMECODE_VITC: 3
        }
        self.timecode_combo.setCurrentIndex(timecode_map.get(current_patch.timecode_format, 0))

        self.statusBar.showMessage(f"Editing Patch {patch_number + 1}: {current_patch.name}")
        print(f"DEBUG: Calling _populate_midi_matrix for patch {patch_number}")
        self._populate_midi_matrix(patch_number)

    def _update_patch_name_in_model(self, text):
        self.patches[self.current_patch_index].name = text
        self.patch_list_widget.item(self.current_patch_index).setText(f"Patch {self.current_patch_index+1}: {text}")

    def _update_patch_slot_in_model(self, index):
        # Note: changing the slot of a patch means it moves to a new position logically
        # This requires more complex data management (e.g., swapping or reordering patches)
        # For now, we'll just update the slot attribute of the current patch in case it's meant for metadata.
        # If the intention is to physically move a patch to a new slot on the device, that's a SysEx command.
        new_slot = self.patch_slot_combo.currentIndex()
        self.patches[self.current_patch_index].slot = new_slot # Update the in-memory model
        self.statusBar.showMessage(f"Patch {self.current_patch_index+1} selected storage slot {new_slot+1}.", 2000)

    def _update_timecode_format_in_model(self, index):
        timecode_map_reverse = {
            0: TIMECODE_OFF,
            1: TIMECODE_LTC_SMPTE,
            2: TIMECODE_LTC_AES_EBU,
            3: TIMECODE_VITC
        }
        self.patches[self.current_patch_index].timecode_format = timecode_map_reverse.get(index, TIMECODE_OFF)
        self.statusBar.showMessage(f"Timecode format set to {self.timecode_combo.currentText()}", 2000)


    def _populate_midi_matrix(self, patch_number):
        # Clear existing layout widgets
        while self.midi_matrix_grid.count():
            item = self.midi_matrix_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Get active device's ports
        in_ports = []
        out_ports = []
        if self.emagic_devices:
            active_device = self.emagic_devices[0] # Assuming we're editing for the first device for now
            print(f"DEBUG: _populate_midi_matrix: active_device: {active_device}")
            in_ports = active_device.get("in_ports", [])
            out_ports = active_device.get("out_ports", [])
        print(f"DEBUG: _populate_midi_matrix: in_ports received: {in_ports}, out_ports received: {out_ports}")

        num_in = len(in_ports)
        num_out = len(out_ports)
        print(f"DEBUG: _populate_midi_matrix - in_ports: {in_ports}, out_ports: {out_ports}")

        if num_in == 0 or num_out == 0:
            print(f"DEBUG: _populate_midi_matrix - No MIDI ports detected for active device. num_in: {num_in}, num_out: {num_out}")
            self.midi_matrix_grid.addWidget(QLabel("No MIDI ports detected for active device to configure matrix."), 0, 0)
            return

        current_patch = self.patches[patch_number] # Define current_patch here

        # Add OUT port labels (horizontal)
        for col, out_port in enumerate(out_ports):
            self.midi_matrix_grid.addWidget(QLabel(f"OUT {col+1}"), 0, col + 1, Qt.AlignmentFlag.AlignCenter)

        # Add IN port labels (vertical) and checkboxes
        for row, in_port in enumerate(in_ports):
            self.midi_matrix_grid.addWidget(QLabel(f"IN {row+1}"), row + 1, 0, Qt.AlignmentFlag.AlignRight)
            for col in range(num_out):
                checkbox = QCheckBox()
                # Use 0-based indices for matrix, as expected by EmagicPatch.midi_matrix
                is_checked = current_patch.midi_matrix.get((row, col), False)
                checkbox.setChecked(is_checked)
                print(f"DEBUG: _populate_midi_matrix - Creating checkbox at ({row}, {col}), checked: {is_checked}")
                checkbox.stateChanged.connect(lambda state, ip_idx=row, op_idx=col: self._update_midi_matrix_in_model(ip_idx, op_idx, state))
                self.midi_matrix_grid.addWidget(checkbox, row + 1, col + 1, Qt.AlignmentFlag.AlignCenter)

        self.statusBar.showMessage(f"MIDI matrix populated for Patch {patch_number + 1} with {num_in} IN and {num_out} OUT ports.")

    def _update_midi_matrix_in_model(self, in_port, out_port, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        self.patches[self.current_patch_index].midi_matrix[(in_port, out_port)] = is_checked
        self.statusBar.showMessage(f"Connection IN {in_port+1} -> OUT {out_port+1} set to {is_checked}", 1000)

    def _create_patch_editor_tab(self):
        self.patch_editor_tab = QWidget()
        self.tab_widget.addTab(self.patch_editor_tab, "Patch Editor View")
        layout = QVBoxLayout()

        # Patch Name and Slot
        name_slot_layout = QHBoxLayout()
        name_slot_layout.addWidget(QLabel("Patch Name:"))
        self.patch_name_input = QLineEdit("New Patch")
        name_slot_layout.addWidget(self.patch_name_input)
        self.patch_name_input.textChanged.connect(self._update_patch_name_in_model)

        name_slot_layout.addWidget(QLabel("Storage Slot:"))
        self.patch_slot_combo = QComboBox()
        for i in range(32):
            self.patch_slot_combo.addItem(str(i + 1))
        name_slot_layout.addWidget(self.patch_slot_combo)
        self.patch_slot_combo.currentIndexChanged.connect(self._update_patch_slot_in_model)
        layout.addLayout(name_slot_layout)

        # Timecode Options
        timecode_layout = QHBoxLayout()
        timecode_layout.addWidget(QLabel("Timecode Format:"))
        self.timecode_combo = QComboBox()
        self.timecode_combo.addItems(["Off", "LTC SMPTE (30 fps)", "LTC AES/EBU (25 fps)", "VITC"])
        timecode_layout.addWidget(self.timecode_combo)
        self.timecode_combo.currentIndexChanged.connect(self._update_timecode_format_in_model)
        layout.addLayout(timecode_layout)

        # MIDI Matrix (placeholder for now)
        self.midi_matrix_grid = QGridLayout()
        # This will be dynamically populated based on detected device ports
        layout.addLayout(self.midi_matrix_grid)

        self.patch_editor_tab.setLayout(layout)
        print("DEBUG: _create_patch_editor_tab - Patch Editor tab layout set.")

    def _create_device_settings_tab(self):
        self.device_settings_tab = QWidget()
        self.tab_widget.addTab(self.device_settings_tab, "Device Settings")
        layout = QVBoxLayout()

        # Firmware Version
        firmware_layout = QHBoxLayout()
        firmware_layout.addWidget(QLabel("Firmware Version:"))
        self.firmware_version_label = QLabel(self.global_settings.firmware_version)
        firmware_layout.addWidget(self.firmware_version_label)
        
        self.request_firmware_button = QPushButton("Request Firmware")
        self.request_firmware_button.clicked.connect(self._request_firmware_version)
        firmware_layout.addWidget(self.request_firmware_button)
        layout.addLayout(firmware_layout)

        # Placeholder for other global settings
        layout.addWidget(QLabel("Additional global settings are not currently implemented due to lack of publicly available SysEx documentation."))
        layout.addWidget(QLabel("Placeholders exist for future expansion if documentation becomes available."))

        self.device_settings_tab.setLayout(layout)
        print("DEBUG: _create_device_settings_tab - Device Settings tab layout set.")

    def _create_connected_devices_tab(self):
        """Create tab for scanning connected MIDI devices"""
        self.connected_devices_tab = QWidget()
        self.tab_widget.addTab(self.connected_devices_tab, "Connected Devices")
        layout = QVBoxLayout()
        
        # Title and instructions
        layout.addWidget(QLabel("<b>Scan for Connected MIDI Devices</b>"))
        layout.addWidget(QLabel("Scans each Unitor8 port to detect connected synthesizers and other MIDI devices."))
        
        # Buttons
        button_layout = QHBoxLayout()
        self.scan_ports_button = QPushButton("Scan All Ports")
        self.scan_ports_button.clicked.connect(self._start_device_scan)
        button_layout.addWidget(self.scan_ports_button)
        
        self.clear_scan_button = QPushButton("Clear Results")
        self.clear_scan_button.clicked.connect(self._clear_device_scan)
        button_layout.addWidget(self.clear_scan_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Results table
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["Port", "Status", "Device"])
        self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.device_table.setRowCount(8)
        
        # Initialize table with port numbers
        for i in range(8):
            self.device_table.setItem(i, 0, QTableWidgetItem(f"Port {i+1}"))
            self.device_table.setItem(i, 1, QTableWidgetItem("-"))
            self.device_table.setItem(i, 2, QTableWidgetItem("-"))
        
        layout.addWidget(self.device_table)
        
        # Notes
        layout.addWidget(QLabel("<i>Note: Only devices that support MIDI Device Identity Request will be detected.</i>"))
        layout.addWidget(QLabel("<i>Scanning takes approximately 4 seconds (500ms per port).</i>"))
        
        self.connected_devices_tab.setLayout(layout)
        print("DEBUG: _create_connected_devices_tab - Connected Devices tab layout set.")
    
    def _start_device_scan(self):
        """Start scanning for connected devices"""
        if not self.emagic_devices:
            self.statusBar.showMessage("No Emagic device detected. Cannot scan.", 5000)
            return
        
        # Disable scan button during scan
        self.scan_ports_button.setEnabled(False)
        self.scan_ports_button.setText("Scanning...")
        self.statusBar.showMessage("Scanning ports for connected devices...")
        
        # Create scanner
        # Extract base port name (e.g., "Unitor8:Unitor8 MIDI")
        first_port = self.emagic_devices[0]['in_ports'][0]  # e.g., "Unitor8:Unitor8 MIDI 1 24:0"
        # Strip the port number and address
        base_port = first_port.rsplit(' ', 2)[0]  # "Unitor8:Unitor8 MIDI"
        
        self.device_scanner = DeviceScanner(base_port)
        self.device_scanner.scan_progress.connect(self._update_scan_progress)
        self.device_scanner.scan_complete.connect(self._scan_finished)
        self.device_scanner.start_scan(8)
    
    def _update_scan_progress(self, port_num, status, device_info):
        """Update table as scan progresses"""
        row = port_num - 1  # Convert to 0-based
        self.device_table.setItem(row, 1, QTableWidgetItem(status))
        self.device_table.setItem(row, 2, QTableWidgetItem(device_info))
        print(f"DEBUG: Port {port_num} scan result: {status} - {device_info}")
    
    def _scan_finished(self):
        """Called when scan completes"""
        self.scan_ports_button.setEnabled(True)
        self.scan_ports_button.setText("Scan All Ports")
        self.statusBar.showMessage("Scan complete.", 3000)
        print("DEBUG: Device scan completed")
    
    def _clear_device_scan(self):
        """Clear scan results"""
        for i in range(8):
            self.device_table.setItem(i, 1, QTableWidgetItem("-"))
            self.device_table.setItem(i, 2, QTableWidgetItem("-"))
        self.statusBar.showMessage("Scan results cleared.")

    def _request_firmware_version(self):
        print("DEBUG: _request_firmware_version called.")
        if not self.midi_worker or not self.midi_worker.isRunning():
            self.statusBar.showMessage("MIDI handler not ready. Cannot request firmware.", 5000)
            print("DEBUG: _request_firmware_version: MIDI handler not running or not active.")
            return
        
        self.firmware_version_label.setText("Requesting...")
        
        # Send computer mode first, then firmware request
        computer_mode_msg = EmagicSysEx.get_computer_mode_message()
        firmware_request_msg = self.global_settings.get_firmware_request_message()
        
        # Send both messages and wait for response
        self.midi_worker.send_and_wait_for_response(computer_mode_msg, timeout_ms=100)
        QTimer.singleShot(150, lambda: self.midi_worker.send_and_wait_for_response(firmware_request_msg, timeout_ms=2000))
        
        self.statusBar.showMessage("Requesting firmware version...")

    def _switch_to_computer_mode(self):
        print("DEBUG: _switch_to_computer_mode called.")
        if not self.midi_worker or not self.midi_worker.isRunning():
            self.statusBar.showMessage("MIDI worker not running. Cannot switch mode.", 5000)
            print("DEBUG: _switch_to_computer_mode: MIDI worker not running or not active.")
            return
        self.sysex_sequence_state = {"active": True, "operation": "switch_mode", "target_mode": "computer", "current_patch_idx": None, "state": "send_computer_mode", "last_received_msg": None}
        self.statusBar.showMessage("Switching to Computer Mode...")
        self._continue_sysex_sequence()

    def _switch_to_patch_mode(self):
        print("DEBUG: _switch_to_patch_mode called.")
        if not self.midi_worker or not self.midi_worker.isRunning():
            self.statusBar.showMessage("MIDI worker not running. Cannot switch mode.", 5000)
            print("DEBUG: _switch_to_patch_mode: MIDI worker not running or not active.")
            return
        self.sysex_sequence_state = {"active": True, "operation": "switch_mode", "target_mode": "patch", "current_patch_idx": self.current_patch_index, "state": "send_patch_mode", "last_received_msg": None}
        self.statusBar.showMessage("Switching to Patch Mode...")
        self._continue_sysex_sequence()

    def _continue_sysex_sequence(self):
        current_idx = self.sysex_sequence_state["current_patch_idx"]
        operation = self.sysex_sequence_state["operation"]
        state = self.sysex_sequence_state.get("state", "idle") # Default to idle if not set
        print(f"DEBUG: _continue_sysex_sequence: state: {state}, operation: {operation}, current_idx: {current_idx}")

        if state == "send_computer_mode":
            if self._send_computer_mode_message():
                self.sysex_sequence_state["state"] = "wait_for_computer_mode_ack" # Transition to next state
                self.sysex_sequence_timer.start(500) # Wait for ACK
            else:
                self._stop_sysex_sequence("Failed to send Computer Mode message.")
            return
        elif state == "wait_for_computer_mode_ack":
            last_msg = self.sysex_sequence_state.pop("last_received_msg", None)
            if last_msg and last_msg.type == 'sysex':
                raw_sysex_bytes = last_msg.bytes()[1:-1]
                print(f"DEBUG: Received SysEx during Computer Mode ACK wait: {raw_sysex_bytes.hex()}")
                # We received a SysEx, but still assume no explicit ACK and proceed after a short delay.
                self.statusBar.showMessage("Received SysEx during Computer Mode ACK wait. Proceeding.", 2000)

            # After a short delay, assume computer mode is active and proceed.
            self.sysex_sequence_state["state"] = "start_patch_operation" # Proceed to next state
            self.sysex_sequence_timer.start(200) # Small delay to allow device to settle
            return
        elif state == "send_firmware_request":
            # Step 1: Send Computer Mode
            if self._send_computer_mode_message():
                print("DEBUG: _continue_sysex_sequence: Sent Computer Mode. Waiting 100ms before sending Firmware Request.")
                self.sysex_sequence_state["state"] = "send_firmware_request_msg" # Next state
                self.sysex_sequence_timer.start(100) # 100ms delay
            else:
                self._stop_sysex_sequence("Failed to send Computer Mode for Firmware Request.")
            return
        elif state == "send_firmware_request_msg":
            # Step 2: Send Firmware Request
            firmware_request_msg = self.global_settings.get_firmware_request_message()
            if self.midi_worker:
                print(f"DEBUG: _continue_sysex_sequence: Requesting firmware. SysEx message generated: {bytearray(firmware_request_msg.bytes()).hex()}")
                self.midi_worker.send_message(firmware_request_msg)
                self.statusBar.showMessage("Sent Firmware Version Request.")
            
            self.sysex_sequence_state["state"] = "wait_for_firmware_response"
            self.sysex_sequence_timer.start(2000) # Wait for firmware response
            return
        # Removed wait_for_computer_mode_ack_firmware state as we now skip it
        elif state == "send_computer_mode": # This state is used for explicit computer mode switch
            if self._send_computer_mode_message():
                self.sysex_sequence_state["state"] = "wait_for_computer_mode_ack_switch"
                self.sysex_sequence_timer.start(500) # Wait for ACK
            else:
                self._stop_sysex_sequence("Failed to send Computer Mode message.")
            return
        elif state == "wait_for_computer_mode_ack_switch":
            last_msg = self.sysex_sequence_state.pop("last_received_msg", None)
            if last_msg and last_msg.type == 'sysex':
                raw_sysex_bytes = last_msg.bytes()[1:-1]
                print(f"DEBUG: Received SysEx during Computer Mode ACK wait for switch: {raw_sysex_bytes.hex()}")
                self.statusBar.showMessage("Received SysEx during Computer Mode ACK. Mode switched.", 2000)

            self.current_device_mode = "Computer Mode"
            self.device_mode_label.setText(f"Mode: {self.current_device_mode}")
            self._stop_sysex_sequence("Switched to Computer Mode.")
            return
        elif state == "send_patch_mode": # This state is used for explicit patch mode switch
            patch_mode_msg = EmagicSysEx.get_patch_mode_message(self.current_patch_index)
            if self.midi_worker:
                print(f"DEBUG: _continue_sysex_sequence: Sending Patch Mode message for slot {self.current_patch_index}. SysEx: {bytearray(patch_mode_msg.bytes()).hex()}")
                self.midi_worker.send_message(patch_mode_msg)
                self.statusBar.showMessage(f"Sent Patch Mode command for Patch {self.current_patch_index+1}.")
            self.sysex_sequence_state["state"] = "wait_for_patch_mode_ack"
            self.sysex_sequence_timer.start(500) # Wait for ACK
            return
        elif state == "wait_for_patch_mode_ack":
            last_msg = self.sysex_sequence_state.pop("last_received_msg", None)
            if last_msg and last_msg.type == 'sysex':
                raw_sysex_bytes = last_msg.bytes()[1:-1]
                print(f"DEBUG: Received SysEx during Patch Mode ACK wait: {raw_sysex_bytes.hex()}")
                self.statusBar.showMessage("Received SysEx during Patch Mode ACK. Mode switched.", 2000)

            self.current_device_mode = "Patch Mode"
            self.device_mode_label.setText(f"Mode: {self.current_device_mode}")
            self._stop_sysex_sequence("Switched to Patch Mode.")
            return
        elif state == "wait_for_firmware_response":
            last_msg = self.sysex_sequence_state.pop("last_received_msg", None)
            if last_msg and last_msg.type == 'sysex':
                raw_sysex_bytes = bytearray(last_msg.bytes()) # Pass full message including F0/F7 for robust parsing
                print(f"DEBUG: _continue_sysex_sequence (wait_for_firmware_response): last_msg received: {last_msg.bytes().hex()}")
                print(f"DEBUG: _continue_sysex_sequence (wait_for_firmware_response): raw_sysex_bytes: {raw_sysex_bytes.hex()}")
                self.global_settings.parse_firmware_response(raw_sysex_bytes)
                print(f"DEBUG: _continue_sysex_sequence (wait_for_firmware_response): Parsed firmware version from global_settings: {self.global_settings.firmware_version}")
                self.firmware_version_label.setText(self.global_settings.firmware_version)
                self.statusBar.showMessage(f"Firmware Version: {self.global_settings.firmware_version}")
            else:
                print("DEBUG: _continue_sysex_sequence (wait_for_firmware_response): No message received or not sysex.")
                self.statusBar.showMessage("No firmware response received.", 3000)
                self.firmware_version_label.setText("Timeout")
            self._stop_sysex_sequence("Firmware request completed.")
            return
        elif state == "start_patch_operation" or state == "idle": # Add "idle" as a fallback state
            print("DEBUG: _continue_sysex_sequence: Entering load/save operation block.")
            print(f"DEBUG: _continue_sysex_sequence: Operation: {operation}, current_idx: {current_idx}, MIDI worker running: {self.midi_worker and self.midi_worker.isRunning()}")

            if operation == "load":
                if current_idx >= 32:
                    self._stop_sysex_sequence("Finished loading patches.")
                    self._populate_midi_matrix(self.current_patch_index)
                    return

                # Process previous response if any
                last_msg = self.sysex_sequence_state.pop("last_received_msg", None)
                if last_msg and last_msg.type == 'sysex':
                    raw_sysex_bytes = last_msg.bytes()[1:-1] # Remove F0 and F7
                    expected_prefix_len = len(EMAGIC_MANUFACTURER_ID) + 1 + 1 + 1 # ManID (3) + DevID (1) + Cmd (1) + Slot (1)

                    print(f"Received raw SysEx: {raw_sysex_bytes.hex()}") # Added logging
                    if len(raw_sysex_bytes) >= expected_prefix_len and \
                       raw_sysex_bytes[0:3] == bytearray(EMAGIC_MANUFACTURER_ID) and \
                       raw_sysex_bytes[3] == DEFAULT_DEVICE_ID and \
                       raw_sysex_bytes[4] == SYSEX_COMMAND_CONFIGURE_PATCHES and \
                       raw_sysex_bytes[5] == current_idx: # Ensure the response is for the requested patch and operation

                        response_data_bytes = raw_sysex_bytes[expected_prefix_len:]
                        try:
                            received_patch = EmagicPatch.from_sysex_data(response_data_bytes)
                            received_patch.slot = current_idx # Ensure the slot matches the requested one
                            self.patches[current_idx] = received_patch
                            self.patch_list_widget.item(current_idx).setText(f"Patch {received_patch.slot+1}: {received_patch.name}")
                            self.statusBar.showMessage(f"Loaded Patch {current_idx+1}: {received_patch.name}")
                            print(f"Parsed patch: {received_patch.name}, Timecode: {received_patch.timecode_format}") # Added logging
                        except Exception as e:
                            self.statusBar.showMessage(f"Error parsing SysEx data for Patch {current_idx+1}: {e}", 5000)
                    else:
                        self.statusBar.showMessage(f"Received unexpected SysEx response for Patch {current_idx+1}", 3000)

                # Send next request
                request_msg = self.patches[current_idx].get_sysex_message(SYSEX_COMMAND_REQUEST_PATCH)
                if self.midi_worker:
                    print(f"DEBUG: _continue_sysex_sequence: Requesting patch {current_idx+1}. SysEx message generated but not yet sent to worker. Hex: {bytearray(request_msg.bytes()).hex()}")
                    self.midi_worker.send_message(request_msg)
                    self.statusBar.showMessage(f"Requesting Patch {current_idx+1}...")
                self.sysex_sequence_state["current_patch_idx"] += 1
                # Set a timeout for the next response
                self.sysex_sequence_timer.start(500) # Wait up to 500ms for response before continuing (adjust as needed)

            elif operation == "save":
                if current_idx >= 32:
                    self._stop_sysex_sequence("Finished saving patches.")
                    return

                # Send the current patch
                send_msg = self.patches[current_idx].get_sysex_message(SYSEX_COMMAND_SEND_PATCH)
                if self.midi_worker:
                    print(f"DEBUG: _continue_sysex_sequence: Saving patch {current_idx+1}. SysEx message generated for \"{self.patches[current_idx].name}\". Hex: {bytearray(send_msg.bytes()).hex()}")
                    self.midi_worker.send_message(send_msg)
                    self.statusBar.showMessage(f"Sending Patch {current_idx+1}: {self.patches[current_idx].name}...")
                
                self.sysex_sequence_state["current_patch_idx"] += 1
                self.sysex_sequence_timer.start(50) # Small delay between sending patches (50ms)

    def _stop_sysex_sequence(self, message="MIDI operation completed."):
        self.sysex_sequence_state["active"] = False
        self.sysex_sequence_timer.stop()
        self.sysex_sequence_state = {"active": False, "current_patch_idx": 0, "operation": None, "last_received_msg": None}
        self.statusBar.showMessage(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EmagicMidiConfig()
    window.show()
    sys.exit(app.exec())
