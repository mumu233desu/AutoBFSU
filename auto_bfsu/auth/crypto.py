import ctypes
from ctypes import wintypes
import base64
import sys

# Win32 structures for DPAPI
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def _xor_cipher(data: bytes, key: str = "AutoBFSU_Secret_Key_2026") -> bytes:
    """A simple symmetric XOR cipher for cross-platform obfuscation."""
    key_bytes = key.encode("utf-8")
    return bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data))

def encrypt_password(password: str) -> str:
    """Encrypt password using Windows DPAPI, returned as base64 string."""
    if not password:
        return ""
    if not sys.platform.startswith("win"):
        # Fallback to symmetric XOR obfuscation for non-Windows
        try:
            encrypted_bytes = _xor_cipher(password.encode("utf-8"))
            encoded = base64.b64encode(encrypted_bytes).decode("utf-8")
            return f"OBF:{encoded}"
        except Exception:
            return password
        
    try:
        # Prepare input blob
        data_bytes = password.encode("utf-8")
        in_blob = DATA_BLOB(len(data_bytes), ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        
        # Call CryptProtectData
        # CryptProtectData(pDataIn, szDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
        success = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            u"AutoBFSU_Key",
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob)
        )
        
        if not success:
            raise ctypes.WinError()
            
        # Read encrypted bytes
        result_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        # Free allocated memory using LocalFree
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        
        # Return base64 encoded string prefixed with DPAPI:
        b64_str = base64.b64encode(result_bytes).decode("utf-8")
        return f"DPAPI:{b64_str}"
    except Exception as e:
        print(f"[Crypto] DPAPI encryption failed, falling back to basic encoding: {e}")
        try:
            encrypted_bytes = _xor_cipher(password.encode("utf-8"))
            encoded = base64.b64encode(encrypted_bytes).decode("utf-8")
            return f"OBF:{encoded}"
        except Exception:
            return password

def decrypt_password(encrypted_str: str) -> str:
    """Decrypt password using Windows DPAPI or basic fallback."""
    if not encrypted_str:
        return ""
    if encrypted_str.startswith("OBF:"):
        try:
            b64_data = encrypted_str[4:]
            encrypted_bytes = base64.b64decode(b64_data.encode("utf-8"))
            decrypted_bytes = _xor_cipher(encrypted_bytes)
            # Try to decode as utf-8, if it fails it might be old pure base64
            try:
                return decrypted_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Backward compatibility for old pure base64 OBF strings
                return base64.b64decode(b64_data.encode("utf-8")).decode("utf-8")
        except Exception:
            return encrypted_str
    if not encrypted_str.startswith("DPAPI:"):
        # If it is not prefixed, treat it as a plain-text password for backward compatibility
        return encrypted_str
        
    if not sys.platform.startswith("win"):
        # Non-Windows fallback cannot decrypt DPAPI, but they shouldn't have DPAPI passwords
        return encrypted_str
        
    try:
        b64_data = encrypted_str[6:]
        encrypted_bytes = base64.b64decode(b64_data.encode("utf-8"))
        
        in_blob = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        
        # Call CryptUnprotectData
        success = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob)
        )
        
        if not success:
            raise ctypes.WinError()
            
        result_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        
        return result_bytes.decode("utf-8")
    except Exception as e:
        print(f"[Crypto] DPAPI decryption failed: {e}")
        return encrypted_str
