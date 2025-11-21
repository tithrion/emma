
import struct
import mido
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Emagic Manufacturer ID (00 20 0B)
EMAGIC_MANUFACTURER_ID = [0x00, 0x20, 0x31]

# Device ID (64 for Unitor8, as per documentation)
DEFAULT_DEVICE_ID = 0x64

# SysEx Command Opcodes (from documentation)
SYSEX_COMMAND_COMPUTER_MODE = 0x0F  # Set Computer Mode
SYSEX_COMMAND_SELECT_PATCH = 0x10   # Select Patch / Set Patch Mode
SYSEX_COMMAND_CONFIGURE_PATCHES = 0x11 # Configure Patches (likely used for sending patch data)
SYSEX_COMMAND_REQUEST_PATCH = 0x12  # Request specific patch data
SYSEX_COMMAND_LED_BRIGHTNESS = 0x13 # LED Brightness Control
SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS = 0x14 # Request Various Setups
SYSEX_COMMAND_FIRMWARE_VERSION_REQUEST = 0x0B # Request Firmware Version

# Renaming SYSEX_COMMAND_SEND_PATCH to SYSEX_COMMAND_CONFIGURE_PATCHES as per documentation
# This means the command itself might include the patch slot.
SYSEX_COMMAND_SEND_PATCH = SYSEX_COMMAND_CONFIGURE_PATCHES

# Timecode Formats (from user description)
TIMECODE_OFF = 0x00
TIMECODE_LTC_SMPTE = 0x01 # 30 fps
TIMECODE_LTC_AES_EBU = 0x02 # 25 fps
TIMECODE_VITC = 0x03

# Universal SysEx - Device Identity Request/Reply
UNIVERSAL_NON_REALTIME_SYSEX = 0x7E
DEVICE_ID_BROADCAST = 0x7F
IDENTITY_REQUEST_CATEGORY = 0x06
IDENTITY_REQUEST = 0x01
IDENTITY_REPLY = 0x02

# Manufacturer ID Database for common MIDI manufacturers
# Format: ID (1 byte or 3-tuple for extended): Name
MANUFACTURER_DATABASE = {
    # Single-byte IDs (0x01-0x7D)
    0x01: "Sequential",
    0x02: "IDP",
    0x03: "Voyetra/Octave-Plateau",
    0x04: "Moog",
    0x05: "Passport Designs",
    0x06: "Lexicon",
    0x07: "Kurzweil",
    0x08: "Fender",
    0x09: "Gulbransen",
    0x0A: "AKG Acoustics",
    0x0B: "Voyce Music",
    0x0C: "Waveframe Corp",
    0x0D: "ADA Signal Processors",
    0x0E: "Garfield Electronics",
    0x0F: "Ensoniq",
    0x10: "Oberheim/Gibson Labs",
    0x11: "Apple",
    0x12: "Grey Matter Response",
    0x13: "Digidesign Inc.",
    0x14: "Palm Tree Instruments",
    0x15: "JLCooper Electronics",
    0x16: "Lowrey",
    0x17: "Adams-Smith",
    0x18: "E-mu",
    0x19: "Harmony Systems",
    0x1A: "ART",
    0x1B: "Baldwin",
    0x1C: "Eventide",
    0x1D: "Inventronics",
    0x1F: "Clarity",
    0x20: "Passac",
    0x21: "SIEL",
    0x22: "Synthaxe",
    0x24: "Hohner",
    0x25: "Twister",
    0x26: "Solton",
    0x27: "Jellinghaus MS",
    0x28: "Southworth Music Systems",
    0x29: "PPG",
    0x2A: "JEN",
    0x2B: "SSL",
    0x2C: "Audio Veritrieb-P.Struven",
    0x2F: "ELKA",
    0x30: "Dynacord",
    0x31: "Jomox",
    0x33: "Clavia Digital Instruments",
    0x39: "Soundcraft Electronics",
    0x3E: "Waldorf",
    0x3F: "Kawai",
    0x40: "Roland",
    0x41: "Korg",
    0x42: "Yamaha",
    0x43: "Casio",
    0x47: "Akai",
    
    # Extended IDs (3 bytes: 0x00, region, ID)
    (0x00, 0x20, 0x29): "Novation",
    (0x00, 0x20, 0x31): "Emagic",
    (0x00, 0x20, 0x32): "Behringer",
    (0x00, 0x20, 0x3C): "Clavia (Nord)",
    (0x00, 0x21, 0x09): "AKAI professional",
    (0x00, 0x40, 0x26): "Arturia",
}

