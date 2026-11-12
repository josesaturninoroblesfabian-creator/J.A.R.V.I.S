$ErrorActionPreference = 'Stop'
$jarvisRoot = Split-Path $PSScriptRoot -Parent
$jarvisPrivate = Join-Path $jarvisRoot 'packaging/android-signing'
$jarvisJava = Join-Path ${env:ProgramFiles} 'Android/Android Studio/jbr'
if ($env:JAVA_HOME) { $jarvisJava = $env:JAVA_HOME }
if (-not (Test-Path (Join-Path $jarvisJava 'bin/java.exe'))) { throw 'Configura JAVA_HOME con un JDK compatible con Gradle 9.3.1.' }
$env:JAVA_HOME = $jarvisJava
New-Item -ItemType Directory -Path $jarvisPrivate -Force | Out-Null
$jarvisSecret = Join-Path $jarvisPrivate 'signing.json'
if (-not (Test-Path $jarvisSecret)) {
    $jarvisBytes = New-Object byte[] 32
    $jarvisRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $jarvisRandom.GetBytes($jarvisBytes) } finally { $jarvisRandom.Dispose() }
    @{password=[Convert]::ToBase64String($jarvisBytes)} | ConvertTo-Json | Set-Content -LiteralPath $jarvisSecret -Encoding utf8
}
$env:JARVIS_ANDROID_STORE_PASSWORD = (Get-Content -LiteralPath $jarvisSecret -Raw | ConvertFrom-Json).password
$env:JARVIS_ANDROID_KEYSTORE = Join-Path $jarvisPrivate 'jarvis-beta.jks'
try {
    if (-not (Test-Path $env:JARVIS_ANDROID_KEYSTORE)) {
        & (Join-Path $jarvisJava 'bin/keytool.exe') -genkeypair -keystore $env:JARVIS_ANDROID_KEYSTORE -storetype JKS -storepass:env JARVIS_ANDROID_STORE_PASSWORD -keypass:env JARVIS_ANDROID_STORE_PASSWORD -alias jarvis-beta -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Jarvis Personal Beta'
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la firma de la beta.' }
    }
    & (Join-Path $PSScriptRoot 'gradlew.bat') -p $PSScriptRoot testReleaseUnitTest lintRelease assembleRelease assembleReleaseAndroidTest --no-daemon --console plain
    if ($LASTEXITCODE -ne 0) { throw 'Falló la validación o compilación Android.' }
    New-Item -ItemType Directory -Path (Join-Path $jarvisRoot 'release') -Force | Out-Null
    $jarvisApk = Join-Path $jarvisRoot 'release/Jarvis-Personal-0.1.1-beta-android13.apk'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'app/build/outputs/apk/release/app-release.apk') -Destination $jarvisApk -Force
    $jarvisHash = (Get-FileHash -LiteralPath $jarvisApk -Algorithm SHA256).Hash
    "$jarvisHash  Jarvis-Personal-0.1.1-beta-android13.apk" | Set-Content -LiteralPath (Join-Path $jarvisRoot 'release/ANDROID-SHA256SUMS.txt') -Encoding ascii
    Write-Output "APK validado: $jarvisApk"
} finally {
    Remove-Item Env:JARVIS_ANDROID_STORE_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:JARVIS_ANDROID_KEYSTORE -ErrorAction SilentlyContinue
}
