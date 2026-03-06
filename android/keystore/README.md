# ADAAD Android Release Keystore

## ⚠️ CRITICAL SECURITY NOTICE

This directory contains the Android release signing keystore.
**The keystore file itself MUST NOT be committed to Git.**
Only this README and the `.gitignore` are tracked.

---

## Keystore Details

| Field          | Value                                                    |
|----------------|----------------------------------------------------------|
| File           | `innovativeai-release.jks`                               |
| Type           | PKCS12                                                   |
| Alias          | `adaad-release`                                          |
| Algorithm      | RSA 4096-bit, SHA384withRSA                              |
| Valid from     | 2026-03-06                                               |
| Valid until    | 2051-02-28 (25 years)                                    |
| DN             | CN=InnovativeAI LLC, OU=ADAAD Platform, L=Blackwell, ST=Oklahoma, C=US |

## Certificate Fingerprints

```
SHA-1:   67:0C:3C:99:B8:19:FF:F6:A4:B0:41:96:CD:EA:5C:E4:E2:CB:EA:1E
SHA-256: E2:04:C6:F3:97:A2:58:D0:42:29:9E:F7:EC:6A:35:8D:64:2E:62:77:BD:32:42:B5:A4:85:81:BF:F2:E5:27:ED
```

Upload the SHA-256 fingerprint to Google Play Console →
App signing → Upload key certificate when enrolling in Play App Signing.

---

## Password Storage

Store passwords in a secrets manager — NEVER in plain text or in source control:

```bash
# GitHub Actions (repository secrets):
ADAAD_STORE_PASSWORD   = <storepass>
ADAAD_KEY_ALIAS        = adaad-release
ADAAD_KEY_PASSWORD     = <keypass>
ADAAD_KEYSTORE_BASE64  = $(base64 -w0 innovativeai-release.jks)
```

---

## Backup Procedure

1. Store the `.jks` file in an encrypted vault (1Password / Bitwarden / AWS Secrets Manager).
2. Store the passwords separately from the keystore file.
3. Never email or Slack the keystore file — use secure file transfer only.
4. If the keystore is lost and not enrolled in Play App Signing, the app **cannot be updated**
   on the Play Store. Treat this file as you would a production TLS private key.

---

## Play App Signing Enrolment (REQUIRED before first upload)

Google Play App Signing lets Google manage the final distribution key while
you retain the upload key. This protects against keystore loss.

Steps:
1. Go to Play Console → Your app → Setup → App signing
2. Choose "Use Google-managed key" or "Use a key from a Java keystore"
3. If using upload key: generate a separate upload key (see below)
4. Upload the upload key certificate (.pem) to Play Console

### Generate upload key certificate for Play Console
```bash
keytool -export -rfc \
  -keystore innovativeai-release.jks \
  -alias adaad-release \
  -storepass YOUR_STOREPASS \
  -file adaad-upload-cert.pem
```
Then upload `adaad-upload-cert.pem` in Play Console.