def get_manufacturer_name(manufacturer_id):
    """
    Get manufacturer name from ID.
    manufacturer_id can be int (1 byte) or tuple (3 bytes for extended IDs)
    """
    return MANUFACTURER_DATABASE.get(manufacturer_id, f"Unknown ({manufacturer_id})")

def create_identity_request():
    """Create a Universal Device Identity Request SysEx message"""
    return mido.Message('sysex', data=[
        UNIVERSAL_NON_REALTIME_SYSEX,
        DEVICE_ID_BROADCAST,
        IDENTITY_REQUEST_CATEGORY,
        IDENTITY_REQUEST
    ])

def parse_identity_reply(sysex_data):
    """
    Parse a Universal Device Identity Reply message.
    Returns dict with manufacturer, device_family, device_member, software_version
    or None if not a valid identity reply.
    
    Format: F0 7E <dev> 06 02 <mfr> <family> <member> <version> F7
    """
    # Strip F0/F7 if present
    if len(sysex_data) > 0 and sysex_data[0] == 0xF0:
        sysex_data = sysex_data[1:]
    if len(sysex_data) > 0 and sysex_data[-1] == 0xF7:
        sysex_data = sysex_data[:-1]
    
    # Check for Universal Non-Realtime SysEx Identity Reply
    if len(sysex_data) < 5:
        return None
    if sysex_data[0] != UNIVERSAL_NON_REALTIME_SYSEX:
        return None
    # sysex_data[1] is device ID
    if sysex_data[2] != IDENTITY_REQUEST_CATEGORY or sysex_data[3] != IDENTITY_REPLY:
        return None
    
    # Parse manufacturer ID (1 or 3 bytes)
    offset = 4
    if sysex_data[offset] == 0x00:
        # Extended 3-byte ID
        if len(sysex_data) < offset + 3:
            return None
        manufacturer_id = tuple(sysex_data[offset:offset+3])
        offset += 3
    else:
        # Single-byte ID
        manufacturer_id = sysex_data[offset]
        offset += 1
    
    # Device family (2 bytes LSB first)
    if len(sysex_data) < offset + 2:
        device_family = None
    else:
        device_family = sysex_data[offset] | (sysex_data[offset+1] << 7)
        offset += 2
    
    # Device member (2 bytes LSB first)
    if len(sysex_data) < offset + 2:
        device_member = None
    else:
        device_member = sysex_data[offset] | (sysex_data[offset+1] << 7)
        offset += 2
    
    # Software version (4 bytes)
    if len(sysex_data) < offset + 4:
        software_version = None
    else:
        software_version = tuple(sysex_data[offset:offset+4])
        offset += 4
    
    return {
        'manufacturer_id': manufacturer_id,
        'manufacturer_name': get_manufacturer_name(manufacturer_id),
        'device_family': device_family,
        'device_member': device_member,
        'software_version': software_version
    }


