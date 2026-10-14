"""Offline checks for the Ubuntu/Debian DKMS backend: the patch list is complete, ports are well formed, scripts parse."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "modules" / "imac5k-amdgpu"


def series():
    return [l.strip() for l in (MODULE / "patch-series.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]


class UbuntuDkmsTests(unittest.TestCase):
    def test_every_listed_patch_exists(self):
        for name in series():
            self.assertTrue((ROOT / "patches" / name).is_file(), name)

    def test_series_matches_the_lean_installer(self):
        # The DKMS backend must build the same stack as the Arch backend's lean default.
        text = (ROOT / "scripts" / "patch-imac5k-amdgpu.sh").read_text()
        lean = text.split("lean)")[1].split("verbose)")[0]
        arch = re.findall(r"patches/([\w.\-]+\.patch)", lean)
        self.assertEqual(arch, series())

    def test_ports_replace_a_listed_patch_and_are_diffs(self):
        for port in (ROOT / "patches" / "ports").glob("*/*.patch"):
            self.assertIn(port.name, series(), f"{port} replaces nothing in patch-series.txt")
            body = port.read_text()
            self.assertRegex(body, r"(?m)^--- a/drivers/gpu/drm/amd/")
            self.assertRegex(body, r"(?m)^\+\+\+ b/drivers/gpu/drm/amd/")

    def test_dkms_conf_shape(self):
        conf = (MODULE / "dkms.conf").read_text()
        for needle in ('PACKAGE_VERSION="@VERSION@"', 'BUILT_MODULE_NAME[0]="amdgpu"', 'DEST_MODULE_LOCATION[0]="/updates/dkms/"', 'AUTOINSTALL="yes"'):
            self.assertIn(needle, conf)
        for step in ("prepare", "build", "verify", "post-install"):
            self.assertIn(f"imac5k-dkms {step}", conf)
        # verify must look where DKMS leaves the module at POST_BUILD time, not in the build tree
        self.assertIn("${kernelver}/${arch}/module", conf)

    def test_scripts_parse(self):
        for script in (MODULE / "imac5k-dkms", ROOT / "scripts" / "ubuntu-imac5k"):
            self.assertEqual(subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode, 0, script)

    def test_unsupported_series_is_refused_before_any_download(self):
        r = subprocess.run(["bash", str(MODULE / "imac5k-dkms"), "prepare", "7.3.1-1-generic"], capture_output=True, text=True, cwd="/tmp")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("verified for", r.stderr)


if __name__ == "__main__":
    unittest.main()
