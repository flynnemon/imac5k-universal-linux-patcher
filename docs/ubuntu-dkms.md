# Ubuntu / Debian: native 5K that survives kernel updates (DKMS)

The Arch and Fedora backends build the patched `amdgpu` once, for the running kernel, and say "re-run after a kernel
update". On Ubuntu a kernel update arrives in the normal security stream, so this backend uses **DKMS**: every kernel
package that gets installed triggers a rebuild of the patched module for that kernel, automatically.

```bash
sudo scripts/ubuntu-imac5k install     # or: sudo scripts/patch-imac5k-amdgpu.sh (dispatches here on Ubuntu/Debian)
scripts/ubuntu-imac5k status           # read-only
sudo scripts/ubuntu-imac5k remove      # full undo
```

Reboot after `install`. The patched module stitches the two tiles on its own: `amdgpu.tiled_stitch` defaults to `-1`
(auto), which enables stitching for supported Apple panels, the same as `1`. **No kernel command-line change is made.**
(`amdgpu.tiled_stitch=0` switches stitching off, leaving two separate tile connectors; that is a debug switch, not a
recovery path.)

## What happens on a kernel update
1. dpkg installs `linux-image-X` and `linux-headers-X`; the DKMS kernel hook runs `dkms autoinstall` for kernel X.
2. `imac5k-dkms prepare X` reads the headers package's version (e.g. `7.0.0-38.38`), downloads **that exact**
   `linux-source-7.0.0=7.0.0-38.38` from the Ubuntu archive (or uses it if installed), and extracts only
   `drivers/gpu/drm/amd` and `include/trace` (the amdgpu build is self-contained there).
3. It applies the patch stack in `modules/imac5k-amdgpu/patch-series.txt` with `patch --fuzz=0`, trying each patch with
   `--dry-run` first. A file in `patches/ports/<series>/` replaces the same-named patch for that kernel series.
4. `imac5k-dkms build` compiles only `amdgpu.ko` against the kernel's headers (about 5 minutes on 4 cores, niced).
5. `imac5k-dkms verify` refuses the module unless its vermagic equals the kernel's and it has the `tiled_stitch`
   parameter. DKMS then installs it to `/lib/modules/X/updates/dkms/`, which `depmod` prefers over `kernel/`.
6. `imac5k-dkms post-install` regenerates that kernel's initramfs if it already exists (the initramfs carries `amdgpu`
   for early graphics; without this the stock module would load first).

**Failure is safe.** If any step fails (a patch no longer applies because amdgpu changed, the source cannot be
downloaded, the series is not 7.0/7.1/7.2, the compile breaks), nothing is installed for that kernel: it boots the stock
module at 4K. `scripts/ubuntu-imac5k status` shows which installed kernels have the patched module. A new kernel
**series** (for example 7.3) always needs a human re-port first; that is deliberate (patches/README.md, RULE 1).

## Kernel series and ports
The stack is written against 7.2. On 7.0 (Ubuntu 26.04) two patches need a changed context line and carry **no changed
code**; they live in `patches/ports/7.0/`:

| patch | why 7.0 differs |
|---|---|
| `imac5k-lean-core-7.2.x.patch` | last `link_detection.c` hunk: 7.0 still has `DC_LOGGER_INIT(link->ctx->logger);` in `link_detect()` and no `{` after the `verify_link_capability` condition |
| `dce110-genlock-master-from-pipe0.patch` | `dce110_enable_per_frame_crtc_position_reset()` has `DC_LOGGER_INIT();` in 7.0 and `DC_LOGGER_INIT(dc->ctx);` in 7.1+ |

Verified on Ubuntu 26.04, `7.0.0-38-generic`: all twelve patches apply at `--fuzz=0` to `linux-source-7.0.0 7.0.0-38.38`
and the module builds. Hardware result for 7.0 is recorded in the project that uses this fork (see the commit history).

## Requirements
`dkms`, `dwarves` (pahole, for module BTF), `bc`, `cpio`, `build-essential`, `bzip2`, `patch`, the running kernel's
headers, network access to the Ubuntu archive during a build, and about 6 GiB free under `/var/lib/dkms`.
On a system with Secure Boot enabled the module must be signed with an enrolled key; this backend does not set that up
(the iMac17,1 firmware has no Secure Boot).

## Recovery
- Booted, SSH works (the GPU is not involved in Wi-Fi): `sudo scripts/ubuntu-imac5k remove && sudo reboot`.
- Display broken and no network: at the (hidden) GRUB menu hold Esc or Shift, press `e` on the entry, append
  `nomodeset systemd.unit=multi-user.target`, boot with Ctrl-x, log in on the text console, run the same command.
- `install` saves the running kernel's initramfs once as `/boot/initrd.img-<ver>.pre-imac5k`.

## Not covered
The interactive `imac-patcher` menu does not know this backend (its `5k` module assumes Limine or Arch GRUB and a 4K
fallback parameter); use the commands above. The 5K iMac behaviours that are not display (audio, EQ, colour, suspend) are
untouched.