class EmagicPatch:
    def __init__(self, name="Unnamed Patch", slot=0):
        self.name = name
        self.slot = slot # 0-31
        self.midi_matrix = {} # { (in_port, out_port): True/False }
        self.timecode_format = TIMECODE_OFF
        # Add other patch parameters as needed, e.g., filter settings, merge options

    def get_sysex_data(self, num_in_ports=8, num_out_ports=8):
        """
        Generates the SysEx data bytes for this patch.
        Based on documentation, MIDI data is stored across two bytes (nibble encoding).
        No checksums found in messages.
        """
        data = bytearray()

        # Patch name (padded to 16 chars, 7-bit ASCII for SysEx)
        name_bytes = self.name.encode('ascii', errors='replace')
        padded_name = name_bytes[:16].ljust(16, b' ') # Pad with spaces
        # Encode each ASCII character (byte) into two 7-bit SysEx nibbles
        for char_byte in padded_name:
            data.append((char_byte >> 4) & 0x0F) # Most significant nibble
            data.append(char_byte & 0x0F)       # Least significant nibble

        # MIDI matrix (bitwise OR for routing)
        # Assuming a structure where each IN port has a byte or set of nibbles
        # representing its connections to OUT ports.
        # The documentation mentions input-to-output routing uses bitwise OR.
        # Let's assume 8 bytes, where each byte represents an IN port's connections to 8 OUT ports.
        # Each bit in the byte corresponds to an OUT port (e.g., bit 0 for OUT1, bit 7 for OUT8).
        # This is a common pattern for routing matrices.
        matrix_bytes_raw = bytearray(num_in_ports) # One byte for each IN port
        for in_idx in range(num_in_ports):
            connections_for_in_port = 0
            for out_idx in range(num_out_ports):
                # Use the logical port indices (0-based) for the matrix
                if self.midi_matrix.get((in_idx, out_idx), False):
                    connections_for_in_port |= (1 << out_idx)
            matrix_bytes_raw[in_idx] = connections_for_in_port
        
        # Encode raw matrix bytes into SysEx 7-bit nibbles (2 bytes per raw byte)
        for byte_val in matrix_bytes_raw:
            data.append((byte_val >> 4) & 0x0F)
            data.append(byte_val & 0x0F)

        # Timecode format (single byte, encoded into two nibbles)
        data.append((self.timecode_format >> 4) & 0x0F)
        data.append(self.timecode_format & 0x0F)

        # No checksums mentioned in documentation
        logger.debug(f"EmagicPatch.get_sysex_data: Generated raw patch data (hex): {data.hex()}")
        return data

    def _calculate_checksum(self, data):
        """
        Documentation states no checksums were found in messages.
        Returning 0 or removing this might be appropriate.
        """
        return 0 # No checksum as per documentation

    @classmethod
    def from_sysex_data(cls, data, num_in_ports=8, num_out_ports=8):
        """
        Parses SysEx data bytes to create an EmagicPatch object.
        """
        patch = cls()
        offset = 0

        # Patch name (16 chars, each 2 SysEx bytes)
        name_bytes = bytearray()
        for _ in range(16):
            if offset + 1 >= len(data): break
            msn = data[offset] & 0x0F
            lsn = data[offset + 1] & 0x0F
            name_bytes.append((msn << 4) | lsn)
            offset += 2
        patch.name = name_bytes.decode('ascii', errors='replace').strip()

        # MIDI matrix (8 IN ports, each 2 SysEx bytes representing connections to 8 OUT ports)
        # This assumes num_in_ports * 2 bytes for the matrix
        matrix_bytes_raw = bytearray(num_in_ports)
        for in_idx in range(num_in_ports):
            if offset + 1 >= len(data): break
            msn = data[offset] & 0x0F
            lsn = data[offset + 1] & 0x0F
            matrix_byte = (msn << 4) | lsn
            matrix_bytes_raw[in_idx] = matrix_byte
            offset += 2

            for out_idx in range(num_out_ports):
                if (matrix_byte >> out_idx) & 1:
                    patch.midi_matrix[(in_idx, out_idx)] = True

        # Timecode format (2 SysEx bytes)
        if offset + 1 < len(data):
            msn = data[offset] & 0x0F
            lsn = data[offset + 1] & 0x0F
            patch.timecode_format = (msn << 4) | lsn
            offset += 2

        return patch

    def get_sysex_message(self, command_opcode):
        """
        Constructs a full Mido SysEx message from the patch data and a command.
        """
        sysex_data = bytearray(EMAGIC_MANUFACTURER_ID)
        sysex_data.append(DEFAULT_DEVICE_ID)
        sysex_data.append(command_opcode)

        if command_opcode == SYSEX_COMMAND_CONFIGURE_PATCHES:
            # For configuring patches, the slot needs to be part of the data
            # Assuming nibble encoding for slot as well, consistent with SELECT_PATCH
            slot_msb = (self.slot >> 4) & 0x0F
            slot_lsb = self.slot & 0x0F
            sysex_data.append(slot_msb)
            sysex_data.append(slot_lsb)
            
            patch_data = self.get_sysex_data()
            sysex_data.extend(patch_data) # Then the patch specific data
            logger.debug(f"EmagicPatch.get_sysex_message (CONFIGURE_PATCHES) for slot {self.slot}: Patch data hex: {patch_data.hex()}")
        elif command_opcode == SYSEX_COMMAND_REQUEST_PATCH:
            # Request specific slot - likely nibble encoded
            slot_msb = (self.slot >> 4) & 0x0F
            slot_lsb = self.slot & 0x0F
            sysex_data.append(slot_msb)
            sysex_data.append(slot_lsb)
            logger.debug(f"EmagicPatch.get_sysex_message (REQUEST_PATCH) for slot {self.slot}: sysex_data: {sysex_data.hex()}")
        elif command_opcode == SYSEX_COMMAND_SELECT_PATCH:
            # Select specific slot - nibble encoded
            slot_msb = (self.slot >> 4) & 0x0F
            slot_lsb = self.slot & 0x0F
            sysex_data.append(slot_msb)
            sysex_data.append(slot_lsb)
        
        # No checksums are applied as per documentation
        logger.debug(f"EmagicPatch.get_sysex_message: Final sysex_data before mido.Message: {sysex_data.hex()}, len: {len(sysex_data)}")
        return mido.Message('sysex', data=list(sysex_data))


