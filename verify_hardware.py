
import time
import mido
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.emagic_sysex import EmagicSysEx, EmagicGlobalSettings, EmagicPatch, SYSEX_COMMAND_REQUEST_PATCH

def find_emagic_ports():
    inputs = mido.get_input_names()
    outputs = mido.get_output_names()
    
    print(f"Available Inputs: {inputs}")
    print(f"Available Outputs: {outputs}")

    emagic_in = None
    emagic_out = None

    # Simple heuristic: look for "Unitor", "AMT8", "MT4"
    keywords = ["Unitor", "AMT8", "MT4", "Emagic"]
    
    for name in inputs:
        if any(k in name for k in keywords):
            emagic_in = name
            break
            
    for name in outputs:
        if any(k in name for k in keywords):
            emagic_out = name
            break
            
    return emagic_in, emagic_out

def main():
    print("--- Emagic Hardware Verification Script ---")
    
    in_port_name, out_port_name = find_emagic_ports()
    
    if not in_port_name or not out_port_name:
        print("ERROR: Could not find Emagic MIDI ports.")
        print(f"Found IN: {in_port_name}, OUT: {out_port_name}")
        # Fallback: try to use the first available port if it looks like a USB MIDI device
        # or just ask user? For now, let's abort if not found.
        return

    print(f"Using IN: {in_port_name}")
    print(f"Using OUT: {out_port_name}")

    try:
        with mido.open_input(in_port_name) as in_port, mido.open_output(out_port_name) as out_port:
            
            # 1. Send Computer Mode Message
            print("\n[1] Sending Computer Mode Message...")
            msg = EmagicSysEx.get_computer_mode_message()
            print(f"Sending: {msg.hex()}")
            out_port.send(msg)
            
            # Wait for potential response (ACK)
            print("Waiting for response (2s)...")
            start_time = time.time()
            while time.time() - start_time < 2:
                for msg in in_port.iter_pending():
                    print(f"Received: {msg.hex()}")
            
            # 2. Request Firmware Version
            print("\n[2] Requesting Firmware Version...")
            global_settings = EmagicGlobalSettings()
            msg = global_settings.get_firmware_request_message()
            print(f"Sending: {msg.hex()}")
            out_port.send(msg)
            
            # Wait for response
            print("Waiting for response (2s)...")
            start_time = time.time()
            while time.time() - start_time < 2:
                for msg in in_port.iter_pending():
                    print(f"Received: {msg.hex()}")
                    if msg.type == 'sysex':
                        # Try to parse it
                        # mido.Message.bytes() includes F0/F7, but our parser expects the payload?
                        # Let's check the parser implementation.
                        # parse_firmware_response expects the full bytes including F0 (but maybe not F7 if from mido.Message.data?)
                        # mido.Message.bytes() returns the full wire format.
                        # The parser in emagic_sysex.py:
                        # if sysex_message_data[:header_len] == expected_header:
                        # It expects the full header.
                        
                        # Let's pass the full bytes, converted to bytearray
                        sysex_bytes = bytearray(msg.bytes())
                        global_settings.parse_firmware_response(sysex_bytes)
                        if global_settings.firmware_version != "Unknown" and global_settings.firmware_version != "Unexpected response format":
                            print(f"SUCCESS: Parsed Firmware Version: {global_settings.firmware_version}")
                        else:
                             print(f"Failed to parse firmware. Version state: {global_settings.firmware_version}")

            # 3. Request Patch 1 (Slot 0) - Experimental
            print("\n[3] Requesting Patch 1 (Slot 0)...")
            print("NOTE: This command (0x12) is currently not working with all devices.")
            
            dummy_patch = EmagicPatch(slot=0)
            msg = dummy_patch.get_sysex_message(SYSEX_COMMAND_REQUEST_PATCH)
            print(f"Sending: {msg.hex()}")
            out_port.send(msg)
            
            # Wait for response
            print("Waiting for response (2s)...")
            start_time = time.time()
            response_received = False
            while time.time() - start_time < 2:
                for msg in in_port.iter_pending():
                    print(f"Received: {msg.hex()}")
                    if msg.type == 'sysex':
                        data = bytearray(msg.bytes())
                        # Strip F0/F7
                        if len(data) > 0 and data[0] == 0xF0: data = data[1:]
                        if len(data) > 0 and data[-1] == 0xF7: data = data[:-1]
                        
                        if len(data) > 6 and data[4] == 0x11: # Opcode 0x11
                            response_received = True
                            slot = data[5]
                            print(f"Received Patch Data for Slot {slot}")
                            patch_payload = data[6:]
                            try:
                                patch = EmagicPatch.from_sysex_data(patch_payload)
                                print(f"SUCCESS: Parsed Patch Name: '{patch.name}'")
                            except Exception as e:
                                print(f"ERROR Parsing Patch: {e}")
            
            if not response_received:
                print("No patch response received (Expected behavior if protocol is unknown).")



    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
