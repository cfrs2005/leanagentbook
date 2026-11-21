"""Optional macOS OS-policy probe, not a general code execution sandbox.

Only creates temporary files. Network probe binds loopback; no packet is sent.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    sandbox = shutil.which("sandbox-exec")
    if sys.platform != "darwin" or not sandbox:
        print("SKIP: macOS sandbox-exec unavailable; no arbitrary-code tool is provided")
        return
    with tempfile.TemporaryDirectory(prefix="gateway-probe-") as directory:
        root = Path(directory).resolve()
        blocked = root / "outside.txt"
        blocked.write_text("synthetic-canary", encoding="utf-8")
        script = root / "probe.py"
        script.write_text('''import json, socket, sys
result = {}
try:
    open(sys.argv[1]).read()
    result["file"] = "allowed"
except PermissionError:
    result["file"] = "denied"
with socket.socket() as connection:
    try:
        connection.bind(("127.0.0.1", 0))
        result["network"] = "allowed"
    except PermissionError:
        result["network"] = "denied"
print(json.dumps(result, sort_keys=True))
''', encoding="utf-8")
        command = [sys.executable, "-I", str(script), str(blocked)]
        baseline = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
        assert json.loads(baseline.stdout) == {"file": "allowed", "network": "allowed"}
        # Narrow negative-policy probe; default allow is NOT safe for untrusted programs.
        profile = root / "probe.sb"
        profile.write_text('(version 1)\n(allow default)\n(deny network*)\n'
                           f'(deny file-read* (literal "{blocked}"))\n', encoding="utf-8")
        result = subprocess.run([sandbox, "-f", str(profile), *command],
                                capture_output=True, text=True, timeout=10)
        if result.returncode and "sandbox_init" in result.stderr:
            print("SKIP: OS rejected sandbox initialization: " + result.stderr.strip())
            return
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"file": "denied", "network": "denied"}, result.stdout
        print("PASS baseline: file/network allowed; OS policy: file/network denied")
        print("LIMIT: specific file and loopback bind only; not a complete sandbox")


if __name__ == "__main__":
    main()
