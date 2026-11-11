"""Pack agent, hub, config and service installers into one portable ZIP."""
import argparse
import hashlib
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--hub", required=True)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--output", default="release-assets")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"DeviceShare-{args.suffix}.zip"
    entries = {
        Path(args.agent): f"DeviceShare/{Path(args.agent).name}",
        Path(args.hub): f"DeviceShare/{Path(args.hub).name}",
        root / "config/agent.example.json": "DeviceShare/config/agent.example.json",
        root / "docs/INSTALL_AGENT.md": "DeviceShare/INSTALL_AGENT.md",
        root / "SECURITY.md": "DeviceShare/SECURITY.md",
    }
    for name in ["install_agent_linux.sh", "install_agent_macos.sh", "install_agent_windows.ps1"]:
        entries[root / "scripts" / name] = "DeviceShare/installers/" + name
    for src in entries:
        if not src.is_file():
            raise FileNotFoundError(src)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
        for src, dst in entries.items():
            info = zipfile.ZipInfo(dst)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Retain executable permission for Unix binaries and shell scripts.
            mode = 0o755 if (
                src in (Path(args.agent), Path(args.hub)) or src.suffix == ".sh"
            ) else 0o644
            info.external_attr = (0o100000 | mode) << 16
            zipfile_obj.writestr(info, src.read_bytes())
    print(f"Created {archive}, SHA256={hashlib.sha256(archive.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
