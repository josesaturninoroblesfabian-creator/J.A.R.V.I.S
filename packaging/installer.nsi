Unicode True
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "Jarvis Personal 0.2.1 beta"
OutFile "..\release\Jarvis-Setup-0.2.1-beta-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\JarvisPersonal"
RequestExecutionLevel user
SetCompressor /SOLID zlib
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Esta versión de Jarvis requiere Windows de 64 bits."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Esta versión de Jarvis requiere Windows 10 u 11."
    Abort
  ${EndIf}
FunctionEnd
Section "Jarvis"
  SetOutPath "$INSTDIR"
  File /r "..\dist\Jarvis\*"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  CreateDirectory "$SMPROGRAMS\Jarvis Personal"
  CreateShortcut "$SMPROGRAMS\Jarvis Personal\Jarvis.lnk" "$INSTDIR\Jarvis.exe"
  CreateShortcut "$DESKTOP\Jarvis Personal.lnk" "$INSTDIR\Jarvis.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPersonal" "DisplayName" "Jarvis Personal 0.2.1 beta"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPersonal" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
SectionEnd
Section "Uninstall"
  Delete "$DESKTOP\Jarvis Personal.lnk"
  Delete "$SMPROGRAMS\Jarvis Personal\Jarvis.lnk"
  RMDir "$SMPROGRAMS\Jarvis Personal"
  Delete "$INSTDIR\Jarvis.exe"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir /r "$INSTDIR\_internal"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPersonal"
  ; Personal data in LOCALAPPDATA\JarvisPersonal is deliberately preserved.
SectionEnd
