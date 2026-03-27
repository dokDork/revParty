# revParty
[![License](https://img.shields.io/badge/license-MIT-_red.svg)](https://opensource.org/licenses/MIT)  
<img src="https://github.com/dokDork/revParty/raw/main/images/revParty.png" width="500" height="500">  

## Description
It is an advanced tool capable of creating Backdoors and Trojans for Windows systems, for educational purposes only.
The tool must obviously be used only with the approval of the owner of the machine on which the Backdoors and Trojans will be run.

The main features of the tool are:
- It can generate Trojans and backdoors with **polymorphic code**, making them difficult for defense systems to detect through static code analysis.
- It has various types of reverse shells that can be used:
  - **Simple reverse shell**: It has simple code that is often undetected by AVs (sometimes simplicity pays);
  - **TLS reverse shell**: Traffic between the reverse shell and the listener is encrypted over a TLS channel;
  - **FTP reverse shell**: The reverse shell simulates an FTP connection through the following steps:
    - Connect to a remote server: the attacker's machine;
    - Authenticate: To make the action more credible;
    - ask to download a file: the file's body will contain the command the attacker wants to execute on the target machine. To make things a little more obscure, the command could be encoded in base64, and the encoding could be broken by adding a few characters to the alphanumeric sequence.
    - the reverse shell could then execute the command and send the response to the attacker, uploading a file whose body is nothing more than the base64 encoding of the response.
  - **FTP reverse shell with sandbox analysis**: like the previous reverse shell, but when it starts, it analyzes whether it has been activated in a sandbox. If so, it waits before activating.

The **tool is modular** and allows anyone to create their own backdoors. Simply save them in the /engine/second-stage folder to have them processed and inserted into the generated software.

The resulting processing consists of several files:
- **01.second.exe**: the reverse shell (or backdoor) in .exe format;
- **02.stager.exe**: the stager that downloads the reverse shell in .exe format;
- **03.trojan.exe**: an example of a Trojan in .exe format;
- **04.LAUNCHER-SECOND.zip**: a zip file containing a launcher.bat file that bypasses Smartscreen, which then executes the backdoor;
- **05.LAUNCHER-STAGER.zip**: a zip file containing a launcher.bat file that bypasses Smartscreen, which then executes the stager, which in turn downloads the backdoor;
- **06.LAUNCHER-TROJAN.iso**: This is an ISO file containing a launcher.bat file that bypasses SmartScreen, which then executes the backdoor.
- **second.txt**: This is the backdoor's text format, obfuscated with polymorphic code.
- **stager.txt**: This is the stager's text format, obfuscated with polymorphic code.
- **update_k897867.msu**: This is the file used by the Trojan as a front-end file.

  
## Example Usage
 ```
python3 reverseParty.py
 ``` 
<img src="https://github.com/dokDork/red-team-penetration-test-script/raw/main/images/01.png">

select one of the penetration test PHASES you are interested in:
<img src="https://github.com/dokDork/red-team-penetration-test-script/raw/main/images/02.png">

Once selected the PHASE, scripts will be generated using tmux as terminal.
At this point you can select a specific SUB-PHASE using tmux commands:  
**(CTRL + b) w**  
<img src="https://github.com/dokDork/red-team-penetration-test-script/raw/main/images/03.png">

once the SUB-PHASE has been selected you will be able to view the commands that have been pre-compiled to analyse the SUB-PHASE. At this point it is possible to selecet and execute a specific command just pressing ENTER:
<img src="https://github.com/dokDork/red-team-penetration-test-script/raw/main/images/04.png">

When you need to change penetration test PHASE and return to main manu, you need to close the tmux session. To implement this action you need to use the tmux shortcut:  
**(CTRL + b) :kill-session**  
or, if you configure tmux as reported in the Installation section, you can use the shortcut:
**(CTRL + b) (CTRL + n)**  

<img src="https://github.com/dokDork/red-team-penetration-test-script/raw/main/images/05.png">

  
## Command-line parameters
```
./siteSniper.sh <interface> <target url>
```

| Parameter | Description                          | Example       |
|-----------|--------------------------------------|---------------|
| `interface`      | network interface through which the target is reached | `eth0`, `wlan0`, `tun0`, ... |
| `target url`      | Target URL you need to test          | `http://www.example.com`          |

  
## How to install it on Kali Linux (or Debian distribution)
It's very simple  
```
cd /opt
sudo git clone https://github.com/dokDork/SiteSniper.git
cd SiteSniper 
chmod 755 siteSniper.sh 
./siteSniper.sh 
```
Optional: You can insert a shortcut to move faster through the tool.
```
echo "bind-key C-n run-shell \"tmux kill-session -t #{session_name}\"" >> ~/.tmux.conf
```

