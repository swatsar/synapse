; Synapse Agent - Windows Installer
; Protocol Version: 1.0
; Spec Version: 3.1

!include "MUI2.nsh"
!include "FileFunc.nsh"

; Protocol version
!define SYNAPSE_VERSION "3.1.0"
!define PROTOCOL_VERSION "1.0"
!define SPEC_VERSION "3.1"

; Installer settings
Name "Synapse Agent ${SYNAPSE_VERSION}"
OutFile "synapse-installer-${SYNAPSE_VERSION}.exe"
InstallDir "$PROGRAMFILES\Synapse"
InstallDirRegKey HKLM "Software\Synapse" "InstallDir"
RequestExecutionLevel admin

; UI settings
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Russian"

Section "Synapse Core" SecCore
    SetOutPath "$INSTDIR"

    ; Install Python bundled
    File "python-3.11.exe"

    ; Install application
    File /r "synapse\*.*"
    File /r "config\*.*"
    File /r "skills\*.*"

    ; Install dependencies
    ExecWait '"$INSTDIR\python.exe" -m pip install -r requirements.txt'

    ; Create shortcuts
    CreateDirectory "$SMPROGRAMS\Synapse"
    CreateShortcut "$SMPROGRAMS\Synapse\Synapse.lnk" "$INSTDIR\python.exe" "$INSTDIR\synapse\main.py"
    CreateShortcut "$DESKTOP\Synapse.lnk" "$INSTDIR\python.exe" "$INSTDIR\synapse\main.py"

    ; Add to PATH
    Push "$INSTDIR"
    Call AddToPath

    ; Registry
    WriteRegStr HKLM "Software\Synapse" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\Synapse" "Version" "${SYNAPSE_VERSION}"
    WriteRegStr HKLM "Software\Synapse" "ProtocolVersion" "${PROTOCOL_VERSION}"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    ; Remove from PATH
    Push "$INSTDIR"
    Call RemoveFromPath

    ; Remove registry
    DeleteRegKey HKLM "Software\Synapse"

    ; Remove files
    RMDir /r "$INSTDIR"
    RMDir /r "$SMPROGRAMS\Synapse"
    Delete "$DESKTOP\Synapse.lnk"
SectionEnd

Function AddToPath
    Exch $0
    Push $1
    Push $2
    Push $3

    ReadRegStr $1 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    StrCpy $2 $1 1 -1
    StrCmp $2 ";" 0 +2
    StrCpy $1 $1 -1
    StrCpy $0 "$1;$0"
    WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" $0

    Pop $3
    Pop $2
    Pop $1
    Pop $0
FunctionEnd

Function RemoveFromPath
    Exch $0
    Push $1
    Push $2
    Push $3
    Push $4

    ReadRegStr $1 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    StrCpy $2 $1 1 -1
    StrCmp $2 ";" 0 +2
    StrCpy $1 $1 -1

    Push $1
    Push "$0;"
    Call StrStr
    Pop $2
    StrCmp $2 "" done

    StrLen $3 "$0;"
    StrLen $4 $1
    IntOp $4 $4 - $3
    StrCpy $1 $1 $4 0
    StrCpy $1 "$1$2"
    WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" $1

done:
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Pop $0
FunctionEnd

Function StrStr
    Exch $1
    Exch
    Exch $0
    Push $2
    Push $3
    Push $4

    StrCpy $2 0
    StrLen $4 $0

loop:
    StrCpy $3 $1 $4 $2
    StrCmp $3 $0 found
    StrCmp $3 "" notfound
    IntOp $2 $2 + 1
    Goto loop

found:
    StrCpy $0 $1 "" $2
    Goto done

notfound:
    StrCpy $0 ""

done:
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Exch $0
FunctionEnd