class EmagicSysEx:
    """
    A class to handle general Emagic SysEx communication not specific to a single patch.
    """
    @staticmethod
    def get_computer_mode_message():
        """
        Returns the SysEx message to switch the device to computer mode.
        Format: F0 <man_id> <dev_id> 0x0F F7
        """
        sysex_data = bytearray(EMAGIC_MANUFACTURER_ID)
        sysex_data.append(DEFAULT_DEVICE_ID)
        sysex_data.append(SYSEX_COMMAND_COMPUTER_MODE)
        logger.debug(f"EmagicSysEx.get_computer_mode_message: Generated sysex_data: {sysex_data.hex()}, len: {len(sysex_data)}")
        return mido.Message('sysex', data=list(sysex_data))

    @staticmethod
    def get_patch_mode_message(patch_slot):
        """
        Returns the SysEx message to switch the device to patch mode for a specific slot.
        Format: F0 <man_id> <dev_id> 0x10 <slot_nibble_msb> <slot_nibble_lsb> F7
        """
        sysex_data = bytearray(EMAGIC_MANUFACTURER_ID)
        sysex_data.append(DEFAULT_DEVICE_ID)
        sysex_data.append(SYSEX_COMMAND_SELECT_PATCH)
        
        # Patch slot needs to be nibble encoded
        slot_msb = (patch_slot >> 4) & 0x0F
        slot_lsb = patch_slot & 0x0F
        sysex_data.append(slot_msb)
        sysex_data.append(slot_lsb)

        logger.debug(f"EmagicSysEx.get_patch_mode_message: Generated sysex_data: {sysex_data.hex()}, len: {len(sysex_data)}")
        return mido.Message('sysex', data=list(sysex_data))

    @staticmethod
    def get_device_info_request_message():
        """
        The documentation mentions SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS (0x14)
        This command might be used to request device information.
        """
        sysex_data = bytearray(EMAGIC_MANUFACTURER_ID)
        sysex_data.append(DEFAULT_DEVICE_ID)
        sysex_data.append(SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS)
        # The exact data for what information is requested is not fully detailed in potm.org analysis.
        # Additional data bytes might be needed here to specify *what* information is requested.
        logger.debug(f"EmagicSysEx.get_device_info_request_message: Generated sysex_data: {sysex_data.hex()}, len: {len(sysex_data)}")
        return mido.Message('sysex', data=list(sysex_data))


    @staticmethod
    def parse_device_info_response(sysex_message_data):
        """
        Parses the SysEx response for device information.
        This needs specific documentation on the response format from SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS.
        The potm.org analysis did not provide details for this specific response.
        Consult local PDF documentation (SysEx.pdf, emagic_MT4-en.pdf, emagic_unitor8_mkII_amt8_manual.pdf) for details.
        """
        device_info = {"ports_in": 0, "ports_out": 0, "has_timecode": False}
        # Placeholder parsing - this is still highly speculative.
        # The documentation mentioned '0rbbbgggB' for device type/ROM/EEPROM in some SysEx contexts.
        # This could be part of a device info response, but the exact structure is unknown.
        return device_info

