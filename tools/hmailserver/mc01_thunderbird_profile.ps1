# MC01 (local, current Windows user): create a Thunderbird profile with remoteIT@mail.np.local preset.
# MC01's DNS doesn't resolve mail.np.local (not the lab DC), so the server is the IP 10.4.20.21.
# The password is typed once at the first prompt ("Use Password Manager to remember").
$ErrorActionPreference = 'Stop'
$tb = 'C:\Program Files\Mozilla Thunderbird\thunderbird.exe'
$root = Join-Path $env:APPDATA 'Thunderbird'
if (Test-Path "$root\profiles.ini") { throw "a Thunderbird profile already exists for $env:USERNAME - not touching it" }
Start-Process $tb -ArgumentList '-CreateProfile', 'remoteIT' -Wait
$prof = Get-ChildItem "$root\Profiles" -Directory | Where-Object Name -like '*.remoteIT' | Select-Object -First 1
if (-not $prof) { throw 'profile was not created' }
$prefs = @'
user_pref("mail.shell.checkDefaultClient", false);
user_pref("mailnews.start_page.enabled", false);
user_pref("mail.provider.enabled", false);
user_pref("mail.rights.version", 1);
user_pref("mail.accountmanager.accounts", "account1,account2");
user_pref("mail.accountmanager.defaultaccount", "account1");
user_pref("mail.accountmanager.localfoldersserver", "server2");
user_pref("mail.account.account1.server", "server1");
user_pref("mail.account.account1.identities", "id1");
user_pref("mail.account.account2.server", "server2");
user_pref("mail.server.server1.type", "imap");
user_pref("mail.server.server1.hostname", "10.4.20.21");
user_pref("mail.server.server1.port", 143);
user_pref("mail.server.server1.socketType", 0);
user_pref("mail.server.server1.authMethod", 3);
user_pref("mail.server.server1.userName", "remoteIT@mail.np.local");
user_pref("mail.server.server1.name", "remoteIT@mail.np.local");
user_pref("mail.server.server1.login_at_startup", true);
user_pref("mail.server.server1.check_new_mail", true);
user_pref("mail.server.server2.type", "none");
user_pref("mail.server.server2.hostname", "Local Folders");
user_pref("mail.server.server2.name", "Local Folders");
user_pref("mail.server.server2.userName", "nobody");
user_pref("mail.identity.id1.fullName", "Remote IT");
user_pref("mail.identity.id1.useremail", "remoteIT@mail.np.local");
user_pref("mail.identity.id1.smtpServer", "smtp1");
user_pref("mail.identity.id1.valid", true);
user_pref("mail.smtpservers", "smtp1");
user_pref("mail.smtp.defaultserver", "smtp1");
user_pref("mail.smtpserver.smtp1.hostname", "10.4.20.21");
user_pref("mail.smtpserver.smtp1.port", 587);
user_pref("mail.smtpserver.smtp1.try_ssl", 0);
user_pref("mail.smtpserver.smtp1.authMethod", 3);
user_pref("mail.smtpserver.smtp1.username", "remoteIT@mail.np.local");
user_pref("mail.smtpserver.smtp1.description", "Lab mail (mail.np.local)");
'@
[IO.File]::WriteAllText((Join-Path $prof.FullName 'prefs.js'), $prefs, (New-Object Text.UTF8Encoding($false)))
"profile: $($prof.FullName)"
Get-Content "$root\profiles.ini"
