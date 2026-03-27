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

The prerequisite for everything to work is a Windows machine reachable from Kali via the winRM protocol (it can obviously also be a virtual machine).
The Windows machine is used to transform PowerShell scripts into Windows executables.
Note:
To enable the winRM protocol on a Windows machine, you must use the PowerShell command:
 ```
Enable-PSRemoting
 ```
  
## Example Usage
 ```
python3 reverseParty.py
 ``` 
<img src="https://github.com/dokDork/revParty/raw/main/images/01.png">

This is the result of the elaboration process:
<img src="https://github.com/dokDork/revParty/raw/main/images/02.png">

  
## Tool parameters
All parameters are passed by means of python script variables.
The variabiles to be defined are the follow:

| Variable | Description                          | Example       |
|-----------|--------------------------------------|---------------|
| `LHOST`      | IP Public which the listener is listening | `10.10.10.10`|
| `LPORT`      | Portort on which the listener is listening | `21`|
| `ATTACKER_URL`      |  Host from which stager (STAGERNAME) download second stage (SECONDNAME) | `https://raw.githubusercontent.com/test/download`|
| `TROJAN_URL`      | Host from which trojan download stager (STAGERNAME) and front end file (e.g. windows update - TROJAN-FE) | `https://raw.githubusercontent.com/test/download`|
|   |  | |
| `SECONDNAME`      | Name of second stage (PS1) | `10.10.10.10`|
| `STAGERNAME`      | Name of stager (PS1) that calls the second stage via the web | `second.txt`|
| `TROJANNAME`      | Name of trojan (PS1) that calls the stager that calls the second stage via the web + if all goes well, calls the FE file | `stager.ps1`|
| `TROJAN_FE`      | Name of windows update to use as the Trojan's FE (other files are fine) | `installer.ps1`|
| `LAUNCHERNAME`      | Name of launcher (file trusted by Windows) that calls any .exe file to bypass SmartScreen | `launcher.bat`|

| `EXENAME`      | name of the .exe file to be called by the launcher  | `ps2pdf.exe`|
| `ICONNAME`      | Name of icon to inject into executables to make them appear more trustworthy | `sicurezza.ico`|
| `EXESECONDNAME`      | name to give to the compiled second stage (EXE)  | `01.second.exe`|
| `EXESTAGER`      | name to give to the compiled stager (EXE)  | `02.stager.exe`|
| `EXETROJAN`      | name to give to the Trojan (EXE) compiled  | `03.trojan.exe`|

| `ZIPSECONDNAME`      | Name of zip which contains launcher + secondStage.exe | `04.LAUNCHER-SECOND.zip`|
| `ZIPNAME`      | Name of zip which contains launcher + stager.exe (which calls secondStage via the web) | `05.LAUNCHER-STAGER.zip`|
| `ISONAME`      | Name of iso which contains launcher + trojan (which calls stager, which calls secondStage via the web + if all goes well, also calls the FE file) | `06.LAUCHER-TROJAN.iso`|

| `WIN_IP`      | IP to connect to Windows Machine in order to perform the ISO to EXE conversion operation  | `192.168.1.10`|
| `WIN_USER`      | User to connect to Windows Machine in order to perform the ISO to EXE conversion operation  | `myUSer`|
| `WIN_PASS`      | Pass to connect to Windows Machine in order to perform the ISO to EXE conversion operation  | `myPass`|
  
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

