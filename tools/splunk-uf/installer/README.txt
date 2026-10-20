Put exactly one Splunk Universal Forwarder installer here:

  splunkforwarder-<version>-<build>-windows-x64.msi   (Windows 64-bit .msi)

Version: same as the SIEM (10.6.x) or older - a forwarder must not be newer than its indexer.
Download: https://www.splunk.com/en_us/download/universal-forwarder.html (needs a splunk.com login).
push_uf.py refuses the file unless its Authenticode signature is valid and signed by Splunk.