class EmagicGlobalSettings:
    """
    A class to manage global device settings.
    """
    def __init__(self):
        self.firmware_version = "Unknown"
        # Add other global settings as identified from documentation
        self.computer_mode_setup_data = None # Example: stores data for 0x14 0x01
        self.patch_mode_setup_data = None # Example: stores data for 0x14 0x02
        self.click_tip_ring_setup_data = None # Example: stores data for 0x14 0x03
        self.led_brightness = {} # Example: { "IO_LED": 0x00, "RS_LED": 0x00 }

    def get_firmware_request_message(self, device_index=0x00):
        """
        Returns the SysEx message to request firmware version.
        Format: F0 <man_id> <dev_id> 0x0B 00 <device_index> F7
        """
        sysex_data = bytearray(EMAGIC_MANUFACTURER_ID)
        sysex_data.append(DEFAULT_DEVICE_ID)
        sysex_data.append(SYSEX_COMMAND_FIRMWARE_VERSION_REQUEST)
        sysex_data.append(0x00) # Sub-command, usually 00 for initial request
        sysex_data.append(device_index) # For chained units, 0x00 for first/only
        logger.debug(f"EmagicGlobalSettings.get_firmware_request_message: Generated sysex_data: {sysex_data.hex()}, len: {len(sysex_data)}")
        return mido.Message('sysex', data=list(sysex_data))

    def parse_firmware_response(self, sysex_message_data):
        """
        Parses the SysEx response for firmware version.
        Response format (example): F0 00 20 31 64 0B 00 00 32 30 32 F7 (for 2.0.2)
        The ASCII bytes for the version are after the command (0x0B) and sub-command (0x00) and device index (0x00).
        
        Update: Hardware seems to respond with opcode 0x7B and payload 00 01 <version>.
        """
        # Ensure we have a bytearray
        if isinstance(sysex_message_data, list):
            sysex_message_data = bytearray(sysex_message_data)
        
        # Strip F0 and F7 if present (robustness for different mido usages)
        if len(sysex_message_data) > 0 and sysex_message_data[0] == 0xF0:
            sysex_message_data = sysex_message_data[1:]
        if len(sysex_message_data) > 0 and sysex_message_data[-1] == 0xF7:
            sysex_message_data = sysex_message_data[:-1]
        
        # Expected header: 00 20 31 64 <CMD> ... (Payload only)
        # Manufacturer ID: 0x00, 0x20, 0x31 (3 bytes)
        # Device ID: 0x64 (1 byte)
        
        base_header = bytearray(EMAGIC_MANUFACTURER_ID)
        base_header.append(DEFAULT_DEVICE_ID)
        
        if len(sysex_message_data) < len(base_header) + 2:
             logger.error(f"EmagicGlobalSettings.parse_firmware_response: Message too short: {sysex_message_data.hex()}")
             return

        # Check Manufacturer and Device ID
        if sysex_message_data[:4] != base_header:
             logger.error(f"EmagicGlobalSettings.parse_firmware_response: Header mismatch: {sysex_message_data[:4].hex()}")
             return

        command = sysex_message_data[4]
        
        # Check for known firmware response opcodes
        # 0x0B: Expected from documentation (request opcode)
        # 0x7B: Observed from hardware
        if command == SYSEX_COMMAND_FIRMWARE_VERSION_REQUEST:
             # Standard format: 0B 00 00 <ASCII>
             offset = 7 # 4 (Header) + 1 (Cmd) + 2 (SubCmd/Idx)
        elif command == 0x7B:
             # Observed format: 7B 00 01 <ASCII>
             offset = 7 # 4 (Header) + 1 (Cmd) + 2 (Unknown)
        else:
             logger.warning(f"EmagicGlobalSettings.parse_firmware_response: Unknown command opcode: {hex(command)}")
             # Try to parse anyway if it looks like it has enough data?
             # For now, let's assume if it's not 0B or 7B, we might not know where the ASCII starts.
             return

        if len(sysex_message_data) > offset:
            firmware_bytes = sysex_message_data[offset:] 
            # F7 is already stripped above if it was present.

            try:
                self.firmware_version = firmware_bytes.decode('ascii', errors='replace')
                logger.debug(f"EmagicGlobalSettings.parse_firmware_response: Parsed firmware version: {self.firmware_version}")
            except Exception as e:
                self.firmware_version = "Error parsing ASCII"
                logger.error(f"EmagicGlobalSettings.parse_firmware_response: Error for firmware bytes: {firmware_bytes.hex()} - {e}")
        else:
            self.firmware_version = "Empty payload"
            logger.warning("EmagicGlobalSettings.parse_firmware_response: No payload found after header.")


