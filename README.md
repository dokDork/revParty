# revParty
It is an advanced tool capable of creating Backdoors and Trojans for Windows systems, for educational purposes only.
The tool must obviously be used only with the approval of the owner of the machine on which the Backdoors and Trojans will be run.

The main features of the tool are:
- It can generate Trojans and backdoors with polymorphic code, making them difficult for defense systems to detect through static code analysis.
- It has various types of reverse shells that can be used:
  - Simple reverse shell: It has simple code that is often undetected by AVs (sometimes simplicity pays);
  - TLS reverse shell: Traffic between the reverse shell and the listener is encrypted over a TLS channel;
  - FTP reverse shell: The reverse shell simulates an FTP connection through the following steps:
    - Connect to a remote server: the attacker's machine;
    - Authenticate: To make the action more credible;
    - ask to download a file: the file's body will contain the command the attacker wants to execute on the target machine. To make things a little more obscure, the command could be encoded in base64, and the encoding could be broken by adding a few characters to the alphanumeric sequence.
    - the reverse shell could then execute the command and send the response to the attacker, uploading a file whose body is nothing more than the base64 encoding of the response.
  - FTP reverse shell with sandbox analysis: like the previous reverse shell, but when it starts, it analyzes whether it has been activated in a sandbox. If so, it waits before activating.
