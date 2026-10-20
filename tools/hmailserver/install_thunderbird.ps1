# L4H1_RAC: Thunderbird ESR, silent, with the remoteIT@mail.np.local account preset for every
# Windows user (mozilla.cfg defaultPref = machine-wide defaults; users can still change them).
# The password is NOT preset: the user types it on first use (Thunderbird stores it per user).
# isp\mail.np.local.xml lets "Add account" fill in the server settings from just email + password.
$ErrorActionPreference = 'Stop'
$msi = '__MSI__'
$dir = 'C:\Program Files\Mozilla Thunderbird'
$log = 'C:\ProgramData\LabConsole\hmail\thunderbird-msi.log'
if (-not (Test-Path "$dir\thunderbird.exe")) {
  $p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList @('/i', "`"$msi`"", '/qn', '/norestart', "/l*v `"$log`"",
    'INSTALL_MAINTENANCE_SERVICE=false', 'TASKBAR_SHORTCUT=false', 'DESKTOP_SHORTCUT=true', 'START_MENU_SHORTCUT=true', 'PREVENT_REBOOT_REQUIRED=true')
  "msiexec exit: $($p.ExitCode)"
} else { "already installed" }
"version: " + (Get-Item "$dir\thunderbird.exe").VersionInfo.ProductVersion

$utf8 = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText("$dir\defaults\pref\autoconfig.js", @'
// Lab Console (tools/hmailserver): load the lab defaults from mozilla.cfg
pref("general.config.filename", "mozilla.cfg");
pref("general.config.obscure_value", 0);
'@, $utf8)

[IO.File]::WriteAllText("$dir\mozilla.cfg", @'
// Lab Console (tools/hmailserver): mail.np.local defaults for every user on this machine.
// No first-run noise (the lab has no internet).
defaultPref("mail.shell.checkDefaultClient", false);
defaultPref("mailnews.start_page.enabled", false);
defaultPref("mail.provider.enabled", false);
defaultPref("datareporting.policy.dataSubmissionEnabled", false);
defaultPref("toolkit.telemetry.reportingpolicy.firstRun", false);
defaultPref("mail.rights.version", 1);
// Preset account: remoteIT@mail.np.local, IMAP 143 + SMTP 587, normal password (no TLS in the lab).
defaultPref("mail.accountmanager.accounts", "account1,account2");
defaultPref("mail.accountmanager.defaultaccount", "account1");
defaultPref("mail.accountmanager.localfoldersserver", "server2");
defaultPref("mail.account.account1.server", "server1");
defaultPref("mail.account.account1.identities", "id1");
defaultPref("mail.account.account2.server", "server2");
defaultPref("mail.server.server1.type", "imap");
defaultPref("mail.server.server1.hostname", "mail.np.local");
defaultPref("mail.server.server1.port", 143);
defaultPref("mail.server.server1.socketType", 0);
defaultPref("mail.server.server1.authMethod", 3);
defaultPref("mail.server.server1.userName", "remoteIT@mail.np.local");
defaultPref("mail.server.server1.name", "remoteIT@mail.np.local");
defaultPref("mail.server.server1.login_at_startup", true);
defaultPref("mail.server.server1.check_new_mail", true);
defaultPref("mail.server.server2.type", "none");
defaultPref("mail.server.server2.hostname", "Local Folders");
defaultPref("mail.server.server2.name", "Local Folders");
defaultPref("mail.server.server2.userName", "nobody");
defaultPref("mail.identity.id1.fullName", "Remote IT");
defaultPref("mail.identity.id1.useremail", "remoteIT@mail.np.local");
defaultPref("mail.identity.id1.smtpServer", "smtp1");
defaultPref("mail.identity.id1.valid", true);
defaultPref("mail.smtpservers", "smtp1");
defaultPref("mail.smtp.defaultserver", "smtp1");
defaultPref("mail.smtpserver.smtp1.hostname", "mail.np.local");
defaultPref("mail.smtpserver.smtp1.port", 587);
defaultPref("mail.smtpserver.smtp1.try_ssl", 0);
defaultPref("mail.smtpserver.smtp1.authMethod", 3);
defaultPref("mail.smtpserver.smtp1.username", "remoteIT@mail.np.local");
defaultPref("mail.smtpserver.smtp1.description", "mail.np.local");
'@, $utf8)

New-Item -ItemType Directory -Force "$dir\isp" | Out-Null
[IO.File]::WriteAllText("$dir\isp\mail.np.local.xml", @'
<?xml version="1.0" encoding="UTF-8"?>
<clientConfig version="1.1">
  <emailProvider id="mail.np.local">
    <domain>mail.np.local</domain>
    <displayName>Lab mail (hMailServer)</displayName>
    <displayShortName>Lab mail</displayShortName>
    <incomingServer type="imap">
      <hostname>mail.np.local</hostname><port>143</port><socketType>plain</socketType>
      <authentication>password-cleartext</authentication><username>%EMAILADDRESS%</username>
    </incomingServer>
    <outgoingServer type="smtp">
      <hostname>mail.np.local</hostname><port>587</port><socketType>plain</socketType>
      <authentication>password-cleartext</authentication><username>%EMAILADDRESS%</username>
    </outgoingServer>
  </emailProvider>
</clientConfig>
'@, $utf8)

New-Item -ItemType Directory -Force "$dir\distribution" | Out-Null
[IO.File]::WriteAllText("$dir\distribution\policies.json", '{"policies":{"DisableAppUpdate":true,"DisableTelemetry":true}}', $utf8)
"files: " + ((Get-ChildItem "$dir\mozilla.cfg", "$dir\defaults\pref\autoconfig.js", "$dir\isp\mail.np.local.xml", "$dir\distribution\policies.json" | ForEach-Object { "$($_.Name)=$($_.Length)B" }) -join ' ')
"mail.np.local resolves to: " + ((Resolve-DnsName mail.np.local -Type A -ErrorAction SilentlyContinue | Where-Object Type -eq A).IPAddress -join ',')
foreach ($port in 143, 587) { $c = New-Object Net.Sockets.TcpClient; try { $c.Connect('mail.np.local', $port); "tcp $port : open" } catch { "tcp $port : FAILED $($_.Exception.Message)" } finally { $c.Close() } }
