import unittest
from src.emagic_sysex import EmagicPatch, EmagicSysEx, EmagicGlobalSettings, EMAGIC_MANUFACTURER_ID, DEFAULT_DEVICE_ID, SYSEX_COMMAND_COMPUTER_MODE, SYSEX_COMMAND_REQUEST_PATCH, SYSEX_COMMAND_CONFIGURE_PATCHES, SYSEX_COMMAND_FIRMWARE_VERSION_REQUEST, SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS, TIMECODE_LTC_SMPTE

class TestEmagicSysEx(unittest.TestCase):

    def test_emagic_patch_get_sysex_data(self):
        patch = EmagicPatch(name="Test Patch", slot=0)
        patch.midi_matrix[(0, 0)] = True  # IN 1 -> OUT 1
        patch.midi_matrix[(1, 7)] = True  # IN 2 -> OUT 8
        patch.timecode_format = TIMECODE_LTC_SMPTE

        sysex_data = patch.get_sysex_data(num_in_ports=8, num_out_ports=8)

        # Expected length: 16 (name) * 2 + 8 (matrix) * 2 + 1 (timecode) * 2 = 32 + 16 + 2 = 50 bytes
        self.assertEqual(len(sysex_data), 50)

        # Verify Name Encoding (first 32 nibbles)
        expected_name_hex = "54657374205061746368202020202020" # "Test Patch      "
        # Actual SysEx data is nibble encoded. "T" (0x54) -> 0x05, 0x04
        expected_name_nibble_hex = "0504060507030704020005000601070406030608020002000200020002000200"
        self.assertEqual(sysex_data[0:32].hex(), expected_name_nibble_hex)

        # Verify MIDI Matrix Encoding (next 16 nibbles)
        # IN 1 -> OUT 1: 0x01 (bit 0 set) -> 0x00, 0x01
        # IN 2 -> OUT 8: 0x80 (bit 7 set) -> 0x08, 0x00
        # Other IN ports are 0x00 -> 0x00, 0x00
        self.assertEqual(sysex_data[32:34].hex(), "0001") # IN 1
        self.assertEqual(sysex_data[34:36].hex(), "0800") # IN 2
        self.assertEqual(sysex_data[36:38].hex(), "0000") # IN 3 (assuming 8 in_ports)

        # Verify Timecode Format Encoding (last 2 nibbles)
        self.assertEqual(sysex_data[48:50].hex(), "0001") # TIMECODE_LTC_SMPTE = 0x01

    def test_emagic_patch_from_sysex_data(self):
        # Create a sample SysEx data bytearray that would be received from a device
        # This corresponds to "Test Patch      ", IN1->OUT1, IN2->OUT8, LTC SMPTE
        sample_sysex_data = bytearray.fromhex(
            "0504060507030704020005000601070406030608020002000200020002000200" + # Name (16 chars * 2 nibbles = 32 bytes)
            "00010800000000000000000000000000" + # MIDI Matrix (8 in_ports * 2 nibbles = 16 bytes)
            "0001" # Timecode (1 byte * 2 nibbles = 2 bytes)
        )
        
        patch = EmagicPatch.from_sysex_data(sample_sysex_data, num_in_ports=8, num_out_ports=8)

        self.assertEqual(patch.name, "Test Patch")
        self.assertTrue(patch.midi_matrix.get((0, 0)))
        self.assertTrue(patch.midi_matrix.get((1, 7)))
        self.assertFalse(patch.midi_matrix.get((0, 1))) # Ensure other connections are false
        self.assertEqual(patch.timecode_format, TIMECODE_LTC_SMPTE)

    def test_emagic_patch_get_sysex_message(self):
        patch = EmagicPatch(name="Test Patch", slot=0)
        command = SYSEX_COMMAND_CONFIGURE_PATCHES # Using CONFIGURE_PATCHES as a send command

        mido_msg = patch.get_sysex_message(command)

        self.assertEqual(mido_msg.type, 'sysex')
        # F0 + ManID (3) + DevID (1) + Cmd (1) + Slot (1) + Patch Data (50) + F7 = 58 bytes
        # The data attribute of mido.Message will not include F0 and F7
        self.assertEqual(len(mido_msg.data), 56) 
        
        # Verify prefix: ManID, DevID, Cmd, Slot
        expected_prefix = bytearray(EMAGIC_MANUFACTURER_ID) + bytearray([DEFAULT_DEVICE_ID, command, patch.slot])
        self.assertEqual(bytearray(mido_msg.data[0:len(expected_prefix)]), expected_prefix)

    def test_get_computer_mode_message(self):
        computer_mode_msg = EmagicSysEx.get_computer_mode_message()
        self.assertEqual(computer_mode_msg.type, 'sysex')
        # F0 + ManID (3) + DevID (1) + Cmd (1) + F7 = 7 bytes
        self.assertEqual(len(computer_mode_msg.data), 5) # ManID (3) + DevID (1) + Cmd (1)

        expected_data = bytearray(EMAGIC_MANUFACTURER_ID) + bytearray([DEFAULT_DEVICE_ID, SYSEX_COMMAND_COMPUTER_MODE])
        self.assertEqual(bytearray(computer_mode_msg.data), expected_data)

    def test_get_device_info_request_message(self):
        device_info_msg = EmagicSysEx.get_device_info_request_message()
        self.assertEqual(device_info_msg.type, 'sysex')
        # F0 + ManID (3) + DevID (1) + Cmd (1) + F7 = 7 bytes
        self.assertEqual(len(device_info_msg.data), 5) # ManID (3) + DevID (1) + Cmd (1)

        expected_data = bytearray(EMAGIC_MANUFACTURER_ID) + bytearray([DEFAULT_DEVICE_ID, SYSEX_COMMAND_REQUEST_VARIOUS_SETUPS])
        self.assertEqual(bytearray(device_info_msg.data), expected_data)

    def test_global_settings_get_firmware_request_message(self):
        global_settings = EmagicGlobalSettings()
        firmware_request_msg = global_settings.get_firmware_request_message(device_index=0x00)

        self.assertEqual(firmware_request_msg.type, 'sysex')
        # Expected: ManID (3) + DevID (1) + Cmd (1) + SubCmd (1) + DevIdx (1) = 7 bytes
        self.assertEqual(len(firmware_request_msg.data), 7)

        expected_data = bytearray(EMAGIC_MANUFACTURER_ID) + bytearray([DEFAULT_DEVICE_ID, SYSEX_COMMAND_FIRMWARE_VERSION_REQUEST, 0x00, 0x00])
        self.assertEqual(bytearray(firmware_request_msg.data), expected_data)

    def test_global_settings_parse_firmware_response(self):
        global_settings = EmagicGlobalSettings()

        # Mock SysEx response for firmware version "2.0.2"
        # F0 00 20 31 64 0B 00 00 32 30 32 F7
        mock_firmware_response_data = bytearray.fromhex(
            "002031640B0000" + # Header: ManID, DevID, Cmd, SubCmd, DevIdx
            "323032"        # ASCII for "202"
        )
        global_settings.parse_firmware_response(mock_firmware_response_data)
        self.assertEqual(global_settings.firmware_version, "202")

        # Test with different version, e.g., "1.5.0"
        mock_firmware_response_data_2 = bytearray.fromhex(
            "002031640B0000" + # Header
            "312E352E30"    # ASCII for "1.5.0"
        )
        global_settings.parse_firmware_response(mock_firmware_response_data_2)
        self.assertEqual(global_settings.firmware_version, "1.5.0")

        # Test with malformed response (incorrect header)
        global_settings.firmware_version = "Unknown" # Reset for test
        malformed_response = bytearray.fromhex(
            "002031640B0001" + # Incorrect device index
            "323032"
        )
        global_settings.parse_firmware_response(malformed_response)
        self.assertEqual(global_settings.firmware_version, "Unexpected response format")

        # Test with non-ASCII data (UnicodeDecodeError scenario handled with replace)
        global_settings.firmware_version = "Unknown" # Reset for test
        non_ascii_response = bytearray.fromhex(
            "002031640B0000" + # Header
            "F0F0"          # Non-ASCII example
        )
        global_settings.parse_firmware_response(non_ascii_response)
        # "F0" is not a valid ASCII byte, so it should be replaced.
        # The exact number of replacement chars depends on the decoder implementation for invalid sequences.
        # We just check that it's not the "Error parsing ASCII" string anymore, but something else.
        # Or better, check that it contains the replacement char.
        self.assertIn("\ufffd", global_settings.firmware_version)



if __name__ == '__main__':
    unittest.main()
